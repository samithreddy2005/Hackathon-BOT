"""The /compare command: contrast the two most recent resume versions."""

from __future__ import annotations

import logging
from contextlib import suppress

from telegram import Update
from telegram.error import TelegramError

from ats_bot.ats.comparison import compare_evaluations
from ats_bot.ats.scorer import evaluate_resume
from ats_bot.db import repository
from ats_bot.handlers.common import BotContext, user_id_of
from ats_bot.reporting import render_comparison
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, code, safe_reply

__all__ = ["handle_compare"]

logger = logging.getLogger(__name__)


async def handle_compare(update: Update, context: BotContext) -> None:
    """Score the two newest resumes against the latest job description and diff them."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    user_id = user_id_of(update)
    resumes = await run_blocking(repository.get_all_resumes, user_id, limit=2)

    if len(resumes) < 2:
        await safe_reply(
            message,
            f"🔄 {bold('Two versions are needed to compare')}\n\n"
            "Edit your resume, upload the new file, and I will show you what changed — "
            "keywords gained or lost, sections added, issues fixed, and the score "
            "movement.",
        )
        return

    job = await run_blocking(repository.get_latest_jd, user_id)
    if job is None:
        await safe_reply(
            message,
            f"📝 {bold('A job description is needed first')}\n\n"
            "Comparison is always relative to a target role. Paste a job description, "
            f"then run {code('/compare')} again.",
        )
        return

    notice = await message.reply_text("🔄 Comparing your two most recent versions…")

    current, previous = resumes[0], resumes[1]
    current_evaluation = await run_blocking(evaluate_resume, current.extracted_text, job.jd_text)
    previous_evaluation = await run_blocking(evaluate_resume, previous.extracted_text, job.jd_text)

    delta = compare_evaluations(current_evaluation, previous_evaluation)
    report = render_comparison(
        delta,
        current_name=current.display_name,
        previous_name=previous.display_name,
        current_score=current_evaluation.overall_score,
        previous_score=previous_evaluation.overall_score,
    )

    # The report can exceed one message, so it is sent fresh rather than edited in;
    # removing the placeholder is cosmetic and must not fail the command.
    with suppress(TelegramError):
        await notice.delete()
    await safe_reply(message, report)
