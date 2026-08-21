"""Document parsing: turn an uploaded file into clean, comparable text."""

from __future__ import annotations

import logging
from pathlib import Path

from ats_bot.constants import SUPPORTED_EXTENSIONS
from ats_bot.errors import ParsingError, UnsupportedFileTypeError
from ats_bot.parsing.cleaner import (
    clean_text,
    extract_potential_keywords,
    focus_on_requirements,
    tokenize,
)
from ats_bot.parsing.docx_reader import extract_text_from_docx
from ats_bot.parsing.extractor import (
    count_quantified_achievements,
    detect_sections,
    extract_email,
    extract_links,
    extract_phone,
    looks_like_resume,
)
from ats_bot.parsing.image_reader import extract_text_from_image, ocr_available
from ats_bot.parsing.pdf_reader import extract_text_from_pdf

__all__ = [
    "ParsingError",
    "UnsupportedFileTypeError",
    "clean_text",
    "count_quantified_achievements",
    "describe_extraction_failure",
    "detect_sections",
    "document_kind",
    "extract_email",
    "extract_links",
    "extract_phone",
    "extract_potential_keywords",
    "extract_text",
    "extract_text_from_docx",
    "extract_text_from_image",
    "extract_text_from_pdf",
    "focus_on_requirements",
    "looks_like_resume",
    "ocr_available",
    "tokenize",
]

logger = logging.getLogger(__name__)


def document_kind(file_name: str) -> str:
    """Map a filename to the document kind this package can parse.

    >>> document_kind("Resume_v2.PDF")
    'pdf'
    >>> document_kind("scan.jpeg")
    'image'

    Raises:
        UnsupportedFileTypeError: If the extension is not supported.
    """
    extension = Path(file_name).suffix.lower()
    kind = SUPPORTED_EXTENSIONS.get(extension)
    if kind is None:
        raise UnsupportedFileTypeError(extension or "(none)")
    return kind


def extract_text(file_path: str | Path, kind: str | None = None) -> str:
    """Extract text from a document, dispatching on its kind.

    Args:
        file_path: Path to the downloaded file.
        kind: One of ``"pdf"``, ``"docx"``, ``"image"``. Inferred from the file
            extension when omitted.

    Raises:
        ParsingError: If the document cannot be read.
        UnsupportedFileTypeError: If the extension is not supported.
    """
    path = Path(file_path)
    resolved = kind or document_kind(path.name)

    match resolved:
        case "pdf":
            return extract_text_from_pdf(path)
        case "docx":
            return extract_text_from_docx(path)
        case "image":
            return extract_text_from_image(path)
        case _:
            raise UnsupportedFileTypeError(resolved)


def describe_extraction_failure(kind: str) -> str:
    """A user-facing hint for why a supported file yielded no text."""
    if kind == "pdf":
        return (
            "No text could be read from this PDF. It is most likely a scan — every "
            "page is an image. Export a text-based PDF from your editor, or send the "
            "pages as photos so OCR can read them."
        )
    if kind == "image":
        return (
            "No text could be recognised in this image. Try a sharper, well-lit, "
            "straight-on photo, or upload the original PDF/DOCX instead."
        )
    return "No text could be read from this document."
