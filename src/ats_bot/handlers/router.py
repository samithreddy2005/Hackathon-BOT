"""Routing for plain text messages and inline-keyboard callbacks.

A single text message can mean two completely different things: "here is the job
posting, score me" or "answer my question". :func:`looks_like_job_description`
decides which, and getting it wrong is the most visible failure mode the bot has —
so the rule is stated explicitly and tested rather than left implicit.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Final

from telegram import Update
from telegram.error import TelegramError

from ats_bot.handlers.chat import handle_question
from ats_bot.handlers.common import (
    CB_COMPARE,
    CB_HELP,
    CB_HISTORY,
    CB_LATEST_SCORE,
    CB_TIPS,
    STATE_AWAITING_JD,
    BotContext,
    SessionKey,
)
from ats_bot.handlers.compare import handle_compare
from ats_bot.handlers.history import handle_history
from ats_bot.handlers.score import handle_job_description, handle_latest_score
from ats_bot.handlers.start import handle_help
from ats_bot.utils.telegram_html import bold, safe_reply

__all__ = ["handle_callback", "handle_text", "looks_like_job_description"]

logger = logging.getLogger(__name__)

#: Words that open a question. A message starting with one is a question even if
#: it is long, which is why this is checked before the length rule.
_QUESTION_OPENERS: Final[frozenset[str]] = frozenset("""
    how what why who where when which can could should would will shall is are am
    do does did was were have has had may might must tell show give explain describe
    suggest recommend help review improve rewrite write make list compare check
    """.split())

#: Phrases that only appear in a job posting.
_JD_MARKERS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bjob\s+(?:description|title|summary|id)\b",
        r"\b(?:key\s+)?responsibilities\b",
        r"\b(?:minimum|basic|preferred|desired)?\s*(?:requirements|qualifications)\b",
        r"\bwe(?:'re| are)\s+(?:looking|seeking|hiring)\b",
        r"\bthe\s+(?:ideal|successful)\s+candidate\b",
        r"\b\d+\+?\s*years?\s+(?:of\s+)?experience\b",
        r"\bwhat\s+you(?:'ll| will)\s+(?:do|bring)\b",
        r"\bbachelor'?s?\s+degree\b",
        r"\bfull[\s-]?time\b|\bpart[\s-]?time\b|\bcontract\s+role\b",
        r"\babout\s+the\s+(?:role|position|team)\b",
    )
)

#: A message this long is a pasted document, not something typed into a chat box.
_LENGTH_THRESHOLD: Final[int] = 60

#: With a posting marker present, a shorter message still reads as a job description.
_MARKER_LENGTH_THRESHOLD: Final[int] = 25


def looks_like_job_description(text: str) -> bool:
    """Classify a text message as a job description rather than a question.

    The rules, in order:

    1. A message ending in "?" is a question.
    2. A message opening with an interrogative is a question — this beats length,
       because "can you rewrite my summary, here is the posting…" is a request.
    3. A message containing a posting marker ("responsibilities", "5+ years of
       experience") and more than 25 words is a job description.
    4. Anything over 60 words is a pasted document.
    5. Everything else is a question.

    >>> looks_like_job_description("What sections should I include?")
    False
    >>> looks_like_job_description(
    ...     "Responsibilities: build and operate our billing services. Requirements: "
    ...     "5+ years of experience with Python, Django and PostgreSQL. A bachelor's "
    ...     "degree is preferred. You will own the platform roadmap and mentor "
    ...     "other engineers on the team."
    ... )
    True
    >>> looks_like_job_description("thanks!")
    False
    """
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.endswith("?"):
        return False

    words = stripped.split()
    first = words[0].lower().strip(".,!?\"'“”‘’")
    if first in _QUESTION_OPENERS:
        return False

    has_marker = any(pattern.search(stripped) for pattern in _JD_MARKERS)
    if has_marker and len(words) > _MARKER_LENGTH_THRESHOLD:
        return True

    return len(words) > _LENGTH_THRESHOLD


async def handle_text(update: Update, context: BotContext) -> None:
    """Send a plain text message to the scorer or the assistant."""
    message = update.effective_message
    if message is None or not message.text:  # pragma: no cover
        return

    state = (context.user_data or {}).get(SessionKey.STATE)
    is_jd = looks_like_job_description(message.text)

    if state == STATE_AWAITING_JD:
        # A resume was just uploaded. Treat the reply as the posting unless it is
        # plainly a question — users often ask something before pasting the JD.
        if is_jd or not _reads_as_question(message.text):
            await handle_job_description(update, context)
        else:
            await handle_question(update, context)
        return

    if is_jd:
        await handle_job_description(update, context)
    else:
        await handle_question(update, context)


def _reads_as_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    words = stripped.split()
    if not words:
        return False
    return words[0].lower().strip(".,!?\"'") in _QUESTION_OPENERS


async def handle_callback(update: Update, context: BotContext) -> None:
    """Dispatch an inline-keyboard press.

    The callback query is acknowledged first and unconditionally: Telegram shows a
    spinner on the button until it is, so an unhandled value would leave the
    button looking permanently stuck.
    """
    query = update.callback_query
    if query is None:  # pragma: no cover - filtered upstream
        return

    try:
        await query.answer()
    except TelegramError as exc:
        # A query older than ~15 minutes can no longer be answered; the button
        # press is still worth handling.
        logger.debug("Could not acknowledge callback query: %s", exc)

    action = _CALLBACK_ACTIONS.get(query.data or "")
    if action is None:
        logger.warning("Unknown callback data: %r", query.data)
        if update.effective_message:
            await safe_reply(
                update.effective_message,
                "That button came from an older version of the bot. Send /start for a "
                "fresh menu.",
            )
        return

    await action(update, context)


async def _show_question_prompt(update: Update, context: BotContext) -> None:
    """Explain what the free-form assistant can be asked."""
    message = update.effective_message
    if message is None:  # pragma: no cover
        return
    await safe_reply(
        message,
        f"💬 {bold('Ask me anything')}\n\n"
        "Type your question and send it. For example:\n"
        "• How do I explain a two-year career gap?\n"
        "• What should my professional summary say?\n"
        "• Is a two-column resume safe for an ATS?\n"
        "• How do I answer a salary expectations question?\n\n"
        "If you have uploaded a resume, I can answer about that too — "
        '"which of my bullets are weakest?"',
    )


#: callback_data value -> handler. Defined last so every handler already exists.
_CALLBACK_ACTIONS: Final[dict[str, Callable[[Update, BotContext], Awaitable[None]]]] = {
    CB_LATEST_SCORE: handle_latest_score,
    CB_COMPARE: handle_compare,
    CB_HISTORY: handle_history,
    CB_HELP: handle_help,
    CB_TIPS: _show_question_prompt,
}
