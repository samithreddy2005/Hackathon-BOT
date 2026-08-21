"""Formatting and completeness checks.

Each check owns a named penalty so the scoring rationale is visible in one place
and a rule can be re-weighted without hunting through arithmetic.
"""

from __future__ import annotations

import re
from typing import Final

from ats_bot.ats.models import FormattingResult
from ats_bot.parsing.extractor import (
    count_quantified_achievements,
    extract_email,
    extract_links,
    extract_phone,
)

__all__ = ["PENALTIES", "check_formatting"]

#: Penalty, in points off a perfect 100, for each failed check.
PENALTIES: Final[dict[str, float]] = {
    "no_email": 25.0,
    "no_phone": 15.0,
    "no_links": 5.0,
    "too_short": 25.0,
    "too_long": 12.0,
    "placeholder_text": 20.0,
    "no_quantified_results": 10.0,
    "first_person": 5.0,
}

#: A resume shorter than this reads as a stub; longer than this loses recruiters.
MIN_WORDS: Final[int] = 180
MAX_WORDS: Final[int] = 1200

#: How many measurable outcomes a resume should show before the penalty lifts.
MIN_QUANTIFIED: Final[int] = 2

_PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:lorem\s+ipsum|loremipsum|placeholder|your\s+name\s+here|insert\s+\w+|"
    r"xxx+|tbd|to\s+be\s+decided|\[.{1,30}\]|<.{1,30}>)\b",
    re.IGNORECASE,
)

# First-person narration is a well-known resume anti-pattern; recruiters expect
# implied-subject bullets ("Led the migration", not "I led the migration").
_FIRST_PERSON_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[.\n]\s*)(?:I|My|We)\b", re.MULTILINE
)

_MIN_FIRST_PERSON_HITS: Final[int] = 3


def check_formatting(resume_text: str) -> FormattingResult:
    """Score a resume's formatting and completeness, out of 100.

    >>> result = check_formatting("")
    >>> result.score
    0.0
    """
    if not resume_text.strip():
        return FormattingResult(score=0.0, issues=("The resume text is empty or unreadable.",))

    word_count = len(resume_text.split())
    email = extract_email(resume_text)
    phone = extract_phone(resume_text)
    links = extract_links(resume_text)
    quantified = count_quantified_achievements(resume_text)

    issues: list[str] = []
    score = 100.0

    if word_count < MIN_WORDS:
        issues.append(
            f"The resume is short ({word_count} words). Aim for {MIN_WORDS}-{MAX_WORDS} "
            "words so each role has room for two or three achievement bullets."
        )
        score -= PENALTIES["too_short"]
    elif word_count > MAX_WORDS:
        issues.append(
            f"The resume is long ({word_count} words). Trim to about {MAX_WORDS} words — "
            "recruiters skim, and older roles rarely need more than one line each."
        )
        score -= PENALTIES["too_long"]

    if not email:
        issues.append(
            "No email address found. Put it in the top three lines as plain text — "
            "an address inside an image or text box is invisible to an ATS."
        )
        score -= PENALTIES["no_email"]

    if not phone:
        issues.append("No phone number found. Add one next to your email in the header.")
        score -= PENALTIES["no_phone"]

    if not links:
        issues.append(
            "No LinkedIn or portfolio link found. Add one — it is the first thing "
            "most recruiters click after the header."
        )
        score -= PENALTIES["no_links"]

    placeholders = {
        match.group(0).strip().lower() for match in _PLACEHOLDER_PATTERN.finditer(resume_text)
    }
    if placeholders:
        sample = ", ".join(sorted(placeholders)[:4])
        issues.append(f"Unfinished placeholder text is still in the document: {sample}.")
        score -= PENALTIES["placeholder_text"]

    if quantified < MIN_QUANTIFIED:
        issues.append(
            "Few measurable results. Add numbers to your strongest bullets "
            "(percentages, revenue, users, time saved) — they are what makes an "
            "achievement credible."
        )
        score -= PENALTIES["no_quantified_results"]

    if len(_FIRST_PERSON_PATTERN.findall(resume_text)) >= _MIN_FIRST_PERSON_HITS:
        issues.append(
            "The resume is written in the first person. Drop 'I' and 'my' and start "
            "bullets with an action verb instead ('Led', 'Built', 'Reduced')."
        )
        score -= PENALTIES["first_person"]

    return FormattingResult(
        score=round(max(score, 0.0), 1),
        issues=tuple(issues),
        word_count=word_count,
        has_email=email is not None,
        has_phone=phone is not None,
        has_links=bool(links),
        quantified_achievements=quantified,
    )
