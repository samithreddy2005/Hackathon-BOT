"""Exception hierarchy for the ATS bot.

Every error the application raises deliberately derives from :class:`ATSBotError`,
so callers can distinguish "our" failures from unexpected ones.
"""

from __future__ import annotations

__all__ = [
    "ATSBotError",
    "ConfigurationError",
    "DatabaseError",
    "FileTooLargeError",
    "ParsingError",
    "UnsupportedFileTypeError",
    "UploadError",
]


class ATSBotError(Exception):
    """Base class for all errors raised by this application."""


class ConfigurationError(ATSBotError):
    """Raised when required configuration is missing or malformed."""


class DatabaseError(ATSBotError):
    """Raised when a database operation fails."""


class ParsingError(ATSBotError):
    """Raised when a document cannot be converted to text."""


class UploadError(ATSBotError):
    """Base class for problems with an uploaded file."""


class UnsupportedFileTypeError(UploadError):
    """Raised when the uploaded file has an extension we cannot parse."""

    def __init__(self, extension: str) -> None:
        self.extension = extension
        super().__init__(f"Unsupported file type: {extension!r}")


class FileTooLargeError(UploadError):
    """Raised when the uploaded file exceeds the configured size limit."""

    def __init__(self, size_bytes: int, limit_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes
        super().__init__(f"File is {size_bytes} bytes; limit is {limit_bytes} bytes")
