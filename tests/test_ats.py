"""The scoring engine: keywords, sections, formatting, totals, and comparison."""

from __future__ import annotations

import json

import pytest

from ats_bot.ats.comparison import compare_evaluations
from ats_bot.ats.formatting import MAX_WORDS, MIN_WORDS, check_formatting
from ats_bot.ats.keywords import extract_skills, is_term_present, match_keywords
from ats_bot.ats.scorer import evaluate_resume
from ats_bot.ats.sections import check_sections
from ats_bot.ats.suggestions import generate_suggestions
from ats_bot.constants import SCORE_WEIGHTS, canonical_skill


class TestTermBoundaries:
    @pytest.mark.parametrize(
        "text,term",
        [
            ("experienced in c++ development", "c++"),
            ("we use c# daily", "c#"),
            ("built on .net core", ".net"),
            ("owns ci/cd pipelines", "ci/cd"),
            ("shipped with node.js", "node.js"),
            ("writes go services", "go"),
            ("go, python, rust", "go"),
            ("scikit-learn models", "scikit-learn"),
        ],
    )
    def test_present(self, text: str, term: str) -> None:
        assert is_term_present(text, term)

    @pytest.mark.parametrize(
        "text,term",
        [
            ("he goes to work", "go"),
            ("golang developer", "go"),
            ("negotiation skills", "go"),
            ("scala expertise", "c"),
            ("javascript only", "java"),
            ("", "python"),
            ("python", ""),
        ],
    )
    def test_absent(self, text: str, term: str) -> None:
        assert not is_term_present(text, term)


class TestSkillExtraction:
    def test_finds_dictionary_skills(self) -> None:
        skills = extract_skills("Strong Python, Django and PostgreSQL background")
        assert {"python", "django", "postgresql"} <= set(skills)

    def test_aliases_collapse_to_one_canonical_skill(self) -> None:
        skills = extract_skills("React.js and ReactJS and react experience")
        assert skills.count("react") == 1

    @pytest.mark.parametrize(
        "surface,canonical",
        [
            ("Golang", "go"),
            ("K8s", "kubernetes"),
            ("scikit learn", "scikit-learn"),
            ("Postgres", "postgresql"),
            ("GCP", "google cloud"),
            ("Kubernetes", "kubernetes"),
        ],
    )
    def test_canonical_skill(self, surface: str, canonical: str) -> None:
        assert canonical_skill(surface) == canonical

    def test_longer_terms_win_over_their_parts(self) -> None:
        skills = extract_skills("Deep machine learning expertise")
        assert "machine learning" in skills

    def test_empty_text(self) -> None:
        assert extract_skills("") == []


class TestKeywordMatching:
    def test_percentage_and_lists(self) -> None:
        result = match_keywords(
            "Python and Docker experience", "Requires Python, Docker and Kubernetes"
        )
        assert result.score == 66.7
        assert set(result.matched) == {"python", "docker"}
        assert result.missing == ("kubernetes",)
        assert result.from_dictionary

    def test_perfect_match(self, resume_text: str) -> None:
        result = match_keywords(resume_text, "Needs Python, Django and Docker")
        assert result.score == 100.0
        assert result.missing == ()

    def test_alias_in_the_resume_matches_the_canonical_requirement(self) -> None:
        result = match_keywords("Deployed with K8s and Postgres", "Needs Kubernetes and PostgreSQL")
        assert result.score == 100.0

    def test_typos_are_tolerated_for_long_words(self) -> None:
        assert match_keywords("Kubernetes and Postgresql", "Needs Kubernets").score == 100.0

    def test_short_words_are_not_fuzzy_matched(self) -> None:
        """ "go" must not match "no" — a one-character edit is a different word."""
        assert match_keywords("no relevant skills at all", "Needs Go").score == 0.0

    def test_falls_back_to_statistical_keywords(self) -> None:
        jd = (
            "Coordinate the editorial calendar. Own brand voice across channels. "
            "Editorial calendar ownership is essential for this brand voice role."
        )
        result = match_keywords("I coordinate an editorial calendar for a magazine", jd)
        assert not result.from_dictionary
        assert result.total > 0

    def test_empty_inputs_score_zero(self) -> None:
        assert match_keywords("", "Python").score == 0.0
        assert match_keywords("Python", "").score == 0.0

    def test_unextractable_posting_scores_zero_not_a_hundred(self) -> None:
        """An empty checklist must not be reported as a perfect match."""
        result = match_keywords("A resume with content", "!!! ??? ...")
        assert result.score == 0.0
        assert result.total == 0


