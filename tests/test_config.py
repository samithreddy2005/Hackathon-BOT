"""Settings resolution and validation."""

from __future__ import annotations

import pytest

from ats_bot.config import PROJECT_ROOT, Settings
from ats_bot.errors import ConfigurationError

VALID_TOKEN = "123456789:AAHf-abcdefghijklmnopqrstuvwxyz0123456"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every variable Settings reads so tests start from a blank slate."""
    for name in (
        "BOT_TOKEN",
        "DATABASE_PATH",
        "UPLOAD_DIR",
        "LOG_DIR",
        "LOG_LEVEL",
        "LOG_TO_FILE",
        "GROQ_API_KEY",
        "GROK_API_KEY",
        "GROQ_MODEL",
        "MAX_UPLOAD_MB",
        "UPLOAD_RETENTION_HOURS",
        "MIN_RESUME_WORDS",
    ):
        monkeypatch.delenv(name, raising=False)


class TestTokenValidation:
    def test_missing_token_is_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="BOT_TOKEN is not set"):
            Settings.from_env(load_dotenv_file=False)

    def test_placeholder_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
        with pytest.raises(ConfigurationError, match="does not look like"):
            Settings.from_env(load_dotenv_file=False)

    def test_malformed_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", "no-colon-here")
        with pytest.raises(ConfigurationError):
            Settings.from_env(load_dotenv_file=False)

    def test_valid_token_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        assert Settings.from_env(load_dotenv_file=False).bot_token == VALID_TOKEN

    def test_token_can_be_waived(self) -> None:
        settings = Settings.from_env(require_token=False, load_dotenv_file=False)
        assert settings.bot_token == ""


class TestPaths:
    def test_relative_paths_resolve_against_the_project_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("DATABASE_PATH", "data/bot.db")
        settings = Settings.from_env(load_dotenv_file=False)
        assert settings.database_path == PROJECT_ROOT / "data" / "bot.db"

    def test_absolute_paths_are_left_alone(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        target = tmp_path / "elsewhere.db"
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("DATABASE_PATH", str(target))
        assert Settings.from_env(load_dotenv_file=False).database_path == target

    def test_ensure_directories_creates_all_of_them(self, settings: Settings) -> None:
        settings.ensure_directories()
        assert settings.database_path.parent.is_dir()
        assert settings.upload_dir.is_dir()
        assert settings.log_dir.is_dir()


class TestOtherValues:
    def test_invalid_log_level_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("LOG_LEVEL", "CHATTY")
        with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
            Settings.from_env(load_dotenv_file=False)

    def test_non_numeric_upload_limit_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("MAX_UPLOAD_MB", "big")
        with pytest.raises(ConfigurationError, match="MAX_UPLOAD_MB"):
            Settings.from_env(load_dotenv_file=False)

    def test_upload_limit_is_converted_to_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("MAX_UPLOAD_MB", "5")
        assert Settings.from_env(load_dotenv_file=False).max_upload_bytes == 5 * 1024 * 1024

    def test_legacy_grok_key_is_still_honoured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("GROK_API_KEY", "gsk_legacy_value")
        settings = Settings.from_env(load_dotenv_file=False)
        assert settings.groq_api_key == "gsk_legacy_value"
        assert settings.llm_enabled

    def test_placeholder_api_key_disables_the_assistant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOT_TOKEN", VALID_TOKEN)
        monkeypatch.setenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
        assert not Settings.from_env(load_dotenv_file=False).llm_enabled

    def test_settings_are_immutable(self, settings: Settings) -> None:
        with pytest.raises(AttributeError):
            settings.bot_token = "changed"  # type: ignore[misc]
