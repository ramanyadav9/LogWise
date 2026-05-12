"""The in-memory representation of one log line.

W1 populated three fields (timestamp, level, raw). W2 adds two optional
fields that parsers fill in: `msg` (the parser-extracted human message,
often shorter than raw) and `fields` (structured data like JSON keys or
nginx access-log fields). Both default to None so W1 callers keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from logwise.core.log_level import LogLevel


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One log line as it flows through logwise."""

    timestamp: datetime
    level: LogLevel
    raw: str
    msg: str | None = None
    fields: Mapping[str, Any] | None = None
