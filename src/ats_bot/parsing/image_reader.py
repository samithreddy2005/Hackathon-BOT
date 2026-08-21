"""Image text extraction via Tesseract OCR.

OCR is optional infrastructure: the bot works fully without Tesseract installed,
it simply cannot read resumes sent as photos. :func:`ocr_available` lets callers
check up front and tell the user something actionable instead of failing late.
"""

from __future__ import annotations

import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError

from ats_bot.errors import ParsingError
from ats_bot.parsing.cleaner import clean_text

__all__ = ["extract_text_from_image", "ocr_available", "tesseract_path"]

logger = logging.getLogger(__name__)

#: Common install locations checked when Tesseract is not on PATH.
_FALLBACK_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
)

#: Upscaling below this width measurably improves OCR accuracy on phone photos.
_MIN_OCR_WIDTH = 1600

#: Refuse absurd resolutions rather than letting Pillow allocate gigabytes.
_MAX_PIXELS = 40_000_000

INSTALL_HINT = (
    "Tesseract OCR is not installed, so images cannot be read. "
    "Install it from https://github.com/UB-Mannheim/tesseract/wiki (Windows) or "
    "`apt install tesseract-ocr` / `brew install tesseract`, then restart the bot. "
    "In the meantime, please upload your resume as a PDF or DOCX."
)


@lru_cache(maxsize=1)
def tesseract_path() -> str | None:
    """Locate the Tesseract binary, honouring ``TESSERACT_CMD`` if set."""
    explicit = os.getenv("TESSERACT_CMD", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    for candidate in _FALLBACK_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def ocr_available() -> bool:
    """True when OCR can be performed on this machine."""
    return tesseract_path() is not None


def _configure() -> None:
    path = tesseract_path()
    if path:
        pytesseract.pytesseract.tesseract_cmd = path


def extract_text_from_image(file_path: str | Path) -> str:
    """Run OCR over an image and return the recognised text.

    The image is converted to greyscale, upscaled when small, and auto-contrasted
    before recognition, which is what lifts phone photographs of a printed resume
    from unusable to readable.

    Raises:
        ParsingError: If the file is missing or unreadable, or if Tesseract is not
            installed on this machine.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ParsingError(f"Image file not found: {path.name}")
    if not ocr_available():
        raise ParsingError(INSTALL_HINT)

    _configure()

    try:
        with Image.open(path) as image:
            width, height = image.size
            if width * height > _MAX_PIXELS:
                raise ParsingError("This image is too large to process. Please send a smaller one.")

            processed = ImageOps.exif_transpose(image).convert("L")
            if width < _MIN_OCR_WIDTH:
                scale = min(_MIN_OCR_WIDTH / max(width, 1), 3.0)
                processed = processed.resize(
                    (int(width * scale), int(height * scale)), Image.Resampling.LANCZOS
                )
            processed = ImageOps.autocontrast(processed)
            text = pytesseract.image_to_string(processed)
    except UnidentifiedImageError as exc:
        raise ParsingError("This file is not a readable image.") from exc
    except pytesseract.TesseractNotFoundError as exc:
        # PATH changed since the availability check, or a stale cached path.
        tesseract_path.cache_clear()
        raise ParsingError(INSTALL_HINT) from exc
    except ParsingError:
        raise
    except Exception as exc:
        logger.exception("OCR failed for %s", path.name)
        raise ParsingError("Text could not be recognised in this image.") from exc

    return clean_text(text)
