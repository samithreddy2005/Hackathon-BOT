"""Upload intake: validation, safe storage paths, download retries, and cleanup."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import TypeAlias

from telegram import Document, PhotoSize
from telegram.error import NetworkError, RetryAfter, TimedOut

from ats_bot.config import Settings
from ats_bot.constants import SUPPORTED_EXTENSIONS
from ats_bot.errors import FileTooLargeError, UnsupportedFileTypeError, UploadError

__all__ = [
    "Downloadable",
    "download_to",
    "purge_old_uploads",
    "safe_display_name",
    "storage_path_for",
    "validate_upload",
]

logger = logging.getLogger(__name__)

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 45.0
_BACKOFF_BASE_SECONDS = 1.0

#: Characters that are illegal in a Windows filename, plus path separators.
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

#: Keep stored filenames short enough to stay well under any path length limit.
_MAX_STORED_NAME = 60


#: The Telegram attachment types this module knows how to fetch. Both expose the
#: same ``get_file()`` interface; there is no shared base class in the library.
Downloadable: TypeAlias = Document | PhotoSize


def safe_display_name(file_name: str) -> str:
    """Sanitise a user-supplied filename for display and storage.

    Strips directory components and characters that are illegal or dangerous in a
    path. The result is never empty and never resolves outside its parent
    directory, which is what keeps ``../../etc/passwd`` from being honoured.

    >>> safe_display_name("../../etc/passwd")
    'passwd'
    >>> safe_display_name("My Resume (final).pdf")
    'My Resume (final).pdf'
    >>> safe_display_name("   ")
    'resume'
    """
    # Take the last path component under either separator before sanitising.
    tail = file_name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _UNSAFE_CHARS.sub("", tail).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return "resume"
    if len(cleaned) > _MAX_STORED_NAME:
        suffix = Path(cleaned).suffix[:10]
        cleaned = cleaned[: _MAX_STORED_NAME - len(suffix)] + suffix
    return cleaned


def validate_upload(file_name: str, size_bytes: int | None, settings: Settings) -> str:
    """Check an upload before downloading it and return its document kind.

    Raises:
        UnsupportedFileTypeError: If the extension cannot be parsed.
        FileTooLargeError: If the declared size exceeds the configured limit.
    """
    extension = Path(safe_display_name(file_name)).suffix.lower()
    kind = SUPPORTED_EXTENSIONS.get(extension)
    if kind is None:
        raise UnsupportedFileTypeError(extension or "(none)")

    if size_bytes is not None and size_bytes > settings.max_upload_bytes:
        raise FileTooLargeError(size_bytes, settings.max_upload_bytes)

    return kind


def storage_path_for(user_id: int, file_name: str, settings: Settings) -> Path:
    """Build a collision-free path for a user's upload.

    A random token is prefixed rather than trusting the filename to be unique, so
    two users (or one user twice) uploading "resume.pdf" never overwrite each
    other, and a crafted name cannot target an existing file.
    """
    safe_name = safe_display_name(file_name)
    user_dir = settings.upload_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f"{secrets.token_hex(6)}_{safe_name}"


async def download_to(
    source: Downloadable,
    destination: Path,
    *,
    attempts: int = DOWNLOAD_ATTEMPTS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Path:
    """Download a Telegram file to ``destination``, retrying transient failures.

    Telegram's file endpoint intermittently times out under concurrent uploads and
    answers ``RetryAfter`` when rate limited; both are retried with exponential
    backoff. Permanent failures raise immediately rather than burning the retries.

    Raises:
        UploadError: If every attempt fails.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            telegram_file = await source.get_file(read_timeout=DOWNLOAD_TIMEOUT_SECONDS)
            await telegram_file.download_to_drive(
                destination,
                read_timeout=DOWNLOAD_TIMEOUT_SECONDS,
                write_timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
            return destination
        except RetryAfter as exc:
            last_error = exc
            # retry_after is an int on older python-telegram-bot and a timedelta
            # on newer ones.
            wait = exc.retry_after
            delay = (wait.total_seconds() if isinstance(wait, timedelta) else float(wait)) + 0.5
            logger.warning("Rate limited downloading %s; waiting %.1fs.", destination.name, delay)
        except (TimedOut, NetworkError, OSError) as exc:
            last_error = exc
            delay = _BACKOFF_BASE_SECONDS * 2 ** (attempt - 1)
            logger.warning(
                "Download attempt %d/%d for %s failed (%s); retrying in %.1fs.",
                attempt,
                attempts,
                destination.name,
                exc,
                delay,
            )

        if attempt < attempts:
            await sleep(delay)

    # Remove any partial file so a later read cannot pick up a truncated document.
    destination.unlink(missing_ok=True)
    raise UploadError(
        "The file could not be downloaded from Telegram after several attempts."
    ) from last_error


def purge_old_uploads(settings: Settings, *, now: float | None = None) -> int:
    """Delete stored uploads older than the configured retention window.

    Resumes contain personal data; keeping the raw files indefinitely is both a
    privacy liability and an unbounded disk cost. The extracted text stays in the
    database, so history and comparisons continue to work after the file is gone.

    Returns:
        The number of files deleted.
    """
    if settings.upload_retention_hours <= 0:
        return 0

    cutoff = (now or time.time()) - settings.upload_retention_hours * 3600
    removed = 0

    if not settings.upload_dir.is_dir():
        return 0

    for path in settings.upload_dir.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as exc:
            logger.warning("Could not remove stale upload %s: %s", path, exc)

    # Tidy up the now-empty per-user directories.
    for directory in sorted(settings.upload_dir.rglob("*"), reverse=True):
        if directory.is_dir():
            with suppress(OSError):  # not empty; leave it
                directory.rmdir()

    if removed:
        logger.info("Purged %d upload(s) older than %dh.", removed, settings.upload_retention_hours)
    return removed
