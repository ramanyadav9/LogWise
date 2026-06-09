"""Docker container log source — streams logs via docker-py."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from logwise.sources.base import LogSource


class DockerSource(LogSource):
    """Streams log lines from a running Docker container.

    Connects to the Docker daemon via docker.from_env() and calls
    container.logs(stream=True, follow=True). The blocking docker-py
    iterator is bridged to async via a thread + asyncio.Queue.

    Requires the `docker` optional extra: pip install logwise[docker].
    The import is lazy — it only fires inside stream(), so importing
    this module without docker-py installed is safe.
    """

    def __init__(self, container: str) -> None:
        self.container = container

    async def stream(self) -> AsyncIterator[str]:
        import docker

        loop = asyncio.get_running_loop()
        client = docker.from_env()
        ctr = client.containers.get(self.container)
        log_stream = ctr.logs(stream=True, follow=True, timestamps=False)

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _read_logs() -> None:
            try:
                for chunk in log_stream:
                    for line in chunk.decode(errors="replace").splitlines():
                        if line:
                            loop.call_soon_threadsafe(queue.put_nowait, line)
            except Exception:
                pass
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _read_logs)

        while True:
            line = await queue.get()
            if line is None:
                return
            yield line
