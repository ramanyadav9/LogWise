"""File-tailing source — polls a file with aiofiles and yields raw lines."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles

from logwise.sources.base import LogSource


class FileSource(LogSource):
    """Reads a file from the start, then keeps tailing new appended lines.

    Opens the file in stream() (not __init__), so missing-file errors surface
    to the caller's async context. Reads existing content from byte 0 so the
    user sees what's already in the file (the common "open this log and look
    at it" case). After hitting EOF, polls every poll_interval seconds for
    new lines. Handles truncation (file shrinks) by seeking back to byte 0;
    rename-style rotation is a documented W1 limitation.

    For very large files, the downstream ring buffer caps the in-memory size
    (default 10 000 lines), so the table shows the last N lines regardless of
    file size — startup is still fast and bounded.
    """

    def __init__(self, path: Path, poll_interval: float = 0.1) -> None:
        self.path = Path(path)
        self.poll = poll_interval

    async def stream(self) -> AsyncIterator[str]:
        async with aiofiles.open(self.path, mode="r", errors="replace") as f:
            while True:
                line = await f.readline()
                if line:
                    yield line.rstrip("\n")
                else:
                    # Truncation check: file shrunk under us (e.g. `> log.txt`).
                    pos = await f.tell()
                    if pos > os.path.getsize(self.path):
                        await f.seek(0)
                    await asyncio.sleep(self.poll)
