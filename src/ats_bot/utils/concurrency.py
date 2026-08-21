"""Helpers for keeping blocking work off the event loop.

Telegram handlers are coroutines running on a single event loop. Any synchronous
call that touches the disk, the network, or a CPU-heavy parser will stall *every*
user's conversation for its duration, so all of it goes through
:func:`run_blocking`.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

__all__ = ["run_blocking"]

_P = ParamSpec("_P")
_R = TypeVar("_R")


async def run_blocking(func: Callable[_P, _R], /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
    """Run a blocking callable in the default thread pool and await its result.

    Example:
        >>> import asyncio
        >>> asyncio.run(run_blocking(sum, [1, 2, 3]))
        6
    """
    return await asyncio.to_thread(functools.partial(func, *args, **kwargs))
