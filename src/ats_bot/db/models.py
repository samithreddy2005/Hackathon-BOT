"""Typed row objects for the persistence layer.

Repository functions return these instead of raw ``sqlite3.Row`` / ``dict`` so that
callers get attribute access, defaults for nullable columns, and type checking.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

__all__ = ["JobDescription", "Resume", "ScoreRecord", "User"]


def _text(row: sqlite3.Row, key: str, default: str = "") -> str:
    """Read a column that may be absent (older database) or NULL."""
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else str(value)


def _number(row: sqlite3.Row, key: str, default: float = 0.0) -> float:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else float(value)


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    username: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> User:
        return cls(
            user_id=int(row["user_id"]),
            username=_text(row, "username"),
            created_at=_text(row, "created_at"),
        )


@dataclass(frozen=True, slots=True)
class Resume:
    resume_id: int
    user_id: int
    file_path: str
    file_name: str
    file_type: str
    extracted_text: str
    word_count: int
    uploaded_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Resume:
        text = _text(row, "extracted_text")
        return cls(
            resume_id=int(row["resume_id"]),
            user_id=int(row["user_id"]),
            file_path=_text(row, "file_path"),
            file_name=_text(row, "file_name"),
            file_type=_text(row, "file_type", "unknown"),
            extracted_text=text,
            word_count=int(_number(row, "word_count")) or len(text.split()),
            uploaded_at=_text(row, "uploaded_at"),
        )

    @property
    def display_name(self) -> str:
        """A human-friendly label for reports, falling back to the stored path."""
        if self.file_name:
            return self.file_name
        tail = self.file_path.replace("\\", "/").rsplit("/", 1)[-1]
        return tail or f"resume #{self.resume_id}"


@dataclass(frozen=True, slots=True)
class JobDescription:
    jd_id: int
    user_id: int
    jd_text: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobDescription:
        return cls(
            jd_id=int(row["jd_id"]),
            user_id=int(row["user_id"]),
            jd_text=_text(row, "jd_text"),
            created_at=_text(row, "created_at"),
        )


@dataclass(frozen=True, slots=True)
class ScoreRecord:
    """A stored evaluation, joined with the resume it was computed from."""

    score_id: int
    resume_id: int
    jd_id: int
    overall_score: float
    keyword_score: float
    structure_score: float
    formatting_score: float
    details_json: str
    created_at: str
    file_name: str = ""
    file_type: str = "unknown"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ScoreRecord:
        return cls(
            score_id=int(row["score_id"]),
            resume_id=int(row["resume_id"]),
            jd_id=int(row["jd_id"]),
            overall_score=_number(row, "overall_score"),
            keyword_score=_number(row, "keyword_score"),
            structure_score=_number(row, "structure_score"),
            formatting_score=_number(row, "formatting_score"),
            details_json=_text(row, "details", "{}") or "{}",
            created_at=_text(row, "created_at"),
            file_name=_text(row, "file_name"),
            file_type=_text(row, "file_type", "unknown"),
        )
