"""Tests for logwise.core.quick_level."""

import pytest

from logwise.core.log_level import LogLevel
from logwise.core.quick_level import quick_level


@pytest.mark.parametrize(
    "line, expected",
    [
        ("[ERROR] connection refused",          LogLevel.ERROR),
        ('{"level":"error","msg":"boom"}',      LogLevel.ERROR),
        ("2026-05-09 ERROR app.py:42 boom",     LogLevel.ERROR),
        ("WARN: cache miss",                    LogLevel.WARNING),
        ("WARNING: deprecated",                 LogLevel.WARNING),
        ("FATAL: out of memory",                LogLevel.FATAL),
        ("CRITICAL: disk full",                 LogLevel.FATAL),
        ("PANIC: goroutine leak",               LogLevel.FATAL),
        ("DEBUG req.id=abc",                    LogLevel.DEBUG),
        ("plain info message",                  LogLevel.INFO),
        ("",                                    LogLevel.INFO),
        # Documented W1 false-positive: any line containing the word ERROR
        # is classified as ERROR even when used in prose. W2 parsers fix this.
        ("user reported error in form",         LogLevel.ERROR),
    ],
)
def test_quick_level(line: str, expected: LogLevel) -> None:
    assert quick_level(line) is expected
