"""Shared helpers used by every parser's fallback path.

Every parser falls back to keyword-based level extraction when its
strict-parse step fails (e.g., a non-JSON line in a JSON log). This module
holds the keyword classifier and a regex for Python exception lines that
PlainParser's traceback merger also needs.
"""

from __future__ import annotations

import re

from logwise.core.log_level import LogLevel

# Matches a Python exception class line:
#   ValueError: foo
#   KeyboardInterrupt
# Requires the first character to be uppercase (Python convention for
# exception class names). It is the terminating line of a traceback.
# Limitation: StopIteration / StopAsyncIteration are not matched because
# they lack the Error/Exception/Warning/Interrupt/Exit suffix.
EXCEPTION_LINE = re.compile(
    r"^[A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*"
    r"(?:Error|Exception|Warning|Interrupt|Exit)\b"
)

# Lines inserted between chained exceptions in a Python 3 traceback.
CHAINED_MARKERS = (
    "During handling of the above exception, another exception occurred:",
    "The above exception was the direct cause of the following exception:",
)


def keyword_level(line: str) -> LogLevel:
    """Classify a raw line by case-insensitive keyword search.

    Same algorithm as the deleted W1 `quick_level`. Order matters: FATAL/
    CRITICAL/PANIC are checked before ERROR (because some FATAL lines also
    contain the word ERROR), ERROR before WARN, etc.
    """
    upper = line.upper()
    if any(keyword in upper for keyword in ("FATAL", "CRITICAL", "PANIC")):
        return LogLevel.FATAL
    if "ERROR" in upper:
        return LogLevel.ERROR
    if "WARN" in upper:
        return LogLevel.WARNING
    if "DEBUG" in upper:
        return LogLevel.DEBUG
    return LogLevel.INFO
