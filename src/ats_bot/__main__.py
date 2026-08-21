"""Command-line entry point: ``python -m ats_bot`` or ``ats-bot``."""

from __future__ import annotations

import logging
import sys

from ats_bot.config import Settings
from ats_bot.errors import ATSBotError, ConfigurationError
from ats_bot.logging_config import configure_logging

__all__ = ["main"]

logger = logging.getLogger("ats_bot")

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_RUNTIME_ERROR = 1


def main() -> int:
    """Start the bot, returning a process exit code.

    Configuration problems exit with a distinct code and a single readable line
    rather than a traceback — the operator needs to know *what to set*, not where
    in the library the value was read.
    """
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    configure_logging(settings)

    # Imported after logging is configured so start-up messages are formatted.
    from ats_bot.app import run

    try:
        run(settings)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        logger.info("Stopped by user.")
        return EXIT_OK
    except ATSBotError as exc:
        logger.critical("%s", exc)
        return EXIT_RUNTIME_ERROR
    except Exception:
        logger.critical("The bot stopped because of an unexpected error.", exc_info=True)
        return EXIT_RUNTIME_ERROR

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
