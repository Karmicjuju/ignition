from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, RadioButton, RadioSet, Static

from ignition.core.config import load_config, save_config
from ignition.schemas.config import AppConfigModel
from ignition.schemas.state import AppStateModel


class SettingsScreen(Screen[None]):
    """Settings screen with immediate-apply preferences.

    Backed by AppConfigModel. Each RadioSet change calls save_config()
    immediately — no Save button required.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        background: $background;
    }

    #settings-container {
        padding: 2 4;
        height: 1fr;
    }

    .settings-row {
        height: auto;
        margin-bottom: 2;
        align: left middle;
    }

    .settings-label {
        width: 20;
        text-style: bold;
    }

    .settings-control {
        width: 1fr;
    }

    #settings-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
        padding-bottom: 1;
        border-bottom: solid $surface;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._config: AppConfigModel = load_config()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="settings-container"):
            yield Static("Settings", id="settings-title")

            with Horizontal(classes="settings-row"):
                yield Label("Theme", classes="settings-label")
                with RadioSet(id="radio-theme", classes="settings-control"):
                    yield RadioButton(
                        "Dark",
                        id="theme-dark",
                        value=self._config.theme == "dark",
                    )
                    yield RadioButton(
                        "Light",
                        id="theme-light",
                        value=self._config.theme == "light",
                    )

            with Horizontal(classes="settings-row"):
                yield Label("Density", classes="settings-label")
                with RadioSet(id="radio-density", classes="settings-control"):
                    yield RadioButton(
                        "Full",
                        id="density-full",
                        value=self._config.density == "full",
                    )
                    yield RadioButton(
                        "Compact",
                        id="density-compact",
                        value=self._config.density == "compact",
                    )

            with Horizontal(classes="settings-row"):
                yield Label("Motion", classes="settings-label")
                with RadioSet(id="radio-motion", classes="settings-control"):
                    yield RadioButton(
                        "Standard",
                        id="motion-standard",
                        value=self._config.motion == "standard",
                    )
                    yield RadioButton(
                        "Reduced",
                        id="motion-reduced",
                        value=self._config.motion == "reduced",
                    )

            with Horizontal(classes="settings-row"):
                yield Label("Automation", classes="settings-label")
                with RadioSet(id="radio-automation", classes="settings-control"):
                    yield RadioButton(
                        "Observe",
                        id="automation-observe",
                        value=self._config.automation_level == "observe",
                    )
                    yield RadioButton(
                        "Assist",
                        id="automation-assist",
                        value=self._config.automation_level == "assist",
                    )
                    yield RadioButton(
                        "Autopilot",
                        id="automation-autopilot",
                        value=self._config.automation_level == "autopilot",
                    )

        yield Footer()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle any RadioSet change — update config and save immediately."""
        radio_id = event.radio_set.id
        # The pressed RadioButton label is the new value (lower-cased)
        selected_label: str = str(event.pressed.label).lower()

        if radio_id == "radio-theme":
            self._config.theme = selected_label
        elif radio_id == "radio-density":
            self._config.density = selected_label
        elif radio_id == "radio-motion":
            self._config.motion = selected_label
        elif radio_id == "radio-automation":
            self._config.automation_level = selected_label
        else:
            return

        save_config(self._config)
        self.notify(f"Setting saved: {radio_id.replace('radio-', '')} → {selected_label}")
