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


def install_id_file() -> Path:
    return state_dir() / "install_id"
