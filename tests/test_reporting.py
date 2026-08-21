"""Report rendering — the text users actually read."""

from __future__ import annotations

import pytest

from ats_bot.ats.comparison import compare_evaluations
from ats_bot.ats.models import (
    Evaluation,
    FormattingResult,
    KeywordResult,
    SectionResult,
    VersionDelta,
)
from ats_bot.ats.scorer import evaluate_resume
from ats_bot.db.models import ScoreRecord
from ats_bot.reporting import (
    render_comparison,
    render_evaluation,
    render_history,
    score_emoji,
)

TAGS = ("b", "i", "code")


def assert_balanced(text: str) -> None:
    for tag in TAGS:
        assert text.count(f"<{tag}>") == text.count(f"</{tag}>"), f"unbalanced <{tag}>"


def _record(score: float, **overrides: object) -> ScoreRecord:
    defaults: dict[str, object] = {
        "score_id": 1,
        "resume_id": 1,
        "jd_id": 1,
        "overall_score": score,
        "keyword_score": score,
        "structure_score": score,
        "formatting_score": score,
        "details_json": "{}",
        "created_at": "2026-01-01 12:00:00.123456",
        "file_name": "cv.pdf",
        "file_type": "pdf",
    }
    defaults.update(overrides)
    return ScoreRecord(**defaults)  # type: ignore[arg-type]


class TestScoreEmoji:
    @pytest.mark.parametrize(
        "score,expected", [(95, "🟢"), (70, "🟢"), (60, "🟡"), (50, "🟡"), (30, "🔴"), (0, "🔴")]
    )
    def test_bands(self, score: float, expected: str) -> None:
        assert score_emoji(score) == expected


class TestRenderEvaluation:
    def test_contains_the_headline_numbers(self, resume_text: str, jd_text: str) -> None:
        evaluation = evaluate_resume(resume_text, jd_text)
        report = render_evaluation(evaluation, resume_name="cv.pdf")

        assert f"{evaluation.overall_score}/100" in report
        assert evaluation.grade in report
        assert "cv.pdf" in report
        assert_balanced(report)

    def test_works_without_a_resume_name(self, resume_text: str, jd_text: str) -> None:
        report = render_evaluation(evaluate_resume(resume_text, jd_text))
        assert "ATS Match Report" in report
        assert_balanced(report)

    def test_an_empty_evaluation_renders(self) -> None:
        report = render_evaluation(evaluate_resume("", "Python developer"))
        assert "0.0/100" in report
        assert_balanced(report)

    def test_long_keyword_lists_are_summarised(self) -> None:
        many = tuple(f"skill{index}" for index in range(40))
        evaluation = Evaluation(
            overall_score=50.0,
            keywords=KeywordResult(score=50.0, matched=many, missing=many),
            sections=SectionResult(score=50.0),
            formatting=FormattingResult(score=50.0),
        )
        report = render_evaluation(evaluation)
        assert "more" in report
        assert_balanced(report)

    def test_an_unusable_posting_says_so(self) -> None:
        evaluation = Evaluation(
            overall_score=30.0,
            keywords=KeywordResult(score=0.0),
            sections=SectionResult(score=50.0),
            formatting=FormattingResult(score=50.0),
        )
        report = render_evaluation(evaluation)
        assert "No requirements could be extracted" in report

    def test_all_sections_present_is_stated_positively(
        self, resume_text: str, jd_text: str
    ) -> None:
        report = render_evaluation(evaluate_resume(resume_text, jd_text))
        assert "all present" in report

    def test_hostile_content_is_escaped(self) -> None:
        evaluation = Evaluation(
            overall_score=10.0,
            keywords=KeywordResult(score=0.0, missing=("<script>alert(1)</script>",)),
            sections=SectionResult(score=0.0),
            formatting=FormattingResult(score=0.0),
        )
        report = render_evaluation(evaluation, resume_name="a & b <c>.pdf")
        assert "<script>" not in report
        assert "&amp;" in report


class TestRenderComparison:
    def test_improvement(self) -> None:
        jd = "We need Python and Docker"
        delta = compare_evaluations(
            evaluate_resume("Python and Docker experience", jd),
            evaluate_resume("Python experience", jd),
        )
        report = render_comparison(delta, current_score=80.0, previous_score=60.0)

        assert "Improved" in report
        assert "80.0/100" in report
        assert "docker" in report
        assert_balanced(report)

    def test_decline(self) -> None:
        report = render_comparison(
            VersionDelta(
                score_delta=-12.5,
                keyword_delta=-20.0,
                section_delta=0.0,
                formatting_delta=0.0,
                no_longer_matched=("docker",),
            )
        )
        assert "Declined" in report
        assert "-12.5" in report
        assert_balanced(report)

    def test_no_change_gets_actionable_advice(self) -> None:
        report = render_comparison(
            VersionDelta(
                score_delta=0.0, keyword_delta=0.0, section_delta=0.0, formatting_delta=0.0
            )
        )
        assert "No score change" in report
        assert "score identically" in report

    def test_file_names_are_shown_and_escaped(self) -> None:
        report = render_comparison(
            VersionDelta(
                score_delta=1.0, keyword_delta=0.0, section_delta=0.0, formatting_delta=0.0
            ),
            current_name="new_<v2>.pdf",
            previous_name="old_v1.pdf",
        )
        assert "&lt;v2&gt;" in report
        assert "old_v1.pdf" in report
        assert_balanced(report)

    def test_every_change_category_renders(self) -> None:
        report = render_comparison(
            VersionDelta(
                score_delta=5.0,
                keyword_delta=5.0,
                section_delta=5.0,
                formatting_delta=5.0,
                newly_matched=("docker",),
                no_longer_matched=("perl",),
                added_sections=("projects",),
                removed_sections=("languages",),
                resolved_issues=("No phone number found.",),
                new_issues=("The resume is long.",),
            )
        )
        for fragment in (
            "Newly matched",
            "no longer matched",
            "added",
            "removed",
            "resolved",
            "New issues",
        ):
            assert fragment.lower() in report.lower()
        assert_balanced(report)


class TestRenderHistory:
    def test_lists_records(self) -> None:
        report = render_history([_record(90.0), _record(40.0)], total=2)
        assert "90.0/100" in report
        assert "40.0/100" in report
        assert "2026-01-01 12:00:00" in report
        assert_balanced(report)

    def test_truncation_note(self) -> None:
        report = render_history([_record(50.0)], total=25)
        assert "1 most recent of 25" in report

    def test_no_truncation_note_when_everything_is_shown(self) -> None:
        assert "most recent of" not in render_history([_record(50.0)], total=1)

    def test_trend_line_appears(self) -> None:
        report = render_history([_record(80.0), _record(50.0)], total=2)
        assert "up 30.0 points" in report

    def test_trend_line_reports_a_decline(self) -> None:
        report = render_history([_record(50.0), _record(80.0)], total=2)
        assert "down 30.0 points" in report

    def test_a_single_record_has_no_trend_line(self) -> None:
        assert "points" not in render_history([_record(50.0)], total=1)

    def test_missing_filename_falls_back_to_an_id(self) -> None:
        report = render_history([_record(50.0, file_name="")], total=1)
        assert "resume #1" in report

    def test_filenames_are_escaped(self) -> None:
        report = render_history([_record(50.0, file_name="a<b>&c.pdf")], total=1)
        assert "a&lt;b&gt;&amp;c.pdf" in report
        assert "a<b>" not in report
        assert_balanced(report)
