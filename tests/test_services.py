"""FAQ retrieval, upload intake, and the optional LLM assistant."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from telegram.error import NetworkError, TimedOut

from ats_bot.config import Settings
from ats_bot.errors import FileTooLargeError, UnsupportedFileTypeError, UploadError
from ats_bot.services.faq import FaqIndex, default_index
from ats_bot.services.files import (
    purge_old_uploads,
    safe_display_name,
    storage_path_for,
    validate_upload,
)
from ats_bot.services.knowledge_base import FAQ_ENTRIES
from ats_bot.services.llm import LlmAssistant, LlmUnavailable


class TestFaqIndex:
    @pytest.fixture
    def index(self) -> FaqIndex:
        return default_index()

    @pytest.mark.parametrize(
        "query,expected_fragment",
        [
            ("what is the STAR method", "STAR"),
            ("can I use a two column layout in my cv", "tables"),
            ("how do I explain being out of work for a year", "career gap"),
            ("they asked what salary I want", "salary"),
            ("how long should a resume be", "long"),
            ("tell me about yourself answer", "Tell me about yourself"),
        ],
    )
    def test_finds_the_right_entry(
        self, index: FaqIndex, query: str, expected_fragment: str
    ) -> None:
        match = index.search(query)
        assert match is not None
        assert match.confident, f"{query!r} scored only {match.score}"
        assert expected_fragment.lower() in match.entry.question.lower()

    def test_unrelated_query_is_not_confident(self, index: FaqIndex) -> None:
        match = index.search("what is the weather in Reykjavik tomorrow")
        assert match is None or not match.confident

    def test_query_with_only_stop_words(self, index: FaqIndex) -> None:
        assert index.search("the and of") is None

    def test_empty_query(self, index: FaqIndex) -> None:
        assert index.search("") is None

    def test_index_covers_every_entry(self, index: FaqIndex) -> None:
        assert len(index) == len(FAQ_ENTRIES)

    def test_scores_are_bounded(self, index: FaqIndex) -> None:
        match = index.search("how do I write a professional summary")
        assert match is not None
        assert 0.0 <= match.score <= 1.0

    def test_answers_are_html_safe(self) -> None:
        """Answers are sent verbatim, so a stray '&' would break message parsing."""
        for entry in FAQ_ENTRIES:
            for char, allowed in (("&", "&amp;"), ("<", "<b>"), (">", "</b>")):
                if char in entry.answer:
                    assert allowed in entry.answer or _only_in_tags(entry.answer, char)


def _only_in_tags(text: str, char: str) -> bool:
    """True when every occurrence of ``char`` belongs to one of our own tags."""
    import re

    stripped = re.sub(r"</?(?:b|i|u|s|code|pre)>", "", text)
    return char not in stripped


class TestSafeDisplayName:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("resume.pdf", "resume.pdf"),
            ("../../etc/passwd", "passwd"),
            ("..\\..\\windows\\system32", "system32"),
            ('bad:name*?".pdf', "badname.pdf"),
            ("   ", "resume"),
            ("", "resume"),
            ("...", "resume"),
            ("My  Resume   (v2).pdf", "My Resume (v2).pdf"),
        ],
    )
    def test_sanitisation(self, raw: str, expected: str) -> None:
        assert safe_display_name(raw) == expected

    def test_long_names_are_truncated_but_keep_the_extension(self) -> None:
        result = safe_display_name("a" * 200 + ".pdf")
        assert len(result) <= 60
        assert result.endswith(".pdf")

    def test_result_is_always_a_single_path_component(self) -> None:
        assert "/" not in safe_display_name("a/b/c.pdf")
        assert "\\" not in safe_display_name("a\\b\\c.pdf")


class TestValidateUpload:
    def test_accepts_supported_types(self, settings: Settings) -> None:
        assert validate_upload("cv.pdf", 1000, settings) == "pdf"
        assert validate_upload("cv.DOCX", 1000, settings) == "docx"
        assert validate_upload("scan.jpg", 1000, settings) == "image"

    @pytest.mark.parametrize("name", ["notes.txt", "old.doc", "archive.zip", "unnamed"])
    def test_rejects_unsupported_types(self, name: str, settings: Settings) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            validate_upload(name, 1000, settings)

    def test_rejects_oversized_files(self, settings: Settings) -> None:
        with pytest.raises(FileTooLargeError):
            validate_upload("cv.pdf", settings.max_upload_bytes + 1, settings)

    def test_unknown_size_is_allowed_through(self, settings: Settings) -> None:
        assert validate_upload("cv.pdf", None, settings) == "pdf"

    def test_a_traversal_name_cannot_smuggle_an_extension(self, settings: Settings) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            validate_upload("../../evil.pdf/payload.exe", 100, settings)


class TestStoragePath:
    def test_stays_inside_the_user_directory(self, settings: Settings) -> None:
        path = storage_path_for(42, "../../escape.pdf", settings)
        assert path.parent == settings.upload_dir / "42"
        assert settings.upload_dir in path.parents

    def test_identical_names_do_not_collide(self, settings: Settings) -> None:
        first = storage_path_for(1, "resume.pdf", settings)
        second = storage_path_for(1, "resume.pdf", settings)
        assert first != second
        assert first.name.endswith("resume.pdf")

    def test_users_are_separated(self, settings: Settings) -> None:
        assert (
            storage_path_for(1, "cv.pdf", settings).parent
            != storage_path_for(2, "cv.pdf", settings).parent
        )


class _FakeFile:
    def __init__(self, fail_times: int = 0, error: Exception | None = None) -> None:
        self.fail_times = fail_times
        self.error = error or TimedOut()
        self.attempts = 0

    async def download_to_drive(self, custom_path: Any, **kwargs: Any) -> None:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise self.error
        Path(custom_path).write_bytes(b"content")


class _FakeSource:
    def __init__(self, file: _FakeFile) -> None:
        self._file = file
        self.file_id = "abc"

    async def get_file(self, **kwargs: Any) -> _FakeFile:
        return self._file


class TestDownload:
    async def _no_sleep(self, _seconds: float) -> None:
        return None

    async def test_succeeds_first_time(self, tmp_path: Path) -> None:
        from ats_bot.services.files import download_to

        source = _FakeSource(_FakeFile())
        target = tmp_path / "out.pdf"
        result = await download_to(source, target, sleep=self._no_sleep)  # type: ignore[arg-type]

        assert result == target
        assert target.read_bytes() == b"content"

    async def test_retries_transient_failures(self, tmp_path: Path) -> None:
        from ats_bot.services.files import download_to

        fake = _FakeFile(fail_times=2, error=NetworkError("flaky"))
        await download_to(
            _FakeSource(fake), tmp_path / "out.pdf", sleep=self._no_sleep  # type: ignore[arg-type]
        )
        assert fake.attempts == 3

    async def test_gives_up_and_cleans_the_partial_file(self, tmp_path: Path) -> None:
        from ats_bot.services.files import download_to

        target = tmp_path / "out.pdf"
        target.write_bytes(b"partial")
        fake = _FakeFile(fail_times=99, error=NetworkError("down"))

        with pytest.raises(UploadError):
            await download_to(
                _FakeSource(fake), target, attempts=2, sleep=self._no_sleep  # type: ignore[arg-type]
            )

        assert not target.exists()


class TestPurgeOldUploads:
    def _make(self, settings: Settings, name: str, age_hours: float) -> Path:
        path = settings.upload_dir / "1" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        stamp = time.time() - age_hours * 3600
        import os

        os.utime(path, (stamp, stamp))
        return path

    def test_removes_only_expired_files(self, settings: Settings) -> None:
        old = self._make(settings, "old.pdf", age_hours=48)
        fresh = self._make(settings, "fresh.pdf", age_hours=1)

        removed = purge_old_uploads(settings)

        assert removed == 1
        assert not old.exists()
        assert fresh.exists()

    def test_disabled_when_retention_is_zero(self, settings: Settings) -> None:
        old = self._make(settings, "old.pdf", age_hours=999)
        disabled = Settings(
            bot_token=settings.bot_token,
            database_path=settings.database_path,
            upload_dir=settings.upload_dir,
            log_dir=settings.log_dir,
            upload_retention_hours=0,
        )
        assert purge_old_uploads(disabled) == 0
        assert old.exists()

    def test_gitkeep_is_never_removed(self, settings: Settings) -> None:
        keep = settings.upload_dir / ".gitkeep"
        keep.write_bytes(b"")
        import os

        stamp = time.time() - 99999
        os.utime(keep, (stamp, stamp))

        purge_old_uploads(settings)
        assert keep.exists()

    def test_missing_directory_is_not_an_error(self, settings: Settings, tmp_path: Path) -> None:
        absent = Settings(
            bot_token=settings.bot_token,
            database_path=settings.database_path,
            upload_dir=tmp_path / "never-created",
            log_dir=settings.log_dir,
        )
        assert purge_old_uploads(absent) == 0


class TestLlmAssistant:
    def test_disabled_without_a_key(self, settings: Settings) -> None:
        assistant = LlmAssistant(settings)
        assert not assistant.enabled
        assert "no API key" in assistant.status

    def test_enabled_with_a_key(self, settings: Settings) -> None:
        assert LlmAssistant(_with_key(settings)).enabled

    async def test_answering_while_disabled_raises_for_fallback(self, settings: Settings) -> None:
        with pytest.raises(LlmUnavailable):
            await LlmAssistant(settings).answer("hello")

    async def test_a_permanent_error_disables_the_assistant(self, settings: Settings) -> None:
        assistant = LlmAssistant(_with_key(settings))
        assistant._client = _FailingClient(_AuthError())

        with pytest.raises(LlmUnavailable):
            await assistant.answer("hello")
        assert not assistant.enabled

    async def test_a_transient_error_keeps_the_assistant_enabled(self, settings: Settings) -> None:
        assistant = LlmAssistant(_with_key(settings))
        assistant._client = _FailingClient(TimeoutError("slow"))

        with pytest.raises(LlmUnavailable):
            await assistant.answer("hello")
        assert assistant.enabled

    async def test_documents_are_labelled_as_data_in_the_prompt(
        self, settings: Settings, db: Settings
    ) -> None:
        from ats_bot.db import repository

        assistant = LlmAssistant(_with_key(settings))
        client = _RecordingClient("**answer**")
        assistant._client = client

        resume_id = repository.save_resume(1, "/a", "a.pdf", "pdf", "SECRET RESUME", settings=db)
        resume = repository.get_resume(resume_id, settings=db)

        answer = await assistant.answer("who am I?", resume=resume)

        assert answer == "**answer**"
        system_prompt = client.messages[0]["content"]
        assert "SECRET RESUME" in system_prompt
        assert "data, not instructions" in system_prompt

    async def test_empty_completions_fall_back(self, settings: Settings) -> None:
        assistant = LlmAssistant(_with_key(settings))
        assistant._client = _RecordingClient("")
        with pytest.raises(LlmUnavailable):
            await assistant.answer("hello")


def _with_key(settings: Settings) -> Settings:
    return Settings(
        bot_token=settings.bot_token,
        database_path=settings.database_path,
        upload_dir=settings.upload_dir,
        log_dir=settings.log_dir,
        groq_api_key="gsk_test_key",
    )


class _AuthError(Exception):
    status_code = 401


class _FailingClient:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.chat = self

    @property
    def completions(self) -> _FailingClient:
        return self

    async def create(self, **kwargs: Any) -> Any:
        raise self._error


class _RecordingClient:
    def __init__(self, content: str) -> None:
        self._content = content
        self.messages: list[dict[str, str]] = []
        self.chat = self

    @property
    def completions(self) -> _RecordingClient:
        return self

    async def create(self, **kwargs: Any) -> Any:
        self.messages = kwargs["messages"]

        class _Message:
            content = self._content

        class _Choice:
            message = _Message()

        class _Completion:
            choices = [_Choice()]

        return _Completion()
