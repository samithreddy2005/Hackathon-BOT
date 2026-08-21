#!/usr/bin/env python
"""Convenience launcher so ``python bot.py`` keeps working.

The application itself lives in ``src/ats_bot``. Installing the project
(``pip install -e .``) provides the same entry point as the ``ats-bot`` command,
which is what a deployment should use; this script only adds ``src`` to the import
path so the bot also runs straight from a checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ats_bot.__main__ import main  # noqa: E402  (path must be set up first)

if __name__ == "__main__":
    raise SystemExit(main())
