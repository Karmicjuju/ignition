from __future__ import annotations

import json
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, Static

from ignition.schemas.state import AppStateModel


class _RawStateOverlay(ModalScreen[None]):
    """Read-only scrollable overlay showing AppStateModel as indented JSON."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Close"),
    ]

    DEFAULT_CSS = """
    _RawStateOverlay {
        align: center middle;
    }

    #raw-state-dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: round $border;
        padding: 1 2;
    }

    #raw-state-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #raw-state-scroll {
        height: 1fr;
        border: round $border;
        background: $background;
        padding: 1;
    }

    #raw-state-content {
        color: $text;
    }

    #raw-state-close {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(id="raw-state-dialog"):
            yield Static("App State (read-only)", id="raw-state-title")
            with ScrollableContainer(id="raw-state-scroll"):
                json_text = json.dumps(
                    self._state.model_dump(mode="json"),
                    indent=2,
                    default=str,
                )
                yield Static(json_text, id="raw-state-content")
            yield Button(
                "Close",
                id="raw-state-close",
                variant="default",
                tooltip="Close this overlay and return to the Operator Panel.",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "raw-state-close":
            self.app.pop_screen()


class OperatorPanel(ModalScreen[None]):
    """Operator debug panel. Accessible only when app is in operator mode.

    Shows raw app state, catalog force-reload, and demo scenario seeding buttons.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Close"),
    ]

    DEFAULT_CSS = """
    OperatorPanel {
        align: center middle;
    }

    #operator-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: round $warning;
        padding: 1 2;
    }

    #operator-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    .section-label {
        color: $text-secondary;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    OperatorPanel Button {
        width: 1fr;
        margin-top: 1;
    }

    #operator-version {
        color: $text-secondary;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        try:
            from importlib.metadata import version as pkg_version

            ver = pkg_version("ignition")
        except Exception:
            ver = "0.1.0"

        with Vertical(id="operator-dialog"):
            yield Static("Operator Panel", id="operator-title")

            yield Label("App state", classes="section-label")
            yield Button(
                "View raw state JSON",
                id="btn-view-state",
                variant="default",
                tooltip="Open a read-only overlay showing the full AppStateModel as JSON.",
            )

            yield Label("Catalog", classes="section-label")
            yield Button(
                "Force reload",
                id="btn-force-reload",
                variant="default",
                tooltip="Clear the catalog ETag cache and re-fetch from remote.",
            )

            yield Label("Demo scenarios", classes="section-label")
            yield Button(
                "Seed: Partially onboarded backend",
                id="btn-seed-1",
                variant="default",
                tooltip="Scenario 1: backend persona, onboarding in progress, 3 tools installed.",
            )
            yield Button(
                "Seed: Healthy devops",
                id="btn-seed-2",
                variant="default",
                tooltip="Scenario 2: backend + devops, all tools installed, active AWS session.",
            )
            yield Button(
                "Seed: Needs attention",
                id="btn-seed-3",
                variant="default",
                tooltip="Scenario 3: degraded environment, outdated tools, expired AWS session.",
            )

            yield Static(f"Version: {ver}   Mode: OPERATOR", id="operator-version")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-view-state":
            self.app.push_screen(_RawStateOverlay(self._state))
            return

        if btn_id == "btn-force-reload":
            self._do_force_reload()
            return

        if btn_id == "btn-seed-1":
            self._seed_scenario(1)
            return

        if btn_id == "btn-seed-2":
            self._seed_scenario(2)
            return

        if btn_id == "btn-seed-3":
            self._seed_scenario(3)
            return

    def _do_force_reload(self) -> None:
        try:
            from ignition.core.catalog import CatalogService

            catalog = CatalogService()
            catalog.force_refresh()
            self.app.notify("Catalog reloaded.", title="Operator")
        except Exception as exc:
            self.app.notify(f"Reload failed: {exc}", severity="error", title="Operator")

    def _seed_scenario(self, scenario: int) -> None:
        from ignition.core.demo import (
            seed_scenario_healthy_devops,
            seed_scenario_needs_attention,
            seed_scenario_partially_onboarded,
        )
        from ignition.core.state import save_state

        _SEED_FN = {
            1: seed_scenario_partially_onboarded,
            2: seed_scenario_healthy_devops,
            3: seed_scenario_needs_attention,
        }
        fn = _SEED_FN.get(scenario)
        if fn is None:
            return
        try:
            new_state = fn(self._state)
            save_state(new_state)
            self._state = new_state
            label = {1: "Partially onboarded", 2: "Healthy devops", 3: "Needs attention"}.get(
                scenario, str(scenario)
            )
            self.app.notify(f"Seeded scenario: {label}", title="Operator")
            # Pop the operator panel and reload home
            self.app.pop_screen()
            self._reload_home(new_state)
        except Exception as exc:
            self.app.notify(f"Seed failed: {exc}", severity="error", title="Operator")

    def _reload_home(self, state: AppStateModel) -> None:
        """Pop back to the base screen and push a fresh HomeScreen."""
        from ignition.ui.screens.home import HomeScreen

        # Pop all screens until we reach the bottom, then push HomeScreen.
        # We use a safe pop-loop to avoid crashing if the stack is already shallow.
        while len(self.app.screen_stack) > 1:
            try:
                self.app.pop_screen()
            except Exception:
                break
        self.app.push_screen(HomeScreen(state))


# ---------------------------------------------------------------------------
# Stand-alone screen wrapper (used only in test harness)
# ---------------------------------------------------------------------------


class OperatorScreen(Screen[None]):
    """Thin wrapper that immediately pushes OperatorPanel — used for testing."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        self.app.push_screen(OperatorPanel(self._state))
