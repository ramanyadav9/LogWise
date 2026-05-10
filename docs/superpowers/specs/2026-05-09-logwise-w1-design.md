# LogWise W1 — Design Spec

**Status:** approved 2026-05-09
**Scope:** Week 1 only (file/stdin tail + colored TUI). W2–W6 get their own specs.
**Target release:** v0.1.0a1 (alpha — local install only, no PyPI yet)

---

## 1. Goal & boundaries

### What the user can do at the end of W1

```
logwise --file app.log
kubectl logs -f my-pod | logwise
tail -f /var/log/syslog | logwise
```

Each of those opens a live, scrolling, color-coded log table in the terminal.

### Ships in W1

- Typer CLI: `--file PATH`, `--max-lines N`, `--debug`, `--version`
- Stdin auto-detected via `sys.stdin.isatty()` — no flag needed
- `LogSource` ABC with two implementations: `FileSource`, `StdinSource`
- `LogEntry` dataclass with exactly three fields: `timestamp`, `level`, `raw`
- `quick_level()` — ~15-line regex-based level extractor (W1-only; deleted in W2)
- `RingBuffer` — bounded `deque`, default 10 000 lines, overridable via `--max-lines`
- Textual `App` with one `DataTable`, rows colored by level via Rich markup
- Pytest suite for `quick_level`, `RingBuffer`, `FileSource`
- `pyproject.toml` (uv toolchain), Python 3.11+, MIT license, console-script entry point

### Explicitly NOT in W1

| Deferred to | Item |
|---|---|
| W2 | Format-aware parsers (JSON / nginx / syslog / Python tracebacks) |
| W2 | DockerSource |
| W2 | Stats bar (events/sec, error %) |
| W3 | LiteLLM client, AI explain panel, system prompts |
| W4 | NL filter modal, anomaly detection, journaldSource |
| W5 | Pause/resume, search, multi-file panes, export, snapshot tests |
| W6 | PyPI publish, GitHub Actions, README GIF |

### Done definition

1. `uv run logwise --file <path>` opens a TUI showing live tail with colored rows.
2. Piping stdin works without flags on Linux, Mac, and Windows.
3. `uv run pytest` passes locally on Windows + Linux.
4. README has a one-paragraph "what it does today" + a screenshot or asciinema cast.

---

## 2. Architecture

### Module layout

```
logwise/                          # repo root
├── pyproject.toml                # uv + Typer entry: logwise = "logwise.cli:app"
├── README.md
├── logwise/                      # the package
│   ├── __init__.py               # __version__
│   ├── __main__.py               # python -m logwise → cli.app()
│   ├── cli.py                    # Typer: --file, --max-lines, --debug, --version
│   ├── core/
│   │   ├── log_entry.py          # @dataclass LogEntry (timestamp, level, raw)
│   │   ├── log_level.py          # LogLevel enum
│   │   ├── quick_level.py        # quick_level(line) → LogLevel  (W1-only)
│   │   └── ring_buffer.py        # RingBuffer(maxlen) wrapping deque
│   ├── sources/
│   │   ├── base.py               # class LogSource(ABC); async def stream()
│   │   ├── file_source.py        # FileSource(path) — aiofiles polling tail
│   │   └── stdin_source.py       # StdinSource() — async stdin reader
│   └── app/
│       ├── main_app.py           # LogWiseApp(App) — wires source → buffer → table
│       └── log_table.py          # LogTable(DataTable) — colored row rendering
└── tests/
    ├── test_quick_level.py
    ├── test_ring_buffer.py
    └── test_file_source.py
```

### Dependency direction (one-way, no cycles)

```
cli.py  →  app/  →  sources/  →  core/
                ↘             ↗
                  core/  ←──
```

- `core/` depends on nothing internal — pure data + pure functions, importable from script/test/future-non-TUI mode.
- `sources/` depends only on `core/` — zero Textual knowledge. `LogSource.stream()` is a pure `AsyncIterator[LogEntry]`. **Adding `DockerSource` in W2 is one new file in `sources/` and zero changes elsewhere.**
- `app/` is the only place Textual is imported.
- `cli.py` is the wiring layer: parse flags → pick source → construct app → run.

### What we deliberately do NOT scaffold in W1

The detailed structure tree from the original brainstorm includes `parsers/`, `ai/`, `screens/`, `widgets/`. **None of these are created in W1.** Empty stub folders signal "incomplete project" to anyone browsing the GitHub repo. Folders are added when their first real file is needed.

---

## 3. Data flow & async lifecycle

### The single async path

