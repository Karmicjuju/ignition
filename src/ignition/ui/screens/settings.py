from __future__ import annotations

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Label, RadioButton, RadioSet, Static

from ignition.core.config import load_config, save_config
from ignition.core.state import save_state
from ignition.schemas.config import AppConfigModel
from ignition.schemas.state import AppStateModel

_ALL_PERSONAS: list[tuple[str, str]] = [
    ("backend", "Backend Engineer"),
    ("frontend", "Frontend Engineer"),
    ("devops", "DevOps / Platform"),
    ("security", "Security"),
    ("contractor", "Contractor"),
]


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

    #personas-section {
        margin-top: 2;
        border-top: solid $surface;
        padding-top: 1;
        height: auto;
    }

    #personas-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #active-personas-label {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #btn-manage-personas {
        margin-top: 1;
        width: auto;
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

            with Horizontal(classes="settings-row"):
                yield Label("Release channel", classes="settings-label")
                with RadioSet(id="radio-channel", classes="settings-control"):
                    yield RadioButton(
                        "Stable",
                        id="channel-stable",
                        value=self._state.preferred_channel == "stable",
                    )
                    yield RadioButton(
                        "Beta",
                        id="channel-beta",
                        value=self._state.preferred_channel == "beta",
                    )
                    yield RadioButton(
                        "Experimental",
                        id="channel-experimental",
                        value=self._state.preferred_channel == "experimental",
                    )

            with Vertical(id="personas-section"):
                yield Static("Personas", id="personas-title")
                active = self._state.selected_personas
                if active:
                    names = [label for pid, label in _ALL_PERSONAS if pid in active]
                    yield Static(f"Active: {', '.join(names)}", id="active-personas-label")
                else:
                    yield Static("No personas selected.", id="active-personas-label")
                yield Button(
                    "Manage personas",
                    id="btn-manage-personas",
                    variant="default",
                    tooltip="Add or remove personas to tailor tool recommendations.",
                )

        yield Footer()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle any RadioSet change — update config and save immediately."""
        radio_id = event.radio_set.id
        # The pressed RadioButton label is the new value (lower-cased)
        selected_label: str = str(event.pressed.label).lower()

        if radio_id == "radio-theme":
            self._config.theme = selected_label
            save_config(self._config)
        elif radio_id == "radio-density":
            self._config.density = selected_label
            save_config(self._config)
        elif radio_id == "radio-motion":
            self._config.motion = selected_label
            save_config(self._config)
        elif radio_id == "radio-automation":
            self._config.automation_level = selected_label
            save_config(self._config)
        elif radio_id == "radio-channel":
            self._state.preferred_channel = selected_label
            save_state(self._state)
        else:
            return

        self.notify(f"Setting saved: {radio_id.replace('radio-', '')} -> {selected_label}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Settings button presses."""
        if event.button.id == "btn-manage-personas":
            self.app.push_screen(PersonaManagerModal(self._state), self._on_personas_updated)

    def _on_personas_updated(self, new_personas: list[str] | None) -> None:
        """Callback invoked when PersonaManagerModal is dismissed."""
        if new_personas is None:
            return
        self._state.selected_personas = new_personas
        save_state(self._state)
        # Refresh the active personas display
        active = self._state.selected_personas
        if active:
            names = [label for pid, label in _ALL_PERSONAS if pid in active]
            display = f"Active: {', '.join(names)}"
        else:
            display = "No personas selected."
        import contextlib

        with contextlib.suppress(Exception):
            self.query_one("#active-personas-label", Static).update(display)

    @work(exclusive=False)
    async def _install_persona_tools(self, persona_id: str) -> None:
        """Install recommended tools for a newly added persona."""
        from ignition.core.catalog import CatalogService
        from ignition.core.installer import InstallerEngine

        catalog = CatalogService()
        installer = InstallerEngine(self._state)
        tools = [
            t
            for t in catalog.get_tools_for_personas([persona_id])
            if t.install_status.value in ("missing", "failed")
        ]
        if not tools:
            return
        self.notify(f"Installing {len(tools)} tool(s) for {persona_id} persona…")
        await installer.install_bundle(tools)
        save_state(self._state)
        self.notify("Persona tools installed.", title=persona_id.capitalize())


# ---------------------------------------------------------------------------
# PersonaInstallPromptModal
# ---------------------------------------------------------------------------


