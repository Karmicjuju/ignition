from __future__ import annotations

from pathlib import Path

from platformdirs import PlatformDirs

_DIRS = PlatformDirs(appname="ignition", appauthor=False)


def config_dir() -> Path:
    path = Path(_DIRS.user_config_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir() -> Path:
    path = Path(_DIRS.user_state_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = state_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_file() -> Path:
    return state_dir() / "state.json"


def activity_file() -> Path:
    return state_dir() / "activity.json"


def install_id_file() -> Path:
    return state_dir() / "install_id"


def cache_dir() -> Path:
    path = Path(_DIRS.user_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_cache_dir() -> Path:
    path = cache_dir() / "catalog"
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_override_dir() -> Path:
    # intentionally does NOT mkdir — its existence is the opt-in signal
    return config_dir() / "catalog" / "tools"


def config_file() -> Path:
    return config_dir() / "config.json"


# --- AWS CLI well-known paths -------------------------------------------------
# These are NOT Ignition application directories; they are dictated by the AWS
# CLI specification (always rooted at ~/.aws). Centralised here so callers in
# core/ never construct `Path.home() / ".aws" / ...` directly — which simplifies
# test mocking and gives a single point to override via env (future work).


def aws_dir() -> Path:
    return Path.home() / ".aws"


def aws_config_file() -> Path:
    return aws_dir() / "config"


def aws_credentials_file() -> Path:
    return aws_dir() / "credentials"


def aws_sso_cache_dir() -> Path:
    return aws_dir() / "sso" / "cache"
