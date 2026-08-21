"""Handler behaviour: routing, the upload/score flow, and error handling."""

from __future__ import annotations

from typing import Any

import pytest
from tests.conftest import FakeCallbackQuery, FakeContext, FakeMessage, FakeUpdate, FakeUser

from ats_bot.ats.scorer import evaluate_resume
from ats_bot.config import Settings
from ats_bot.db import repository
from ats_bot.errors import DatabaseError, ParsingError
from ats_bot.handlers.chat import handle_question
from ats_bot.handlers.common import (
    CB_COMPARE,
    CB_HISTORY,
    STATE_AWAITING_JD,
    SessionKey,
    clear_session,
)
from ats_bot.handlers.compare import handle_compare
from ats_bot.handlers.errors import handle_error
from ats_bot.handlers.history import handle_history
from ats_bot.handlers.router import handle_callback, handle_text, looks_like_job_description
from ats_bot.handlers.score import handle_job_description, handle_latest_score
from ats_bot.handlers.session import handle_forget_me, handle_newchat
from ats_bot.handlers.start import handle_about, handle_help, handle_start
from ats_bot.reporting import render_evaluation


class TestJobDescriptionClassifier:
    @pytest.mark.parametrize(
        "text",
        [
            "What sections should I include?",
            "how do I explain a career gap",
            "thanks!",
            "can you review my summary",
            "Is a two-column layout safe",
            "",
        ],
    )
    def test_questions(self, text: str) -> None:
        assert not looks_like_job_description(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Responsibilities: own the billing platform end to end. Requirements: "
            "5+ years of experience with Python, Django and PostgreSQL. Bachelor's "
            "degree preferred. You will mentor engineers and set technical direction.",
            "word " * 70,
        ],
    )
    def test_postings(self, text: str) -> None:
        assert looks_like_job_description(text)

    def test_a_long_question_is_still_a_question(self) -> None:
        text = "Can you tell me " + "more about this topic " * 30
        assert not looks_like_job_description(text)

    def test_the_bundled_sample_posting_is_recognised(self, jd_text: str) -> None:
        assert looks_like_job_description(jd_text)


