"""The application-wide error handler.

Without one, an exception inside a handler is logged by python-telegram-bot and
the user is left staring at a chat that simply stopped responding. This turns
every unhandled failure into an honest message plus a full traceback in the log.
"""

from __future__ import annotations

import logging

from telegram.error import Forbidden, NetworkError, RetryAfter, TelegramError

from ats_bot.errors import (
    ATSBotError,
    ConfigurationError,
    DatabaseError,
    ParsingError,
    UploadError,
)
from ats_bot.handlers.common import BotContext
from ats_bot.utils.telegram_html import bold, safe_reply

__all__ = ["handle_error"]

logger = logging.getLogger(__name__)

_GENERIC_MESSAGE = (
    f"⚠️ {bold('Something went wrong')}\n\n"
    "That request failed on our side. Please try again — and if it keeps happening, "
    "send /newchat to reset the session."
)

#: Errors the user can act on, mapped to what to tell them.
_USER_FACING: dict[type[Exception], str] = {
    DatabaseError: (
        f"⚠️ {bold('Storage is temporarily unavailable')}\n\n"
        "Your request could not be saved. Please try again in a moment."
    ),
    ParsingError: (
        f"⚠️ {bold('That document could not be read')}\n\n"
        "Please try a different file — a text-based PDF works best."
    ),
    UploadError: (f"⚠️ {bold('The upload did not complete')}\n\n" "Please send the file again."),
}


async def handle_error(update: object, context: BotContext) -> None:
    """Log the exception and, where possible, tell the user what happened."""
    error = context.error
    if error is None:  # pragma: no cover - PTB always sets it
        return

    if isinstance(error, Forbidden):
        # The user blocked the bot or deleted the chat; nothing to report and
        # nobody to report it to.
        logger.info("Update ignored — the bot is blocked by this user.")
        return

    if isinstance(error, RetryAfter):
        logger.warning("Rate limited by Telegram; retry after %ss.", error.retry_after)
        return

    if isinstance(error, NetworkError):
        logger.warning("Network error talking to Telegram: %s", error)
        return

    if isinstance(error, ConfigurationError):
        # Misconfiguration is an operator problem, and it will recur on every
        # update until it is fixed, so it is logged loudly.
        logger.critical("Configuration error while handling an update: %s", error)
    elif isinstance(error, ATSBotError):
        logger.error("Application error: %s", error, exc_info=error)
    else:
        logger.exception("Unhandled exception while processing an update.", exc_info=error)

    await _notify(update, error)


async def _notify(update: object, error: BaseException) -> None:
    """Best-effort user notification; never raises.

    ``update`` is typed as ``object`` because python-telegram-bot passes whatever
    was being processed, which is not always an :class:`~telegram.Update`.
    """
    message = getattr(update, "effective_message", None)
    if message is None:
        return

    text = _GENERIC_MESSAGE
    for error_type, advice in _USER_FACING.items():
        if isinstance(error, error_type):
            text = advice
            break

    try:
        await safe_reply(message, text)
    except TelegramError:
        logger.debug("Could not deliver the error notice to the user.", exc_info=True)
