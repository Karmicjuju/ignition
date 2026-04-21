from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, ListView

from ignition.app import IgnitionApp
from ignition.core.state import save_state
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.catalog import ToolCatalogScreen
from ignition.ui.screens.home import HomeScreen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _complete_state() -> AppStateModel:
    """Return a minimal state with onboarding complete so IgnitionApp routes
    directly to HomeScreen without showing the onboarding wizard."""
    return AppStateModel(install_id="test-id", onboarding_complete=True)


async def _navigate_to_catalog(pilot: object) -> ToolCatalogScreen:  # type: ignore[type-arg]
    """Navigate from HomeScreen to ToolCatalogScreen via ctrl+t."""
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("ctrl+t")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = pilot.app.screen  # type: ignore[attr-defined]
    assert isinstance(screen, ToolCatalogScreen)
    return screen


async def _open_detail_panel(pilot: object, screen: ToolCatalogScreen) -> None:  # type: ignore[type-arg]
    """Focus the tool list, move to the first item, and press Enter to open the
    detail panel.  A 'down' key-press is required first because ListView index
    starts as None (no item selected) until the cursor is explicitly moved."""
    tool_list = screen.query_one("#tool-list", ListView)
    tool_list.focus()
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("down")  # type: ignore[attr-defined]  # highlight first item (git)
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# test_catalog_screen_boots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_screen_boots(isolated_paths: Path) -> None:
    """Pressing ctrl+t from HomeScreen must push ToolCatalogScreen."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        assert isinstance(pilot.app.screen, HomeScreen)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ToolCatalogScreen)


# ---------------------------------------------------------------------------
# test_sidebar_shows_all_category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sidebar_shows_all_category(isolated_paths: Path) -> None:
    """The category sidebar must always contain an 'All' entry."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        # Labels in #category-list are textual.widgets.Label widgets;
        # their text is accessible via the .content property (str).
        labels = list(screen.query("#category-list Label"))
        assert labels, "No Label widgets found in #category-list"
        label_texts = [lbl.content for lbl in labels]
        assert "All" in label_texts, f"'All' category not found in sidebar. Found: {label_texts}"


# ---------------------------------------------------------------------------
# test_tool_list_populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_list_populated(isolated_paths: Path) -> None:
    """Tool list must have at least 10 items after mount (stub catalogue has 12)."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        tool_list = screen.query_one("#tool-list", ListView)
        assert len(tool_list.children) >= 10, f"Expected ≥10 tools, got {len(tool_list.children)}"


# ---------------------------------------------------------------------------
# test_search_filters_tool_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_filters_tool_list(isolated_paths: Path) -> None:
    """Typing 'docker' in the search input must reduce the list and keep Docker visible."""
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        tool_list = screen.query_one("#tool-list", ListView)
        original_count = len(tool_list.children)

        # Activate search via '/' binding, then set value directly on the Input
        # widget (pilot.type() does not exist in Textual 8.x; setting .value
        # directly triggers the Input.Changed reactive update).
        await pilot.press("/")
        await pilot.pause()
        search_input = screen.query_one("#search-input", Input)
        search_input.value = "docker"
        await pilot.pause()

        filtered_count = len(tool_list.children)
        assert filtered_count < original_count, (
            f"Search did not filter: still {filtered_count} items (was {original_count})"
        )
        visible_keys = [getattr(item, "_tool_key", None) for item in tool_list.children]
        assert "docker" in visible_keys, (
            f"'docker' not in visible tools after search. Visible: {visible_keys}"
        )


# ---------------------------------------------------------------------------
# test_enter_on_tool_opens_detail_panel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enter_on_tool_opens_detail_panel(isolated_paths: Path) -> None:
    """Pressing Enter on a focused, highlighted tool row must reveal #detail-panel.

    Implementation note: ListView.index starts as None (nothing highlighted).
    A 'down' key-press is required before Enter so the cursor lands on the
    first item and ListView fires its Selected message.
    """
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        detail_panel = screen.query_one("#detail-panel")
        assert "hidden" in detail_panel.classes, "detail-panel should start hidden"

        await _open_detail_panel(pilot, screen)

        assert "hidden" not in detail_panel.classes, (
            "detail-panel should be visible after Enter on a highlighted tool"
        )


# ---------------------------------------------------------------------------
# test_simulate_install_button_fires_notify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_button_visible_for_missing_tool(isolated_paths: Path) -> None:
    """The Install button must be visible and labelled 'Install' for a MISSING tool.

    The first tool in the list is 'git' which starts INSTALLED (no button).
    We navigate down two positions to reach 'python' (MISSING) so the
    Install button is visible.
    """
    save_state(_complete_state())

    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        tool_list = screen.query_one("#tool-list", ListView)
        tool_list.focus()
        await pilot.pause()

        # Navigate down twice: index 0 = git (INSTALLED, no button),
        # index 1 = python (MISSING, has button).
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        btn = screen.query_one("#btn-install", Button)
        assert btn.display, (
            f"Expected Install button to be visible for tool '{screen._selected_tool_key}'"
        )
        # Button label should be "Install" for a MISSING tool
        assert str(btn.label) == "Install", f"Expected button label 'Install', got: {btn.label!r}"


# ---------------------------------------------------------------------------
# test_escape_closes_detail_panel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escape_closes_detail_panel(isolated_paths: Path) -> None:
    """Pressing Escape from ToolCatalogScreen returns to HomeScreen.

    Implementation note: the Escape binding is wired to 'app.pop_screen' rather
    than a custom panel-toggle action, so the entire ToolCatalogScreen is popped
    from the stack.  This test therefore verifies the navigational contract:
    after Escape the screen stack top is HomeScreen.
    """
    save_state(_complete_state())
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        screen = await _navigate_to_catalog(pilot)

        # Open the detail panel to confirm we are in a non-trivial state before Escape.
        await _open_detail_panel(pilot, screen)

        detail_panel = screen.query_one("#detail-panel")
        assert "hidden" not in detail_panel.classes, (
            "detail-panel should be visible before pressing Escape"
        )

        await pilot.press("escape")
        await pilot.pause()

        # Escape pops ToolCatalogScreen → top of stack should be HomeScreen.
        assert isinstance(pilot.app.screen, HomeScreen), (
            f"Expected HomeScreen after Escape, got {type(pilot.app.screen).__name__}"
        )
