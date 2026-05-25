"""File-tailing source — brief-opens polling, no persistent file handle."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

from logwise.sources.base import LogSource


class FileSource(LogSource):
    """Reads a file from the start, then keeps tailing new appended lines.

    Uses a brief-opens strategy: opens the file each poll cycle, reads from
    the last known byte position to current EOF, then closes. This:

    - Eliminates the Windows file-lock problem (the file handle exists only
      for ~1ms per cycle, leaving a >99% window for other processes to open
      the file for writing).
    - Handles rename-style log rotation transparently (next poll opens by
      path → gets the new file → its size is smaller than our tracked
      position → we reset to 0 and read the new file from the start).
    - Handles delete-then-recreate the same way, via FileNotFoundError.
    - Handles truncation (`> log.txt`) the same way, via the size check.

    Trade-off: ~10 open() calls per second per source. Negligible for local
    log files; could matter on a slow network mount (not a W1.1 concern).
    """

    def __init__(self, path: Path, poll_interval: float = 0.1) -> None:
        self.path = Path(path)
        self.poll = poll_interval

    async def stream(self) -> AsyncIterator[str]:
        pos = 0  # byte offset into the current file
        while True:
            try:
                with open(self.path, "r", errors="replace") as f:
                    size = os.fstat(f.fileno()).st_size
                    if size < pos:
                        # File shrank under us — truncation or rotation.
                        pos = 0
                    f.seek(pos)
                    while True:
                        line = f.readline()
                        if not line:
                            break
                        yield line.rstrip("\n")
                    pos = f.tell()
            except FileNotFoundError:
                # File was renamed/deleted; it'll likely be recreated.
                pos = 0
            except PermissionError:
                # Brief mid-rotation moment where the new file isn't readable
                # yet. Keep polling — usually clears on the next cycle.
                pass
            await asyncio.sleep(self.poll)
