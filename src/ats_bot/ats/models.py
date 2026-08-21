"""Result objects produced by the scoring engine.

These are immutable dataclasses rather than dictionaries so that a typo in a key
is a type error at development time instead of a ``KeyError`` in front of a user,
and so the report renderer has a stable contract to code against.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = [
    "Evaluation",
    "FormattingResult",
    "KeywordResult",
    "SectionResult",
    "Suggestion",
    "VersionDelta",
]


@dataclass(frozen=True, slots=True)
class KeywordResult:
    """Outcome of matching job-description skills against a resume."""

    score: float
    matched: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    #: True when the skills came from the curated dictionary rather than the
    #: statistical fallback — the fallback's "missing keywords" are noisier and the
    #: report words its advice more cautiously because of it.
    from_dictionary: bool = True

    @property
    def total(self) -> int:
        return len(self.matched) + len(self.missing)


@dataclass(frozen=True, slots=True)
class SectionResult:
    """Outcome of checking for the standard resume sections."""

    score: float
    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    bonus: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FormattingResult:
    """Outcome of the formatting and completeness checks."""

    score: float
    issues: tuple[str, ...] = ()
    word_count: int = 0
    has_email: bool = False
    has_phone: bool = False
    has_links: bool = False
    quantified_achievements: int = 0


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One actionable recommendation.

    ``priority`` orders the report: 1 is most impactful.
    """

    category: str
    text: str
    priority: int = 2


@dataclass(frozen=True, slots=True)
class Evaluation:
    """The complete result of scoring one resume against one job description."""

    overall_score: float
    keywords: KeywordResult
    sections: SectionResult
    formatting: FormattingResult
    suggestions: tuple[Suggestion, ...] = field(default=())

    @property
    def grade(self) -> str:
        """A coarse band for the score, used as the report headline."""
        score = self.overall_score
        if score >= 85:
            return "Excellent"
        if score >= 70:
            return "Strong"
        if score >= 55:
            return "Fair"
        if score >= 40:
            return "Needs work"
        return "Poor"

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready snapshot, stored alongside the score row for history."""
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class VersionDelta:
    """Difference between two evaluations of the same job description."""

    score_delta: float
    keyword_delta: float
    section_delta: float
    formatting_delta: float
    newly_matched: tuple[str, ...] = ()
    no_longer_matched: tuple[str, ...] = ()
    added_sections: tuple[str, ...] = ()
    removed_sections: tuple[str, ...] = ()
    resolved_issues: tuple[str, ...] = ()
    new_issues: tuple[str, ...] = ()

    @property
    def improved(self) -> bool:
        return self.score_delta > 0

    @property
    def unchanged(self) -> bool:
        """True when nothing observable changed between the two versions."""
        return (
            self.score_delta == 0
            and not self.newly_matched
            and not self.no_longer_matched
            and not self.added_sections
            and not self.removed_sections
            and not self.resolved_issues
            and not self.new_issues
        )
