# LogWise

An AI-powered log intelligence TUI for files, Docker, and stdin — packaged so any developer can `pip install logwise` and start triaging logs in seconds.

> **Status:** v0.1.0a1 alpha. W1 ships the core TUI: file/stdin tail with colored rows. AI features land in W3–W4.

## What it does today (W1)

- Tails a log file or stdin and renders lines in a live, color-coded Textual TUI.
- ERROR rows are red, WARN amber, FATAL/CRITICAL/PANIC bold red, DEBUG dim.
- Bounded in-memory ring buffer (default 10 000 lines).
- Recovers from file truncation (`> log.txt`).
- Cross-platform: Linux, macOS, Windows.

### Known W1 limitations

- Level detection uses keyword search, so `"user reported error in form"` is colored as ERROR. Format-aware parsers (W2) will fix this.
- Rename-style log rotation (logrotate's default `create` mode) is not yet handled — restart logwise after rotation.
- No AI yet. That's W3.

## Install

```bash
# from a checkout
uv sync --extra dev
uv run logwise --help
```

## Use

```bash
# tail a file
uv run logwise --file app.log

# pipe from anything
kubectl logs -f my-pod | uv run logwise
tail -f /var/log/syslog | uv run logwise
```

Press `q` to quit.

## Roadmap

- W2: format-aware parsers, Docker source, stats bar
- W3: LiteLLM integration, AI explain panel (press `E` on a line)
- W4: NL filter, anomaly detection, journald
- W5: search, multi-file panes, snapshot tests
- W6: PyPI publish, GitHub Actions CI

## Development

```bash
uv run pytest         # run tests
uv run logwise --debug --file app.log    # write internals to logwise.debug.log
```

MIT licensed.
