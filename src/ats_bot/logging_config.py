"""Central logging configuration.

Configured exactly once, from the application entry point. Library loggers that are
chatty at INFO (``httpx`` logs every Telegram poll) are turned down so the bot's own
messages stay readable.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys

from ats_bot.config import Settings

__all__ = ["configure_logging"]

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Third-party loggers that are too verbose at INFO level.
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "telegram.ext.Updater",
    "groq._base_client",
    "pdfminer",
    "apscheduler",
)

_configured = False


def configure_logging(settings: Settings, *, force: bool = False) -> None:
    """Install console (and optionally rotating-file) handlers on the root logger.

    Calling this more than once is a no-op unless ``force`` is set, which keeps
    module-level imports from clobbering an already-configured application.
    """
    global _configured
    if _configured and not force:
        return

    level = getattr(logging, settings.log_level, logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if settings.log_to_file:
        try:
            settings.log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                settings.log_dir / "ats_bot.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:  # read-only volume, permissions, ...
            root.warning("File logging disabled (%s); continuing with console only.", exc)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))

    _configured = True
