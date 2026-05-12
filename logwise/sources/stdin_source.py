"""Stdin-tailing source — reads from sys.stdin asynchronously."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator

from logwise.sources.base import LogSource


class StdinSource(LogSource):
    """Reads raw log lines from stdin.

    On Linux/macOS: asyncio.connect_read_pipe on sys.stdin.buffer for true
    async stdin reads. On Windows: that mechanism is not supported on stdin,
    so falls back to a thread executor running blocking sys.stdin.readline().
    """

    async def stream(self) -> AsyncIterator[str]:
        if sys.platform == "win32":
            async for line in self._stream_threaded():
                yield line
        else:
            async for line in self._stream_pipe():
                yield line

    async def _stream_pipe(self) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer
        )
        while not reader.at_eof():
            line_bytes = await reader.readline()
            if not line_bytes:
                return
            yield line_bytes.decode(errors="replace").rstrip("\n")

    async def _stream_threaded(self) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return
            yield line.rstrip("\n")