class TestStartAndHelp:
    async def test_start_greets_and_records_the_user(
        self, update: FakeUpdate, context: FakeContext, db: Settings
    ) -> None:
        await handle_start(update, context)  # type: ignore[arg-type]

        assert "Hello" in update.effective_message.last_reply  # type: ignore[union-attr]
        assert repository.get_user(42, settings=db) is not None

    async def test_start_still_greets_when_the_database_is_down(
        self, update: FakeUpdate, context: FakeContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _explode(*args: Any, **kwargs: Any) -> None:
            raise DatabaseError("disk on fire")

        monkeypatch.setattr(repository, "add_user", _explode)
        await handle_start(update, context)  # type: ignore[arg-type]
        assert update.effective_message.replies  # type: ignore[union-attr]

    async def test_help_lists_every_command(self, update: FakeUpdate, context: FakeContext) -> None:
        await handle_help(update, context)  # type: ignore[arg-type]
        text = update.effective_message.last_reply  # type: ignore[union-attr]
        for command in ("/start", "/help", "/compare", "/history", "/newchat"):
            assert command in text

    async def test_about_reports_status(self, update: FakeUpdate, context: FakeContext) -> None:
        await handle_about(update, context)  # type: ignore[arg-type]
        assert "ATS Resume Analyzer" in update.effective_message.last_reply  # type: ignore[union-attr]


class TestScoring:
    @pytest.fixture
    def stored_resume(self, db: Settings, resume_text: str) -> int:
        return repository.save_resume(42, "/tmp/cv.pdf", "cv.pdf", "pdf", resume_text, settings=db)

    async def test_scores_and_persists(
        self, db: Settings, stored_resume: int, jd_text: str, context: FakeContext
    ) -> None:
        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(42))
        context.user_data[SessionKey.PENDING_RESUME_IDS] = [stored_resume]

        await handle_job_description(update, context)  # type: ignore[arg-type]

        assert "ATS Match Report" in message.all_output
        history = repository.get_score_history(42, settings=db)
        assert len(history) == 1
        assert history[0].overall_score > 0

    async def test_state_is_reset_afterwards(
        self, db: Settings, stored_resume: int, jd_text: str, context: FakeContext
    ) -> None:
        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(42))
        context.user_data[SessionKey.PENDING_RESUME_IDS] = [stored_resume]

        await handle_job_description(update, context)  # type: ignore[arg-type]

        assert context.user_data[SessionKey.STATE] is None
        assert context.user_data[SessionKey.PENDING_RESUME_IDS] == []
        assert context.user_data[SessionKey.ACTIVE_JD_ID]

    async def test_falls_back_to_the_stored_resume(
        self, db: Settings, stored_resume: int, jd_text: str, context: FakeContext
    ) -> None:
        """A user returning in a new session still gets scored."""
        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(42))

        await handle_job_description(update, context)  # type: ignore[arg-type]
        assert "ATS Match Report" in message.all_output

    async def test_asks_for_a_resume_when_there_is_none(
        self, db: Settings, jd_text: str, context: FakeContext
    ) -> None:
        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(99))

        await handle_job_description(update, context)  # type: ignore[arg-type]
        assert "Upload a resume first" in message.last_reply

    async def test_rejects_a_too_short_posting(
        self, db: Settings, stored_resume: int, context: FakeContext
    ) -> None:
        message = FakeMessage("Python dev needed")
        update = FakeUpdate(message=message, user=FakeUser(42))

        await handle_job_description(update, context)  # type: ignore[arg-type]
        assert "very short" in message.last_reply

    async def test_another_user_s_resume_is_not_scored(
        self, db: Settings, jd_text: str, resume_text: str, context: FakeContext
    ) -> None:
        """A stale pending id from another account must be ignored."""
        other = repository.save_resume(7, "/x", "x.pdf", "pdf", resume_text, settings=db)
        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(42))
        context.user_data[SessionKey.PENDING_RESUME_IDS] = [other]

        await handle_job_description(update, context)  # type: ignore[arg-type]
        assert "Upload a resume first" in message.last_reply

    async def test_a_second_version_gets_a_comparison(
        self, db: Settings, jd_text: str, resume_text: str, context: FakeContext
    ) -> None:
        repository.save_resume(42, "/v1", "v1.pdf", "pdf", resume_text, settings=db)
        improved = resume_text.replace("Docker, AWS", "Docker, AWS, Kubernetes, Terraform")
        second = repository.save_resume(42, "/v2", "v2.pdf", "pdf", improved, settings=db)

        message = FakeMessage(jd_text)
        update = FakeUpdate(message=message, user=FakeUser(42))
        context.user_data[SessionKey.PENDING_RESUME_IDS] = [second]

        await handle_job_description(update, context)  # type: ignore[arg-type]
        assert "Version comparison" in message.all_output


class TestLatestScore:
    async def test_reports_nothing_when_there_is_no_history(
        self, db: Settings, update: FakeUpdate, context: FakeContext
    ) -> None:
        await handle_latest_score(update, context)  # type: ignore[arg-type]
        assert "No scores yet" in update.effective_message.last_reply  # type: ignore[union-attr]

    async def test_reproduces_the_stored_score(
        self, db: Settings, resume_text: str, jd_text: str, update: FakeUpdate, context: FakeContext
    ) -> None:
        resume_id = repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        jd_id = repository.save_jd(42, jd_text, settings=db)
        evaluation = evaluate_resume(resume_text, jd_text)
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=evaluation.overall_score,
            keyword_score=evaluation.keywords.score,
            structure_score=evaluation.sections.score,
            formatting_score=evaluation.formatting.score,
            settings=db,
        )

        await handle_latest_score(update, context)  # type: ignore[arg-type]

        reply = update.effective_message.last_reply  # type: ignore[union-attr]
        assert f"{evaluation.overall_score}/100" in reply

    async def test_a_newer_unscored_resume_does_not_change_the_number(
        self, db: Settings, resume_text: str, jd_text: str, update: FakeUpdate, context: FakeContext
    ) -> None:
        """Regression guard: the report must follow the score row, not the newest files."""
        resume_id = repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        jd_id = repository.save_jd(42, jd_text, settings=db)
        evaluation = evaluate_resume(resume_text, jd_text)
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=evaluation.overall_score,
            keyword_score=0,
            structure_score=0,
            formatting_score=0,
            settings=db,
        )
        # A completely different, unscored resume uploaded afterwards.
        repository.save_resume(42, "/b", "b.pdf", "pdf", "Totally unrelated text", settings=db)

        await handle_latest_score(update, context)  # type: ignore[arg-type]

        assert f"{evaluation.overall_score}/100" in update.effective_message.last_reply  # type: ignore[union-attr]


