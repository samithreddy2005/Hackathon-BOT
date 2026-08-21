"""Rendering of evaluation results into Telegram messages.

Kept separate from both the scoring engine and the handlers: the engine should not
know about Telegram, and handlers should not contain paragraphs of string
building. Every dynamic value goes through :func:`~ats_bot.utils.telegram_html.esc`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ats_bot.ats.models import Evaluation, VersionDelta
from ats_bot.db.models import ScoreRecord
from ats_bot.utils.telegram_html import bold, code, esc, italic, progress_bar

__all__ = [
    "render_comparison",
    "render_evaluation",
    "render_history",
    "score_emoji",
]

_RULE = "──────────────────────"

#: How many keywords to list before collapsing the rest into a count.
_KEYWORD_LIMIT = 18

#: How many suggestions to show; the list is already sorted by priority.
_SUGGESTION_LIMIT = 8


def score_emoji(score: float) -> str:
    """A traffic-light indicator for a 0-100 score."""
    if score >= 70:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"


def _keyword_line(keywords: Sequence[str]) -> str:
    if not keywords:
        return italic("none")
    shown = ", ".join(keywords[:_KEYWORD_LIMIT])
    remainder = len(keywords) - _KEYWORD_LIMIT
    if remainder > 0:
        return f"{esc(shown)} {italic(f'+{remainder} more')}"
    return esc(shown)


def render_evaluation(evaluation: Evaluation, *, resume_name: str | None = None) -> str:
    """Render a full evaluation report."""
    lines: list[str] = []

    if resume_name:
        lines.append(f"📄 {bold(resume_name)}")

    lines += [
        f"{score_emoji(evaluation.overall_score)} {bold('ATS Match Report')}",
        _RULE,
        f"{bold(f'{evaluation.overall_score}/100')} — {esc(evaluation.grade)}",
        progress_bar(evaluation.overall_score),
        "",
        f"🔑 Keywords {italic('(40%)')} — {bold(f'{evaluation.keywords.score}%')}",
        f"🏛 Sections {italic('(30%)')} — {bold(f'{evaluation.sections.score}%')}",
        f"📐 Formatting {italic('(30%)')} — {bold(f'{evaluation.formatting.score}%')}",
        _RULE,
        "",
    ]

    keywords = evaluation.keywords
    if keywords.total:
        header = (
            "Skills from the posting" if keywords.from_dictionary else "Key terms in the posting"
        )
        lines.append(f"{bold(header)} — {len(keywords.matched)}/{keywords.total} found")
        lines.append(f"✅ {_keyword_line(keywords.matched)}")
        lines.append(f"❌ {_keyword_line(keywords.missing)}")
    else:
        lines.append(
            italic(
                "No requirements could be extracted from that job description — "
                "paste the full posting for a keyword score."
            )
        )
    lines.append("")

    if evaluation.sections.missing:
        lines.append(f"{bold('Missing sections')}: {esc(', '.join(evaluation.sections.missing))}")
    else:
        lines.append(f"{bold('Sections')}: all present ✅")

    stats = evaluation.formatting
    lines.append(
        f"{bold('At a glance')}: {stats.word_count} words · "
        f"email {'✅' if stats.has_email else '❌'} · "
        f"phone {'✅' if stats.has_phone else '❌'} · "
        f"links {'✅' if stats.has_links else '❌'} · "
        f"{stats.quantified_achievements} quantified result"
        f"{'' if stats.quantified_achievements == 1 else 's'}"
    )

    if evaluation.suggestions:
        lines += ["", _RULE, bold("What to fix, highest impact first"), ""]
        for index, suggestion in enumerate(evaluation.suggestions[:_SUGGESTION_LIMIT], start=1):
            lines.append(f"{index}. {esc(suggestion.text)}")
        remaining = len(evaluation.suggestions) - _SUGGESTION_LIMIT
        if remaining > 0:
            lines.append(italic(f"…and {remaining} more."))

    return "\n".join(lines)


def render_comparison(
    delta: VersionDelta,
    *,
    current_name: str | None = None,
    previous_name: str | None = None,
    current_score: float | None = None,
    previous_score: float | None = None,
) -> str:
    """Render the difference between two versions of a resume."""
    if delta.score_delta > 0:
        headline, arrow = "Improved", "📈"
    elif delta.score_delta < 0:
        headline, arrow = "Declined", "📉"
    else:
        headline, arrow = "No score change", "➖"

    sign = "+" if delta.score_delta > 0 else ""
    lines = [
        f"{arrow} {bold('Version comparison')}",
        _RULE,
        f"{bold(headline)}: {code(f'{sign}{delta.score_delta} points')}",
    ]

    if previous_score is not None and current_score is not None:
        lines.append(f"{previous_score}/100 → {bold(f'{current_score}/100')}")

    if previous_name and current_name:
        lines.append(italic(f"{previous_name} → {current_name}"))

    lines += [
        "",
        f"🔑 Keywords {_delta_label(delta.keyword_delta)}",
        f"🏛 Sections {_delta_label(delta.section_delta)}",
        f"📐 Formatting {_delta_label(delta.formatting_delta)}",
    ]

    sections: list[tuple[str, Sequence[str]]] = [
        ("✨ Newly matched skills", delta.newly_matched),
        ("⚠️ Skills no longer matched", delta.no_longer_matched),
        ("🏛 Sections added", delta.added_sections),
        ("🗑 Sections removed", delta.removed_sections),
        ("✅ Issues resolved", delta.resolved_issues),
        ("🔴 New issues", delta.new_issues),
    ]
    for title, items in sections:
        if items:
            lines += ["", bold(title)]
            lines += [f"• {esc(item)}" for item in items]

    if delta.unchanged:
        lines += [
            "",
            italic(
                "The two versions score identically against this job description. "
                "Close a missing keyword or add a measurable result to move the number."
            ),
        ]

    return "\n".join(lines)


def _delta_label(value: float) -> str:
    if value > 0:
        return f"{code(f'+{value}')} ▲"
    if value < 0:
        return f"{code(str(value))} ▼"
    return f"{code('0')} —"


def render_history(records: Sequence[ScoreRecord], *, total: int | None = None) -> str:
    """Render a user's scoring history, newest first."""
    lines = [f"📜 {bold('Your scoring history')}", _RULE, ""]

    for index, record in enumerate(records, start=1):
        timestamp = record.created_at.split(".")[0] or "unknown date"
        label = record.file_name or f"resume #{record.resume_id}"
        lines += [
            f"{index}. {score_emoji(record.overall_score)} {bold(f'{record.overall_score}/100')} "
            f"· {code(timestamp)}",
            f"    {progress_bar(record.overall_score, width=12)}",
            f"    📄 {esc(label)} {italic(f'({record.file_type})')}",
            "",
        ]

    if total is not None and total > len(records):
        lines.append(italic(f"Showing the {len(records)} most recent of {total} evaluations."))

    if len(records) >= 2:
        newest, oldest = records[0].overall_score, records[-1].overall_score
        movement = round(newest - oldest, 1)
        if movement:
            direction = "up" if movement > 0 else "down"
            lines.append(
                italic(f"Across this window your score is {direction} {abs(movement)} points.")
            )

    return "\n".join(lines)