class PersonaInstallPromptModal(ModalScreen[bool]):
    """Prompt the user to install tools recommended for a newly added persona.

    Returns True if the user chooses to install, False if they skip.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Skip"),
    ]

    DEFAULT_CSS = """
    PersonaInstallPromptModal {
        align: center middle;
    }

    #prompt-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: round $border;
        padding: 1 2;
    }

    #prompt-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #prompt-tools {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #prompt-buttons {
        height: auto;
        margin-top: 1;
    }

    #prompt-buttons Button {
        margin-right: 1;
    }
    """

    def __init__(self, persona_id: str, tool_names: list[str]) -> None:
        super().__init__()
        self._persona_id = persona_id
        self._tool_names = tool_names

    def compose(self) -> ComposeResult:
        label = next(
            (lbl for pid, lbl in _ALL_PERSONAS if pid == self._persona_id),
            self._persona_id,
        )
        with Vertical(id="prompt-dialog"):
            yield Static(f"Install tools for {label}?", id="prompt-title")
            if self._tool_names:
                tools_list = "\n".join(f"  - {n}" for n in self._tool_names)
                yield Static(f"Recommended tools:\n{tools_list}", id="prompt-tools")
            else:
                yield Static("No new tools to install.", id="prompt-tools")
            with Horizontal(id="prompt-buttons"):
                yield Button(
                    "Install",
                    id="btn-install",
                    variant="primary",
                    tooltip="Install the recommended tools for this persona.",
                )
                yield Button(
                    "Skip",
                    id="btn-skip",
                    variant="default",
                    tooltip="Skip tool installation for this persona.",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-install":
            self.dismiss(True)
        elif event.button.id == "btn-skip":
            self.dismiss(False)


# ---------------------------------------------------------------------------
# PersonaManagerModal
# ---------------------------------------------------------------------------


class PersonaManagerModal(ModalScreen[list[str]]):
    """Modal for managing active personas.

    Displays a checkbox for each of the 5 personas. Checking a new persona
    triggers PersonaInstallPromptModal. Unchecking removes the persona and
    shows a notification. Dismisses with the updated list of selected personas.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    DEFAULT_CSS = """
    PersonaManagerModal {
        align: center middle;
    }

    #persona-dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    #persona-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #persona-note {
        color: $text-secondary;
        margin-bottom: 1;
    }

    #persona-checkboxes {
        height: auto;
        margin-bottom: 1;
    }

    #persona-done {
        width: auto;
        margin-top: 1;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        # Work with a mutable copy so we can dismiss with the result
        self._selected: list[str] = list(state.selected_personas)

    def compose(self) -> ComposeResult:
        with Vertical(id="persona-dialog"):
            yield Static("Manage Personas", id="persona-title")
            yield Static(
                "Check personas to activate. Unchecking removes the persona"
                " — tools remain installed.",
                id="persona-note",
            )
            with Vertical(id="persona-checkboxes"):
                for pid, label in _ALL_PERSONAS:
                    yield Checkbox(
                        label,
                        id=f"persona-{pid}",
                        value=pid in self._selected,
                        tooltip=f"Toggle the {label} persona on or off.",
                    )
            yield Button(
                "Done",
                id="persona-done",
                variant="primary",
                tooltip="Save persona selections and close this panel.",
            )

    def action_dismiss_modal(self) -> None:
        self.dismiss(self._selected)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "persona-done":
            self.dismiss(self._selected)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle persona checkbox toggle."""
        cb_id = event.checkbox.id or ""
        if not cb_id.startswith("persona-"):
            return
        persona_id = cb_id[len("persona-") :]
        if event.value:
            # Persona added
            if persona_id not in self._selected:
                self._selected.append(persona_id)
                self._prompt_install(persona_id)
        else:
            # Persona removed
            if persona_id in self._selected:
                self._selected.remove(persona_id)
                self.app.notify(
                    "Tools from this persona remain installed. "
                    "They will no longer appear in health checks for this role.",
                    title=f"Persona removed: {persona_id}",
                )

    def _prompt_install(self, persona_id: str) -> None:
        """Push the install-prompt modal for a newly added persona."""
        from ignition.core.catalog import CatalogService

        catalog = CatalogService()
        missing_tools = [
            t.name
            for t in catalog.get_tools_for_personas([persona_id])
            if t.install_status.value in ("missing", "failed")
        ]
        self.app.push_screen(
            PersonaInstallPromptModal(persona_id, missing_tools),
            lambda install: self._handle_install_choice(persona_id, install),
        )

    def _handle_install_choice(self, persona_id: str, install: bool | None) -> None:
        """Callback from PersonaInstallPromptModal."""
        if install:
            # Trigger install from the parent SettingsScreen
            # We reach it via the app screen stack
            for screen in reversed(self.app.screen_stack):
                if isinstance(screen, SettingsScreen):
                    screen._install_persona_tools(persona_id)
                    break
