"""Session management: /newchat and /forgetme."""

from __future__ import annotations

import logging
import shutil

from telegram import Update

from ats_bot.db import repository
from ats_bot.handlers.common import (
    BotContext,
    clear_session,
    get_settings_from,
    user_id_of,
)
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, code, italic, safe_reply

__all__ = ["handle_forget_me", "handle_newchat"]

logger = logging.getLogger(__name__)


async def handle_newchat(update: Update, context: BotContext) -> None:
    """Clear the conversation state without deleting stored data."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    clear_session(context)
    await safe_reply(
        message,
        f"🧹 {bold('Fresh session')}\n\n"
        "I have forgotten the resume and job description we were working on. Your "
        f"saved history is untouched — {code('/history')} still works.\n\n"
        + italic("Upload a resume to start a new evaluation, or just ask me a question."),
    )


async def handle_forget_me(update: Update, context: BotContext) -> None:
    """Permanently delete everything stored for this user.

    Resumes are personal data. Offering an unambiguous, self-service delete is
    both good practice and, in several jurisdictions, a legal requirement.
    """
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    settings = get_settings_from(context)
    user_id = user_id_of(update)

    removed = await run_blocking(repository.delete_user_data, user_id)
    clear_session(context)

    user_uploads = settings.upload_dir / str(user_id)
    if user_uploads.is_dir():
        await run_blocking(shutil.rmtree, user_uploads, ignore_errors=True)

    await safe_reply(
        message,
        f"🗑 {bold('Everything deleted')}\n\n"
        f"{removed} resume{'' if removed == 1 else 's'}, along with your job "
        "descriptions, scores, and uploaded files, have been permanently removed.\n\n"
        + italic("Send a new resume whenever you would like to start again."),
    )
