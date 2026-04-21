from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ignition.core.activity import ActivityLog
from ignition.schemas.activity import EventType, Outcome
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.activity import ActivityScreen, _day_label

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state() -> AppStateModel:
    return AppStateModel(install_id="test-id", onboarding_complete=True)


def _log_with_events(n: int, *, outcome: Outcome = Outcome.SUCCESS) -> ActivityLog:
    log = ActivityLog()
    for i in range(n):
        log.append(
            EventType.TOOL_INSTALL,
            outcome,
            f"Installed tool-{i}",
            tool_key=f"tool-{i}",
        )
    return log


# ---------------------------------------------------------------------------
# Unit: _day_label helper
# ---------------------------------------------------------------------------


def test_day_label_today(isolated_paths: Path) -> None:
    now = datetime.now(UTC)
    assert _day_label(now) == "Today"


def test_day_label_yesterday(isolated_paths: Path) -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    assert _day_label(yesterday) == "Yesterday"


def test_day_label_older(isolated_paths: Path) -> None:
    two_days_ago = datetime.now(UTC) - timedelta(days=2)
    label = _day_label(two_days_ago)
    assert label == two_days_ago.date().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Pilot: row display
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_screen_shows_rows(isolated_paths: Path) -> None:
    """Rows are rendered for each event in the log."""
    from ignition.app import IgnitionApp

    log = _log_with_events(3)
    state = _state()

    app = IgnitionApp(demo_mode=False)
    app._activity_log = log
    app._current_state = state

    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ActivityScreen(state, log))
        await pilot.pause()

        # Three rows should be present
        from ignition.ui.screens.activity import _ActivityRow

        rows = app.screen.query(_ActivityRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_activity_screen_empty_state(isolated_paths: Path) -> None:
    """Empty log shows the 'no activity' placeholder."""

    from ignition.app import IgnitionApp

    log = ActivityLog()
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ActivityScreen(state, log))
        await pilot.pause()

        empty_widgets = app.screen.query("#activity-empty")
        assert len(empty_widgets) == 1


# ---------------------------------------------------------------------------
# Pilot: day grouping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_screen_day_grouping(isolated_paths: Path) -> None:
    """Events from different days get separate day separator headers."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import _DaySeparator

    log = ActivityLog()
    # Two today events
    log.append(EventType.TOOL_INSTALL, Outcome.SUCCESS, "Today event 1")
    log.append(EventType.AUTH_SIGN_IN, Outcome.SUCCESS, "Today event 2")
    # One yesterday event — manually set a past timestamp by seeding directly
    # We use a yesterday-timestamped ActivityEvent
    from ignition.schemas.activity import ActivityEvent

    yesterday_ts = datetime.now(UTC) - timedelta(days=1)
    old_event = ActivityEvent(
        id="old-1",
        timestamp=yesterday_ts,
        event_type=EventType.TOOL_INSTALL,
        outcome=Outcome.SUCCESS,
        summary="Yesterday event",
    )
    log._events.insert(0, old_event)
    log._persist()

    state = _state()
    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ActivityScreen(state, log))
        await pilot.pause()

        separators = app.screen.query(_DaySeparator)
        # Should have at least 2 separators: "Today" and "Yesterday"
        assert len(separators) >= 2


# ---------------------------------------------------------------------------
# Pilot: j/k navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_screen_j_navigates_down(isolated_paths: Path) -> None:
    """Pressing j moves cursor down one row."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import ActivityScreen

    log = _log_with_events(3)
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ActivityScreen(state, log)
        app.push_screen(screen)
        await pilot.pause()

        assert screen._cursor == 0
        await pilot.press("j")
        await pilot.pause()
        assert screen._cursor == 1


@pytest.mark.asyncio
async def test_activity_screen_k_navigates_up(isolated_paths: Path) -> None:
    """Pressing k moves cursor up one row."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import ActivityScreen

    log = _log_with_events(3)
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ActivityScreen(state, log)
        app.push_screen(screen)
        await pilot.pause()

        # Move down first, then back up
        await pilot.press("j")
        await pilot.pause()
        assert screen._cursor == 1

        await pilot.press("k")
        await pilot.pause()
        assert screen._cursor == 0


@pytest.mark.asyncio
async def test_activity_screen_j_does_not_go_past_end(isolated_paths: Path) -> None:
    """j does not move cursor past the last row."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import ActivityScreen

    log = _log_with_events(2)
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ActivityScreen(state, log)
        app.push_screen(screen)
        await pilot.pause()

        await pilot.press("j")
        await pilot.pause()
        assert screen._cursor == 1

        # Press j again — should stay at 1 (last index)
        await pilot.press("j")
        await pilot.pause()
        assert screen._cursor == 1


@pytest.mark.asyncio
async def test_activity_screen_k_does_not_go_before_start(isolated_paths: Path) -> None:
    """k does not move cursor before index 0."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import ActivityScreen

    log = _log_with_events(2)
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ActivityScreen(state, log)
        app.push_screen(screen)
        await pilot.pause()

        # Already at 0, pressing k should stay at 0
        await pilot.press("k")
        await pilot.pause()
        assert screen._cursor == 0


# ---------------------------------------------------------------------------
# Pilot: expand/collapse with Enter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_screen_enter_toggles_expand(isolated_paths: Path) -> None:
    """Pressing Enter on a row with detail toggles expansion."""
    from ignition.app import IgnitionApp
    from ignition.ui.screens.activity import ActivityScreen

    log = ActivityLog()
    log.append(
        EventType.TOOL_INSTALL,
        Outcome.SUCCESS,
        "Installed kubectl",
        tool_key="kubectl",
        detail="Method: brew",
    )
    state = _state()

    app = IgnitionApp(demo_mode=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ActivityScreen(state, log)
        app.push_screen(screen)
        await pilot.pause()

        row = screen._rows[0]
        assert row._expanded is False

        await pilot.press("enter")
        await pilot.pause()
        assert row._expanded is True

        # Press Enter again — collapses
        await pilot.press("enter")
        await pilot.pause()
        assert row._expanded is False


# ---------------------------------------------------------------------------
# Pilot: Esc pops screen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_screen_esc_pops_screen(isolated_paths: Path) -> None:
    """Pressing Escape dismisses ActivityScreen and returns to the previous screen."""
    from ignition.app import IgnitionApp
    from ignition.core.state import save_state
    from ignition.ui.screens.home import HomeScreen

    # Pre-seed a complete state so on_mount routes to HomeScreen not OnboardingScreen.
    save_state(_state())

    log = ActivityLog()
    app = IgnitionApp(demo_mode=False)
    app._activity_log = log

    async with app.run_test() as pilot:
        await pilot.pause()
        # Navigate to ActivityScreen via binding
        await pilot.press("ctrl+l")
        await pilot.pause()

        assert isinstance(app.screen, ActivityScreen)

        await pilot.press("escape")
        await pilot.pause()

        # Should be back on HomeScreen
        assert isinstance(app.screen, HomeScreen)
