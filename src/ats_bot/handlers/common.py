"""Shared handler plumbing: session keys, keyboards, and context accessors.

``context.bot_data`` carries the process-wide singletons (settings, FAQ index, LLM
assistant) that :func:`ats_bot.app.build_application` installs at start-up, so
handlers never reach for module-level globals and tests can inject fakes.
"""

from __future__ import annotations

from typing import Any, Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ats_bot.config import Settings
from ats_bot.services.faq import FaqIndex
from ats_bot.services.llm import LlmAssistant

__all__ = [
    "CB_COMPARE",
    "CB_HELP",
    "CB_HISTORY",
    "CB_LATEST_SCORE",
    "CB_TIPS",
    "STATE_AWAITING_JD",
    "BotContext",
    "SessionKey",
    "clear_session",
    "get_faq_index",
    "get_llm",
    "get_settings_from",
    "main_menu",
    "post_report_menu",
]

BotContext = ContextTypes.DEFAULT_TYPE

# --- bot_data keys (set once at start-up) ----------------------------------

KEY_SETTINGS: Final = "settings"
KEY_FAQ_INDEX: Final = "faq_index"
KEY_LLM: Final = "llm"


# --- user_data keys (per conversation) -------------------------------------


class SessionKey:
    """Namespaced keys for ``context.user_data``."""

    STATE: Final = "state"
    #: Resumes uploaded since the last evaluation, all scored against the next JD.
    PENDING_RESUME_IDS: Final = "pending_resume_ids"
    LAST_RESUME_ID: Final = "last_resume_id"
    ACTIVE_JD_ID: Final = "active_jd_id"
    #: Set by /newchat so the assistant stops using the previous documents.
    SESSION_CLEARED: Final = "session_cleared"


STATE_AWAITING_JD: Final = "awaiting_jd"

# --- callback_data values --------------------------------------------------

CB_LATEST_SCORE: Final = "menu:latest_score"
CB_COMPARE: Final = "menu:compare"
CB_HISTORY: Final = "menu:history"
CB_HELP: Final = "menu:help"
CB_TIPS: Final = "menu:tips"


def get_settings_from(context: BotContext) -> Settings:
    """The application settings installed at start-up."""
    settings = (context.bot_data or {}).get(KEY_SETTINGS)
    if not isinstance(settings, Settings):  # pragma: no cover - wiring guard
        raise RuntimeError("Settings are missing from bot_data; build_application was bypassed.")
    return settings


def get_faq_index(context: BotContext) -> FaqIndex:
    index = (context.bot_data or {}).get(KEY_FAQ_INDEX)
    if not isinstance(index, FaqIndex):  # pragma: no cover - wiring guard
        raise RuntimeError("FAQ index is missing from bot_data.")
    return index


def get_llm(context: BotContext) -> LlmAssistant | None:
    """The LLM assistant, or None when the feature is not configured."""
    assistant = (context.bot_data or {}).get(KEY_LLM)
    return assistant if isinstance(assistant, LlmAssistant) else None


def clear_session(context: BotContext) -> None:
    """Forget the active documents and conversation state."""
    if context.user_data is None:  # pragma: no cover - PTB always provides it
        return
    context.user_data.clear()
    context.user_data[SessionKey.SESSION_CLEARED] = True


def user_id_of(update: Update) -> int:
    """The Telegram user id behind an update, whatever kind it is.

    Raises:
        ValueError: If the update carries no user, which the handlers' filters
            already exclude but the type checker cannot know.
    """
    user = update.effective_user
    if user is None:  # pragma: no cover - filtered upstream
        raise ValueError("Update has no effective user")
    return user.id


def main_menu() -> InlineKeyboardMarkup:
    """The keyboard shown by /start."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Latest score", callback_data=CB_LATEST_SCORE),
                InlineKeyboardButton("🔄 Compare versions", callback_data=CB_COMPARE),
            ],
            [
                InlineKeyboardButton("📜 History", callback_data=CB_HISTORY),
                InlineKeyboardButton("💬 Ask a question", callback_data=CB_TIPS),
            ],
            [InlineKeyboardButton("❓ How this works", callback_data=CB_HELP)],
        ]
    )


def post_report_menu() -> InlineKeyboardMarkup:
    """The keyboard attached under a freshly generated report."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📜 History", callback_data=CB_HISTORY),
                InlineKeyboardButton("🔄 Compare versions", callback_data=CB_COMPARE),
            ]
        ]
    )


def bot_data_defaults(
    settings: Settings, faq_index: FaqIndex, llm: LlmAssistant | None
) -> dict[str, Any]:
    """The ``bot_data`` payload installed by :func:`ats_bot.app.build_application`."""
    return {KEY_SETTINGS: settings, KEY_FAQ_INDEX: faq_index, KEY_LLM: llm}
