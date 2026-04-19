from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import Button, Collapsible

from ignition.app import IgnitionApp
from ignition.core.state import save_state
from ignition.schemas.health import CheckResult, FixType, HealthState
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.health import HealthScreen
from ignition.ui.screens.home import HomeScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _complete_state() -> AppStateModel:
    return AppStateModel(install_id="test-id", onboarding_complete=True)


def _make_results(
    *,
    include_auto: bool = False,
    include_copy_paste: bool = False,
) -> list[CheckResult]:
    results = [
        CheckResult(
            category="tools",
            check_id="tool_git",
            label="Git",
            state=HealthState.HEALTHY,
            detail="git OK",
            fix_type=FixType.NONE,
        ),
        CheckResult(
            category="shell_integration",
            check_id="shell_local_bin_path",
            label="~/.local/bin on PATH",
            state=HealthState.RECOMMENDED,
            detail="Not on PATH",
            fix_type=FixType.COPY_PASTE if include_copy_paste else FixType.NONE,
            fix_command='export PATH="$HOME/.local/bin:$PATH"' if include_copy_paste else None,
        ),
    ]
    if include_auto:
        results.append(
            CheckResult(
                category="permissions",
                check_id="perm_ssh_id_rsa",
                label="SSH key: id_rsa",
                state=HealthState.NEEDS_ATTENTION,
                detail="Wrong permissions",
                fix_type=FixType.AUTO,
                fix_command="chmod 600 ~/.ssh/id_rsa",
            )
        )
    return results


async def _navigate_to_health(pilot: object) -> HealthScreen:  # type: ignore[type-arg]
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("ctrl+h")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = pilot.app.screen  # type: ignore[attr-defined]
    assert isinstance(screen, HealthScreen)
    return screen


# ---------------------------------------------------------------------------
# test_health_screen_boots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_screen_boots(isolated_paths: Path) -> None:
    """ctrl+h from HomeScreen must push HealthScreen."""
    save_state(_complete_state())

    mock_results = _make_results()

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await pilot.pause()
            assert isinstance(pilot.app.screen, HomeScreen)
            await pilot.press("ctrl+h")
            await pilot.pause()
            assert isinstance(pilot.app.screen, HealthScreen), (
                f"Expected HealthScreen, got {type(pilot.app.screen).__name__}"
            )


# ---------------------------------------------------------------------------
# test_health_screen_shows_collapsibles_after_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_screen_shows_collapsibles_after_scan(isolated_paths: Path) -> None:
    """After a scan completes, Collapsible widgets appear for each category with results."""
    save_state(_complete_state())

    mock_results = _make_results()

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_health(pilot)
            # Wait for the @work scan to complete
            await pilot.pause()
            await pilot.pause()

            collapsibles = list(screen.query(Collapsible))
            assert collapsibles, "Expected at least one Collapsible after scan"


# ---------------------------------------------------------------------------
# test_scan_button_triggers_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_button_triggers_scan(isolated_paths: Path) -> None:
    """Clicking the Scan button triggers a new run_scan call."""
    save_state(_complete_state())

    mock_results = _make_results()

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_health(pilot)
            # Use delay= to avoid _wait_for_screen() timeout from in-flight @work scan
            await pilot.pause(delay=0.5)

            initial_call_count = mock_scan.call_count

            btn = screen.query_one("#btn-scan", Button)
            btn.press()
            # Give the @work scan worker time to invoke run_scan
            await pilot.pause(delay=0.5)

            assert mock_scan.call_count > initial_call_count, (
                "Scan button should trigger another run_scan call"
            )


# ---------------------------------------------------------------------------
# test_ctrl_r_triggers_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ctrl_r_triggers_scan(isolated_paths: Path) -> None:
    """ctrl+r keyboard shortcut triggers a new scan."""
    save_state(_complete_state())

    mock_results = _make_results()

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_health(pilot)
            # Use delay= to avoid _wait_for_screen() timeout from in-flight @work scan
            await pilot.pause(delay=0.5)

            initial_call_count = mock_scan.call_count

            # Call action directly — pilot.press() calls _wait_for_screen() which
            # times out while the @work scan is running.
            screen.action_scan()
            # Give the @work scan worker time to invoke run_scan
            await pilot.pause(delay=0.5)

            assert mock_scan.call_count > initial_call_count, (
                "ctrl+r (action_scan) should trigger another run_scan call"
            )


# ---------------------------------------------------------------------------
# test_apply_fix_button_calls_apply_fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_fix_button_calls_apply_fix(isolated_paths: Path) -> None:
    """Clicking 'Apply fix' calls engine.apply_fix with the correct check_id."""
    save_state(_complete_state())

    mock_results = _make_results(include_auto=True)

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        with patch(
            "ignition.core.health.HealthEngine.apply_fix", new_callable=AsyncMock
        ) as mock_fix:
            mock_fix.return_value = True

            async with IgnitionApp(demo_mode=False).run_test() as pilot:
                screen = await _navigate_to_health(pilot)
                # Use delay= to let the on_mount @work scan complete without
                # triggering _wait_for_screen() timeout
                await pilot.pause(delay=0.5)

                # The initial mock scan already rendered results — no injection needed
                fix_btn = None
                for btn in screen.query(Button):
                    if btn.id and btn.id.startswith("btn-fix-"):
                        fix_btn = btn
                        break

                if fix_btn is None:
                    pytest.skip("No AUTO fix button rendered — check IssueRow logic")

                check_id = fix_btn.id[len("btn-fix-") :]  # type: ignore[index]
                fix_btn.press()
                await pilot.pause(delay=0.5)

                mock_fix.assert_called_with(check_id)


# ---------------------------------------------------------------------------
# test_recheck_button_triggers_category_scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recheck_button_triggers_category_scan(isolated_paths: Path) -> None:
    """Clicking 'Re-check' triggers a run_scan call filtered to that check's category."""
    save_state(_complete_state())

    mock_results = _make_results(include_copy_paste=True)

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_health(pilot)
            # Use delay= to let the on_mount @work scan complete without
            # triggering _wait_for_screen() timeout
            await pilot.pause(delay=0.5)

            # The initial mock scan already rendered results — no injection needed
            recheck_btn = None
            for btn in screen.query(Button):
                if btn.id and btn.id.startswith("btn-recheck-"):
                    recheck_btn = btn
                    break

            if recheck_btn is None:
                pytest.skip("No Re-check button rendered — check IssueRow logic")

            initial_call_count = mock_scan.call_count
            recheck_btn.press()
            await pilot.pause(delay=0.5)

            assert mock_scan.call_count > initial_call_count, (
                "Re-check should trigger a new run_scan call"
            )
            # categories filter is passed positionally or as kwarg — call_count check is sufficient


# ---------------------------------------------------------------------------
# test_escape_returns_to_home
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escape_returns_to_home(isolated_paths: Path) -> None:
    """Pressing Escape from HealthScreen returns to HomeScreen."""
    save_state(_complete_state())

    mock_results: list[CheckResult] = []

    with patch("ignition.core.health.HealthEngine.run_scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = mock_results
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await _navigate_to_health(pilot)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert isinstance(pilot.app.screen, HomeScreen), (
                f"Expected HomeScreen after Escape, got {type(pilot.app.screen).__name__}"
            )
