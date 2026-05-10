"""Tests for logwise.sources.file_source."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from logwise.core.log_entry import LogEntry
from logwise.sources.file_source import FileSource


async def test_streams_appended_lines(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("")  # exists, empty — important: stream() seeks to EOF
    src = FileSource(log, poll_interval=0.01)

    received: list[LogEntry] = []

    async def collect() -> None:
        async for entry in src.stream():
            received.append(entry)
            if len(received) == 2:
                return

    task = asyncio.create_task(collect())
    # Give stream() a moment to open the file and seek to end.
    await asyncio.sleep(0.05)
    log.write_text("first\nsecond\n")
    await asyncio.wait_for(task, timeout=1.0)

    assert [e.raw.strip() for e in received] == ["first", "second"]


async def test_recovers_from_truncation(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("")
    src = FileSource(log, poll_interval=0.01)

    received: list[LogEntry] = []

    async def collect() -> None:
        async for entry in src.stream():
            received.append(entry)
            if len(received) == 2:
                return

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    log.write_text("before-truncate\n")
    await asyncio.sleep(0.05)
    # Simulate `> log.txt` — file shrinks, then new content appears.
    log.write_text("after-truncate\n")
    await asyncio.wait_for(task, timeout=2.0)

    raws = [e.raw.strip() for e in received]
    assert "before-truncate" in raws
    assert "after-truncate" in raws


def test_missing_file_raises_on_stream_start(tmp_path: Path) -> None:
    """FileSource constructor doesn't touch disk; stream() does."""
    src = FileSource(tmp_path / "does-not-exist.log", poll_interval=0.01)

    async def consume() -> None:
        async for _ in src.stream():
            return

    with pytest.raises(FileNotFoundError):
        asyncio.run(consume())
