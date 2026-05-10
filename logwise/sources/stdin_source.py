"""Stdin-tailing source — reads from sys.stdin asynchronously."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import datetime

from logwise.core.log_entry import LogEntry
from logwise.core.quick_level import quick_level
from logwise.sources.base import LogSource


class StdinSource(LogSource):
    """Reads log lines from stdin.

    On Linux/macOS, uses asyncio.connect_read_pipe for true async stdin reads.
    On Windows, that mechanism is not supported on stdin, so falls back to a
    thread executor running blocking sys.stdin.readline() calls.
    """

    async def stream(self) -> AsyncIterator[LogEntry]:
        if sys.platform == "win32":
            async for entry in self._stream_threaded():
                yield entry
        else:
            async for entry in self._stream_pipe():
                yield entry

    async def _stream_pipe(self) -> AsyncIterator[LogEntry]:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer
        )
        while not reader.at_eof():
            line_bytes = await reader.readline()
            if not line_bytes:
                return
            yield _to_entry(line_bytes.decode(errors="replace"))

    async def _stream_threaded(self) -> AsyncIterator[LogEntry]:
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return
            yield _to_entry(line)


def _to_entry(line: str) -> LogEntry:
    stripped = line.rstrip("\n")
    return LogEntry(
        timestamp=datetime.now(),
        level=quick_level(stripped),
        raw=stripped,
    )
