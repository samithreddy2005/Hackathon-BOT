"""The ATS scoring engine — pure functions over text, with no I/O."""

from __future__ import annotations

from ats_bot.ats.comparison import compare_evaluations
from ats_bot.ats.formatting import check_formatting
from ats_bot.ats.keywords import extract_skills, match_keywords
from ats_bot.ats.models import (
    Evaluation,
    FormattingResult,
    KeywordResult,
    SectionResult,
    Suggestion,
    VersionDelta,
)
from ats_bot.ats.scorer import evaluate_resume
from ats_bot.ats.sections import check_sections
from ats_bot.ats.suggestions import generate_suggestions

__all__ = [
    "Evaluation",
    "FormattingResult",
    "KeywordResult",
    "SectionResult",
    "Suggestion",
    "VersionDelta",
    "check_formatting",
    "check_sections",
    "compare_evaluations",
    "evaluate_resume",
    "extract_skills",
    "generate_suggestions",
    "match_keywords",
]
