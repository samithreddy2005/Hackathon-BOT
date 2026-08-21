"""Application wiring: everything a handler expects must be in place at start-up."""

from __future__ import annotations

import logging

import pytest

from ats_bot.app import build_application
from ats_bot.config import Settings
from ats_bot.handlers import BOT_COMMANDS
from ats_bot.handlers.common import get_faq_index, get_llm, get_settings_from
from ats_bot.logging_config import configure_logging


class TestBuildApplication:
    @pytest.fixture
    def application(self, settings: Settings):  # type: ignore[no-untyped-def]
        return build_application(settings)

    def test_creates_the_database(self, settings: Settings, application) -> None:  # type: ignore[no-untyped-def]
        assert settings.database_path.is_file()

    def test_registers_handlers_and_an_error_handler(self, application) -> None:  # type: ignore[no-untyped-def]
        assert application.handlers[0]
        assert application.error_handlers

    def test_installs_the_singletons_handlers_depend_on(
        self, settings: Settings, application
    ) -> None:  # type: ignore[no-untyped-def]
        class _Context:
            bot_data = application.bot_data
            user_data: dict[str, object] = {}

        context = _Context()
        assert get_settings_from(context) is settings  # type: ignore[arg-type]
        assert get_faq_index(context) is not None  # type: ignore[arg-type]
        assert get_llm(context) is not None  # type: ignore[arg-type]

    def test_command_menu_covers_the_registered_commands(self) -> None:
        published = {command.command for command in BOT_COMMANDS}
        assert {"start", "help", "compare", "history", "newchat", "forgetme", "about"} == published

    def test_command_descriptions_fit_telegram_limits(self) -> None:
        for command in BOT_COMMANDS:
            assert 1 <= len(command.command) <= 32
            assert 1 <= len(command.description) <= 256


class TestLogging:
    def test_console_only_when_file_logging_is_off(self, settings: Settings) -> None:
        configure_logging(settings, force=True)
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1

    def test_adds_a_rotating_file_handler_when_enabled(self, settings: Settings) -> None:
        with_file = Settings(
            bot_token=settings.bot_token,
            database_path=settings.database_path,
            upload_dir=settings.upload_dir,
            log_dir=settings.log_dir,
            log_to_file=True,
        )
        try:
            configure_logging(with_file, force=True)
            assert (with_file.log_dir / "ats_bot.log").exists()
        finally:
            # Release the file handle so tmp_path cleanup succeeds on Windows.
            configure_logging(settings, force=True)

    def test_respects_the_configured_level(self, settings: Settings) -> None:
        debug = Settings(
            bot_token=settings.bot_token,
            database_path=settings.database_path,
            upload_dir=settings.upload_dir,
            log_dir=settings.log_dir,
            log_level="DEBUG",
            log_to_file=False,
        )
        configure_logging(debug, force=True)
        assert logging.getLogger().level == logging.DEBUG
        configure_logging(settings, force=True)
