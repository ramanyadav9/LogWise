"""Tests for logwise.sources.file_source."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from logwise.sources.file_source import FileSource


async def test_reads_existing_content_on_start(tmp_path: Path) -> None:
    # FileSource reads from byte 0, so existing lines show up immediately.
    log = tmp_path / "app.log"
    log.write_text("line one\nline two\nline three\n")
    src = FileSource(log, poll_interval=0.01)

    received: list[str] = []

    async def collect() -> None:
        async for line in src.stream():
            received.append(line)
            if len(received) == 3:
                return

    await asyncio.wait_for(collect(), timeout=1.0)
    assert received == ["line one", "line two", "line three"]


async def test_streams_appended_lines(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("")  # exists, empty — stream() begins at position 0
    src = FileSource(log, poll_interval=0.01)

    received: list[str] = []

    async def collect() -> None:
        async for line in src.stream():
            received.append(line)
            if len(received) == 2:
                return

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    log.write_text("first\nsecond\n")
    await asyncio.wait_for(task, timeout=1.0)

    assert received == ["first", "second"]


async def test_recovers_from_truncation(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("")
    src = FileSource(log, poll_interval=0.01)

    received: list[str] = []

    async def collect() -> None:
        async for line in src.stream():
            received.append(line)
            if len(received) == 2:
                return

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    log.write_text("before-truncate\n")
    await asyncio.sleep(0.05)
    log.write_text("after-truncate\n")
    await asyncio.wait_for(task, timeout=2.0)

    assert "before-truncate" in received
    assert "after-truncate" in received


def test_missing_file_raises_on_stream_start(tmp_path: Path) -> None:
    """FileSource constructor doesn't touch disk; stream() does."""
    src = FileSource(tmp_path / "does-not-exist.log", poll_interval=0.01)

    async def consume() -> None:
        async for _ in src.stream():
            return

    with pytest.raises(FileNotFoundError):
        asyncio.run(consume())
