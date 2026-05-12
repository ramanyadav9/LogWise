"""PlainParser — plain-text parsing with Python traceback merging.

Single-line behavior: each input line becomes one LogEntry with level from
keyword search (the W1 algorithm). msg stays None — there's no structured
message to extract from plain text.

Multi-line behavior: when the parser sees a `Traceback (most recent call last):`
line, it starts accumulating. Continuation rules: indented lines, blank lines
within the traceback, chained-exception markers, and the terminating exception
class line are all part of the traceback. The first line that doesn't match
any continuation rule ends the traceback — flush as one ERROR entry whose raw
is the multi-line block and whose msg is the last exception class line.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.core.log_level import LogLevel
from logwise.parsers._plain_helpers import (
    CHAINED_MARKERS,
    EXCEPTION_LINE,
    keyword_level,
)
from logwise.parsers.base import Parser


class PlainParser(Parser):
    """Plain text + Python traceback merging. Always the fallback."""

    def can_parse(self, sample: list[str]) -> bool:
        return True

    async def parse(self, lines: AsyncIterator[str]) -> AsyncIterator[LogEntry]:
        pending: list[str] = []

        async for line in lines:
            stripped = line.rstrip("\n")

            if pending:
                if _is_traceback_continuation(stripped):
                    pending.append(stripped)
                    continue
                # Traceback ended; flush, then fall through to handle this line.
                yield _make_traceback_entry(pending)
                pending = []

            if stripped.lstrip().startswith("Traceback (most recent call last):"):
                pending = [stripped]
            else:
                yield _make_plain_entry(stripped)

        # End of stream: flush any pending traceback.
        if pending:
            yield _make_traceback_entry(pending)


def _is_traceback_continuation(line: str) -> bool:
    """True if `line` belongs to the currently-accumulating traceback.

    Consequence: two unrelated tracebacks emitted back-to-back with no
    intervening normal line (as can happen with concurrent workers) will
    merge into a single entry. The merged entry's `msg` is still the last
    exception line, so display is sensible — but `raw` conflates two events.
    Accepted trade-off for clean Python 3 chained-exception handling.
    """
    if not line:
        return True  # blank lines inside tracebacks are common
    if line[0].isspace():
        return True  # indented frame lines
    if line in CHAINED_MARKERS:
        return True  # Python 3 chained exception separator
    if line.startswith("Traceback (most recent call last):"):
        return True  # start of a chained traceback (or unrelated traceback)
    if EXCEPTION_LINE.match(line):
        return True  # the terminating exception class line
    return False


def _make_plain_entry(line: str) -> LogEntry:
    return LogEntry(
        timestamp=datetime.now(),
        level=keyword_level(line),
        raw=line,
        msg=None,
        fields=None,
    )


def _make_traceback_entry(pending: list[str]) -> LogEntry:
    raw = "\n".join(pending)
    # The msg is the last line that looks like an exception class.
    msg = None
    for line in reversed(pending):
        if EXCEPTION_LINE.match(line):
            msg = line
            break
    if msg is None:
        msg = pending[-1]
    return LogEntry(
        timestamp=datetime.now(),
        level=LogLevel.ERROR,
        raw=raw,
        msg=msg,
        fields=None,
    )
