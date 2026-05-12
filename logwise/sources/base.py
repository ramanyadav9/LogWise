"""Abstract base class for log producers.

In W2 the contract changed: sources yield raw line strings, not LogEntry.
The Parser layer (logwise/parsers/) is responsible for turning those strings
into LogEntry objects. This decouples line acquisition (sources' job) from
line interpretation (parsers' job).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LogSource(ABC):
    """A producer of raw log lines as strings."""

    @abstractmethod
    def stream(self) -> AsyncIterator[str]:
        """Yield raw log lines (without trailing newline) until exhausted.

        Implementations should be cancellation-safe: when the consuming task
        is cancelled, any open file handles or pipes must close cleanly.
        """
