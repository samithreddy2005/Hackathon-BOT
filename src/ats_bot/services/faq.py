"""Offline FAQ retrieval — a small TF-IDF index with cosine similarity.

This is the fallback that keeps the assistant useful with no API key and no
network. It is deliberately dependency-free: the corpus is a dozen documents, so
a hand-rolled index costs microseconds and avoids pulling in scikit-learn.

Each entry is indexed over its question and tags (weighted heavily, since they are
how a user phrases the request) plus its answer body (weighted lightly, for
recall). Document vectors are L2-normalised at build time so a query only needs
one dot product per document.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from ats_bot.parsing.cleaner import tokenize
from ats_bot.services.knowledge_base import FAQ_ENTRIES, FaqEntry

__all__ = ["FaqIndex", "FaqMatch", "default_index"]

logger = logging.getLogger(__name__)

#: Below this cosine similarity a match is treated as "no answer found".
CONFIDENCE_THRESHOLD = 0.22

#: Relative weight of question/tag tokens versus answer-body tokens.
_TITLE_WEIGHT = 3.0
_BODY_WEIGHT = 1.0


@dataclass(frozen=True, slots=True)
class FaqMatch:
    """A retrieved FAQ entry and how confident the retrieval was."""

    entry: FaqEntry
    score: float

    @property
    def confident(self) -> bool:
        return self.score >= CONFIDENCE_THRESHOLD


class FaqIndex:
    """A TF-IDF index over a fixed set of FAQ entries."""

    def __init__(self, entries: Sequence[FaqEntry]) -> None:
        self._entries = tuple(entries)
        self._idf: dict[str, float] = {}
        self._vectors: list[dict[str, float]] = []
        self._build()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[FaqEntry, ...]:
        return self._entries

    def _build(self) -> None:
        weighted_docs = [self._weighted_terms(entry) for entry in self._entries]

        document_frequency: Counter[str] = Counter()
        for terms in weighted_docs:
            document_frequency.update(terms.keys())

        total = len(self._entries) or 1
        # Smoothed IDF: the +1 terms keep a term present in every document from
        # collapsing to zero weight, and avoid division by zero.
        self._idf = {
            term: math.log((1 + total) / (1 + count)) + 1.0
            for term, count in document_frequency.items()
        }

        self._vectors = [self._normalise(self._weight(terms)) for terms in weighted_docs]

    @staticmethod
    def _weighted_terms(entry: FaqEntry) -> dict[str, float]:
        """Term -> raw weighted frequency for one entry."""
        terms: dict[str, float] = {}
        title_source = f"{entry.question} {' '.join(entry.tags)}"
        for token in tokenize(title_source):
            terms[token] = terms.get(token, 0.0) + _TITLE_WEIGHT
        for token in tokenize(entry.answer):
            terms[token] = terms.get(token, 0.0) + _BODY_WEIGHT
        return terms

    def _weight(self, terms: dict[str, float]) -> dict[str, float]:
        return {term: freq * self._idf.get(term, 0.0) for term, freq in terms.items()}

    @staticmethod
    def _normalise(vector: dict[str, float]) -> dict[str, float]:
        magnitude = math.sqrt(sum(value * value for value in vector.values()))
        if magnitude == 0.0:
            return {}
        return {term: value / magnitude for term, value in vector.items()}

    def search(self, query: str) -> FaqMatch | None:
        """Return the best-matching entry, or None if the query has no usable terms.

        The returned match may still be below :data:`CONFIDENCE_THRESHOLD`; check
        :attr:`FaqMatch.confident` before presenting it as an answer.
        """
        query_terms = tokenize(query)
        if not query_terms:
            return None

        query_vector = self._normalise(
            {term: self._idf[term] for term in query_terms if term in self._idf}
        )
        if not query_vector:
            return None

        best_index = -1
        best_score = 0.0
        for index, document in enumerate(self._vectors):
            # Both vectors are unit length, so the dot product is the cosine.
            shared = query_vector.keys() & document.keys()
            score = sum(query_vector[term] * document[term] for term in shared)
            if score > best_score:
                best_score, best_index = score, index

        if best_index < 0:
            return None
        return FaqMatch(entry=self._entries[best_index], score=round(best_score, 4))


_default_index: FaqIndex | None = None


def default_index() -> FaqIndex:
    """The shared index over the bundled knowledge base, built on first use."""
    global _default_index
    if _default_index is None:
        _default_index = FaqIndex(FAQ_ENTRIES)
        logger.debug("Built FAQ index over %d entries.", len(_default_index))
    return _default_index
