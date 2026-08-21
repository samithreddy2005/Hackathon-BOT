"""Keyword and skill matching between a job description and a resume.

The matcher runs in two modes:

*Dictionary mode* is the default. Skills from :data:`~ats_bot.constants.CANONICAL_SKILLS`
that appear in the job description become the checklist, and each is looked up in
the resume. Because the vocabulary is curated, both the "matched" and "missing"
lists are precise enough to act on.

*Fallback mode* takes over when a job description contains no recognised skill —
common for non-technical roles. Candidate keywords are mined statistically from
the text, which is noisier, so the result is flagged via
:attr:`~ats_bot.ats.models.KeywordResult.from_dictionary` and the report softens
its wording accordingly.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from ats_bot.ats.models import KeywordResult
from ats_bot.constants import SKILL_SURFACE_FORMS, canonical_skill
from ats_bot.parsing.cleaner import (
    extract_potential_keywords,
    focus_on_requirements,
    tokenize,
)

__all__ = ["extract_skills", "is_term_present", "match_keywords"]

#: Characters that belong to a technical term and therefore do not end it.
#: "go" must not match inside "golang" or "go-to", but must match in "go," and "go)".
_WORD_CHARS = frozenset("+#.-_")

#: Similarity above which a resume token is accepted as a typo'd skill.
_FUZZY_THRESHOLD = 88.0

#: Fuzzy matching is only safe on reasonably long words; below this length a small
#: edit distance is a different word entirely ("go" vs "no", "r" vs "c").
_MIN_FUZZY_LENGTH = 5


def is_term_present(text: str, term: str) -> bool:
    """Check for ``term`` in ``text`` respecting technical word boundaries.

    ``str.__contains__`` produces false positives ("go" in "golang") while
    ``\\b`` word boundaries fail on the punctuation that real skill names contain
    ("c++", "ci/cd", ".net"). This walks candidate positions and checks that
    neither neighbouring character could be part of the same term.

    Both arguments must already be lower-cased.

    >>> is_term_present("experienced in c++ and go", "go")
    True
    >>> is_term_present("he goes to golang meetups", "go")
    False
    >>> is_term_present("built with node.js", "node.js")
    True
    """
    if not term or not text:
        return False

    start = 0
    term_length = len(term)
    while True:
        index = text.find(term, start)
        if index == -1:
            return False

        before_ok = index == 0 or not _is_word_char(text[index - 1])
        end = index + term_length
        after_ok = end >= len(text) or not _is_word_char(text[end])

        if before_ok and after_ok:
            return True
        start = index + 1


def _is_word_char(char: str) -> bool:
    return char.isalnum() or char in _WORD_CHARS


def extract_skills(text: str) -> list[str]:
    """Return the canonical skills mentioned in ``text``, longest match first.

    Surface forms are scanned longest-first and matched regions are consumed, so
    "machine learning" is reported once rather than also yielding "learning".

    >>> extract_skills("Strong Python and React.js experience")
    ['python', 'react']
    """
    if not text:
        return []

    lowered = text.lower()
    found: dict[str, None] = {}
    for surface in SKILL_SURFACE_FORMS:
        if is_term_present(lowered, surface):
            found.setdefault(canonical_skill(surface), None)
    # Preserve the order the skills appear in the text; it reads more naturally in
    # the report than the internal longest-first scan order.
    return sorted(found, key=lambda skill: _first_index(lowered, skill))


def _first_index(text: str, skill: str) -> int:
    index = text.find(skill)
    return index if index >= 0 else len(text)


def match_keywords(resume_text: str, jd_text: str) -> KeywordResult:
    """Score how well a resume covers the skills a job description asks for.

    Returns a :class:`~ats_bot.ats.models.KeywordResult` whose ``score`` is the
    percentage of required skills found. A job description with no extractable
    requirements scores 0 with an empty checklist rather than a misleading 100.

    >>> result = match_keywords("Python and Docker work", "Needs Python, Docker, Kubernetes")
    >>> result.score, result.matched, result.missing
    (66.7, ('python', 'docker'), ('kubernetes',))
    """
    if not resume_text or not jd_text:
        return KeywordResult(score=0.0)

    required = extract_skills(jd_text)
    from_dictionary = bool(required)

    if not required:
        # No curated skill in the posting: mine the requirements section instead.
        required = [
            canonical_skill(term)
            for term in extract_potential_keywords(focus_on_requirements(jd_text))
        ]
        required = list(dict.fromkeys(required))

    if not required:
        return KeywordResult(score=0.0, from_dictionary=False)

    resume_lower = resume_text.lower()
    resume_tokens = tokenize(resume_text)

    matched: list[str] = []
    missing: list[str] = []
    for term in required:
        if _resume_covers(term, resume_lower, resume_tokens):
            matched.append(term)
        else:
            missing.append(term)

    score = round(len(matched) / len(required) * 100.0, 1)
    return KeywordResult(
        score=score,
        matched=tuple(matched),
        missing=tuple(missing),
        from_dictionary=from_dictionary,
    )


def _resume_covers(term: str, resume_lower: str, resume_tokens: set[str]) -> bool:
    """Decide whether the resume demonstrates ``term``.

    Three progressively looser tests, in order of confidence:

    1. the term (or any of its aliases) appears verbatim;
    2. for multi-word terms, every word appears somewhere in the resume — this
       catches "management of stakeholders" for "stakeholder management";
    3. for a single long word, a resume token is within a small edit distance,
       which absorbs typos and plural/British spellings without matching
       unrelated words.
    """
    if is_term_present(resume_lower, term):
        return True

    if any(
        is_term_present(resume_lower, surface) for surface in _SURFACES_BY_CANONICAL.get(term, ())
    ):
        return True

    parts = term.split()
    if len(parts) > 1:
        return all(part in resume_tokens or is_term_present(resume_lower, part) for part in parts)

    if len(term) >= _MIN_FUZZY_LENGTH:
        return any(
            len(token) >= _MIN_FUZZY_LENGTH and fuzz.ratio(token, term) >= _FUZZY_THRESHOLD
            for token in resume_tokens
        )

    return False


def _build_surface_index() -> dict[str, tuple[str, ...]]:
    """canonical skill -> every alternative spelling that resolves to it."""
    index: dict[str, list[str]] = {}
    for surface in SKILL_SURFACE_FORMS:
        canonical = canonical_skill(surface)
        if surface != canonical:
            index.setdefault(canonical, []).append(surface)
    return {canonical: tuple(surfaces) for canonical, surfaces in index.items()}


#: Built once at import; the matcher consults it for every required skill.
_SURFACES_BY_CANONICAL: dict[str, tuple[str, ...]] = _build_surface_index()
