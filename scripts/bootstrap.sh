#!/usr/bin/env bash
# One-shot developer setup for Ignition.
# Installs dependencies, wires up all git hooks, and verifies the toolchain.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is not installed." >&2
    echo "hint: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

echo "==> Syncing dependencies (uv sync)"
uv sync

echo "==> Installing git hooks (pre-commit + commit-msg)"
uv run pre-commit install

echo
echo "Bootstrap complete. Try:"
echo "  uv run ignition          # launch the TUI"
echo "  uv run ignition --demo   # launch with seeded demo state"
echo "  uv run pytest            # run the test suite"
