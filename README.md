# LogWise

An AI-powered log intelligence TUI for files, Docker, and stdin — packaged so any developer can `pip install logwise` and start triaging logs in seconds.

> **Status:** v0.3.0a1 alpha. W2b adds Docker container log streaming. W2a ships format-aware parsers. W1.1 polishes the source layer. AI features land in W3.

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

# tail a Docker container
uv run logwise --docker my-container

# (requires: pip install logwise[docker])

# force a parser
uv run logwise --format json --file app.log
uv run logwise --format nginx --file access.log
```

Press `q` to quit (when running in file mode; piped mode requires Ctrl+C).

## Roadmap

- W2c: stats bar (events/sec, error % in last 60s)
- W3: LiteLLM integration, AI explain panel (press E on a line)
- W4: NL filter, anomaly detection, journald
- W5: search, multi-file panes, snapshot tests
- W6: PyPI publish, GitHub Actions CI

## Development

```bash
uv run pytest         # 41 tests
uv run logwise --debug --file app.log    # writes logwise.debug.log
```

MIT licensed.
