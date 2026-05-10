"""Log severity levels used across logwise."""

from __future__ import annotations

from enum import Enum


class LogLevel(Enum):
    """Severity levels. Ordering reflects increasing severity."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"
