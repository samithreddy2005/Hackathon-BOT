"""Compare two evaluations of the same job description.

Both evaluations must be scored against the *same* job description, otherwise the
deltas are meaningless — callers are responsible for re-scoring the older resume
against the current posting rather than reusing its stored score.
"""

from __future__ import annotations

from ats_bot.ats.models import Evaluation, VersionDelta

__all__ = ["compare_evaluations"]


def compare_evaluations(current: Evaluation, previous: Evaluation) -> VersionDelta:
    """Return what changed from ``previous`` to ``current``.

    >>> from ats_bot.ats.scorer import evaluate_resume
    >>> jd = "We need Python and Docker"
    >>> delta = compare_evaluations(
    ...     evaluate_resume("Python and Docker skills here", jd),
    ...     evaluate_resume("Python skills here", jd),
    ... )
    >>> delta.newly_matched
    ('docker',)
    """
    current_matched = set(current.keywords.matched)
    previous_matched = set(previous.keywords.matched)

    current_sections = set(current.sections.present)
    previous_sections = set(previous.sections.present)

    current_issues = set(current.formatting.issues)
    previous_issues = set(previous.formatting.issues)

    return VersionDelta(
        score_delta=round(current.overall_score - previous.overall_score, 1),
        keyword_delta=round(current.keywords.score - previous.keywords.score, 1),
        section_delta=round(current.sections.score - previous.sections.score, 1),
        formatting_delta=round(current.formatting.score - previous.formatting.score, 1),
        # Sorted so the report is stable across runs; set difference is unordered.
        newly_matched=tuple(sorted(current_matched - previous_matched)),
        no_longer_matched=tuple(sorted(previous_matched - current_matched)),
        added_sections=tuple(sorted(current_sections - previous_sections)),
        removed_sections=tuple(sorted(previous_sections - current_sections)),
        resolved_issues=tuple(sorted(previous_issues - current_issues)),
        new_issues=tuple(sorted(current_issues - previous_issues)),
    )
