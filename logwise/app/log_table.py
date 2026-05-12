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
    the level's color. The message cell prefers entry.msg (parser-extracted)
    and falls back to the first line of entry.raw for plain/unparsed lines.
    """

    def on_mount(self) -> None:
        self.add_columns("Time", "Level", "Message")
        self.cursor_type = "row"
        self.zebra_stripes = False

    def add_entry(self, entry: LogEntry) -> None:
        # Capture follow-tail state BEFORE adding the row, because adding it
        # changes max_scroll_y. If the user has scrolled up, they're reading
        # history and we must not jerk them back down on every new line.
        follow_tail = self._is_at_bottom()
        style = LEVEL_STYLE.get(entry.level, "default")
        message = entry.msg if entry.msg is not None else _first_line(entry.raw)
        self.add_row(
            Text(entry.timestamp.strftime("%H:%M:%S"), style=style),
            Text(entry.level.name, style=style),
            Text(message, style=style),
        )
        if follow_tail:
            self.scroll_end(animate=False)

    def add_error_row(self, message: str) -> None:
        """Render an internal logwise error inline so the user sees what failed."""
        follow_tail = self._is_at_bottom()
        self.add_row(
            Text("--:--:--", style=ERROR_ROW_STYLE),
            Text("LOGWISE", style=ERROR_ROW_STYLE),
            Text(message, style=ERROR_ROW_STYLE),
        )
        if follow_tail:
            self.scroll_end(animate=False)

    def _is_at_bottom(self) -> bool:
        """True if the user is at (or within 2 rows of) the bottom of the table.

        When True, new rows should auto-scroll into view (tail-follow mode).
        When False, the user has scrolled up to read history — leave them alone.
        """
        if self.max_scroll_y <= 0:
            return True  # content fits in the viewport; always "at bottom"
        return self.scroll_y >= self.max_scroll_y - 2


def _first_line(text: str) -> str:
    """Return the first line of a (possibly multi-line) string."""
    if not text:
        return ""
    newline_idx = text.find("\n")
    return text if newline_idx < 0 else text[:newline_idx]
