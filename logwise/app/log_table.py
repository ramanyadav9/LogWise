"""LogTable — the single Textual widget that renders the live log stream."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import DataTable

from logwise.core.log_entry import LogEntry
from logwise.core.log_level import LogLevel

LEVEL_STYLE: dict[LogLevel, str] = {
    LogLevel.FATAL:   "bold red",
    LogLevel.ERROR:   "red",
    LogLevel.WARNING: "yellow",
    LogLevel.INFO:    "default",
    LogLevel.DEBUG:   "dim",
}

ERROR_ROW_STYLE = "bold red on dark_red"


class LogTable(DataTable):
    """A scrolling, color-coded log table.

    Columns: timestamp | level | message. Each cell is a Rich Text styled with
    the level's color so the entire row reads as one color.
    """

    def on_mount(self) -> None:
        self.add_columns("Time", "Level", "Message")
        self.cursor_type = "row"
        self.zebra_stripes = False

    def add_entry(self, entry: LogEntry) -> None:
        style = LEVEL_STYLE.get(entry.level, "default")
        self.add_row(
            Text(entry.timestamp.strftime("%H:%M:%S"), style=style),
            Text(entry.level.name, style=style),
            Text(entry.raw, style=style),
        )
        self.scroll_end(animate=False)

    def add_error_row(self, message: str) -> None:
        """Render an internal logwise error inline so the user sees what failed."""
        self.add_row(
            Text("--:--:--", style=ERROR_ROW_STYLE),
            Text("LOGWISE", style=ERROR_ROW_STYLE),
            Text(message, style=ERROR_ROW_STYLE),
        )
        self.scroll_end(animate=False)
