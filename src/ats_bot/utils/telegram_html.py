"""Safe message rendering for Telegram.

The bot renders every message with ``parse_mode="HTML"`` rather than Markdown.
Telegram's legacy Markdown has no escape mechanism that survives arbitrary user
content: a resume filename containing ``_``, or a skill such as ``c++`` or
``.net`` landing next to an asterisk, produces an unbalanced entity and the API
rejects the whole message with ``Can't parse entities``. HTML has exactly three
characters to escape, so :func:`esc` makes any string safe.

Two other Telegram limits are handled here:

* messages are capped at 4096 characters, so :func:`chunk` splits long reports on
  line boundaries instead of letting the API reject them;
* if a message still fails to parse for any reason, :func:`safe_reply` retries
  once as plain text rather than dropping the user's answer on the floor.
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from telegram import Message
from telegram.error import BadRequest, TelegramError

__all__ = [
    "MAX_MESSAGE_LENGTH",
    "bold",
    "bullet_list",
    "chunk",
    "code",
    "esc",
    "italic",
    "markdown_to_html",
    "progress_bar",
    "safe_edit",
    "safe_reply",
]

logger = logging.getLogger(__name__)

#: Telegram's hard limit for a single text message.
MAX_MESSAGE_LENGTH = 4096

#: Leave headroom so a chunk suffix ("… (2/3)") always fits.
_CHUNK_BUDGET = MAX_MESSAGE_LENGTH - 64


def esc(value: object) -> str:
    """Escape a value for inclusion in an HTML-formatted Telegram message.

    >>> esc("Résumé <final> & _v2_")
    'Résumé &lt;final&gt; &amp; _v2_'
    """
    return html.escape(str(value), quote=False)


def bold(value: object) -> str:
    """Escaped bold text."""
    return f"<b>{esc(value)}</b>"


def italic(value: object) -> str:
    """Escaped italic text."""
    return f"<i>{esc(value)}</i>"


def code(value: object) -> str:
    """Escaped inline code."""
    return f"<code>{esc(value)}</code>"


def bullet_list(items: Iterable[object], *, marker: str = "•", formatter: Any = esc) -> str:
    """Render an iterable as an escaped bullet list, one item per line."""
    return "\n".join(f"{marker} {formatter(item)}" for item in items)


def progress_bar(score: float, *, width: int = 10, filled: str = "▰", empty: str = "▱") -> str:
    """Render a 0-100 score as a fixed-width bar.

    >>> progress_bar(70, width=10)
    '▰▰▰▰▰▰▰▱▱▱'
    >>> progress_bar(-5)
    '▱▱▱▱▱▱▱▱▱▱'
    """
    ratio = min(max(score, 0.0), 100.0) / 100.0
    blocks = round(ratio * width)
    return filled * blocks + empty * (width - blocks)


def chunk(text: str, *, limit: int = _CHUNK_BUDGET) -> list[str]:
    """Split ``text`` into message-sized pieces, preferring line boundaries.

    A single line longer than ``limit`` is hard-split, since there is no better
    option. Chunk boundaries never fall inside a line, which keeps HTML tags —
    all of which this module emits within a single line — balanced.

    >>> chunk("a\\nb", limit=100)
    ['a\\nb']
    >>> [len(part) for part in chunk("x" * 250, limit=100)]
    [100, 100, 50]
    """
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in _split_long_lines(text.split("\n"), limit):
        # +1 for the newline that will rejoin this line to the previous one.
        addition = len(line) + (1 if current else 0)
        if current_len + addition > limit:
            parts.append("\n".join(current))
            current, current_len = [line], len(line)
        else:
            current.append(line)
            current_len += addition

    if current:
        parts.append("\n".join(current))
    return parts


def _split_long_lines(lines: Sequence[str], limit: int) -> Iterator[str]:
    for line in lines:
        if len(line) <= limit:
            yield line
        else:
            for start in range(0, len(line), limit):
                yield line[start : start + limit]


async def safe_reply(message: Message, text: str, **kwargs: Any) -> None:
    """Reply with HTML formatting, degrading gracefully instead of raising.

    Long messages are split across several replies. If Telegram rejects the HTML
    (which should not happen now that all dynamic content is escaped, but would
    otherwise lose the user's answer entirely), the text is re-sent unformatted
    with the tags stripped.
    """
    kwargs.setdefault("parse_mode", "HTML")
    kwargs.setdefault("disable_web_page_preview", True)
    reply_markup = kwargs.pop("reply_markup", None)

    parts = chunk(text)
    for index, part in enumerate(parts):
        # Attach any keyboard to the final part so it appears under the full report.
        extra = dict(kwargs)
        if reply_markup is not None and index == len(parts) - 1:
            extra["reply_markup"] = reply_markup
        try:
            await message.reply_text(part, **extra)
        except BadRequest as exc:
            logger.warning("HTML reply rejected (%s); retrying as plain text.", exc)
            plain = dict(extra)
            plain.pop("parse_mode", None)
            try:
                await message.reply_text(_strip_tags(part), **plain)
            except TelegramError:
                logger.exception("Plain-text fallback also failed; message dropped.")
        except TelegramError:
            logger.exception("Failed to deliver message part %d/%d.", index + 1, len(parts))


async def safe_edit(message: Message, text: str, **kwargs: Any) -> None:
    """Edit a message in place, falling back to plain text and tolerating no-ops.

    If the rendered text exceeds one message, the first chunk replaces the edited
    message and the remainder is dropped; callers with long output should use
    :func:`safe_reply` instead.
    """
    kwargs.setdefault("parse_mode", "HTML")
    kwargs.setdefault("disable_web_page_preview", True)
    body = chunk(text)[0]
    try:
        await message.edit_text(body, **kwargs)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return  # editing to identical text is not an error worth surfacing
        logger.warning("HTML edit rejected (%s); retrying as plain text.", exc)
        plain = dict(kwargs)
        plain.pop("parse_mode", None)
        try:
            await message.edit_text(_strip_tags(body), **plain)
        except TelegramError:
            logger.exception("Plain-text edit fallback also failed.")
    except TelegramError:
        logger.exception("Failed to edit message.")


#: Inline Markdown that language models emit, in the order it must be converted:
#: fenced code before inline code, and bold before italic (``**`` before ``*``).
_MARKDOWN_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL), r"<pre>\1</pre>"),
    (re.compile(r"`([^`\n]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*\*(.+?)\*\*\*", re.DOTALL), r"<b><i>\1</i></b>"),
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"<b>\1</b>"),
    (re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])"), r"<i>\1</i>"),
    (re.compile(r"(?<![\w_])__(?!\s)(.+?)(?<!\s)__(?![\w_])", re.DOTALL), r"<b>\1</b>"),
    (re.compile(r"(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])"), r"<i>\1</i>"),
    (re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE), r"<b>\1</b>"),
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), "• "),
)


def markdown_to_html(text: str) -> str:
    """Convert the Markdown a language model emits into Telegram-safe HTML.

    The text is escaped first, so any HTML the model produced is rendered as
    literal characters rather than markup — the model's output is untrusted input,
    and letting it inject tags would break message parsing at best.

    >>> markdown_to_html("Use **bold** and `code` <here>")
    'Use <b>bold</b> and <code>code</code> &lt;here&gt;'
    """
    result = esc(text)
    for pattern, replacement in _MARKDOWN_RULES:
        result = pattern.sub(replacement, result)
    return result


def _strip_tags(text: str) -> str:
    """Remove the small set of tags this module emits and unescape entities."""
    for tag in ("b", "i", "u", "s", "code", "pre"):
        text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return html.unescape(text)
