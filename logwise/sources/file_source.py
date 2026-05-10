"""File-tailing source — polls a file with aiofiles and yields LogEntry objects."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import aiofiles

from logwise.core.log_entry import LogEntry
from logwise.core.quick_level import quick_level
from logwise.sources.base import LogSource


class FileSource(LogSource):
    """Tails a file by polling with aiofiles.

    Opens the file at construction-time of stream() (not __init__) so the
    constructor never raises and missing-file errors surface to the caller's
    async context. Polls every ``poll_interval`` seconds when the file is
    quiet; consumes lines greedily when they're available. Handles truncation
    (file shrinks) by seeking to byte 0; rename-style rotation is a documented
    W1 limitation.
    """

    def __init__(self, path: Path, poll_interval: float = 0.1) -> None:
        self.path = Path(path)
        self.poll = poll_interval

    async def stream(self) -> AsyncIterator[LogEntry]:
        async with aiofiles.open(self.path, mode="r", errors="replace") as f:
            await f.seek(0, os.SEEK_END)
            while True:
                line = await f.readline()
                if line:
                    yield _to_entry(line)
                else:
                    # Truncation check: file shrunk under us (e.g. `> log.txt`).
                    pos = await f.tell()
                    if pos > os.path.getsize(self.path):
                        await f.seek(0)
                    await asyncio.sleep(self.poll)


def _to_entry(line: str) -> LogEntry:
    stripped = line.rstrip("\n")
    return LogEntry(
        timestamp=datetime.now(),
        level=quick_level(stripped),
        raw=stripped,
    )
