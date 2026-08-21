"""SQLite connection management.

Two things here are deliberate and easy to get wrong:

1. ``sqlite3.Connection`` used as a context manager commits or rolls back the
   transaction but does **not** close the connection. Every helper therefore wraps
   it in :func:`contextlib.closing`, which is what keeps file handles (and, on
   Windows, file locks) from leaking.
2. Pragmas are applied per connection, not per database, so they are set on every
   connect: WAL for concurrent readers, a busy timeout so a locked database retries
   instead of raising immediately, and foreign-key enforcement, which SQLite leaves
   off by default.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from ats_bot.config import Settings, get_settings
from ats_bot.errors import DatabaseError

__all__ = ["SCHEMA_PATH", "init_db", "transaction"]

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

_BUSY_TIMEOUT_MS = 5_000


def _database_path(settings: Settings | None) -> Path:
    return (settings or get_settings()).database_path


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    return connection


@contextmanager
def transaction(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a connection inside a transaction, committing on success.

    The transaction is rolled back if the body raises, and the connection is always
    closed. Any :class:`sqlite3.Error` is re-raised as
    :class:`~ats_bot.errors.DatabaseError` so callers only handle our exceptions.

    Example:
        >>> with transaction() as conn:  # doctest: +SKIP
        ...     conn.execute("INSERT INTO users (user_id) VALUES (?)", (1,))
    """
    path = _database_path(settings)
    try:
        with closing(_connect(path)) as connection:
            try:
                with connection:  # commits on success, rolls back on exception
                    yield connection
            except sqlite3.Error as exc:
                raise DatabaseError(f"Database operation failed: {exc}") from exc
    except sqlite3.Error as exc:  # failure while opening the database itself
        raise DatabaseError(f"Could not open database at {path}: {exc}") from exc


def init_db(settings: Settings | None = None) -> None:
    """Create the schema if it does not exist yet.

    Raises:
        DatabaseError: If the schema file is missing or cannot be applied.
    """
    if not SCHEMA_PATH.is_file():
        raise DatabaseError(f"Schema file not found at {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    path = _database_path(settings)
    try:
        with closing(_connect(path)) as connection, connection:
            connection.executescript(schema_sql)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Could not initialise database at {path}: {exc}") from exc

    logger.info("Database ready at %s", path)
