from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ignition.core.activity import _ACTIVITY_CAP, ActivityLog
from ignition.schemas.activity import EventType, Outcome

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_log() -> ActivityLog:
    return ActivityLog()


def _append_event(
    log: ActivityLog,
    *,
    event_type: EventType = EventType.TOOL_INSTALL,
    outcome: Outcome = Outcome.SUCCESS,
    summary: str = "Test event",
) -> None:
    log.append(event_type, outcome, summary)


# ---------------------------------------------------------------------------
# Append and persistence
# ---------------------------------------------------------------------------


def test_append_persists_to_disk(isolated_paths: Path) -> None:
    """append() immediately writes to activity.json."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    _append_event(log, summary="Persisted event")

    activity_path = paths_mod.activity_file()
    assert activity_path.exists(), "activity.json should exist after append"
    raw = json.loads(activity_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["summary"] == "Persisted event"


def test_append_returns_event(isolated_paths: Path) -> None:
    """append() returns the created ActivityEvent."""
    log = _make_log()
    event = log.append(EventType.AUTH_SIGN_IN, Outcome.SUCCESS, "Signed in")
    assert event.summary == "Signed in"
    assert event.event_type == EventType.AUTH_SIGN_IN
    assert event.outcome == Outcome.SUCCESS
    assert event.id  # non-empty UUID string


def test_append_event_has_utc_timestamp(isolated_paths: Path) -> None:
    """Appended events have a timezone-aware UTC timestamp."""
    log = _make_log()
    before = datetime.now(UTC)
    event = log.append(EventType.TOOL_INSTALL, Outcome.SUCCESS, "ts test")
    after = datetime.now(UTC)
    assert event.timestamp.tzinfo is not None
    assert before <= event.timestamp <= after


def test_append_multiple_events(isolated_paths: Path) -> None:
    """Multiple appends accumulate correctly in memory and on disk."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    for i in range(5):
        _append_event(log, summary=f"Event {i}")

    assert len(log.get_all()) == 5

    raw = json.loads(paths_mod.activity_file().read_text(encoding="utf-8"))
    assert len(raw) == 5


# ---------------------------------------------------------------------------
# get_recent
# ---------------------------------------------------------------------------


def test_get_recent_returns_last_n(isolated_paths: Path) -> None:
    """get_recent(n) returns the n most recent events, oldest-first within slice."""
    log = _make_log()
    for i in range(10):
        _append_event(log, summary=f"Event {i}")

    recent = log.get_recent(3)
    assert len(recent) == 3
    # Should be the last 3 appended: Event 7, 8, 9
    assert recent[0].summary == "Event 7"
    assert recent[1].summary == "Event 8"
    assert recent[2].summary == "Event 9"


def test_get_recent_fewer_than_n(isolated_paths: Path) -> None:
    """get_recent(n) returns all events when total < n."""
    log = _make_log()
    _append_event(log, summary="Only event")
    recent = log.get_recent(50)
    assert len(recent) == 1


def test_get_recent_default_limit(isolated_paths: Path) -> None:
    """get_recent() default limit is 50."""
    log = _make_log()
    for i in range(60):
        _append_event(log, summary=f"Event {i}")

    recent = log.get_recent()
    assert len(recent) == 50
    # Most recent 50: events 10..59
    assert recent[0].summary == "Event 10"
    assert recent[-1].summary == "Event 59"


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


def test_get_all_returns_all_events(isolated_paths: Path) -> None:
    """get_all() returns every event in oldest-first order."""
    log = _make_log()
    for i in range(7):
        _append_event(log, summary=f"Event {i}")

    all_events = log.get_all()
    assert len(all_events) == 7
    assert all_events[0].summary == "Event 0"
    assert all_events[-1].summary == "Event 6"


def test_get_all_returns_copy(isolated_paths: Path) -> None:
    """get_all() returns a new list (mutations don't affect internal state)."""
    log = _make_log()
    _append_event(log)
    events = log.get_all()
    events.clear()
    assert len(log.get_all()) == 1


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------


def test_cap_enforced_at_500(isolated_paths: Path) -> None:
    """When more than 500 events are appended, oldest are dropped to keep at 500."""
    log = _make_log()
    for i in range(_ACTIVITY_CAP + 20):
        _append_event(log, summary=f"Event {i}")

    all_events = log.get_all()
    assert len(all_events) == _ACTIVITY_CAP
    # Oldest should be Event 20 (first 20 dropped)
    assert all_events[0].summary == "Event 20"
    assert all_events[-1].summary == f"Event {_ACTIVITY_CAP + 19}"


