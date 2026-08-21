"""ATS Resume Analyzer — a Telegram bot that scores resumes against job descriptions.

The package is organised in layers, each of which depends only on the layers below it:

``handlers``  Telegram-facing controllers (thin; no business logic).
``services``  Cross-cutting application services (file intake, FAQ search, LLM).
``ats``       The scoring engine — pure functions over text, no I/O.
``parsing``   Document text extraction (PDF, DOCX, images) and normalisation.
``db``        SQLite persistence.
``config``    Environment-driven settings.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
