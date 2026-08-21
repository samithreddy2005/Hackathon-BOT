"""The /history command."""

from __future__ import annotations

import logging

from telegram import Update

from ats_bot.db import repository
from ats_bot.handlers.common import BotContext, user_id_of
from ats_bot.reporting import render_history
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, safe_reply

__all__ = ["HISTORY_LIMIT", "handle_history"]

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10


async def handle_history(update: Update, context: BotContext) -> None:
    """Show the user's most recent evaluations."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    user_id = user_id_of(update)
    records = await run_blocking(repository.get_score_history, user_id, limit=HISTORY_LIMIT)

    if not records:
        await safe_reply(
            message,
            f"📜 {bold('No history yet')}\n\n"
            "Upload a resume and paste a job description to record your first score. "
            "Every evaluation after that is kept here so you can watch the number move.",
        )
        return

    total = await run_blocking(repository.count_scores, user_id)
    await safe_reply(message, render_history(records, total=total))
