# LogWise

An AI-powered log intelligence TUI for files, Docker, and stdin — packaged so any developer can `pip install logwise` and start triaging logs in seconds.

> **Status:** v0.2.0a1 alpha. W2a ships format-aware parsers on top of W1's core TUI. AI features land in W3.

## What it does today

- **Tails a log file or stdin** and renders lines in a live, color-coded Textual TUI.
- **Format-aware parsing** — auto-detects JSON / nginx / plain text from the first 10 lines and parses accordingly. Override with `--format {auto,json,nginx,plain}`.
- **Python tracebacks merge into one row** — the full stack lives in the entry's raw text; the table shows the exception line.
- **Level coloring:** ERROR red, WARN yellow, FATAL/CRITICAL/PANIC bold red, DEBUG dim, INFO default.
- **JSON-aware levels:** `{"level":"info","msg":"user reported error"}` correctly colors INFO (no W1-style false positive).
- **nginx access logs:** 4xx rows yellow, 5xx rows red, message column shows `METHOD PATH STATUS`.
- **Bounded ring buffer** — default 10 000 lines, configurable via `--max-lines`.
- **Cross-platform:** Linux, macOS, Windows.

### Known limitations

- Auto-detection sniff window emits the first 10 lines via keyword-level fallback before locking the chosen parser; properly-parsed rendering kicks in from line 11. Use `--format json|nginx|plain` to skip the sniff.
- Custom nginx log formats (non-combined) are not parsed; they fall back to keyword-level classification.
- Rename-style log rotation (logrotate's default `create` mode) is not handled — restart logwise after rotation. (W1.1 polish.)
- On Windows, the FileSource holds an exclusive read lock; external writers may fail to append while logwise tails. (W1.1 polish.)
- Piping into logwise (`tail -f log | logwise`) traps keyboard input — use Ctrl+C to quit. (W1.1 polish.)
- No AI yet. That's W3.

## Install

```bash
uv sync --extra dev
uv run logwise --help
```

## Use

```bash
# tail a file (live tail from end of file)
uv run logwise --file app.log

# pipe content
kubectl logs -f my-pod | uv run logwise
tail -f /var/log/syslog | uv run logwise

# force a parser
uv run logwise --format json --file app.log
uv run logwise --format nginx --file access.log
```

Press `q` to quit (when running in file mode; piped mode requires Ctrl+C).

## Roadmap

- W1.1: file-locking + stdin-pipe-keyboard + rename-rotation polish
- W2b: Docker source (logwise --docker my-container)
- W2c: stats bar (events/sec, error % in last 60s)
- W3: LiteLLM integration, AI explain panel (press E on a line)
- W4: NL filter, anomaly detection, journald
- W5: search, multi-file panes, snapshot tests
- W6: PyPI publish, GitHub Actions CI

## Development

```bash
uv run pytest         # 34 tests
uv run logwise --debug --file app.log    # writes logwise.debug.log
```

MIT licensed.
