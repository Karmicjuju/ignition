from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ignition.app import IgnitionApp
from ignition.core.state import save_state
from ignition.schemas.catalog import InstallStatus, ToolInfo
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.home import HomeScreen
from ignition.ui.screens.updates import UpdatesScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _complete_state(**kwargs: object) -> AppStateModel:
    defaults: dict[str, object] = {
        "install_id": "test-id",
        "onboarding_complete": True,
    }
    defaults.update(kwargs)
    return AppStateModel(**defaults)  # type: ignore[arg-type]


def _outdated_tool(key: str = "docker") -> ToolInfo:
    return ToolInfo(
        key=key,
        name=key.capitalize(),
        description=f"Test tool {key}",
        categories=["testing"],
        persona_tags=["devops"],
        managed=True,
        version_policy="managed",
        install_status=InstallStatus.INSTALLED,
        version="1.0.0",
        managed_version="2.0.0",
    )


# ---------------------------------------------------------------------------
# test_updates_screen_boots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updates_screen_boots(isolated_paths: Path) -> None:
    """ctrl+u from HomeScreen must push UpdatesScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, HomeScreen)
        await pilot.press("ctrl+u")
        await pilot.pause()
        assert isinstance(pilot.app.screen, UpdatesScreen), (
            f"Expected UpdatesScreen, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_updates_screen_empty_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updates_screen_empty_state(isolated_paths: Path) -> None:
    """UpdatesScreen with no outdated tools must show the empty-state message."""
    state = _complete_state()
    save_state(state)

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+u")
        await pilot.pause()

        screen = pilot.app.screen
        assert isinstance(screen, UpdatesScreen)

        # empty-state widget should be visible
        from textual.widgets import Static

        empty_msg = screen.query_one("#empty-message", Static)
        assert "up to date" in str(empty_msg.content).lower()


# ---------------------------------------------------------------------------
# test_updates_screen_update_all_disabled_when_no_updates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_button_disabled_when_no_updates(isolated_paths: Path) -> None:
    """'Update all managed' button must be disabled when no outdated tools exist."""
    state = _complete_state()
    save_state(state)

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+u")
        await pilot.pause()

        screen = pilot.app.screen
        assert isinstance(screen, UpdatesScreen)

        from textual.widgets import Button

        btn = screen.query_one("#btn-update-all-managed", Button)
        assert btn.disabled, "Update all managed button should be disabled when no updates"


# ---------------------------------------------------------------------------
# test_updates_screen_shows_outdated_rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updates_screen_shows_outdated_rows(isolated_paths: Path) -> None:
    """UpdatesScreen must render a row for each outdated tool in the catalog."""
    state = _complete_state()
    save_state(state)

    # Patch CatalogService.get_all_tools() to return one outdated tool
    outdated = _outdated_tool("docker")

    with patch(
        "ignition.ui.screens.updates.CatalogService.get_all_tools",
        return_value=[outdated],
    ):
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            await pilot.pause()

            screen = pilot.app.screen
            assert isinstance(screen, UpdatesScreen)
            await pilot.pause()  # allow on_mount _refresh_view to complete

            # A per-tool update button must be present
            from textual.widgets import Button

            btns = [b for b in screen.query(Button) if b.id and b.id.startswith("btn-update-")]
            assert len(btns) >= 1, "Expected at least one per-tool Update button"
            assert any(b.id == "btn-update-docker" for b in btns)


# ---------------------------------------------------------------------------
# test_updates_screen_update_all_enabled_when_managed_outdated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_enabled_when_managed_outdated(isolated_paths: Path) -> None:
    """'Update all managed' button must be enabled when managed outdated tools exist."""
    state = _complete_state()
    save_state(state)

    outdated = _outdated_tool("docker")

    with patch(
        "ignition.ui.screens.updates.CatalogService.get_all_tools",
        return_value=[outdated],
    ):
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            await pilot.pause()

            screen = pilot.app.screen
            assert isinstance(screen, UpdatesScreen)
            await pilot.pause()

            from textual.widgets import Button

            btn = screen.query_one("#btn-update-all-managed", Button)
            assert not btn.disabled, "Update all managed button must be enabled with outdated tools"


# ---------------------------------------------------------------------------
# test_updates_screen_escape_returns_home
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updates_screen_escape_returns_home(isolated_paths: Path) -> None:
    """Pressing Escape from UpdatesScreen must return to HomeScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+u")
        await pilot.pause()

        assert isinstance(pilot.app.screen, UpdatesScreen)
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(pilot.app.screen, HomeScreen), (
            f"Expected HomeScreen after Escape, got {type(pilot.app.screen).__name__}"
        )


# ---------------------------------------------------------------------------
# test_updates_screen_version_delta_shown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_updates_screen_version_delta_shown(isolated_paths: Path) -> None:
    """Each tool row must display the installed → available version delta."""
    state = _complete_state()
    save_state(state)

    outdated = _outdated_tool("docker")  # version=1.0.0, managed_version=2.0.0

    with patch(
        "ignition.ui.screens.updates.CatalogService.get_all_tools",
        return_value=[outdated],
    ):
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            await pilot.pause()

            screen = pilot.app.screen
            assert isinstance(screen, UpdatesScreen)
            await pilot.pause()

            from textual.widgets import Static

            # Look for a Static that contains the version delta string
            delta_widgets = [
                w
                for w in screen.query(Static)
                if "1.0.0" in str(w.content) and "2.0.0" in str(w.content)
            ]
            assert len(delta_widgets) >= 1, (
                "Expected a widget displaying the version delta '1.0.0 → 2.0.0'"
            )
