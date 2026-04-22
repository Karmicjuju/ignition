#!/usr/bin/env bash
# Install Ignition for end users.
# Supports two modes:
#   Online:  downloads from TestPyPI (falls back to PyPI)
#   Offline: installs from a vendor/ bundle directory alongside this script
set -euo pipefail

TESTPYPI_INDEX="https://test.pypi.org/simple/"
PYPI_INDEX="https://pypi.org/simple/"
MIN_PYTHON_MINOR=14

_check_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "error: Python 3.${MIN_PYTHON_MINOR}+ is required but python3 was not found." >&2
        echo "hint: https://www.python.org/downloads/" >&2
        exit 1
    fi
    local ver major minor
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt "$MIN_PYTHON_MINOR" ]; }; then
        echo "error: Python 3.${MIN_PYTHON_MINOR}+ required (found ${ver})." >&2
        exit 1
    fi
}

_ensure_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "==> uv not found — installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # Attempt to make uv available in the current shell
        export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
        if ! command -v uv >/dev/null 2>&1; then
            echo "error: uv was installed but could not be found on PATH." >&2
            echo "hint: Open a new terminal and re-run this script." >&2
            exit 1
        fi
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Offline mode ────────────────────────────────────────────────────────────
if [ -d "${SCRIPT_DIR}/vendor" ]; then
    echo "==> Offline bundle detected — installing from vendor/"
    _ensure_uv
    uv tool install --no-index --find-links "${SCRIPT_DIR}/vendor" ignition
    echo ""
    echo "Installation complete. Run: ignition"
    exit 0
fi

# ── Online mode ─────────────────────────────────────────────────────────────
_check_python
_ensure_uv

echo "==> Installing ignition..."

if uv tool install \
    --index-url "${TESTPYPI_INDEX}" \
    --extra-index-url "${PYPI_INDEX}" \
    ignition 2>/dev/null; then
    echo ""
    echo "Installation complete. Run: ignition"
    exit 0
fi

echo "==> TestPyPI unavailable — falling back to PyPI..."
uv tool install ignition

echo ""
echo "Installation complete. Run: ignition"
