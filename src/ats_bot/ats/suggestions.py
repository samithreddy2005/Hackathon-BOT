"""Turn analyzer output into a prioritised list of things to fix.

Suggestions are ordered so the user reads the highest-leverage change first:
missing keywords (the pillar with the largest weight), then missing sections,
then formatting.
"""

from __future__ import annotations

from ats_bot.ats.models import FormattingResult, KeywordResult, SectionResult, Suggestion

__all__ = ["generate_suggestions"]

#: Advice keyed by the section that is absent.
_SECTION_ADVICE: dict[str, str] = {
    "experience": (
        "Add a 'Work Experience' section. List each role as "
        "Title — Company — Dates, followed by three achievement bullets."
    ),
    "education": (
        "Add an 'Education' section with your degree, institution, and year. "
        "Many ATS filters reject resumes where they cannot find one."
    ),
    "skills": (
        "Add a dedicated 'Skills' section. It is the block keyword scanners read "
        "first, and it is the cheapest place to close the gaps listed above."
    ),
    "summary": (
        "Open with a 3-4 line 'Professional Summary' naming your title, years of "
        "experience, and the two results you are proudest of."
    ),
    "projects": (
        "Add a 'Projects' section. It is the fastest way to evidence a skill you "
        "have not yet used in a paid role."
    ),
}

#: How many missing keywords to name explicitly before summarising the rest.
_KEYWORD_SAMPLE = 8


def generate_suggestions(
    keywords: KeywordResult,
    sections: SectionResult,
    formatting: FormattingResult,
) -> tuple[Suggestion, ...]:
    """Build the prioritised recommendation list for one evaluation."""
    suggestions: list[Suggestion] = []

    suggestions.extend(_keyword_suggestions(keywords))
    suggestions.extend(
        Suggestion("structure", _SECTION_ADVICE[name], priority=2)
        for name in sections.missing
        if name in _SECTION_ADVICE
    )
    suggestions.extend(Suggestion("formatting", issue, priority=3) for issue in formatting.issues)

    if not suggestions:
        suggestions.append(
            Suggestion(
                "general",
                "No gaps found against this job description. Tailor the summary to "
                "name the role you are applying for and send it.",
                priority=3,
            )
        )

    suggestions.sort(key=lambda item: item.priority)
    return tuple(suggestions)


def _keyword_suggestions(keywords: KeywordResult) -> list[Suggestion]:
    if not keywords.missing:
        if keywords.total:
            return [
                Suggestion(
                    "keywords",
                    "Every skill named in the job description appears in your resume.",
                    priority=3,
                )
            ]
        return []

    sample = list(keywords.missing[:_KEYWORD_SAMPLE])
    remainder = len(keywords.missing) - len(sample)

    if keywords.from_dictionary:
        lead = (
            "Work these job-description skills into your resume where you genuinely "
            f"have them: {', '.join(sample)}."
        )
    else:
        # The statistical fallback produces noisier terms, so hedge the wording.
        lead = (
            "This posting names no skill from our technical dictionary, so these are "
            "the terms it emphasises most — mirror the ones that apply to you: "
            f"{', '.join(sample)}."
        )

    result = [Suggestion("keywords", lead, priority=1)]
    if remainder > 0:
        result.append(
            Suggestion(
                "keywords",
                f"{remainder} further term{'s' if remainder > 1 else ''} from the posting "
                "are absent. Re-read it and mirror its exact wording where it is true of you.",
                priority=2,
            )
        )
    result.append(
        Suggestion(
            "keywords",
            "Put each new keyword inside an achievement bullet, not in a list at the "
            "bottom — keyword stuffing is detected and penalised.",
            priority=3,
        )
    )
    return result