```
       ┌─────────────────┐
       │ cli.py          │   parse flags, pick source instance
       └────────┬────────┘
                │  pass source into LogWiseApp(source)
                ▼
       ┌─────────────────┐
       │ app/main_app.py │   on_mount() spawns one @work task:
       │   LogWiseApp    │
       │                 │   async for entry in self.source.stream():
       │   - buffer      │       self.buffer.append(entry)        ← O(1) deque write
       │   - table       │       self.log_table.add_entry(entry)  ← Textual call
       └─────────────────┘
                ▲
                │  yields LogEntry
       ┌────────┴────────┐
       │ sources/        │   FileSource.stream() | StdinSource.stream()
       └─────────────────┘
```

### LogWiseApp consumer

```python
# app/main_app.py
class LogWiseApp(App):
    def __init__(self, source: LogSource, max_lines: int = 10_000):
        super().__init__()
        self.source = source
        self.buffer = RingBuffer(maxlen=max_lines)
        self.log_table = LogTable()

    def compose(self) -> ComposeResult:
        yield self.log_table

    @work(exclusive=True)
    async def _consume(self) -> None:
        try:
            async for entry in self.source.stream():
                self.buffer.append(entry)
                self.log_table.add_entry(entry)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.log_table.add_error_row(
                f"[logwise] source error: {type(e).__name__}: {e}"
            )

    def on_mount(self) -> None:
        self._consume()
```

`@work` runs on Textual's event loop, so `add_entry` is already on the UI thread — no `call_from_thread` needed. App exit cancels the worker, which cancels the source's stream, which closes the underlying file handle via the `async with` context manager.

### FileSource — polling tail

```python
class FileSource(LogSource):
    def __init__(self, path: Path, poll_interval: float = 0.1):
        self.path = path
        self.poll = poll_interval

    async def stream(self) -> AsyncIterator[LogEntry]:
        async with aiofiles.open(self.path, mode="r", errors="replace") as f:
            await f.seek(0, os.SEEK_END)
            while True:
                line = await f.readline()
                if line:
                    yield _to_entry(line)
                else:
                    # truncation check (file shrunk under us, e.g. `> log.txt`)
                    if await f.tell() > os.path.getsize(self.path):
                        await f.seek(0)
                    await asyncio.sleep(self.poll)
```

Polling at 100 ms — not OS-level inotify. **Why:** aiofiles is already in the stack, polling is identical on Windows + Linux + Mac, 100 ms latency is invisible to a human watching a TUI, and it sidesteps `watchdog`'s sync→async bridge complexity. If a future user reports CPU on a quiet log, we swap to `watchfiles` later — `LogSource` absorbs the change.

### StdinSource — Linux/Mac happy path + Windows fallback

```python
class StdinSource(LogSource):
    async def stream(self) -> AsyncIterator[LogEntry]:
        if sys.platform == "win32":
            async for line in self._stream_threaded():
                yield line
        else:
            async for line in self._stream_pipe():
                yield line

    async def _stream_pipe(self) -> AsyncIterator[LogEntry]:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
        )
        while not reader.at_eof():
            line = await reader.readline()
            if line:
                yield _to_entry(line.decode(errors="replace"))

    async def _stream_threaded(self) -> AsyncIterator[LogEntry]:
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return
            yield _to_entry(line)
```

The Windows branch is required because `connect_read_pipe` on stdin doesn't work on Windows.

### Backpressure

None in W1. If the source produces faster than the table renders, `add_entry` calls queue up in Textual's event loop. The ring buffer caps memory regardless. If this becomes a real problem in W3 we add an `asyncio.Queue` between source and consumer; YAGNI for now.

### Shutdown

Ctrl-C → Textual catches it → app exits → `@work` is cancelled → `async for` raises `CancelledError` → aiofiles context manager closes cleanly. Exit code 0.

---

## 4. Error handling

### Boundary failures (must handle)