class TestCompare:
    async def test_requires_two_versions(
        self, db: Settings, resume_text: str, update: FakeUpdate, context: FakeContext
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        await handle_compare(update, context)  # type: ignore[arg-type]
        assert "Two versions are needed" in update.effective_message.last_reply  # type: ignore[union-attr]

    async def test_requires_a_job_description(
        self, db: Settings, resume_text: str, update: FakeUpdate, context: FakeContext
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        repository.save_resume(42, "/b", "b.pdf", "pdf", resume_text + " extra", settings=db)

        await handle_compare(update, context)  # type: ignore[arg-type]
        assert "job description is needed" in update.effective_message.last_reply  # type: ignore[union-attr]

    async def test_reports_the_difference(
        self, db: Settings, resume_text: str, jd_text: str, update: FakeUpdate, context: FakeContext
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        improved = resume_text.replace("Docker, AWS", "Docker, AWS, Kubernetes")
        repository.save_resume(42, "/b", "b.pdf", "pdf", improved, settings=db)
        repository.save_jd(42, jd_text, settings=db)

        await handle_compare(update, context)  # type: ignore[arg-type]

        output = update.effective_message.all_output
        assert "Version comparison" in output
        assert "kubernetes" in output


class TestHistory:
    async def test_empty(self, db: Settings, update: FakeUpdate, context: FakeContext) -> None:
        await handle_history(update, context)  # type: ignore[arg-type]
        assert "No history yet" in update.effective_message.last_reply  # type: ignore[union-attr]

    async def test_lists_scores_newest_first(
        self, db: Settings, update: FakeUpdate, context: FakeContext
    ) -> None:
        resume_id = repository.save_resume(42, "/a", "a.pdf", "pdf", "text", settings=db)
        jd_id = repository.save_jd(42, "jd", settings=db)
        for score in (40.0, 90.0):
            repository.save_score(
                resume_id=resume_id,
                jd_id=jd_id,
                overall_score=score,
                keyword_score=0,
                structure_score=0,
                formatting_score=0,
                settings=db,
            )

        await handle_history(update, context)  # type: ignore[arg-type]

        reply = update.effective_message.last_reply  # type: ignore[union-attr]
        assert reply.index("90.0") < reply.index("40.0")

    async def test_a_filename_with_markdown_characters_is_safe(
        self, db: Settings, update: FakeUpdate, context: FakeContext
    ) -> None:
        """The exact input that used to crash the old Markdown renderer."""
        resume_id = repository.save_resume(
            42, "/a", "my_resume_*final*_v2.pdf", "pdf", "text", settings=db
        )
        jd_id = repository.save_jd(42, "jd", settings=db)
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=50.0,
            keyword_score=0,
            structure_score=0,
            formatting_score=0,
            settings=db,
        )

        await handle_history(update, context)  # type: ignore[arg-type]
        assert "my_resume_*final*_v2.pdf" in update.effective_message.last_reply  # type: ignore[union-attr]


class TestSession:
    async def test_newchat_clears_state_but_keeps_data(
        self, db: Settings, update: FakeUpdate, context: FakeContext, resume_text: str
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        context.user_data[SessionKey.LAST_RESUME_ID] = 1

        await handle_newchat(update, context)  # type: ignore[arg-type]

        assert context.user_data[SessionKey.SESSION_CLEARED] is True
        assert SessionKey.LAST_RESUME_ID not in context.user_data
        assert repository.get_all_resumes(42, settings=db)

    async def test_forgetme_deletes_everything(
        self, db: Settings, update: FakeUpdate, context: FakeContext, resume_text: str, settings
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        user_dir = settings.upload_dir / "42"
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "cv.pdf").write_bytes(b"data")

        await handle_forget_me(update, context)  # type: ignore[arg-type]

        assert repository.get_all_resumes(42, settings=db) == []
        assert not user_dir.exists()
        assert "deleted" in update.effective_message.last_reply.lower()  # type: ignore[union-attr]


class TestTextRouting:
    async def test_a_question_reaches_the_assistant(
        self, db: Settings, context: FakeContext
    ) -> None:
        message = FakeMessage("What is the STAR method?")
        await handle_text(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "STAR" in message.last_reply

    async def test_a_posting_reaches_the_scorer(
        self, db: Settings, jd_text: str, resume_text: str, context: FakeContext
    ) -> None:
        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        message = FakeMessage(jd_text)
        await handle_text(FakeUpdate(message=message, user=FakeUser(42)), context)  # type: ignore[arg-type]
        assert "ATS Match Report" in message.all_output

    async def test_a_question_asked_while_awaiting_a_posting_is_answered(
        self, db: Settings, context: FakeContext
    ) -> None:
        context.user_data[SessionKey.STATE] = STATE_AWAITING_JD
        message = FakeMessage("What is the STAR method?")
        await handle_text(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "STAR" in message.last_reply

    async def test_a_short_posting_while_awaiting_is_treated_as_one(
        self, db: Settings, context: FakeContext
    ) -> None:
        context.user_data[SessionKey.STATE] = STATE_AWAITING_JD
        message = FakeMessage("Backend engineer needed")
        await handle_text(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "very short" in message.last_reply


class TestChat:
    async def test_unmatched_question_offers_topics(
        self, db: Settings, context: FakeContext
    ) -> None:
        message = FakeMessage("qwertyuiop zxcvbnm")
        await handle_question(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "I am not sure" in message.last_reply

    async def test_newchat_stops_documents_being_used_as_context(
        self, db: Settings, context: FakeContext, resume_text: str
    ) -> None:
        from ats_bot.handlers.chat import _session_documents

        repository.save_resume(42, "/a", "a.pdf", "pdf", resume_text, settings=db)
        clear_session(context)  # type: ignore[arg-type]

        resume, job = await _session_documents(context, 42)  # type: ignore[arg-type]
        assert resume is None
        assert job is None


class TestCallbacks:
    async def test_query_is_always_acknowledged(self, db: Settings, context: FakeContext) -> None:
        message = FakeMessage()
        query = FakeCallbackQuery(CB_HISTORY, message, FakeUser(42))
        await handle_callback(FakeUpdate(message=message, callback_query=query), context)  # type: ignore[arg-type]
        assert query.answered

    async def test_unknown_data_is_acknowledged_and_explained(
        self, db: Settings, context: FakeContext
    ) -> None:
        message = FakeMessage()
        query = FakeCallbackQuery("menu:from_2019", message, FakeUser(42))
        await handle_callback(FakeUpdate(message=message, callback_query=query), context)  # type: ignore[arg-type]

        assert query.answered
        assert "older version" in message.last_reply

    async def test_dispatches_to_the_right_handler(
        self, db: Settings, context: FakeContext
    ) -> None:
        message = FakeMessage()
        query = FakeCallbackQuery(CB_COMPARE, message, FakeUser(42))
        await handle_callback(FakeUpdate(message=message, callback_query=query), context)  # type: ignore[arg-type]
        assert "Two versions are needed" in message.last_reply


class TestErrorHandler:
    async def test_reports_an_unexpected_error_to_the_user(self, context: FakeContext) -> None:
        message = FakeMessage()
        context.error = ValueError("kaboom")
        await handle_error(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "Something went wrong" in message.last_reply

    async def test_maps_known_errors_to_specific_advice(self, context: FakeContext) -> None:
        message = FakeMessage()
        context.error = ParsingError("bad file")
        await handle_error(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert "could not be read" in message.last_reply

    async def test_a_blocked_bot_is_not_reported(self, context: FakeContext) -> None:
        from telegram.error import Forbidden

        message = FakeMessage()
        context.error = Forbidden("bot was blocked by the user")
        await handle_error(FakeUpdate(message=message), context)  # type: ignore[arg-type]
        assert message.replies == []

    async def test_a_non_message_update_does_not_crash(self, context: FakeContext) -> None:
        context.error = ValueError("kaboom")
        await handle_error("not an update", context)  # type: ignore[arg-type]


class TestReportRendering:
    def test_report_is_html_balanced(self, resume_text: str, jd_text: str) -> None:
        report = render_evaluation(evaluate_resume(resume_text, jd_text), resume_name="cv.pdf")
        for tag in ("b", "i", "code"):
            assert report.count(f"<{tag}>") == report.count(f"</{tag}>")

    def test_a_hostile_filename_is_escaped(self, resume_text: str, jd_text: str) -> None:
        report = render_evaluation(
            evaluate_resume(resume_text, jd_text), resume_name="<script>x</script>.pdf"
        )
        assert "<script>" not in report
        assert "&lt;script&gt;" in report