class TestSections:
    def test_full_resume_scores_high(self, resume_text: str) -> None:
        result = check_sections(resume_text)
        assert result.score == 100.0
        assert result.missing == ()

    def test_partial_resume(self) -> None:
        result = check_sections("EXPERIENCE\nEngineer\nEDUCATION\nBSc\nSKILLS\nPython")
        assert result.score == 80.0
        assert set(result.missing) == {"summary", "projects"}

    def test_bonus_sections_are_capped_at_one_hundred(self, resume_text: str) -> None:
        assert check_sections(resume_text + "\nLANGUAGES\nEnglish").score == 100.0

    def test_empty_resume(self) -> None:
        result = check_sections("")
        assert result.score == 0.0
        assert len(result.missing) == 5


class TestFormatting:
    def test_strong_resume(self, resume_text: str) -> None:
        result = check_formatting(resume_text)
        assert result.has_email
        assert result.has_phone
        assert result.has_links
        assert result.quantified_achievements >= 2
        assert result.score >= 70

    def test_missing_contact_details_are_penalised(self) -> None:
        result = check_formatting("word " * (MIN_WORDS + 10))
        assert not result.has_email
        assert not result.has_phone
        assert result.score < 50

    def test_short_resume_is_flagged(self) -> None:
        result = check_formatting("Jane Doe jane@x.com 555 123 4567 Engineer")
        assert any("short" in issue for issue in result.issues)

    def test_long_resume_is_flagged(self) -> None:
        result = check_formatting("word " * (MAX_WORDS + 100))
        assert any("long" in issue for issue in result.issues)

    def test_placeholder_text_is_caught(self, resume_text: str) -> None:
        result = check_formatting(resume_text + "\nLorem ipsum dolor sit amet")
        assert any("placeholder" in issue for issue in result.issues)

    def test_first_person_writing_is_flagged(self) -> None:
        text = "I built things. I led a team. I improved metrics. " * 20
        assert any("first person" in issue for issue in check_formatting(text).issues)

    def test_score_never_goes_negative(self) -> None:
        assert check_formatting("word " * 5).score >= 0.0

    def test_empty_resume(self) -> None:
        result = check_formatting("")
        assert result.score == 0.0
        assert result.issues


class TestSuggestions:
    def test_missing_keywords_come_first(self, jd_text: str) -> None:
        evaluation = evaluate_resume("Python developer with a phone 555 123 4567", jd_text)
        assert evaluation.suggestions
        assert evaluation.suggestions[0].category == "keywords"

    def test_every_missing_section_gets_advice(self) -> None:
        evaluation = evaluate_resume("EXPERIENCE\nDid work at a company\n", "Needs Python")
        categories = {suggestion.category for suggestion in evaluation.suggestions}
        assert "structure" in categories

    def test_fallback_keywords_are_worded_cautiously(self) -> None:
        from ats_bot.ats.models import FormattingResult, KeywordResult, SectionResult

        suggestions = generate_suggestions(
            KeywordResult(score=0.0, missing=("brand voice",), from_dictionary=False),
            SectionResult(score=100.0),
            FormattingResult(score=100.0),
        )
        assert "technical dictionary" in suggestions[0].text

    def test_a_flawless_resume_still_gets_a_closing_note(self) -> None:
        from ats_bot.ats.models import FormattingResult, KeywordResult, SectionResult

        suggestions = generate_suggestions(
            KeywordResult(score=100.0),
            SectionResult(score=100.0),
            FormattingResult(score=100.0),
        )
        assert suggestions


