#!/usr/bin/env bash
# Build an offline-installable vendor bundle.
# Output: dist/ignition-bundle-<version>.tar.gz
# Usage inside the bundle: tar xzf ignition-bundle-*.tar.gz && cd bundle && ./install.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required to build the bundle." >&2
    exit 1
fi

VERSION=$(uv run python -c "import importlib.metadata; print(importlib.metadata.version('ignition'))" 2>/dev/null \
    || grep '^version' pyproject.toml | head -1 | tr -d ' ' | cut -d= -f2 | tr -d '"')

BUNDLE_DIR="dist/bundle"
VENDOR_DIR="${BUNDLE_DIR}/vendor"

echo "==> Building ignition ${VERSION}"
uv build --wheel --out-dir dist/

echo "==> Preparing bundle directory"
rm -rf "${BUNDLE_DIR}"
mkdir -p "${VENDOR_DIR}"

echo "==> Exporting dependency requirements"
uv export --frozen --no-dev --no-emit-project -o "${BUNDLE_DIR}/requirements.txt"

echo "==> Downloading dependency wheels (python 3.14)"
uv pip download \
    --python-version 3.14 \
    --no-deps \
    -r "${BUNDLE_DIR}/requirements.txt" \
    -d "${VENDOR_DIR}"

# Re-download with full dep resolution so transitive deps are included
uv pip download \
    --python-version 3.14 \
    -r "${BUNDLE_DIR}/requirements.txt" \
    -d "${VENDOR_DIR}"

echo "==> Copying ignition wheel into vendor/"
cp dist/ignition-*.whl "${VENDOR_DIR}/"

echo "==> Writing bundle install script"
cat > "${BUNDLE_DIR}/install.sh" << 'INNER'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required. Install from: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi
echo "==> Installing ignition from offline bundle"
uv tool install --no-index --find-links "${SCRIPT_DIR}/vendor" ignition
echo ""
echo "Installation complete. Run: ignition"
INNER
chmod +x "${BUNDLE_DIR}/install.sh"

echo "==> Creating tarball"
TARBALL="dist/ignition-bundle-${VERSION}.tar.gz"
tar -czf "${TARBALL}" -C dist bundle/

echo ""
echo "Bundle ready: ${TARBALL}"
echo "To install offline:"
echo "  tar xzf ignition-bundle-${VERSION}.tar.gz"
echo "  cd bundle && ./install.sh"
