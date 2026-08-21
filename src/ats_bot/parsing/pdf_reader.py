"""PDF text extraction via pdfplumber."""

from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

from ats_bot.errors import ParsingError
from ats_bot.parsing.cleaner import clean_text

__all__ = ["MAX_PAGES", "extract_text_from_pdf"]

logger = logging.getLogger(__name__)

#: Resumes are a handful of pages; the cap bounds work on a hostile or huge upload.
MAX_PAGES = 30


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract text from a PDF.

    Args:
        file_path: Path to the PDF file.

    Returns:
        The cleaned text content. An empty string means the PDF parsed fine but
        holds no extractable text — almost always a scan, where the pages are
        images and OCR is required instead.

    Raises:
        ParsingError: If the file is missing, encrypted, or not a readable PDF.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ParsingError(f"PDF file not found: {path.name}")

    pages: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                logger.warning(
                    "PDF %s has %d pages; reading the first %d.",
                    path.name,
                    len(pdf.pages),
                    MAX_PAGES,
                )
            for page in pdf.pages[:MAX_PAGES]:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text)
    except Exception as exc:  # pdfplumber/pdfminer raise a wide range of types
        message = str(exc).lower()
        if "password" in message or "encrypt" in message:
            raise ParsingError(
                "This PDF is password protected. Please remove the password and re-upload."
            ) from exc
        logger.exception("Failed to parse PDF %s", path.name)
        raise ParsingError("This PDF could not be read. It may be corrupted.") from exc

    return clean_text("\n".join(pages))
