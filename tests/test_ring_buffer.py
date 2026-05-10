"""Tests for logwise.core.ring_buffer."""

from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.core.log_level import LogLevel
from logwise.core.ring_buffer import RingBuffer


def _entry(i: int) -> LogEntry:
    return LogEntry(timestamp=datetime(2026, 5, 9), level=LogLevel.INFO, raw=str(i))


def test_appends_in_order() -> None:
    rb: RingBuffer = RingBuffer(maxlen=3)
    for i in range(3):
        rb.append(_entry(i))
    assert [e.raw for e in rb] == ["0", "1", "2"]


def test_drops_oldest_on_overflow() -> None:
    rb: RingBuffer = RingBuffer(maxlen=3)
    for i in range(5):
        rb.append(_entry(i))
    assert [e.raw for e in rb] == ["2", "3", "4"]


def test_len_reports_current_size() -> None:
    rb: RingBuffer = RingBuffer(maxlen=10)
    for i in range(4):
        rb.append(_entry(i))
    assert len(rb) == 4


def test_len_caps_at_maxlen() -> None:
    rb: RingBuffer = RingBuffer(maxlen=3)
    for i in range(100):
        rb.append(_entry(i))
    assert len(rb) == 3
