"""LogWiseApp — the Textual App that wires source → parser → table."""

from __future__ import annotations

import asyncio

from textual import work
from textual.app import App, ComposeResult

from logwise.app.log_table import LogTable
from logwise.core.ring_buffer import RingBuffer
from logwise.parsers.base import Parser
from logwise.sources.base import LogSource


class LogWiseApp(App):
    """The single Textual screen for W2.

    Owns the ring buffer and the log table. On mount, spawns a worker task
    that consumes `parser.parse(source.stream())`. Errors at either layer
    are rendered as error rows so the TUI stays alive.
    """

    CSS = """
    LogTable {
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        source: LogSource,
        parser: Parser,
        max_lines: int = 10_000,
    ) -> None:
        super().__init__()
        self.source = source
        self.parser = parser
        self.buffer: RingBuffer = RingBuffer(maxlen=max_lines)
        self.log_table = LogTable()

    def compose(self) -> ComposeResult:
        yield self.log_table

    @work(exclusive=True)
    async def _consume(self) -> None:
        try:
            async for entry in self.parser.parse(self.source.stream()):
                self.buffer.append(entry)
                self.log_table.add_entry(entry)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — render-and-survive boundary
            self.log_table.add_error_row(
                f"pipeline error: {type(exc).__name__}: {exc}"
            )

    def on_mount(self) -> None:
        self._consume()
