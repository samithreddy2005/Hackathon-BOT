"""Application assembly and the polling entry point."""

from __future__ import annotations

import datetime as dt
import logging

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from ats_bot.config import Settings, get_settings
from ats_bot.db.connection import init_db
from ats_bot.handlers import BOT_COMMANDS, register_handlers
from ats_bot.handlers.common import bot_data_defaults
from ats_bot.logging_config import configure_logging
from ats_bot.parsing import ocr_available
from ats_bot.services.faq import default_index
from ats_bot.services.files import purge_old_uploads
from ats_bot.services.llm import LlmAssistant
from ats_bot.utils.concurrency import run_blocking

__all__ = ["build_application", "run"]

logger = logging.getLogger(__name__)

#: How often stale uploads are swept, when a job queue is available.
_CLEANUP_INTERVAL = dt.timedelta(hours=6)


def build_application(settings: Settings | None = None) -> Application:
    """Construct a fully wired :class:`~telegram.ext.Application`.

    The database schema is created, singletons are placed in ``bot_data``, and all
    handlers are registered. The application is returned unstarted so callers
    decide how to run it.
    """
    resolved = settings or get_settings()
    resolved.ensure_directories()
    init_db(resolved)

    assistant = LlmAssistant(resolved)

    application = (
        ApplicationBuilder()
        .token(resolved.bot_token)
        .post_init(_on_start)
        .concurrent_updates(True)
        .build()
    )

    application.bot_data.update(bot_data_defaults(resolved, default_index(), assistant))
    register_handlers(application)
    _schedule_cleanup(application, resolved)

    logger.info(
        # Plain ASCII: Windows consoles default to a codepage that mangles dashes.
        "Application built. OCR %s; assistant: %s.",
        "available" if ocr_available() else "unavailable",
        assistant.status,
    )
    return application


async def _on_start(application: Application) -> None:
    """Publish the command menu once the bot is connected."""
    bot = await application.bot.get_me()
    logger.info("Connected as @%s (id=%s).", bot.username, bot.id)
    await application.bot.set_my_commands(BOT_COMMANDS)


def _schedule_cleanup(application: Application, settings: Settings) -> None:
    """Periodically delete uploads past their retention window.

    ``job_queue`` is None unless python-telegram-bot was installed with its
    ``job-queue`` extra, so this degrades to a single sweep at start-up.
    """
    if settings.upload_retention_hours <= 0:
        return

    purge_old_uploads(settings)

    job_queue = application.job_queue
    if job_queue is None:
        logger.info(
            "Job queue unavailable; old uploads were swept once at start-up. "
            "Install python-telegram-bot[job-queue] for periodic cleanup."
        )
        return

    async def _sweep(_: ContextTypes.DEFAULT_TYPE) -> None:
        await run_blocking(purge_old_uploads, settings)

    job_queue.run_repeating(_sweep, interval=_CLEANUP_INTERVAL, first=_CLEANUP_INTERVAL)


def run(settings: Settings | None = None) -> None:
    """Start the bot in long-polling mode and block until interrupted."""
    resolved = settings or get_settings()
    configure_logging(resolved)

    application = build_application(resolved)

    logger.info("Starting long polling. Press Ctrl+C to stop.")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        # Skip the backlog that accumulated while the bot was down: replaying
        # hours-old uploads would confuse users more than dropping them.
        drop_pending_updates=True,
    )