def test_cap_preserved_on_disk(isolated_paths: Path) -> None:
    """The on-disk file also stays at cap after overflow."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    for i in range(_ACTIVITY_CAP + 5):
        _append_event(log, summary=f"E{i}")

    raw = json.loads(paths_mod.activity_file().read_text(encoding="utf-8"))
    assert len(raw) == _ACTIVITY_CAP


# ---------------------------------------------------------------------------
# File always valid JSON array
# ---------------------------------------------------------------------------


def test_empty_log_creates_valid_json_array(isolated_paths: Path) -> None:
    """A fresh log with no events produces a valid JSON array on first append."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    # Before any append, file should not exist yet
    assert not paths_mod.activity_file().exists()

    _append_event(log)
    raw = json.loads(paths_mod.activity_file().read_text(encoding="utf-8"))
    assert isinstance(raw, list)


def test_file_is_valid_json_after_multiple_appends(isolated_paths: Path) -> None:
    """activity.json remains a parseable JSON array after many appends."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    for i in range(20):
        _append_event(log, summary=f"Event {i}")

    content = paths_mod.activity_file().read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, list)
    assert len(data) == 20


# ---------------------------------------------------------------------------
# Load from existing file
# ---------------------------------------------------------------------------


def test_load_from_existing_file(isolated_paths: Path) -> None:
    """A new ActivityLog instance loads events written by a previous instance."""
    log1 = _make_log()
    _append_event(log1, summary="Persisted")

    # Simulate app restart with a fresh instance
    log2 = _make_log()
    all_events = log2.get_all()
    assert len(all_events) == 1
    assert all_events[0].summary == "Persisted"


def test_load_ignores_invalid_json(isolated_paths: Path) -> None:
    """If the file contains invalid JSON, load returns an empty list (no crash)."""
    from ignition.core import paths as paths_mod

    paths_mod.activity_file().write_text("NOT JSON", encoding="utf-8")
    log = _make_log()
    assert log.get_all() == []


def test_load_skips_malformed_events(isolated_paths: Path) -> None:
    """Malformed event entries in the file are skipped; valid ones are loaded."""
    from ignition.core import paths as paths_mod

    good_event = {
        "schema_version": 1,
        "id": "abc",
        "timestamp": "2026-04-21T12:00:00+00:00",
        "event_type": "tool_install",
        "tool_key": None,
        "outcome": "success",
        "summary": "Good event",
        "detail": "",
    }
    bad_event = {"broken": True}  # missing required fields

    paths_mod.activity_file().write_text(json.dumps([good_event, bad_event]), encoding="utf-8")

    log = _make_log()
    events = log.get_all()
    assert len(events) == 1
    assert events[0].summary == "Good event"


def test_load_ignores_non_list_file(isolated_paths: Path) -> None:
    """If the file is valid JSON but not a list, load returns empty list."""
    from ignition.core import paths as paths_mod

    paths_mod.activity_file().write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    log = _make_log()
    assert log.get_all() == []


# ---------------------------------------------------------------------------
# Atomic write pattern
# ---------------------------------------------------------------------------


def test_append_overwrites_not_appends(isolated_paths: Path) -> None:
    """Each append writes the full array, not incremental bytes."""
    from ignition.core import paths as paths_mod

    log = _make_log()
    _append_event(log, summary="First")
    _append_event(log, summary="Second")

    # File should contain exactly 2 events — if it appended raw bytes
    # we'd get malformed JSON or duplicate entries.
    raw = json.loads(paths_mod.activity_file().read_text(encoding="utf-8"))
    assert len(raw) == 2
    assert raw[0]["summary"] == "First"
    assert raw[1]["summary"] == "Second"


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


def test_append_with_tool_key_and_detail(isolated_paths: Path) -> None:
    """tool_key and detail are stored and round-trip correctly."""
    log = _make_log()
    event = log.append(
        EventType.TOOL_INSTALL,
        Outcome.SUCCESS,
        "Installed kubectl",
        tool_key="kubectl",
        detail="Method: brew",
    )
    assert event.tool_key == "kubectl"
    assert event.detail == "Method: brew"

    loaded = _make_log()
    reloaded = loaded.get_all()[0]
    assert reloaded.tool_key == "kubectl"
    assert reloaded.detail == "Method: brew"
