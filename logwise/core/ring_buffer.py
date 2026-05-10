"""Bounded in-memory log store backed by collections.deque."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from logwise.core.log_entry import LogEntry


class RingBuffer:
    """Fixed-capacity FIFO buffer of LogEntry objects.

    Appends are O(1). When full, appending evicts the oldest entry — by design,
    no warning, no overflow signal. Iteration yields entries in arrival order.
    """

    def __init__(self, maxlen: int) -> None:
        self._buf: deque[LogEntry] = deque(maxlen=maxlen)

    def append(self, entry: LogEntry) -> None:
        self._buf.append(entry)

    def __iter__(self) -> Iterator[LogEntry]:
        return iter(self._buf)

    def __len__(self) -> int:
        return len(self._buf)
