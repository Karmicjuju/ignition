from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all XDG paths into a per-test temp directory."""
    state = tmp_path / "state"
    config = tmp_path / "config"
    logs = state / "logs"
    cache = tmp_path / "cache"
    catalog_cache = cache / "catalog"
    for p in (state, config, logs, cache, catalog_cache):
        p.mkdir(parents=True, exist_ok=True)

    from ignition.core import paths as paths_mod

    monkeypatch.setattr(paths_mod, "state_dir", lambda: state)
    monkeypatch.setattr(paths_mod, "config_dir", lambda: config)
    monkeypatch.setattr(paths_mod, "log_dir", lambda: logs)
    monkeypatch.setattr(paths_mod, "state_file", lambda: state / "state.json")
    monkeypatch.setattr(paths_mod, "activity_file", lambda: state / "activity.json")
    monkeypatch.setattr(paths_mod, "install_id_file", lambda: state / "install_id")
    monkeypatch.setattr(paths_mod, "cache_dir", lambda: cache)
    monkeypatch.setattr(paths_mod, "catalog_cache_dir", lambda: catalog_cache)

    # Redirect AWS CLI well-known paths into the per-test temp tree.
    # Tests that need to assert on AWS file content can write to
    # `tmp_path / ".aws" / ...` directly.
    aws = tmp_path / ".aws"
    sso_cache = aws / "sso" / "cache"
    monkeypatch.setattr(paths_mod, "aws_dir", lambda: aws)
    monkeypatch.setattr(paths_mod, "aws_config_file", lambda: aws / "config")
    monkeypatch.setattr(paths_mod, "aws_credentials_file", lambda: aws / "credentials")
    monkeypatch.setattr(paths_mod, "aws_sso_cache_dir", lambda: sso_cache)

    # Reset the structlog-configured sentinel so the file handler re-binds per test.
    from ignition.core import logging as logging_mod

    monkeypatch.setattr(logging_mod, "_configured", False)

    return tmp_path
