"""AutoDetector — meta-parser that sniffs the first N lines, then delegates.

During the sniff window (first N lines), AutoDetector emits each line as a
keyword-classified plain LogEntry immediately, so the user sees colored output
from the very first row. After the sniff buffer is full, AutoDetector picks
the highest-priority parser whose `can_parse(buffer)` returns True, and
delegates all subsequent lines to that parser. The sniff lines themselves are
not re-parsed (small visual inconsistency documented in the W2a spec).

AutoDetector itself implements the Parser interface so callers can treat it
uniformly with the concrete parsers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.parsers._plain_helpers import keyword_level
from logwise.parsers.base import Parser


class AutoDetector(Parser):
    """Picks a concrete parser by sniffing the first `sniff_size` lines."""

    def __init__(self, parsers: list[Parser], sniff_size: int = 10) -> None:
        if not parsers:
            raise ValueError("AutoDetector needs at least one parser")
        self.parsers = parsers
        self.sniff_size = sniff_size

    def can_parse(self, sample: list[str]) -> bool:
        return True  # always — AutoDetector is the universal entry point.

    async def parse(self, lines: AsyncIterator[str]) -> AsyncIterator[LogEntry]:
        buffer: list[str] = []

        # Sniff window: emit each line as plain pass-through, also buffer for decision.
        async for line in lines:
            stripped = line.rstrip("\n")
            buffer.append(stripped)
            yield LogEntry(
                timestamp=datetime.now(),
                level=keyword_level(stripped),
                raw=stripped,
                msg=None,
                fields=None,
            )
            if len(buffer) >= self.sniff_size:
                break

        # Pick parser based on buffered sample.
        chosen = self._pick(buffer)

        # Delegate the rest of the stream to the chosen parser.
        async for entry in chosen.parse(lines):
            yield entry

    def _pick(self, sample: list[str]) -> Parser:
        for parser in self.parsers:
            if parser.can_parse(sample):
                return parser
        return self.parsers[-1]  # last is the plain fallback
