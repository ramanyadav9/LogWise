"""W1-only level detection. Replaced by format-aware parsers in W2.

This module deliberately uses the simplest possible substring match. It is
designed to be deleted, not refined — when W2 ships parsers/, this file goes
away and LogEntry.level is populated by the chosen parser instead.
"""

from __future__ import annotations

from logwise.core.log_level import LogLevel


def quick_level(line: str) -> LogLevel:
    """Classify a raw log line by case-insensitive keyword search.

    Order matters: FATAL/CRITICAL/PANIC checked before ERROR, ERROR before
    WARN, etc. Any line that doesn't match anything is INFO.
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
