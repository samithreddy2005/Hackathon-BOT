"""Shared fixtures.

Every test runs against a throwaway SQLite database and upload directory under
``tmp_path``. The autouse ``_isolated_settings`` fixture redirects the modules that
resolve settings lazily, so production code paths that call ``get_settings()``
never touch the developer's real database or ``.env``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ats_bot.config import Settings
from ats_bot.db.connection import init_db

TEST_TOKEN = "123456789:TESTTOKENvalue_that_is_long_enough_here"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointing entirely at ``tmp_path``."""
    built = Settings(
        bot_token=TEST_TOKEN,
        database_path=tmp_path / "db" / "test.db",
        upload_dir=tmp_path / "uploads",
        log_dir=tmp_path / "logs",
        log_to_file=False,
    )
    built.ensure_directories()
    return built


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Iterator[None]:
    """Point every lazy ``get_settings()`` lookup at the test settings."""
    for module in ("ats_bot.config", "ats_bot.db.connection"):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings, raising=True)
    yield


@pytest.fixture
def db(settings: Settings) -> Settings:
    """An initialised, empty database. Returns the settings that address it."""
    init_db(settings)
    return settings


# ---------------------------------------------------------------------------
# Sample documents
# ---------------------------------------------------------------------------

RESUME_TEXT = """\
Jane Doe
jane.doe@example.com | +1 (555) 123-4567 | linkedin.com/in/janedoe

PROFESSIONAL SUMMARY
Backend engineer with 6 years building payment systems.

TECHNICAL SKILLS
Python, Django, PostgreSQL, Docker, AWS, Git, REST API

WORK EXPERIENCE
Senior Backend Engineer - Acme Payments - Jan 2021 to Present
- Cut checkout latency by 40% by introducing a Redis read-through cache.
- Migrated 12 services to Docker, reducing deploy time from 2 hours to 15 minutes.
- Mentored 4 engineers through the team's first on-call rotation.

Backend Engineer - Initech - Jun 2018 to Dec 2020
- Built a Django billing service handling 30000 transactions per day.
- Reduced database costs by $80000 annually through query optimisation.

EDUCATION
B.Sc. Computer Science, State University, 2018

PROJECTS
Ledger CLI - an open-source double-entry bookkeeping tool in Python.

CERTIFICATIONS
AWS Certified Solutions Architect, 2022
"""

JD_TEXT = """\
Senior Backend Engineer

About the role
We are looking for a senior backend engineer to own our payments platform.

Responsibilities
- Design and operate high-throughput services.
- Mentor other engineers on the team.

Requirements
- 5+ years of experience with Python and Django.
- Strong PostgreSQL and Kubernetes knowledge.
- Experience with Docker, AWS, and CI/CD pipelines.
- A bachelor's degree in a technical field.
"""

WEAK_RESUME_TEXT = """\
John Smith

EXPERIENCE
I worked at a company. I did some tasks. I helped the team.

EDUCATION
I studied things.

SKILLS
Communication
"""


@pytest.fixture
def resume_text() -> str:
    return RESUME_TEXT


@pytest.fixture
def jd_text() -> str:
    return JD_TEXT


# ---------------------------------------------------------------------------
# Telegram doubles
# ---------------------------------------------------------------------------


class FakeMessage:
    """A stand-in for ``telegram.Message`` that records what was sent.

    Handlers only ever call ``reply_text``/``edit_text``/``delete``, so a duck-typed
    double is enough and avoids constructing a Bot.
    """

    def __init__(self, text: str = "", chat_id: int = 1) -> None:
        self.text = text
        self.chat_id = chat_id
        self.chat = None
        self.document = None
        self.photo: list[Any] = []
        self.replies: list[str] = []
        self.edits: list[str] = []
        self.deleted = False
        #: Messages produced by ``reply_text``. Handlers keep a reference to the
        #: status message they sent and later edit it, so the text a user actually
        #: sees lives on these children — ``all_output`` walks them.
        self.sent: list[FakeMessage] = []

    async def reply_text(self, text: str, **kwargs: Any) -> FakeMessage:
        self.replies.append(text)
        child = FakeMessage(text, self.chat_id)
        self.sent.append(child)
        return child

    async def edit_text(self, text: str, **kwargs: Any) -> FakeMessage:
        self.edits.append(text)
        self.text = text
        return self

    async def delete(self) -> bool:
        self.deleted = True
        return True

    @property
    def last_reply(self) -> str:
        assert self.replies, "no reply was sent"
        return self.replies[-1]

    @property
    def all_output(self) -> str:
        """Every piece of text this message and its descendants produced."""
        parts = [*self.replies, *self.edits]
        for child in self.sent:
            parts.extend(child.edits)
            for grandchild in child.sent:
                parts.append(grandchild.all_output)
        return "\n".join(parts)


class FakeUser:
    def __init__(self, user_id: int = 42, username: str = "tester") -> None:
        self.id = user_id
        self.username = username
        self.first_name = "Test"


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage, user: FakeUser) -> None:
        self.data = data
        self.message = message
        self.from_user = user
        self.answered = False

    async def answer(self, *args: Any, **kwargs: Any) -> bool:
        self.answered = True
        return True


class FakeUpdate:
    def __init__(
        self,
        message: FakeMessage | None = None,
        user: FakeUser | None = None,
        callback_query: FakeCallbackQuery | None = None,
    ) -> None:
        self.effective_message = message
        self.effective_user = user or FakeUser()
        self.callback_query = callback_query


class FakeContext:
    def __init__(self, bot_data: dict[str, Any] | None = None) -> None:
        self.user_data: dict[str, Any] = {}
        self.bot_data: dict[str, Any] = bot_data or {}
        self.chat_data: dict[str, Any] = {}
        self.error: BaseException | None = None


@pytest.fixture
def message() -> FakeMessage:
    return FakeMessage()


@pytest.fixture
def user() -> FakeUser:
    return FakeUser()


@pytest.fixture
def update(message: FakeMessage, user: FakeUser) -> FakeUpdate:
    return FakeUpdate(message=message, user=user)


@pytest.fixture
def context(settings: Settings) -> FakeContext:
    """A context carrying the same singletons ``build_application`` installs."""
    from ats_bot.handlers.common import bot_data_defaults
    from ats_bot.services.faq import default_index
    from ats_bot.services.llm import LlmAssistant

    return FakeContext(bot_data_defaults(settings, default_index(), LlmAssistant(settings)))
