from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ignition.schemas.telemetry import TELEMETRY_SCHEMA_VERSION, TelemetryEvent


def test_telemetry_event_validates_with_required_fields() -> None:
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        install_id="test-install-abc123",
        event_name="app.started",
    )
    assert event.event_id is not None
    assert event.install_id == "test-install-abc123"
    assert event.event_name == "app.started"


def test_telemetry_event_schema_version_defaults_to_constant() -> None:
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        install_id="test-install-abc123",
        event_name="app.started",
    )
    assert event.schema_version == TELEMETRY_SCHEMA_VERSION
    assert TELEMETRY_SCHEMA_VERSION == 1


def test_telemetry_event_timestamp_defaults_to_utc_now() -> None:
    before = datetime.now(UTC)
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        install_id="test-install-abc123",
        event_name="app.started",
    )
    after = datetime.now(UTC)
    assert before <= event.timestamp <= after + timedelta(seconds=2)
    assert event.timestamp.tzinfo is not None


def test_telemetry_event_properties_defaults_to_empty_dict() -> None:
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        install_id="test-install-abc123",
        event_name="app.started",
    )
    assert event.properties == {}


def test_telemetry_event_rejects_missing_event_id() -> None:
    with pytest.raises(Exception):
        TelemetryEvent(  # type: ignore[call-arg]
            install_id="test-install-abc123",
            event_name="app.started",
        )


def test_telemetry_event_rejects_missing_install_id() -> None:
    with pytest.raises(Exception):
        TelemetryEvent(  # type: ignore[call-arg]
            event_id=str(uuid.uuid4()),
            event_name="app.started",
        )


def test_telemetry_event_rejects_missing_event_name() -> None:
    with pytest.raises(Exception):
        TelemetryEvent(  # type: ignore[call-arg]
            event_id=str(uuid.uuid4()),
            install_id="test-install-abc123",
        )


def test_telemetry_event_properties_accepts_arbitrary_types() -> None:
    event = TelemetryEvent(
        event_id=str(uuid.uuid4()),
        install_id="test-install-abc123",
        event_name="tool.installed",
        properties={
            "tool_name": "node",
            "exit_code": 0,
            "success": True,
            "error_message": None,
        },
    )
    assert event.properties["tool_name"] == "node"
    assert event.properties["exit_code"] == 0
    assert event.properties["success"] is True
    assert event.properties["error_message"] is None


def test_telemetry_event_schema_version_is_first_field() -> None:
    fields = list(TelemetryEvent.model_fields.keys())
    assert fields[0] == "schema_version"
