"""JSONParser — one JSON object per line.

Reads `level` / `severity` / `lvl`, `msg` / `message` / `text`, and
`ts` / `timestamp` / `time` / `@timestamp` keys. Remaining keys become
`LogEntry.fields`. Non-JSON lines fall back to keyword-level classification.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.core.log_level import LogLevel
from logwise.parsers._plain_helpers import keyword_level
from logwise.parsers.base import Parser

LEVEL_KEYS = ("level", "severity", "lvl")
MSG_KEYS = ("msg", "message", "text")
TS_KEYS = ("ts", "timestamp", "time", "@timestamp")

LEVEL_MAP = {
    "trace":         LogLevel.DEBUG,
    "debug":         LogLevel.DEBUG,
    "info":          LogLevel.INFO,
    "informational": LogLevel.INFO,
    "notice":        LogLevel.INFO,
    "warn":          LogLevel.WARNING,
    "warning":       LogLevel.WARNING,
    "error":         LogLevel.ERROR,
    "err":           LogLevel.ERROR,
    "fatal":         LogLevel.FATAL,
    "critical":      LogLevel.FATAL,
    "panic":         LogLevel.FATAL,
}


class JSONParser(Parser):
    """Parses one JSON object per line into a LogEntry."""

    def can_parse(self, sample: list[str]) -> bool:
        non_empty = [s for s in sample if s.strip()]
        if not non_empty:
            return False
        # At least one of the first 5 non-empty lines must parse as a JSON object.
        for line in non_empty[:5]:
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    obj = json.loads(stripped)
                    if isinstance(obj, dict):
                        return True
                except json.JSONDecodeError:
                    continue
        return False

    async def parse(self, lines: AsyncIterator[str]) -> AsyncIterator[LogEntry]:
        async for line in lines:
            stripped_line = line.rstrip("\n")
            obj = _try_parse(stripped_line)
            if obj is None:
                yield _fallback(stripped_line)
                continue

            level = _extract_level(obj)
            msg = _extract_msg(obj)
            ts = _extract_ts(obj)
            used = set(LEVEL_KEYS + MSG_KEYS + TS_KEYS)
            extras = {k: v for k, v in obj.items() if k not in used}
            yield LogEntry(
                timestamp=ts,
                level=level,
                raw=stripped_line,
                msg=msg,
                fields=extras or None,
            )


def _try_parse(line: str) -> dict | None:
    stripped = line.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _extract_level(obj: dict) -> LogLevel:
    for key in LEVEL_KEYS:
        if key in obj:
            v = str(obj[key]).lower()
            if v in LEVEL_MAP:
                return LEVEL_MAP[v]
    return LogLevel.INFO


def _extract_msg(obj: dict) -> str | None:
    for key in MSG_KEYS:
        if key in obj:
            return str(obj[key])
    return None


def _extract_ts(obj: dict) -> datetime:
    for key in TS_KEYS:
        if key in obj:
            try:
                return datetime.fromisoformat(str(obj[key]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
    return datetime.now()


def _fallback(line: str) -> LogEntry:
    return LogEntry(
        timestamp=datetime.now(),
        level=keyword_level(line),
        raw=line,
        msg=None,
        fields=None,
    )
