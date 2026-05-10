"""Typer CLI — parse flags, pick a source, run the TUI."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from logwise import __version__
from logwise.app.main_app import LogWiseApp
from logwise.sources.base import LogSource
from logwise.sources.file_source import FileSource
from logwise.sources.stdin_source import StdinSource

app = typer.Typer(
    name="logwise",
    help="AI-powered log intelligence TUI (W1: file/stdin tail with colored rows).",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"logwise {__version__}")
        raise typer.Exit()


def _pick_source(file: Path | None) -> LogSource:
    if file is not None:
        if not file.is_file():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(code=2)
        if not os.access(file, os.R_OK):
            typer.echo(f"Error: file not readable: {file}", err=True)
            raise typer.Exit(code=2)
        return FileSource(file)
    if not sys.stdin.isatty():
        return StdinSource()
    typer.echo(
        "Error: no source. Pass --file PATH or pipe stdin "
        "(e.g. `kubectl logs ... | logwise`).",
        err=True,
    )
    raise typer.Exit(code=2)


@app.callback(invoke_without_command=True)
def main(
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Path to the log file to tail."),
    ] = None,
    max_lines: Annotated[
        int,
        typer.Option("--max-lines", help="Ring buffer capacity (oldest lines drop)."),
    ] = 10_000,
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

    source = _pick_source(file)
    LogWiseApp(source=source, max_lines=max_lines).run()