class TestEvaluate:
    def test_weighted_total(self, resume_text: str, jd_text: str) -> None:
        evaluation = evaluate_resume(resume_text, jd_text)
        expected = round(
            evaluation.keywords.score * SCORE_WEIGHTS["keywords"]
            + evaluation.sections.score * SCORE_WEIGHTS["sections"]
            + evaluation.formatting.score * SCORE_WEIGHTS["formatting"],
            1,
        )
        assert evaluation.overall_score == expected

    def test_a_strong_resume_beats_a_weak_one(self, resume_text: str, jd_text: str) -> None:
        from tests.conftest import WEAK_RESUME_TEXT

        strong = evaluate_resume(resume_text, jd_text)
        weak = evaluate_resume(WEAK_RESUME_TEXT, jd_text)
        assert strong.overall_score > weak.overall_score

    def test_score_stays_within_bounds(self, resume_text: str, jd_text: str) -> None:
        assert 0.0 <= evaluate_resume(resume_text, jd_text).overall_score <= 100.0

    def test_deterministic(self, resume_text: str, jd_text: str) -> None:
        assert evaluate_resume(resume_text, jd_text) == evaluate_resume(resume_text, jd_text)

    @pytest.mark.parametrize("text", ["", "   ", "\n\n"])
    def test_empty_resume_scores_zero_without_raising(self, text: str) -> None:
        evaluation = evaluate_resume(text, "Python developer needed")
        assert evaluation.overall_score == 0.0
        assert evaluation.suggestions

    def test_grades(self, resume_text: str, jd_text: str) -> None:
        assert evaluate_resume(resume_text, jd_text).grade in {
            "Excellent",
            "Strong",
            "Fair",
            "Needs work",
            "Poor",
        }

    def test_snapshot_is_json_serialisable(self, resume_text: str, jd_text: str) -> None:
        payload = json.loads(evaluate_resume(resume_text, jd_text).to_json())
        assert payload["overall_score"] >= 0
        assert "keywords" in payload


class TestComparison:
    def test_detects_a_newly_matched_skill(self) -> None:
        jd = "We need Python and Docker"
        delta = compare_evaluations(
            evaluate_resume("Python and Docker work here", jd),
            evaluate_resume("Python work here", jd),
        )
        assert delta.newly_matched == ("docker",)
        assert delta.improved

    def test_detects_a_regression(self) -> None:
        jd = "We need Python and Docker"
        delta = compare_evaluations(
            evaluate_resume("Python work here", jd),
            evaluate_resume("Python and Docker work here", jd),
        )
        assert delta.no_longer_matched == ("docker",)
        assert not delta.improved

    def test_identical_versions_report_no_change(self, resume_text: str, jd_text: str) -> None:
        evaluation = evaluate_resume(resume_text, jd_text)
        delta = compare_evaluations(evaluation, evaluation)
        assert delta.unchanged
        assert delta.score_delta == 0.0

    def test_section_and_issue_changes_are_reported(self, jd_text: str) -> None:
        base = "Jane Doe\njane@x.com\n+1 555 123 4567\nEXPERIENCE\nBuilt Python services\n"
        delta = compare_evaluations(
            evaluate_resume(base + "EDUCATION\nBSc Computer Science\n", jd_text),
            evaluate_resume(base, jd_text),
        )
        assert "education" in delta.added_sections

    def test_output_ordering_is_stable(self) -> None:
        jd = "We need Python, Docker, Kubernetes and Terraform"
        current = evaluate_resume("Python Docker Kubernetes Terraform all here", jd)
        previous = evaluate_resume("Python only here", jd)
        first = compare_evaluations(current, previous).newly_matched
        second = compare_evaluations(current, previous).newly_matched
        assert first == second == tuple(sorted(first))
