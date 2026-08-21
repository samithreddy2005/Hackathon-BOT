"""Entity and section detection over resume text."""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "SECTION_NAMES",
    "count_quantified_achievements",
    "detect_sections",
    "extract_email",
    "extract_links",
    "extract_phone",
    "looks_like_resume",
]

EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"
)

# International and North-American formats. Requires at least 7 digits overall so
# that years ("2019 - 2023") and postcodes are not mistaken for phone numbers.
PHONE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w-])"
    r"(?:\+\d{1,3}[\s.-]?)?"
    r"(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])?"
    r"\d{3,4}[\s.-]?\d{3,4}(?:[\s.-]?\d{1,4})?"
    r"(?![\w-])"
)

LINK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"')]+|(?:linkedin\.com|github\.com)/[^\s<>\"')]+",
    re.IGNORECASE,
)

# A bullet or sentence containing a number with a unit or magnitude marker —
# the signature of a quantified achievement ("reduced latency by 40%").
_QUANTIFIED_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\d+\s*(?:%|percent|x\b|k\b|m\b|bn\b|million|billion|users?|customers?|clients?|"
    r"hours?|days?|weeks?|months?|requests?|records?|transactions?)"
    r"|[$€£₹]\s?\d",
    re.IGNORECASE,
)

#: Section name -> pattern matching the headings that introduce it.
SECTION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "summary": re.compile(
        r"\b(?:professional\s+summary|executive\s+summary|career\s+summary|summary|"
        r"profile|about\s+me|objective|career\s+objective)\b",
        re.IGNORECASE,
    ),
    "experience": re.compile(
        r"\b(?:work\s+experience|professional\s+experience|employment(?:\s+history)?|"
        r"work\s+history|career\s+history|experience|internships?)\b",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"\b(?:education(?:al\s+background)?|academic\s+(?:history|background|qualifications)|"
        r"qualifications)\b",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"\b(?:technical\s+skills|key\s+skills|core\s+competencies|core\s+skills|"
        r"skills(?:\s*&\s*\w+)?|expertise|technologies|tech\s+stack|proficiencies)\b",
        re.IGNORECASE,
    ),
    "projects": re.compile(
        r"\b(?:projects?|personal\s+projects|academic\s+projects|key\s+projects|"
        r"research\s+projects|portfolio)\b",
        re.IGNORECASE,
    ),
    "certifications": re.compile(
        r"\b(?:certifications?|certificates?|licen[cs]es?|courses?|"
        r"professional\s+development)\b",
        re.IGNORECASE,
    ),
    "languages": re.compile(r"\b(?:languages?|language\s+proficienc(?:y|ies))\b", re.IGNORECASE),
}

SECTION_NAMES: Final[tuple[str, ...]] = tuple(SECTION_PATTERNS)

#: Longest a line can be and still plausibly be a heading rather than prose.
_MAX_HEADING_LENGTH = 60

#: Sections whose presence is the minimum bar for calling a document a resume.
_RESUME_SIGNAL_SECTIONS: Final[tuple[str, ...]] = ("experience", "education", "skills")


def extract_email(text: str) -> str | None:
    """Return the first email address in ``text``, or None.

    >>> extract_email("Contact: jane.doe@example.co.uk")
    'jane.doe@example.co.uk'
    >>> extract_email("no address here") is None
    True
    """
    if not text:
        return None
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    """Return the first plausible phone number in ``text``, or None.

    Candidates need at least seven digits, which rejects date ranges and postcodes.

    >>> extract_phone("Tel: +1 (555) 123-4567")
    '+1 (555) 123-4567'
    >>> extract_phone("Employed 2019 - 2023") is None
    True
    """
    if not text:
        return None
    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group(0).strip()
        if sum(ch.isdigit() for ch in candidate) >= 7:
            return candidate
    return None


def extract_links(text: str) -> list[str]:
    """Return unique profile/portfolio links found in ``text``, in order."""
    if not text:
        return []
    seen: dict[str, None] = {}
    for match in LINK_PATTERN.finditer(text):
        seen.setdefault(match.group(0).rstrip(".,;"), None)
    return list(seen)


def count_quantified_achievements(text: str) -> int:
    """Count lines that quantify an outcome with a number, unit, or currency.

    Recruiters and ATS ranking models both reward measurable impact, so this feeds
    a formatting/content check rather than the keyword score.

    >>> count_quantified_achievements("Cut build time by 40%\\nWrote documentation")
    1
    """
    if not text:
        return 0
    return sum(1 for line in text.split("\n") if _QUANTIFIED_PATTERN.search(line))


def detect_sections(text: str) -> dict[str, bool]:
    """Report which standard resume sections are present.

    A heading is recognised when a short standalone line matches a section pattern.
    That is much stricter than scanning the whole document, where the word
    "experience" inside a sentence would falsely mark an Experience section. A
    relaxed whole-text search is kept as a fallback for resumes whose headings were
    flattened into a paragraph by PDF extraction — but it requires the keyword to
    sit at the start of a line or be followed by a colon.

    >>> detect_sections("SKILLS\\nPython, SQL")["skills"]
    True
    >>> detect_sections("I have experience shipping products")["experience"]
    False
    """
    if not text:
        return dict.fromkeys(SECTION_PATTERNS, False)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    headings = [line for line in lines if len(line) <= _MAX_HEADING_LENGTH]

    result: dict[str, bool] = {}
    for name, pattern in SECTION_PATTERNS.items():
        found = any(_is_heading_for(line, pattern) for line in headings)
        if not found:
            found = any(_starts_line_or_labelled(line, pattern) for line in lines)
        result[name] = found
    return result


def _is_heading_for(line: str, pattern: re.Pattern[str]) -> bool:
    """True when a short line is a heading for the given section.

    Headings are mostly the section word itself, optionally decorated ("— SKILLS —",
    "Technical Skills:"). Requiring the match to cover a large share of the line
    keeps a short sentence such as "Skills gained during my degree" from counting.
    """
    match = pattern.search(line)
    if not match:
        return False
    letters = sum(ch.isalpha() for ch in line)
    matched_letters = sum(ch.isalpha() for ch in match.group(0))
    return letters == 0 or matched_letters / letters >= 0.6


def _starts_line_or_labelled(line: str, pattern: re.Pattern[str]) -> bool:
    match = pattern.search(line)
    if not match:
        return False
    if match.start() == 0:
        return True
    # "... | Skills: Python" — a colon right after the keyword marks a label.
    tail = line[match.end() : match.end() + 2]
    return tail.startswith(":")


def looks_like_resume(text: str) -> bool:
    """Heuristic check that a document is a resume rather than, say, a job post.

    Requires either a recognisable core section heading or contact details, which
    together cover the layouts that omit headings entirely.

    >>> looks_like_resume("EDUCATION\\nB.Sc. Computer Science")
    True
    >>> looks_like_resume("We are hiring a backend engineer to join our team.")
    False
    """
    if not text:
        return False
    sections = detect_sections(text)
    if any(sections[name] for name in _RESUME_SIGNAL_SECTIONS):
        return True
    return bool(extract_email(text) and extract_phone(text))
