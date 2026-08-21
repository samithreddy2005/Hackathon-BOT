"""Text normalisation and keyword candidate extraction.

Everything here is pure and side-effect free, which makes the scoring engine
deterministic and cheap to test.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from itertools import pairwise
from typing import Final

__all__ = [
    "JD_BOILERPLATE",
    "STOP_WORDS",
    "clean_text",
    "extract_potential_keywords",
    "focus_on_requirements",
    "tokenize",
]

#: Ordinary English stop words. Applied everywhere text is tokenised, including
#: FAQ search — so it must contain nothing a user might legitimately search for.
STOP_WORDS: Final[frozenset[str]] = frozenset("""
    a about above after again against all also am among an and another any anyone
    anything are aren as at be because been before being below between both but by
    can cannot could couldn did didn do does doesn doing don down during each etc
    few for from further get gets got had hadn has hasn have haven having he her
    here hers herself him himself his how i if in into is isn it its itself let
    like make me more most much must my myself no nor not of off on once only or
    other ought our ours ourselves out over own same shan she should shouldn so
    some such than that the their theirs them themselves then there these they
    this those through to too under until up us use used using various very via
    want was wasn we well were weren what when where which while who whom why will
    with within without won would wouldn you your yours yourself yourselves
    """.split())

#: Recruiting boilerplate. Excluded from *keyword extraction* only: these words
#: saturate job postings and would otherwise crowd out real requirements, but they
#: are meaningful search terms in their own right ("how do I answer a salary
#: question?"), so they must not be filtered out of FAQ queries.
JD_BOILERPLATE: Final[frozenset[str]] = frozenset("""
    ability able applicant applicants apply applying benefits candidate candidates
    company culture description duties employer employment ensure ensuring equal
    excellent experience good great help helping ideal including job join knowledge
    look looking need needed needs new offer opportunity plus position preferred
    proficiency provide providing qualification qualifications qualified related
    require required requirement requirements responsibilities responsibility role
    roles salary seeking skill skills strong support supporting team teams
    understanding work working year years
    """.split())

# Characters that carry meaning inside a technical term and must survive tokenising:
# c++, c#, ci/cd, scikit-learn, node.js
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9][a-z0-9+#./\-]*")

#: Single-character tokens that are real skills and must not be filtered as noise.
_ALLOWED_SINGLE_CHARS: Final[frozenset[str]] = frozenset({"c", "r"})

#: Headings that introduce the part of a job description worth mining for skills.
_REQUIREMENTS_HEADING: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:what\s+you.{0,15}|who\s+you.{0,15})?"
    r"(requirements?|qualifications?|skills?|must[\s-]haves?|you\s+(?:will\s+)?have|"
    r"we(?:'re|\s+are)\s+looking\s+for|technical\s+skills?|desired\s+skills?|"
    r"key\s+competencies|responsibilities)\b.*$",
    re.IGNORECASE,
)

#: Typographic characters mapped onto their ASCII equivalents, position by position.
_PUNCTUATION_TABLE: Final[dict[int, int]] = str.maketrans(
    "‘’“”–—• ",
    "''\"\"---" + " ",
)

#: Punctuation that ends a phrase. Bigram candidates never cross these.
_SEGMENT_SPLIT: Final[re.Pattern[str]] = re.compile(r"[.;:,!?()\[\]{}|/\n\r\t•·–—]+")

#: How often a two-word sequence must recur before it counts as terminology.
_MIN_PHRASE_COUNT: Final[int] = 2

#: Headings that end the interesting part (benefits blurbs, EEO boilerplate).
_CLOSING_HEADING: Final[re.Pattern[str]] = re.compile(
    r"^\s*(benefits?|perks?|compensation|salary|about\s+us|why\s+join|"
    r"equal\s+opportunity|how\s+to\s+apply|our\s+company)\b.*$",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    """Normalise whitespace and Unicode so downstream matching is predictable.

    Collapses runs of whitespace, converts the ligatures and smart punctuation that
    PDF extraction produces into ASCII equivalents, and strips control characters.

    >>> clean_text("  Senior\\u00a0 Engineer \\u2013 Data  ")
    'Senior Engineer - Data'
    """
    if not text:
        return ""

    # NFKC folds ligatures ("ﬁ" -> "fi") and full-width forms into plain ASCII.
    text = unicodedata.normalize("NFKC", text)
    # Smart quotes, dashes, and bullets folded to ASCII so that "Node–js" and
    # "Node-js" compare equal.
    text = text.translate(_PUNCTUATION_TABLE)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str) -> set[str]:
    """Lower-case ``text`` into a set of meaningful tokens.

    Stop words and one-character noise are dropped, but technical punctuation is
    preserved so ``c++`` survives as a single token.

    >>> sorted(tokenize("The C++ and Django framework"))
    ['c++', 'django', 'framework']
    """
    if not text:
        return set()

    tokens = _TOKEN_PATTERN.findall(text.lower())
    return {token.strip(".-/") for token in tokens if _is_meaningful(token.strip(".-/"))}


def _is_meaningful(token: str) -> bool:
    if not token or token in STOP_WORDS:
        return False
    if len(token) == 1:
        return token in _ALLOWED_SINGLE_CHARS
    return True


def _is_candidate(token: str) -> bool:
    """Stricter filter for keyword candidates.

    On top of the ordinary stop words this drops recruiting boilerplate, bare
    numbers, and very short words — none of which a candidate can act on.
    """
    if not _is_meaningful(token) or token in JD_BOILERPLATE:
        return False
    if token.replace(".", "").isdigit():
        return False
    return len(token) > 2 or token in _ALLOWED_SINGLE_CHARS


def focus_on_requirements(text: str) -> str:
    """Return the requirements/skills portion of a job description, if identifiable.

    Job posts bury the actual requirements between a company blurb and a benefits
    list; mining only the middle section produces far cleaner keywords. Falls back
    to the full text when no recognisable heading is present.
    """
    lines = text.split("\n")
    start: int | None = None
    end = len(lines)

    for index, line in enumerate(lines):
        if start is None:
            if len(line.strip()) <= 80 and _REQUIREMENTS_HEADING.match(line):
                start = index + 1
        elif len(line.strip()) <= 80 and _CLOSING_HEADING.match(line):
            end = index
            break

    if start is None:
        return text

    section = "\n".join(lines[start:end]).strip()
    # Guard against a heading that turned out to be the last line of the post.
    return section if len(section.split()) >= 15 else text


def extract_potential_keywords(text: str, *, max_keywords: int = 20) -> list[str]:
    """Extract likely keywords from free text when no dictionary skill is found.

    Used as the fallback path for job descriptions written without any recognised
    technology name (marketing, operations, finance roles, ...). Candidates are
    ranked by frequency, with two-word phrases weighted above single words because
    they carry more meaning ("financial modeling" beats "financial"). A single word
    already covered by a selected phrase is not returned again.

    >>> extract_potential_keywords(
    ...     "Stakeholder management is key. Strong stakeholder management required.",
    ...     max_keywords=2,
    ... )
    ['stakeholder management', 'key']
    """
    if not text:
        return []

    segments = [
        [w.strip(".-/") for w in _TOKEN_PATTERN.findall(segment)]
        for segment in _SEGMENT_SPLIT.split(text.lower())
    ]

    unigrams = Counter(w for segment in segments for w in segment if _is_candidate(w))
    if not unigrams:
        return []

    # Bigrams are only formed inside a segment, so a phrase never straddles a
    # sentence or bullet boundary, and only repeated phrases are trusted — a
    # two-word sequence seen once is far more often coincidence than terminology.
    bigrams: Counter[str] = Counter()
    for segment in segments:
        for first, second in pairwise(segment):
            if _is_candidate(first) and _is_candidate(second):
                bigrams[f"{first} {second}"] += 1

    # Phrases carry a 2x weight so they outrank the individual words they contain.
    ranked: list[tuple[float, str]] = [
        (count * 2.0, phrase) for phrase, count in bigrams.items() if count >= _MIN_PHRASE_COUNT
    ]
    ranked += [(float(count), word) for word, count in unigrams.items()]
    ranked.sort(key=lambda item: (-item[0], item[1]))

    selected: list[str] = []
    covered: set[str] = set()
    for _weight, candidate in ranked:
        parts = candidate.split()
        if len(parts) == 1 and candidate in covered:
            continue
        selected.append(candidate)
        covered.update(parts)
        if len(selected) >= max_keywords:
            break

    return selected
