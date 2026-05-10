"""Abstract base class for log producers.

Sources are async iterators of LogEntry. They have zero knowledge of the TUI —
the consumer is just `async for entry in source.stream(): ...`. This keeps
sources unit-testable headless and lets future modes (JSON output, web UI)
reuse the same producers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from logwise.core.log_entry import LogEntry


class LogSource(ABC):
    """A producer of LogEntry objects."""

    @abstractmethod
    def stream(self) -> AsyncIterator[LogEntry]:
        """Yield LogEntry objects until the underlying source is exhausted.

        Implementations should be cancellation-safe: when the consuming task
        is cancelled, any open file handles or pipes must close cleanly.
        """
        ...
