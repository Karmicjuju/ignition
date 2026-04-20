# Ignition

A terminal-native developer onboarding and workspace command centre for the Reactor ecosystem.

## Status

**Pre-alpha.** Current feature set: onboarding wizard, status dashboard, tool catalog, health diagnostics, and settings.

## Quick start (development)

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.14+.

```bash
./scripts/bootstrap.sh      # installs deps + all git hooks
uv run ignition
```

`bootstrap.sh` runs `uv sync` and installs both `pre-commit` and
`commit-msg` hooks in one step. Run it once per clone.

Other flags:

```bash
uv run ignition --demo      # launch with seeded demo state
uv run ignition --version   # print version and exit
```

## Checks

```bash
uv run ruff check
uv run ruff format --check
uv run ty check src/ignition/core
uv run pytest
```

## Supported platforms

v0.1 targets **macOS** and **Linux (Ubuntu/Debian)**. Other Linux distributions and Windows are out of scope for the first release.

## Documentation

See [docs/](docs/) for product requirements, UX spec, design system, technical architecture, operations model and demo strategy. Project-wide agent guidance lives in [CLAUDE.md](CLAUDE.md).

## License

[GPL-3.0-only](LICENSE).
