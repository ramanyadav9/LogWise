"""The single in-memory representation of one log line in W1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from logwise.core.log_level import LogLevel


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One log line as it flows through logwise.

    W1 only populates three fields. Format-aware parsers in W2 will populate
    additional structured fields on a successor type.
    """

    timestamp: datetime
    level: LogLevel
    raw: str
