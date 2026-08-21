"""Message rendering: escaping, chunking, Markdown conversion, and fallbacks."""

from __future__ import annotations

from typing import Any

import pytest
from telegram.error import BadRequest, TelegramError

from ats_bot.utils.telegram_html import (
    MAX_MESSAGE_LENGTH,
    bold,
    bullet_list,
    chunk,
    code,
    esc,
    italic,
    markdown_to_html,
    progress_bar,
    safe_edit,
    safe_reply,
)


class TestEscaping:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("plain", "plain"),
            ("a & b", "a &amp; b"),
            ("<script>", "&lt;script&gt;"),
            ("Resume_v2_final.pdf", "Resume_v2_final.pdf"),
            ("c++ & .NET", "c++ &amp; .NET"),
            ("100%", "100%"),
        ],
    )
    def test_esc(self, raw: str, expected: str) -> None:
        assert esc(raw) == expected

    def test_escapes_non_strings(self) -> None:
        assert esc(42) == "42"

    def test_wrappers_escape_their_content(self) -> None:
        assert bold("a<b") == "<b>a&lt;b</b>"
        assert italic("a&b") == "<i>a&amp;b</i>"
        assert code("<x>") == "<code>&lt;x&gt;</code>"

    def test_markdown_special_characters_survive(self) -> None:
        """The whole point of HTML mode: underscores and asterisks are literal."""
        assert esc("my_resume_*final*.pdf") == "my_resume_*final*.pdf"


class TestBulletList:
    def test_escapes_items(self) -> None:
        assert bullet_list(["a<b", "c"]) == "• a&lt;b\n• c"

    def test_empty(self) -> None:
        assert bullet_list([]) == ""


class TestProgressBar:
    @pytest.mark.parametrize("score", [0, 25, 50, 75, 100, -10, 150])
    def test_always_the_requested_width(self, score: float) -> None:
        assert len(progress_bar(score, width=10)) == 10

    def test_endpoints(self) -> None:
        assert progress_bar(0, width=4) == "▱▱▱▱"
        assert progress_bar(100, width=4) == "▰▰▰▰"


class TestChunk:
    def test_short_text_is_one_piece(self) -> None:
        assert chunk("hello") == ["hello"]

    def test_splits_on_line_boundaries(self) -> None:
        text = "\n".join(["x" * 40] * 10)
        parts = chunk(text, limit=100)
        assert len(parts) > 1
        assert all(len(part) <= 100 for part in parts)
        assert "\n".join(parts).replace("\n", "") == text.replace("\n", "")

    def test_hard_splits_a_single_long_line(self) -> None:
        parts = chunk("y" * 250, limit=100)
        assert [len(part) for part in parts] == [100, 100, 50]

    def test_respects_the_telegram_limit_by_default(self) -> None:
        assert all(len(part) <= MAX_MESSAGE_LENGTH for part in chunk("z" * 20_000))

    def test_no_content_is_lost(self) -> None:
        text = "\n".join(f"line {index}" for index in range(500))
        assert "\n".join(chunk(text, limit=120)) == text


class _Recorder:
    """A message double that can be told to reject HTML."""

    def __init__(self, *, reject_html: bool = False, error: Exception | None = None) -> None:
        self.reject_html = reject_html
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def reply_text(self, text: str, **kwargs: Any) -> None:
        self._record(text, kwargs)

    async def edit_text(self, text: str, **kwargs: Any) -> None:
        self._record(text, kwargs)

    def _record(self, text: str, kwargs: dict[str, Any]) -> None:
        self.calls.append((text, kwargs))
        if self.error is not None:
            raise self.error
        if self.reject_html and kwargs.get("parse_mode") == "HTML":
            raise BadRequest("Can't parse entities")

    @property
    def texts(self) -> list[str]:
        return [text for text, _ in self.calls]


class TestSafeReply:
    async def test_sends_html_by_default(self) -> None:
        recorder = _Recorder()
        await safe_reply(recorder, bold("hi"))  # type: ignore[arg-type]
        assert recorder.calls[0][1]["parse_mode"] == "HTML"

    async def test_splits_long_messages(self) -> None:
        recorder = _Recorder()
        await safe_reply(recorder, "\n".join(["line"] * 3000))  # type: ignore[arg-type]
        assert len(recorder.calls) > 1

    async def test_keyboard_goes_on_the_last_part_only(self) -> None:
        recorder = _Recorder()
        await safe_reply(
            recorder,  # type: ignore[arg-type]
            "\n".join(["line"] * 3000),
            reply_markup="KEYBOARD",
        )
        markups = [kwargs.get("reply_markup") for _, kwargs in recorder.calls]
        assert markups[-1] == "KEYBOARD"
        assert all(markup is None for markup in markups[:-1])

    async def test_falls_back_to_plain_text(self) -> None:
        recorder = _Recorder(reject_html=True)
        await safe_reply(recorder, f"See {bold('this')} & that")  # type: ignore[arg-type]

        assert len(recorder.calls) == 2
        fallback_text, fallback_kwargs = recorder.calls[1]
        assert "parse_mode" not in fallback_kwargs
        assert fallback_text == "See this & that"

    async def test_a_transport_failure_is_swallowed(self) -> None:
        recorder = _Recorder(error=TelegramError("network down"))
        await safe_reply(recorder, "anything")  # type: ignore[arg-type]  # must not raise


class TestSafeEdit:
    async def test_edits_with_html(self) -> None:
        recorder = _Recorder()
        await safe_edit(recorder, bold("done"))  # type: ignore[arg-type]
        assert recorder.calls[0][1]["parse_mode"] == "HTML"

    async def test_not_modified_is_ignored(self) -> None:
        recorder = _Recorder(error=BadRequest("Message is not modified"))
        await safe_edit(recorder, "same")  # type: ignore[arg-type]
        assert len(recorder.calls) == 1  # no fallback attempt

    async def test_falls_back_to_plain_text(self) -> None:
        recorder = _Recorder(reject_html=True)
        await safe_edit(recorder, bold("x"))  # type: ignore[arg-type]
        assert recorder.texts[-1] == "x"


class TestMarkdownToHtml:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("**bold**", "<b>bold</b>"),
            ("__bold__", "<b>bold</b>"),
            ("*italic*", "<i>italic</i>"),
            ("_italic_", "<i>italic</i>"),
            ("`code`", "<code>code</code>"),
            ("***both***", "<b><i>both</i></b>"),
            ("## Heading", "<b>Heading</b>"),
            ("- item", "• item"),
            ("* item", "• item"),
        ],
    )
    def test_conversions(self, raw: str, expected: str) -> None:
        assert markdown_to_html(raw) == expected

    def test_model_output_cannot_inject_tags(self) -> None:
        assert markdown_to_html("<b>injected</b>") == "&lt;b&gt;injected&lt;/b&gt;"

    def test_snake_case_is_not_italicised(self) -> None:
        assert markdown_to_html("call my_function_name here") == "call my_function_name here"

    def test_fenced_code_blocks(self) -> None:
        assert markdown_to_html("```python\nx = 1\n```") == "<pre>x = 1\n</pre>"

    def test_plain_text_is_unchanged(self) -> None:
        assert markdown_to_html("just words") == "just words"