| Failure | Where | Behavior |
|---|---|---|
| `--file` path doesn't exist | `cli.py` before app starts | Print `Error: file not found: <path>` to stderr, exit code 2. No TUI. |
| `--file` path exists but unreadable (perms) | `cli.py`, `os.access` check | Same as above. |
| File truncated mid-tail (`> log.txt`) | `FileSource.stream()` | After `readline()` returns empty, if `f.tell() > os.path.getsize(path)` → `seek(0)` and continue. Same handle, same inode. |
| File rename-rotated (`logrotate`'s default `create` mode) | `FileSource.stream()` | **Known W1 limitation** — handle keeps reading the renamed file, no new lines appear. Document in README; full rotation handling lands in W2 alongside multi-source work. |
| File deleted mid-tail | `FileSource.stream()` | aiofiles raises on next read → emit a single `[logwise] file disappeared, exiting` row to the buffer, raise `StopAsyncIteration`. App stays open; user reads the message, then Ctrl-C. |
| Non-UTF8 bytes in stream | both sources | Decode with `errors="replace"`. A glyph glitch is better than a crash. |
| Stdin pipe closed (upstream `kubectl` exited) | `StdinSource.stream()` | `at_eof()` → return cleanly. App stays open; user reads, then Ctrl-C. |
| Terminal too narrow for DataTable | Textual handles | Auto-wraps; no code needed. |

### Inside the worker loop

The `_consume` worker wraps its `async for` in `try/except`:
- `asyncio.CancelledError` → re-raise (graceful shutdown).
- Any other exception → render as an error row in the table (styling decided in implementation plan); do **not** re-raise. TUI stays alive so the user can see what failed.

### Deliberate non-goals

- Concurrent writers racing the tail. Not a real-world problem for log tailing.
- Recovery after `--file` is recreated post-deletion. Re-run the command.
- Encoding sniffing. UTF-8-replace covers the realistic cases.
- `quick_level()` validation. It always returns a `LogLevel`; a non-matching line is `INFO`. By design — never raises.
- Ring buffer overflow signal. Bounded `deque(maxlen=N)` *is* the policy — oldest line drops silently.

### Internal logging

`--debug` writes a `logwise.debug.log` file in cwd via stdlib `logging`. Off by default. **No `print()` calls anywhere in the package** — they corrupt the TUI rendering.

---

## 5. Testing

Three test files, ~25 cases, all run in <1 second. Pure-logic only — Textual stays untested in W1.

### `tests/test_quick_level.py`

Pin every coloring decision the TUI makes:

```python
@pytest.mark.parametrize("line, expected", [
    ("[ERROR] connection refused",          LogLevel.ERROR),
    ('{"level":"error","msg":"boom"}',      LogLevel.ERROR),
    ("2026-05-09 ERROR app.py:42 boom",     LogLevel.ERROR),
    ("WARN: cache miss",                    LogLevel.WARNING),
    ("FATAL: out of memory",                LogLevel.FATAL),
    ("CRITICAL: disk full",                 LogLevel.FATAL),
    ("PANIC: goroutine leak",               LogLevel.FATAL),
    ("DEBUG req.id=abc",                    LogLevel.DEBUG),
    ("plain info message",                  LogLevel.INFO),
    ("",                                    LogLevel.INFO),
    ("user reported error in form",         LogLevel.ERROR),  # documented W1 false-positive
])
def test_quick_level(line, expected):
    assert quick_level(line) is expected
```

The "user reported error in form" case is asserted as `ERROR` deliberately — it documents the W1 limitation. When W2 ships proper parsers, this test gets deleted along with `quick_level.py`.

### `tests/test_ring_buffer.py`

Overflow + ordering only:

```python
def test_appends_in_order():
    rb = RingBuffer(maxlen=3)
    for i in range(3): rb.append(_entry(i))
    assert [e.raw for e in rb] == ["0", "1", "2"]

def test_drops_oldest_on_overflow():
    rb = RingBuffer(maxlen=3)
    for i in range(5): rb.append(_entry(i))
    assert [e.raw for e in rb] == ["2", "3", "4"]

def test_len_reports_current_size():
    rb = RingBuffer(maxlen=10)
    for i in range(4): rb.append(_entry(i))
    assert len(rb) == 4
```

### `tests/test_file_source.py`

The only async test. Real temp file, real polling:

```python
async def test_streams_appended_lines(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("")
    src = FileSource(log, poll_interval=0.01)

    received: list[LogEntry] = []
    async def collect():
        async for e in src.stream():
            received.append(e)
            if len(received) == 2: break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    log.write_text("first\nsecond\n")
    await asyncio.wait_for(task, timeout=1.0)

    assert [e.raw.strip() for e in received] == ["first", "second"]
```

### Not tested in W1 — and why

- **`LogWiseApp` rendering** — Textual snapshot tests are slow + Windows-flaky for low ROI on a one-person project. Manual smoke-test instead.
- **`StdinSource`** — Windows + Unix pipe behavior differs enough that a unit test would mostly exercise asyncio plumbing, not our code. Manual smoke-test (`echo hi | logwise`) on each OS.
- **`quick_level` regex performance** — premature.

### CI

None in W1. CI lands in W6 alongside the PyPI publish workflow. Tests run locally with `uv run pytest`.

### Coverage target

No number. Target is "every code path in `core/` is exercised at least once." Coverage badges are W6 vanity.

---

## 6. Open questions for the implementation plan

These are deliberately not answered in this spec — they're tactical and belong in the writing-plans handoff:

- Exact ordering of files/commits across W1's working days
- pyproject.toml dependency pins (latest stable for uv/Typer/Textual/aiofiles/Rich)
- Whether `LogTable.add_error_row` reuses the FATAL color or gets its own style
- Whether `--max-lines 0` means "unlimited" or is rejected at CLI parse time
