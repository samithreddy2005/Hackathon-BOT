"""The scoring engine entry point.

``evaluate_resume`` is a pure function: same inputs, same output, no I/O. That is
what makes the whole engine testable without a database or a Telegram connection.
"""

from __future__ import annotations

from ats_bot.ats.formatting import check_formatting
from ats_bot.ats.keywords import match_keywords
from ats_bot.ats.models import Evaluation, FormattingResult, KeywordResult, SectionResult
from ats_bot.ats.sections import check_sections
from ats_bot.ats.suggestions import generate_suggestions
from ats_bot.constants import SCORE_WEIGHTS

__all__ = ["evaluate_resume"]


def evaluate_resume(resume_text: str, jd_text: str) -> Evaluation:
    """Score ``resume_text`` against ``jd_text``.

    The overall score is the weighted mean of the three pillars, using
    :data:`~ats_bot.constants.SCORE_WEIGHTS` (keywords 40%, sections 30%,
    formatting 30%).

    Empty input is not an error: a resume that could not be read scores 0 with an
    explanatory issue attached, which the report renders like any other result.

    >>> evaluation = evaluate_resume("", "Python developer")
    >>> evaluation.overall_score
    0.0
    """
    if not resume_text or not resume_text.strip():
        return _empty_evaluation()

    keywords = match_keywords(resume_text, jd_text)
    sections = check_sections(resume_text)
    formatting = check_formatting(resume_text)

    overall = (
        keywords.score * SCORE_WEIGHTS["keywords"]
        + sections.score * SCORE_WEIGHTS["sections"]
        + formatting.score * SCORE_WEIGHTS["formatting"]
    )

    return Evaluation(
        overall_score=round(overall, 1),
        keywords=keywords,
        sections=sections,
        formatting=formatting,
        suggestions=generate_suggestions(keywords, sections, formatting),
    )


def _empty_evaluation() -> Evaluation:
    formatting = FormattingResult(
        score=0.0,
        issues=("The resume text is empty or could not be read.",),
    )
    return Evaluation(
        overall_score=0.0,
        keywords=KeywordResult(score=0.0),
        sections=SectionResult(score=0.0),
        formatting=formatting,
        suggestions=generate_suggestions(
            KeywordResult(score=0.0), SectionResult(score=0.0), formatting
        ),
    )
