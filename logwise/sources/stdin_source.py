"""Stdin-tailing source — reads from sys.stdin OR a saved pipe fd."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator

from logwise.sources.base import LogSource


class StdinSource(LogSource):
    """Reads raw log lines from stdin or from a saved pipe fd.

    When `pipe_fd` is provided, reads from that fd via a thread executor.
    This is the W1.1 path: cli.py saves the original piped stdin (via
    os.dup(0)) before swapping sys.stdin to the terminal so the TUI gets
    keyboard input. StdinSource then reads log content from the saved fd.

    When `pipe_fd` is None, reads from sys.stdin using:
      - asyncio.connect_read_pipe on Linux/macOS (true async)
      - thread executor on Windows (connect_read_pipe doesn't support stdin)
    """

    def __init__(self, pipe_fd: int | None = None) -> None:
        self.pipe_fd = pipe_fd

    async def stream(self) -> AsyncIterator[str]:
        if self.pipe_fd is not None:
            async for line in self._stream_fd(self.pipe_fd):
                yield line
        elif sys.platform == "win32":
            async for line in self._stream_threaded():
                yield line
        else:
            async for line in self._stream_pipe():
                yield line

    async def _stream_fd(self, fd: int) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        f = os.fdopen(fd, "rb", buffering=0)
        try:
            while True:
                line = await loop.run_in_executor(None, f.readline)
                if not line:
                    return
                yield line.decode(errors="replace").rstrip("\n")
        finally:
            f.close()

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
