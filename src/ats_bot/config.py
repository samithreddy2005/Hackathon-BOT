"""Environment-driven application settings.

Settings are resolved once at start-up into an immutable :class:`Settings` object,
which is then passed (or looked up via :func:`get_settings`) by the rest of the
application. Nothing else in the codebase reads ``os.environ`` directly, so tests
can build a ``Settings`` instance without touching the process environment.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from ats_bot.errors import ConfigurationError

__all__ = ["Settings", "get_settings", "reset_settings_cache"]

# A Telegram bot token looks like "123456789:AAE...".  Validating the shape up front
# turns a confusing runtime 401 into an actionable start-up message.
_TOKEN_PATTERN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

_VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: Repository root, derived from this file's location (src/ats_bot/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAX_UPLOAD_MB = 20
DEFAULT_UPLOAD_RETENTION_HOURS = 24


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env_str(name)
    if not raw:
        return default
    return raw.lower() in _TRUTHY


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}, got {value}")
    return value


def _resolve(path_str: str) -> Path:
    """Resolve a possibly-relative path against the project root."""
    path = Path(path_str).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application configuration."""

    bot_token: str
    database_path: Path
    upload_dir: Path
    log_dir: Path
    log_level: str = "INFO"
    log_to_file: bool = True
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: float = 20.0
    groq_max_tokens: int = 900
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_MB * 1024 * 1024
    upload_retention_hours: int = DEFAULT_UPLOAD_RETENTION_HOURS
    min_resume_words: int = 50
    _dirs_created: bool = field(default=False, repr=False, compare=False)

    @property
    def llm_enabled(self) -> bool:
        """True when an LLM key is configured and the optional SDK can be used."""
        return bool(self.groq_api_key)

    def ensure_directories(self) -> None:
        """Create the directories the application writes to."""
        for directory in (self.database_path.parent, self.upload_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, *, require_token: bool = True, load_dotenv_file: bool = True) -> Settings:
        """Build settings from environment variables (and a local ``.env`` file).

        Args:
            require_token: When True, a missing or malformed ``BOT_TOKEN`` raises
                :class:`~ats_bot.errors.ConfigurationError`. Tests and tooling that
                only need paths can pass False.
            load_dotenv_file: When True, load ``.env`` from the project root first.
                Real environment variables always take precedence over the file.

        Raises:
            ConfigurationError: If any value is missing or malformed.
        """
        if load_dotenv_file:
            load_dotenv(PROJECT_ROOT / ".env", override=False)

        token = _env_str("BOT_TOKEN")
        if require_token:
            if not token:
                raise ConfigurationError(
                    "BOT_TOKEN is not set. Copy .env.example to .env and add the token "
                    "issued by @BotFather on Telegram."
                )
            if not _TOKEN_PATTERN.match(token):
                raise ConfigurationError(
                    "BOT_TOKEN does not look like a Telegram bot token (expected "
                    "'<digits>:<secret>'). Check for a placeholder value or stray quotes."
                )

        log_level = _env_str("LOG_LEVEL", "INFO").upper() or "INFO"
        if log_level not in _VALID_LOG_LEVELS:
            raise ConfigurationError(
                f"LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}"
            )

        # GROK_API_KEY is accepted for backwards compatibility with older .env files.
        groq_key = _env_str("GROQ_API_KEY") or _env_str("GROK_API_KEY")
        if groq_key.upper().startswith("YOUR_"):  # placeholder left in .env
            groq_key = ""

        max_upload_mb = _env_int("MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)

        return cls(
            bot_token=token,
            database_path=_resolve(_env_str("DATABASE_PATH", "database/ats_bot.db")),
            upload_dir=_resolve(_env_str("UPLOAD_DIR", "uploads")),
            log_dir=_resolve(_env_str("LOG_DIR", "logs")),
            log_level=log_level,
            log_to_file=_env_bool("LOG_TO_FILE", True),
            groq_api_key=groq_key,
            groq_model=_env_str("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_timeout_seconds=float(_env_int("GROQ_TIMEOUT_SECONDS", 20)),
            groq_max_tokens=_env_int("GROQ_MAX_TOKENS", 900),
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            upload_retention_hours=_env_int(
                "UPLOAD_RETENTION_HOURS", DEFAULT_UPLOAD_RETENTION_HOURS
            ),
            min_resume_words=_env_int("MIN_RESUME_WORDS", 50),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, building them on first use."""
    return Settings.from_env()


def reset_settings_cache() -> None:
    """Clear the cached settings. Intended for tests."""
    get_settings.cache_clear()
