"""Structure scoring: which of the standard resume sections are present."""

from __future__ import annotations

from ats_bot.ats.models import SectionResult
from ats_bot.constants import BONUS_SECTION_WEIGHTS, SECTION_WEIGHTS
from ats_bot.parsing.extractor import detect_sections

__all__ = ["check_sections"]


def check_sections(resume_text: str) -> SectionResult:
    """Score a resume on section completeness, out of 100.

    The five core sections carry fixed weights summing to 100; certifications and
    languages add a small bonus on top, with the total capped at 100 so a resume
    cannot buy back a missing Experience section with a Languages list.

    >>> result = check_sections("EXPERIENCE\\nEngineer\\nEDUCATION\\nBSc\\nSKILLS\\nPython")
    >>> result.score
    80.0
    >>> result.missing
    ('summary', 'projects')
    """
    if not resume_text:
        return SectionResult(score=0.0, missing=tuple(SECTION_WEIGHTS))

    detected = detect_sections(resume_text)

    present = tuple(name for name in SECTION_WEIGHTS if detected.get(name))
    missing = tuple(name for name in SECTION_WEIGHTS if not detected.get(name))
    bonus = tuple(name for name in BONUS_SECTION_WEIGHTS if detected.get(name))

    score = sum(SECTION_WEIGHTS[name] for name in present)
    score += sum(BONUS_SECTION_WEIGHTS[name] for name in bonus)

    return SectionResult(
        score=round(min(score, 100.0), 1),
        present=present,
        missing=missing,
        bonus=bonus,
    )
