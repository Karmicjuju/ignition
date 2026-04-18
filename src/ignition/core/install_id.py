from __future__ import annotations

import uuid

from ignition.core.paths import install_id_file


def get_or_create_install_id() -> str:
    path = install_id_file()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = str(uuid.uuid4())
    path.write_text(value, encoding="utf-8")
    return value
