"""The /start, /help, and /about commands."""

from __future__ import annotations

import logging

from telegram import Update

from ats_bot import __version__
from ats_bot.db import repository
from ats_bot.errors import DatabaseError
from ats_bot.handlers.common import BotContext, get_llm, main_menu
from ats_bot.parsing import ocr_available
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, code, esc, italic, safe_reply

__all__ = ["handle_about", "handle_help", "handle_start"]

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    f"❓ {bold('How this bot works')}\n"
    "──────────────────────\n\n"
    f"{bold('1. Send your resume')}\n"
    "Upload it as a file — PDF, DOCX, PNG, or JPG. Photos are read with OCR, so a "
    "text-based PDF always scores more accurately than a picture of one.\n\n"
    f"{bold('2. Paste the job description')}\n"
    "Send the posting as a plain text message. Include the requirements section — "
    "that is where the keywords that matter live.\n\n"
    f"{bold('3. Read the report')}\n"
    "You get a score out of 100 and a prioritised list of fixes:\n"
    f"• {bold('Keywords (40%)')} — how much of what the posting asks for appears in "
    "your resume.\n"
    f"• {bold('Sections (30%)')} — whether the standard resume sections are present "
    "and findable.\n"
    f"• {bold('Formatting (30%)')} — length, contact details, links, measurable "
    "results, and placeholder text.\n\n"
    f"{bold('4. Iterate')}\n"
    "Edit your resume, upload the new version, and send the same posting again. "
    f"{code('/compare')} shows exactly what your edit changed.\n\n"
    f"{bold('Commands')}\n"
    f"{code('/start')} — main menu\n"
    f"{code('/help')} — this guide\n"
    f"{code('/compare')} — contrast your two most recent resumes\n"
    f"{code('/history')} — your past scores\n"
    f"{code('/newchat')} — clear the current session\n"
    f"{code('/about')} — version and status\n\n"
    f"{italic('You can also just ask a question — about interviews, salary, career gaps, or your own resume.')}"
)


async def handle_start(update: Update, context: BotContext) -> None:
    """Greet the user, record them, and show the main menu."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:  # pragma: no cover - filtered upstream
        return

    display_name = user.first_name or user.username or "there"

    try:
        await run_blocking(repository.add_user, user.id, user.username or display_name)
    except DatabaseError:
        # Not being able to record the user is not a reason to refuse to greet them;
        # save_resume creates the row again when it is actually needed.
        logger.exception("Could not record user %s on /start", user.id)

    text = (
        f"👋 {bold(f'Hello {display_name}')} — welcome to the ATS Resume Analyzer.\n\n"
        "I score your resume against a specific job posting the way an applicant "
        "tracking system would, then tell you exactly what to change.\n\n"
        f"{bold('To start:')} send me your resume as a file (PDF, DOCX, or an image), "
        "then paste the job description.\n\n"
        f"{italic('Everything is scored locally. Use /newchat at any time to clear your session.')}"
    )
    await safe_reply(message, text, reply_markup=main_menu())


async def handle_help(update: Update, context: BotContext) -> None:
    """Show the usage guide."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return
    await safe_reply(message, _HELP_TEXT)


async def handle_about(update: Update, context: BotContext) -> None:
    """Report the version and which optional features are active."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    assistant = get_llm(context)
    assistant_status = assistant.status if assistant else "offline knowledge base"

    text = (
        f"🤖 {bold('ATS Resume Analyzer')} {code('v' + __version__)}\n"
        "──────────────────────\n"
        f"• Scoring engine: {bold('local')}, no data leaves this machine\n"
        f"• Image OCR: {bold('available' if ocr_available() else 'not installed')}\n"
        f"• Q&A assistant: {esc(assistant_status)}\n\n"
        f"{italic('Open source under the MIT licence.')}"
    )
    await safe_reply(message, text)
