"""Resume upload handling: download, parse, validate, and store."""

from __future__ import annotations

import logging
from pathlib import Path

from rapidfuzz import fuzz
from telegram import Document, Message, PhotoSize, Update

from ats_bot.db import repository
from ats_bot.db.models import Resume
from ats_bot.errors import (
    FileTooLargeError,
    ParsingError,
    UnsupportedFileTypeError,
    UploadError,
)
from ats_bot.handlers.common import (
    STATE_AWAITING_JD,
    BotContext,
    SessionKey,
    get_settings_from,
    user_id_of,
)
from ats_bot.parsing import describe_extraction_failure, extract_text, looks_like_resume
from ats_bot.services.files import download_to, safe_display_name, storage_path_for, validate_upload
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, code, italic, safe_edit, safe_reply

__all__ = ["handle_resume_upload"]

logger = logging.getLogger(__name__)

#: Similarity above which a new upload is treated as a revision of the last one.
_REVISION_THRESHOLD = 60.0

_SUPPORTED_HINT = "Supported formats: PDF, DOCX, PNG, JPG."


async def handle_resume_upload(update: Update, context: BotContext) -> None:
    """Accept a document or photo, turn it into text, and store it as a resume."""
    message = update.effective_message
    if message is None:  # pragma: no cover - filtered upstream
        return

    settings = get_settings_from(context)
    user_id = user_id_of(update)

    source, file_name, size_bytes = _describe_attachment(message)
    if source is None:
        await safe_reply(
            message,
            f"❌ I could not find a file in that message. {_SUPPORTED_HINT}",
        )
        return

    try:
        kind = validate_upload(file_name, size_bytes, settings)
    except UnsupportedFileTypeError as exc:
        await safe_reply(
            message,
            f"❌ I cannot read {code(exc.extension)} files. {_SUPPORTED_HINT}\n\n"
            + italic("If this is a .doc file, open it in Word and save it as .docx or PDF."),
        )
        return
    except FileTooLargeError as exc:
        limit_mb = exc.limit_bytes // (1024 * 1024)
        await safe_reply(
            message,
            f"❌ That file is {bold(f'{exc.size_bytes / 1_048_576:.1f} MB')}, over the "
            f"{limit_mb} MB limit. Please compress it or export a lighter PDF.",
        )
        return

    status = await message.reply_text("📥 Downloading your resume…")
    display_name = safe_display_name(file_name)
    destination = storage_path_for(user_id, file_name, settings)

    try:
        await download_to(source, destination)
    except UploadError as exc:
        logger.warning("Download failed for user %s: %s", user_id, exc)
        await safe_edit(status, "❌ Telegram would not hand over that file. Please try again.")
        return

    await safe_edit(status, f"🔍 Reading {code(display_name)}…")

    try:
        # Parsing is CPU-bound and can take seconds on a scanned page; keeping it
        # off the event loop is what lets other users be served meanwhile.
        text = await run_blocking(extract_text, destination, kind)
    except ParsingError as exc:
        _discard(destination)
        await safe_edit(status, f"❌ {exc}")
        return

    problem = _reject_reason(text, kind, settings.min_resume_words)
    if problem is not None:
        _discard(destination)
        await safe_edit(status, problem)
        return

    word_count = len(text.split())
    previous = await run_blocking(repository.get_latest_resume, user_id)
    is_revision = _is_revision_of(text, previous)

    resume_id = await run_blocking(
        repository.save_resume, user_id, str(destination), display_name, kind, text
    )

    _remember_upload(context, resume_id)

    if is_revision:
        headline = f"🔄 {bold('New version received')}"
        follow_up = (
            "Send the same job description again and I will show you exactly what "
            f"your edit changed, or use {code('/compare')}."
        )
    else:
        headline = f"✅ {bold('Resume received')}"
        follow_up = (
            f"{bold('Next:')} paste the job description as a text message and I will "
            "score your resume against it."
        )

    await safe_edit(
        status,
        f"{headline}\n" f"📄 {code(display_name)} · {word_count} words\n\n" f"{follow_up}",
    )


def _describe_attachment(
    message: Message,
) -> tuple[Document | PhotoSize | None, str, int | None]:
    """Extract (downloadable, filename, size) from a document or photo message."""
    document = message.document
    if document is not None:
        # A document sent without a name still needs one; the extension decides
        # how it is parsed, so an unnamed file is rejected by validate_upload.
        return document, document.file_name or document.file_id, document.file_size

    if message.photo:
        largest = message.photo[-1]  # Telegram orders photo sizes ascending
        return largest, f"photo_{largest.file_id}.jpg", largest.file_size

    return None, "", None


def _reject_reason(text: str, kind: str, min_words: int) -> str | None:
    """Return a user-facing rejection message, or None when the text is usable."""
    if not text.strip():
        return f"❌ {describe_extraction_failure(kind)}"

    word_count = len(text.split())
    if word_count < min_words:
        return (
            f"❌ {bold('That document is too short to score')}\n\n"
            f"I read only {word_count} words, and an ATS evaluation needs at least "
            f"{min_words}. If this is a scan or a photo, try a text-based PDF — the "
            "text layer is what both this bot and a real ATS read."
        )

    if not looks_like_resume(text):
        return (
            f"❌ {bold('This does not look like a resume')}\n\n"
            "I could not find any of the usual sections (Experience, Education, "
            "Skills) or a contact block.\n\n"
            + italic(
                "If you meant to send a job description, send it as a text message "
                "instead — upload your resume first."
            )
        )

    return None


def _is_revision_of(text: str, previous: Resume | None) -> bool:
    """Whether ``text`` is an edit of the user's previous resume rather than a new one."""
    if previous is None or not previous.extracted_text.strip():
        return False
    similarity = fuzz.ratio(text.lower(), previous.extracted_text.lower())
    return similarity > _REVISION_THRESHOLD


def _remember_upload(context: BotContext, resume_id: int) -> None:
    """Queue the resume for the next job description sent in this conversation."""
    if context.user_data is None:  # pragma: no cover
        return
    context.user_data[SessionKey.STATE] = STATE_AWAITING_JD
    context.user_data[SessionKey.LAST_RESUME_ID] = resume_id
    context.user_data[SessionKey.SESSION_CLEARED] = False

    pending = context.user_data.setdefault(SessionKey.PENDING_RESUME_IDS, [])
    if resume_id not in pending:
        pending.append(resume_id)


def _discard(path: Path) -> None:
    """Delete a stored upload we are not going to use."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - best effort cleanup
        logger.warning("Could not delete rejected upload %s: %s", path, exc)
