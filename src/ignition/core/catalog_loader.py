from __future__ import annotations

import importlib.resources
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ignition.core.logging import get_logger
from ignition.schemas.catalog import ToolInfo


def load_local_override(override_dir: Path) -> list[ToolInfo] | None:
    """Return tools from override_dir, or None if dir absent or empty."""
    log = get_logger("ignition.core.catalog_loader")

    if not override_dir.exists():
        return None

    yaml = YAML(typ="safe")
    tools: list[ToolInfo] = []

    for yaml_file in sorted(override_dir.glob("*.yaml")):
        try:
            raw = yaml.load(yaml_file.read_text(encoding="utf-8"))
            tool = ToolInfo.model_validate(raw)
            tools.append(tool)
        except Exception as exc:
            log.warning(
                "catalog.override.parse_error",
                file=str(yaml_file),
                reason=str(exc),
            )

    if not tools:
        return None

    log.info("catalog.override.loaded", count=len(tools))
    return tools


def load_bundled() -> list[ToolInfo]:
    """Load tools from bundled package data. Never returns None."""
    log = get_logger("ignition.core.catalog_loader")

    yaml = YAML(typ="safe")
    tools: list[ToolInfo] = []

    package_ref = importlib.resources.files("ignition.data.catalog.tools")
    for resource in sorted(
        package_ref.iterdir(),  # type: ignore[attr-defined]
        key=lambda r: r.name,
    ):
        if not resource.name.endswith(".yaml"):
            continue
        try:
            raw = yaml.load(resource.read_text(encoding="utf-8"))
            tool = ToolInfo.model_validate(raw)
            tools.append(tool)
        except Exception as exc:
            log.warning(
                "catalog.bundled.parse_error",
                file=resource.name,
                reason=str(exc),
            )

    if not tools:
        raise RuntimeError(
            "Bundled catalog contains zero valid tool definitions — package may be corrupt."
        )

    log.info("catalog.bundled.loaded", count=len(tools))
    return tools


def load_remote(
    catalog_url: str,
    cache_dir: Path,
    max_age_seconds: int,
) -> list[ToolInfo] | None:
    """Fetch catalog-index.yaml from catalog_url with ETag caching.

    Returns None on any failure.
    """
    log = get_logger("ignition.core.catalog_loader")

    cache_file = cache_dir / "catalog-index.yaml"
    meta_file = cache_dir / "catalog-index.meta.json"

    # Load existing meta (etag + fetched_at) if present.
    etag: str | None = None
    fetched_at: datetime | None = None
    if meta_file.exists():
        try:
            meta: dict[str, Any] = json.loads(meta_file.read_text(encoding="utf-8"))
            raw_ts: str | None = meta.get("fetched_at")
            etag = meta.get("etag") or None
            if raw_ts:
                fetched_at = datetime.fromisoformat(raw_ts)
        except Exception:
            pass

    # Check freshness — if cache is within max_age, parse and return cached file.
    now = datetime.now(UTC)
    if (
        cache_file.exists()
        and fetched_at is not None
        and (now - fetched_at).total_seconds() < max_age_seconds
    ):
        return _parse_remote_cache(cache_file, log)

    # Attempt HTTP fetch.
    try:
        req = urllib.request.Request(catalog_url)
        if etag:
            req.add_header("If-None-Match", etag)

        with urllib.request.urlopen(req, timeout=10) as resp:
            status: int = resp.status
            new_etag: str | None = resp.headers.get("ETag")

            if status == 304:
                # Not modified — bump fetched_at and return cached content.
                _write_meta(meta_file, now, etag)
                return _parse_remote_cache(cache_file, log)

            if status == 200:
                body: bytes = resp.read()
                cache_file.write_bytes(body)
                _write_meta(meta_file, now, new_etag)
                return _parse_remote_cache(cache_file, log)

            log.warning(
                "catalog.remote.failed",
                reason=f"unexpected HTTP status {status}",
                url=catalog_url,
            )
            return None

    except Exception as exc:
        log.warning(
            "catalog.remote.failed",
            reason=str(exc),
            url=catalog_url,
        )
        return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _write_meta(meta_file: Path, fetched_at: datetime, etag: str | None) -> None:
    payload: dict[str, Any] = {
        "fetched_at": fetched_at.isoformat(),
        "etag": etag,
    }
    meta_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_remote_cache(cache_file: Path, log: Any) -> list[ToolInfo] | None:
    yaml = YAML(typ="safe")
    try:
        raw: dict[str, Any] = yaml.load(cache_file.read_text(encoding="utf-8"))
        entries: list[Any] = raw.get("tools", [])
        tools: list[ToolInfo] = []
        for entry in entries:
            try:
                tools.append(ToolInfo.model_validate(entry))
            except Exception as exc:
                log.warning(
                    "catalog.remote.entry_parse_error",
                    reason=str(exc),
                )
        return tools if tools else None
    except Exception as exc:
        log.warning(
            "catalog.remote.failed",
            reason=f"cache parse error: {exc}",
        )
        return None
