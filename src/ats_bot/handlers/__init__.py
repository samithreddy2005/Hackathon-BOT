"""Telegram handlers and their registration.

Handlers are deliberately thin: they validate input, call into ``services``/``ats``,
and render the result. Business logic lives below this layer so it can be tested
without a Telegram connection.
"""

from __future__ import annotations

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from ats_bot.handlers.compare import handle_compare
from ats_bot.handlers.errors import handle_error
from ats_bot.handlers.history import handle_history
from ats_bot.handlers.router import handle_callback, handle_text
from ats_bot.handlers.session import handle_forget_me, handle_newchat
from ats_bot.handlers.start import handle_about, handle_help, handle_start
from ats_bot.handlers.upload import handle_resume_upload

__all__ = ["BOT_COMMANDS", "register_handlers"]

#: The command list published to Telegram's menu button.
BOT_COMMANDS: tuple[BotCommand, ...] = (
    BotCommand("start", "Main menu and how to begin"),
    BotCommand("help", "How scoring works"),
    BotCommand("compare", "Compare your two latest resumes"),
    BotCommand("history", "Your past scores"),
    BotCommand("newchat", "Clear the current session"),
    BotCommand("forgetme", "Delete all of your stored data"),
    BotCommand("about", "Version and status"),
)


def register_handlers(application: Application) -> None:
    """Attach every handler to ``application``, in dispatch order.

    Order matters: commands are matched before free text, and documents/photos
    before the catch-all text handler.
    """
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("about", handle_about))
    application.add_handler(CommandHandler("compare", handle_compare))
    application.add_handler(CommandHandler("history", handle_history))
    application.add_handler(CommandHandler(["newchat", "reset"], handle_newchat))
    application.add_handler(CommandHandler("forgetme", handle_forget_me))

    application.add_handler(CallbackQueryHandler(handle_callback))

    application.add_handler(
        MessageHandler(filters.Document.ALL | filters.PHOTO, handle_resume_upload)
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.add_error_handler(handle_error)
