"""Typer CLI — parse flags, pick a source + parser, run the TUI."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from logwise import __version__
from logwise.app.main_app import LogWiseApp
from logwise.parsers.auto_detect import AutoDetector
from logwise.parsers.base import Parser
from logwise.parsers.json_parser import JSONParser
from logwise.parsers.nginx import NginxParser
from logwise.parsers.plain import PlainParser
from logwise.sources.base import LogSource
from logwise.sources.file_source import FileSource

app = typer.Typer(
    name="logwise",
    help="AI-powered log intelligence TUI (W2: file/stdin tail + format-aware parsers).",
    add_completion=False,
)


class FormatChoice(str, Enum):
    auto = "auto"
    json = "json"
    nginx = "nginx"
    plain = "plain"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"logwise {__version__}")
        raise typer.Exit()


def _drain_pipe_to_tempfile() -> Path | None:
    """If stdin is piped, drain it to a temp file AND restore the console.

    Two things happen when stdin is a pipe:
    1. DATA: a background thread copies pipe bytes to a temp file.
       FileSource tails the temp file via its normal brief-opens loop.
    2. CONSOLE: we replace fd 0 + the process-level standard input handle
       with a real console handle (CONIN$ on Windows, /dev/tty on Unix)
       so Textual gets keyboard input (arrow keys, q, Page Up, etc.).

    Returns the temp file path, or None if stdin is already a terminal.
    """
    if sys.stdin.isatty():
        return None

    # --- Step 1: save the pipe to a SEPARATE fd before touching fd 0 ---
    # os.dup(0) copies the pipe to a new fd number (e.g., 3). After this,
    # the pipe is accessible via saved_pipe_fd even after fd 0 gets replaced.
    saved_pipe_fd = os.dup(0)

    # --- Step 2: restore the console on fd 0 for Textual ---
    if sys.platform == "win32":
        _restore_console_win32()
    else:
        _restore_console_unix()

    # --- Step 3: drain the saved pipe to a temp file in the background ---
    tmp = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".logwise.tmp", delete=False,
    )
    path = Path(tmp.name)
    pipe_file = os.fdopen(saved_pipe_fd, "rb", buffering=0)

    def drain() -> None:
        try:
            while True:
                data = pipe_file.read(4096)
                if not data:
                    break
                tmp.write(data)
                tmp.flush()
        except (OSError, ValueError):
            pass
        finally:
            pipe_file.close()
            tmp.close()

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    return path


def _restore_console_win32() -> None:
    """Replace fd 0 + process standard input with a real console handle.

    Uses CreateFileW (not os.open) to get GENERIC_READ|GENERIC_WRITE access
    on CONIN$, which ReadConsoleInputW and SetConsoleMode require. Then:
    - open_osfhandle + dup2 to update CRT fd 0
    - SetStdHandle to update the process-level STD_INPUT_HANDLE
    - ENABLE_VIRTUAL_TERMINAL_INPUT for ConPTY arrow-key escape sequences
    """
    import ctypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    STD_INPUT_HANDLE = -10
    ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

    # Open CONIN$ with both read AND write (needed for SetConsoleMode)
    handle = kernel32.CreateFileW(
        "CONIN$",
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle == -1:
        raise OSError("Cannot open CONIN$")

    # Update CRT fd 0: open_osfhandle wraps the Win32 handle as a CRT fd,
    # then dup2 copies it into fd 0 (which sys.__stdin__ uses via fileno()).
    tty_fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    os.dup2(tty_fd, 0)
    os.close(tty_fd)

    # Update the process-level standard input handle (used by
    # ReadConsoleInputW, which Textual's Win32 driver calls for arrow keys).
    new_handle = msvcrt.get_osfhandle(0)
    kernel32.SetStdHandle(STD_INPUT_HANDLE, new_handle)

    # Enable VT input mode for ConPTY terminals (VS Code, Windows Terminal)
    # so arrow keys arrive as ESC sequences instead of being swallowed.
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(new_handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(
            new_handle, mode.value | ENABLE_VIRTUAL_TERMINAL_INPUT
        )


def _restore_console_unix() -> None:
    """Replace fd 0 with /dev/tty so Textual gets keyboard input."""
    tty_fd = os.open("/dev/tty", os.O_RDONLY)
    os.dup2(tty_fd, 0)
    os.close(tty_fd)


def _make_docker_source(container: str) -> LogSource:
    try:
        from logwise.sources.docker_source import DockerSource
    except ImportError:
        typer.echo(
            "Error: docker support requires the docker extra.\n"
            "Install with: pip install logwise[docker]",
            err=True,
        )
        raise typer.Exit(code=2)
    return DockerSource(container)


def _pick_source(
    file: Path | None, docker: str | None, pipe_tmp: Path | None
) -> LogSource:
    if file is not None:
        if not file.is_file():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(code=2)
        if not os.access(file, os.R_OK):
            typer.echo(f"Error: file not readable: {file}", err=True)
            raise typer.Exit(code=2)
        return FileSource(file)
    if docker is not None:
        return _make_docker_source(docker)
    if pipe_tmp is not None:
        return FileSource(pipe_tmp)
    typer.echo(
        "Error: no source. Pass --file PATH, --docker CONTAINER, or pipe stdin "
        "(e.g. `kubectl logs ... | logwise`).",
        err=True,
    )
    raise typer.Exit(code=2)


def _pick_parser(choice: FormatChoice) -> Parser:
    if choice is FormatChoice.json:
        return JSONParser()
    if choice is FormatChoice.nginx:
        return NginxParser()
    if choice is FormatChoice.plain:
        return PlainParser()
    return AutoDetector(parsers=[JSONParser(), NginxParser(), PlainParser()])


@app.callback(invoke_without_command=True)
def main(
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Path to the log file to tail."),
    ] = None,
    docker: Annotated[
        str | None,
        typer.Option("--docker", "-d", help="Docker container name or ID to tail."),
    ] = None,
    max_lines: Annotated[
        int,
        typer.Option("--max-lines", help="Ring buffer capacity (oldest lines drop)."),
    ] = 10_000,
    format_: Annotated[
        FormatChoice,
        typer.Option(
            "--format",
            help="Log format. 'auto' sniffs the first 10 lines.",
        ),
    ] = FormatChoice.auto,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Write logwise.debug.log in cwd."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Tail a log source and display it in a colored TUI."""
    if max_lines < 1:
        typer.echo("Error: --max-lines must be >= 1.", err=True)
        raise typer.Exit(code=2)

    if debug:
        logging.basicConfig(
            filename="logwise.debug.log",
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    pipe_tmp = _drain_pipe_to_tempfile() if file is None and docker is None else None
    source = _pick_source(file, docker, pipe_tmp)
    parser = _pick_parser(format_)
    LogWiseApp(source=source, parser=parser, max_lines=max_lines).run()

    if pipe_tmp is not None:
        pipe_tmp.unlink(missing_ok=True)
