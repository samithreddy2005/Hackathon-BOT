"""Data-access functions.

Every function here is synchronous and blocking. Telegram handlers must call them
through :func:`ats_bot.utils.concurrency.run_blocking` so the event loop is never
stalled by disk I/O.
"""

from __future__ import annotations

import logging

from ats_bot.config import Settings
from ats_bot.db.connection import transaction
from ats_bot.db.models import JobDescription, Resume, ScoreRecord, User

__all__ = [
    "add_user",
    "count_scores",
    "delete_user_data",
    "get_all_resumes",
    "get_jd",
    "get_latest_jd",
    "get_latest_resume",
    "get_previous_resume",
    "get_resume",
    "get_score_history",
    "get_user",
    "save_jd",
    "save_resume",
    "save_score",
]

logger = logging.getLogger(__name__)

_RESUME_COLUMNS = (
    "resume_id, user_id, file_path, file_name, file_type, extracted_text, "
    "word_count, uploaded_at"
)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def add_user(user_id: int, username: str, *, settings: Settings | None = None) -> None:
    """Insert the user, or refresh their stored username if they already exist."""
    with transaction(settings) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username) VALUES (?, ?)
            ON CONFLICT (user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, username),
        )


def get_user(user_id: int, *, settings: Settings | None = None) -> User | None:
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return User.from_row(row) if row else None


# ---------------------------------------------------------------------------
# Resumes
# ---------------------------------------------------------------------------


def save_resume(
    user_id: int,
    file_path: str,
    file_name: str,
    file_type: str,
    extracted_text: str,
    *,
    settings: Settings | None = None,
) -> int:
    """Persist an uploaded resume and return its new ``resume_id``.

    The user row is created first so the foreign key always resolves, even if the
    user reached this handler without ever sending ``/start``.
    """
    word_count = len(extracted_text.split())
    with transaction(settings) as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor = conn.execute(
            """
            INSERT INTO resumes
                (user_id, file_path, file_name, file_type, extracted_text, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, file_path, file_name, file_type, extracted_text, word_count),
        )
        resume_id = cursor.lastrowid
    assert resume_id is not None  # AUTOINCREMENT always yields a rowid
    return int(resume_id)


def get_resume(resume_id: int, *, settings: Settings | None = None) -> Resume | None:
    with transaction(settings) as conn:
        row = conn.execute(
            f"SELECT {_RESUME_COLUMNS} FROM resumes WHERE resume_id = ?", (resume_id,)
        ).fetchone()
    return Resume.from_row(row) if row else None


def get_latest_resume(user_id: int, *, settings: Settings | None = None) -> Resume | None:
    with transaction(settings) as conn:
        row = conn.execute(
            f"""
            SELECT {_RESUME_COLUMNS} FROM resumes
            WHERE user_id = ?
            ORDER BY uploaded_at DESC, resume_id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return Resume.from_row(row) if row else None


def get_all_resumes(
    user_id: int, *, limit: int = 50, settings: Settings | None = None
) -> list[Resume]:
    """Return the user's resumes, newest first."""
    with transaction(settings) as conn:
        rows = conn.execute(
            f"""
            SELECT {_RESUME_COLUMNS} FROM resumes
            WHERE user_id = ?
            ORDER BY uploaded_at DESC, resume_id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [Resume.from_row(row) for row in rows]


def get_previous_resume(
    user_id: int, before_resume_id: int, *, settings: Settings | None = None
) -> Resume | None:
    """Return the resume uploaded immediately before ``before_resume_id``."""
    with transaction(settings) as conn:
        row = conn.execute(
            f"""
            SELECT {_RESUME_COLUMNS} FROM resumes
            WHERE user_id = ? AND resume_id < ?
            ORDER BY resume_id DESC
            LIMIT 1
            """,
            (user_id, before_resume_id),
        ).fetchone()
    return Resume.from_row(row) if row else None


# ---------------------------------------------------------------------------
# Job descriptions
# ---------------------------------------------------------------------------


def save_jd(user_id: int, jd_text: str, *, settings: Settings | None = None) -> int:
    with transaction(settings) as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor = conn.execute(
            "INSERT INTO job_descriptions (user_id, jd_text) VALUES (?, ?)",
            (user_id, jd_text),
        )
        jd_id = cursor.lastrowid
    assert jd_id is not None
    return int(jd_id)


def get_jd(jd_id: int, *, settings: Settings | None = None) -> JobDescription | None:
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM job_descriptions WHERE jd_id = ?", (jd_id,)).fetchone()
    return JobDescription.from_row(row) if row else None


def get_latest_jd(user_id: int, *, settings: Settings | None = None) -> JobDescription | None:
    with transaction(settings) as conn:
        row = conn.execute(
            """
            SELECT * FROM job_descriptions
            WHERE user_id = ?
            ORDER BY created_at DESC, jd_id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return JobDescription.from_row(row) if row else None


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


def save_score(
    *,
    resume_id: int,
    jd_id: int,
    overall_score: float,
    keyword_score: float,
    structure_score: float,
    formatting_score: float,
    details_json: str = "{}",
    settings: Settings | None = None,
) -> int:
    with transaction(settings) as conn:
        cursor = conn.execute(
            """
            INSERT INTO scores
                (resume_id, jd_id, overall_score, keyword_score,
                 structure_score, formatting_score, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resume_id,
                jd_id,
                overall_score,
                keyword_score,
                structure_score,
                formatting_score,
                details_json,
            ),
        )
        score_id = cursor.lastrowid
    assert score_id is not None
    return int(score_id)


def count_scores(user_id: int, *, settings: Settings | None = None) -> int:
    """Total number of evaluations recorded for a user."""
    with transaction(settings) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM scores s
            JOIN resumes r ON r.resume_id = s.resume_id
            WHERE r.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return int(row["n"]) if row else 0


def get_score_history(
    user_id: int, *, limit: int = 20, settings: Settings | None = None
) -> list[ScoreRecord]:
    """Return the user's evaluations, newest first, joined with resume metadata."""
    with transaction(settings) as conn:
        rows = conn.execute(
            """
            SELECT s.*, r.file_name, r.file_type
            FROM scores s
            JOIN resumes r ON r.resume_id = s.resume_id
            WHERE r.user_id = ?
            ORDER BY s.created_at DESC, s.score_id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [ScoreRecord.from_row(row) for row in rows]


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------


def delete_user_data(user_id: int, *, settings: Settings | None = None) -> int:
    """Delete everything stored for a user. Returns the number of resumes removed.

    Cascades to job descriptions and scores via the schema's foreign keys.
    """
    with transaction(settings) as conn:
        removed = conn.execute(
            "SELECT COUNT(*) AS n FROM resumes WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        # Rows may predate the cascading foreign keys, so clean up explicitly.
        conn.execute(
            "DELETE FROM scores WHERE resume_id IN (SELECT resume_id FROM resumes WHERE user_id = ?)",
            (user_id,),
        )
        conn.execute("DELETE FROM job_descriptions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    return int(removed)
