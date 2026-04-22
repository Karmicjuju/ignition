from __future__ import annotations

import json
from pathlib import Path

import pytest

from ignition.core.telemetry import _BUFFER_MAX, TelemetryBuffer
from ignition.schemas.config import AppConfigModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(enabled: bool = True) -> AppConfigModel:
    return AppConfigModel(telemetry_enabled=enabled)


def _make_buffer(enabled: bool = True) -> TelemetryBuffer:
    return TelemetryBuffer(config=_make_config(enabled))


def _patch_telemetry_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect TelemetryBuffer's state_dir and install_id_file to tmp_path.

    TelemetryBuffer uses `from ignition.core.paths import state_dir` which
    binds the function at import time — monkeypatching paths_mod alone is not
    enough. We must also patch the name as it appears in the telemetry module.
    """
    buf_state = tmp_path / "tel_state"
    buf_state.mkdir(parents=True, exist_ok=True)

    import ignition.core.install_id as iid_mod
    import ignition.core.telemetry as tel_mod

    monkeypatch.setattr(tel_mod, "state_dir", lambda: buf_state)
    monkeypatch.setattr(iid_mod, "install_id_file", lambda: buf_state / "install_id")
    return buf_state


# ---------------------------------------------------------------------------
# record() — enabled path
# ---------------------------------------------------------------------------


def test_record_writes_ndjson_when_enabled(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    buf_state = _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    buf.record("app_launched")

    buffer_file = buf_state / "telemetry_buffer.ndjson"
    assert buffer_file.exists(), "Buffer file should be created after record()"
    lines = [ln for ln in buffer_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, "Exactly one NDJSON line should be written"
    event = json.loads(lines[0])
    assert event["event_name"] == "app_launched"


# ---------------------------------------------------------------------------
# record() — disabled path
# ---------------------------------------------------------------------------


def test_record_noop_when_disabled(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    buf_state = _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=False)
    buf.record("app_launched")

    buffer_file = buf_state / "telemetry_buffer.ndjson"
    assert not buffer_file.exists(), "Buffer file must not be created when telemetry is disabled"


# ---------------------------------------------------------------------------
# Buffer cap enforcement
# ---------------------------------------------------------------------------


def test_buffer_max_cap_enforced(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    buf_state = _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    for i in range(_BUFFER_MAX + 1):
        buf.record(f"event_{i}")

    buffer_file = buf_state / "telemetry_buffer.ndjson"
    lines = [ln for ln in buffer_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == _BUFFER_MAX, (
        f"Buffer should be capped at {_BUFFER_MAX} lines, got {len(lines)}"
    )


# ---------------------------------------------------------------------------
# flush_pending()
# ---------------------------------------------------------------------------


def test_flush_pending_returns_events(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    names = ["alpha", "beta", "gamma"]
    for name in names:
        buf.record(name)

    events = buf.flush_pending()
    assert len(events) == 3, "flush_pending should return all 3 recorded events"
    returned_names = {e.event_name for e in events}
    assert returned_names == set(names)


def test_flush_pending_skips_malformed_lines(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    buf_state = _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)

    buffer_file = buf_state / "telemetry_buffer.ndjson"
    buffer_file.write_text("not valid json at all\n", encoding="utf-8")

    events = buf.flush_pending()
    assert events == [], "Malformed lines should be skipped; result should be empty list"


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


def test_clear_empties_buffer(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    buf.record("first_event")
    buf.record("second_event")

    buf.clear()

    events = buf.flush_pending()
    assert events == [], "After clear(), flush_pending() should return an empty list"


# ---------------------------------------------------------------------------
# install_id injection
# ---------------------------------------------------------------------------


def test_install_id_injected_automatically(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    buf.record("check_event")

    events = buf.flush_pending()
    assert len(events) == 1
    assert events[0].install_id, "install_id should be non-empty on recorded events"


# ---------------------------------------------------------------------------
# event_name preservation
# ---------------------------------------------------------------------------


def test_event_name_preserved(
    isolated_paths: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_telemetry_paths(monkeypatch, tmp_path)
    buf = _make_buffer(enabled=True)
    buf.record("my_specific_event_name")

    events = buf.flush_pending()
    assert len(events) == 1
    assert events[0].event_name == "my_specific_event_name"
