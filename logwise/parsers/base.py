"""Parser ABC. Two methods: can_parse for detection, parse for the stream.

The shape mirrors LogSource — the abstract `parse` signature returns
`AsyncIterator[LogEntry]`, not `async def`. Concrete implementations are
async generators (`async def parse(...): yield ...`) which Python recognizes
as AsyncIterator[LogEntry] at the type level.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from logwise.core.log_entry import LogEntry


class Parser(ABC):
    """Transforms a stream of raw log lines into a stream of LogEntry."""

    @abstractmethod
    def can_parse(self, sample: list[str]) -> bool:
        """Given up to 10 sniff lines, return True if this parser is a good fit.

        Called by AutoDetector once before any line is parsed. Must be cheap
        and sync (no async). The sample may contain blank lines or partial
        content; implementations should be tolerant.
        """

    @abstractmethod
    def parse(self, lines: AsyncIterator[str]) -> AsyncIterator[LogEntry]:
        """Consume the line stream and yield LogEntry objects.

        Implementations must NOT raise on a malformed line — they should
        emit a fallback LogEntry (raw line + keyword_level + msg=None) so
        the user always sees their data, even when structured parsing fails.
        """
