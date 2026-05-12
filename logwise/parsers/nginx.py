"""NginxParser — nginx access (combined format) + error log lines.

Recognizes the standard nginx combined access-log format and the standard
nginx error-log format. Custom log formats are not supported in W2a;
those lines fall back to keyword-level classification.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.core.log_level import LogLevel
from logwise.parsers._plain_helpers import keyword_level
from logwise.parsers.base import Parser

# Combined log format:
#   $remote_addr - $remote_user [$time_local] "$request" $status $bytes "$ref" "$ua"
ACCESS_LOG = re.compile(
    r'^(?P<remote>\S+)\s+\S+\s+(?P<user>\S+)\s+'
    r'\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+'
    r'(?P<status>\d+)\s+(?P<bytes>\d+)'
)

# Error log:
#   2026/05/09 14:32:01 [error] 1234#0: *567 message
ERROR_LOG = re.compile(
    r'^(?P<time>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
    r'\[(?P<level>\w+)\]\s+\d+#\d+:\s+(?:\*\d+\s+)?(?P<msg>.+)'
)

NGINX_ERROR_LEVELS = {
    "debug":  LogLevel.DEBUG,
    "info":   LogLevel.INFO,
    "notice": LogLevel.INFO,
    "warn":   LogLevel.WARNING,
    "error":  LogLevel.ERROR,
    "crit":   LogLevel.FATAL,
    "alert":  LogLevel.FATAL,
    "emerg":  LogLevel.FATAL,
}


class NginxParser(Parser):
    """Parses nginx access + error log lines."""

    def can_parse(self, sample: list[str]) -> bool:
        non_empty = [s for s in sample if s.strip()]
        if not non_empty:
            return False
        for line in non_empty[:5]:
            if ACCESS_LOG.match(line) or ERROR_LOG.match(line):
                return True
        return False

    async def parse(self, lines: AsyncIterator[str]) -> AsyncIterator[LogEntry]:
        async for line in lines:
            stripped = line.rstrip("\n")

            access_match = ACCESS_LOG.match(stripped)
            if access_match:
                yield _from_access(stripped, access_match)
                continue

            error_match = ERROR_LOG.match(stripped)
            if error_match:
                yield _from_error(stripped, error_match)
                continue

            yield _fallback(stripped)


def _from_access(raw: str, m: re.Match[str]) -> LogEntry:
    status = int(m.group("status"))
    level = _access_level(status)
    return LogEntry(
        timestamp=_parse_access_time(m.group("time")),
        level=level,
        raw=raw,
        msg=f"{m.group('method')} {m.group('path')} {status}",
        fields={
            "remote": m.group("remote"),
            "method": m.group("method"),
            "path": m.group("path"),
            "status": status,
            "bytes": int(m.group("bytes")),
        },
    )


def _from_error(raw: str, m: re.Match[str]) -> LogEntry:
    level_token = m.group("level").lower()
    return LogEntry(
        timestamp=_parse_error_time(m.group("time")),
        level=NGINX_ERROR_LEVELS.get(level_token, LogLevel.ERROR),
        raw=raw,
        msg=m.group("msg"),
        fields={"nginx_level": level_token},
    )


def _access_level(status: int) -> LogLevel:
    if status >= 500:
        return LogLevel.ERROR
    if status >= 400:
        return LogLevel.WARNING
    return LogLevel.INFO


def _parse_access_time(token: str) -> datetime:
    # Example: 09/May/2026:14:32:01 +0000
    try:
        return datetime.strptime(token, "%d/%b/%Y:%H:%M:%S %z")
    except (ValueError, TypeError):
        return datetime.now()


def _parse_error_time(token: str) -> datetime:
    # Example: 2026/05/09 14:32:01
    try:
        return datetime.strptime(token, "%Y/%m/%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.now()


def _fallback(line: str) -> LogEntry:
    return LogEntry(
        timestamp=datetime.now(),
        level=keyword_level(line),
        raw=line,
        msg=None,
        fields=None,
    )
