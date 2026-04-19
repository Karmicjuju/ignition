from __future__ import annotations

from ignition.core.logging import get_logger
from ignition.core.paths import config_file
from ignition.schemas.config import AppConfigModel


def load_config() -> AppConfigModel:
    """Load config from config_file(), return defaults if absent."""
    log = get_logger("ignition.core.config")
    path = config_file()
    if path.exists():
        try:
            config = AppConfigModel.model_validate_json(path.read_text(encoding="utf-8"))
            log.info("config.loaded", path=str(path))
            return config
        except Exception as exc:
            log.warning("config.load_failed", reason=str(exc), path=str(path))
    return AppConfigModel()


def save_config(config: AppConfigModel) -> None:
    """Persist config to config_file() as JSON."""
    log = get_logger("ignition.core.config")
    path = config_file()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    log.info("config.saved", path=str(path))
