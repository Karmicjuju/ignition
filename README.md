# Ignition

A terminal-native developer onboarding and workspace command centre for the Reactor ecosystem.

## Status

**Pre-alpha.** Milestone 0 scaffolding — a minimal Textual app that boots, reads/writes state, and quits cleanly. Product features land in subsequent milestones (see [docs/product/prd.md](docs/product/prd.md)).

## Quick start (development)

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.14+.

```bash
uv sync
uv run ignition
```

Other flags:

```bash
uv run ignition --demo      # launch with seeded demo state
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
