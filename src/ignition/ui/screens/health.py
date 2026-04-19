from __future__ import annotations

import contextlib
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Collapsible, Footer, Header, Static

from ignition.core.health import HealthEngine
from ignition.schemas.health import CheckResult, FixType, HealthState
from ignition.schemas.state import AppStateModel

_STATE_ICON: dict[HealthState, str] = {
    HealthState.HEALTHY: "✓",
    HealthState.RECOMMENDED: "→",
    HealthState.NEEDS_ATTENTION: "⚠",
    HealthState.MANUAL: "✗",
}

_STATE_CLASS: dict[HealthState, str] = {
    HealthState.HEALTHY: "state-healthy",
    HealthState.RECOMMENDED: "state-recommended",
    HealthState.NEEDS_ATTENTION: "state-attention",
    HealthState.MANUAL: "state-manual",
}

_STATE_LABEL: dict[HealthState, str] = {
    HealthState.HEALTHY: "Healthy",
    HealthState.RECOMMENDED: "Rec. fix",
    HealthState.NEEDS_ATTENTION: "Needs attn",
    HealthState.MANUAL: "Manual",
}

_CATEGORY_LABELS: dict[str, str] = {
    "tools": "Tools",
    "configs": "Configs",
    "shell_integration": "Shell integration",
    "permissions": "Permissions",
}

ALL_CATEGORIES = ("tools", "configs", "shell_integration", "permissions")


class IssueRow(Horizontal):
    """A single check-result row inside a category collapsible."""

    DEFAULT_CSS = """
    IssueRow {
        height: auto;
        padding: 0 1;
        min-height: 1;
    }

    IssueRow .issue-icon {
        width: 3;
    }

    IssueRow .issue-label {
        width: 1fr;
    }

    IssueRow .issue-detail {
        color: $text-secondary;
        width: 1fr;
    }

    IssueRow .issue-state {
        width: 14;
        text-align: right;
    }

    IssueRow .state-healthy {
        color: $success;
    }

    IssueRow .state-recommended {
        color: $warning;
    }

    IssueRow .state-attention {
        color: $error;
    }

    IssueRow .state-manual {
        color: $error;
        text-style: bold;
    }

    IssueRow .issue-action {
        width: auto;
        margin-left: 1;
        min-width: 10;
    }

    IssueRow .issue-recheck {
        width: auto;
        margin-left: 1;
        min-width: 10;
    }
    """

    def __init__(self, result: CheckResult) -> None:
        super().__init__()
        self._result = result

    def compose(self) -> ComposeResult:
        icon = _STATE_ICON.get(self._result.state, "?")
        state_class = _STATE_CLASS.get(self._result.state, "")
        state_label = _STATE_LABEL.get(self._result.state, self._result.state.value)

        yield Static(icon, classes=f"issue-icon {state_class}")
        yield Static(self._result.label, classes="issue-label")
        yield Static(self._result.detail, classes="issue-detail")
        yield Static(state_label, classes=f"issue-state {state_class}")

        if self._result.fix_type == FixType.AUTO:
            yield Button(
                "Apply fix",
                id=f"btn-fix-{self._result.check_id}",
                variant="warning",
                classes="issue-action",
                tooltip=f"Automatically apply fix for {self._result.label}.",
            )
        elif self._result.fix_type == FixType.COPY_PASTE and self._result.fix_command:
            yield Static(
                f"[dim]{self._result.fix_command}[/dim]",
                classes="issue-action",
            )

        if self._result.fix_type != FixType.NONE:
            yield Button(
                "Re-check",
                id=f"btn-recheck-{self._result.check_id}",
                classes="issue-recheck",
                tooltip=f"Re-run the check for {self._result.label}.",
            )


class HealthScreen(Screen[None]):
    """Health & Diagnostics screen.

    Displays check results grouped by category in Collapsible widgets.
    Supports per-issue Apply fix (AUTO) and Re-check buttons, plus a
    full-screen Scan button.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "scan", "Scan"),
    ]

    DEFAULT_CSS = """
    HealthScreen {
        background: $background;
    }

    #toolbar {
        height: auto;
        padding: 0 1;
        align: right middle;
    }

    #scan-status {
        width: 1fr;
        color: $text-secondary;
        padding: 0 1;
    }

    #results-container {
        height: 1fr;
        padding: 1;
    }

    Collapsible {
        margin-bottom: 1;
    }

    .category-summary {
        color: $text-secondary;
        padding: 0 2;
        height: auto;
    }

    .no-results {
        color: $text-secondary;
        padding: 1 2;
    }
    """

    def __init__(self, state: AppStateModel) -> None:
        super().__init__()
        self._state = state
        self._engine = HealthEngine()
        self._results: list[CheckResult] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Static("Press Scan to run health checks.", id="scan-status")
            yield Button("Scan", id="btn-scan", variant="primary", tooltip="Run all health checks.")
        with Vertical(id="results-container"):
            yield Static("No scan results yet.", classes="no-results", id="empty-state")
        yield Footer()

    def on_mount(self) -> None:
        self._run_scan()

    @work
    async def _run_scan(self, categories: list[str] | None = None) -> None:
        """Run a full or partial health scan and update the display."""
        self._set_status("Scanning…")
        try:
            results = await self._engine.run_scan(categories)
            self._results = results
            await self._render_results(results)
            self._set_status(self._summarise(results))
        except Exception as exc:
            self._set_status(f"Scan failed: {exc}")

    def _set_status(self, text: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#scan-status", Static).update(text)

    def _summarise(self, results: list[CheckResult]) -> str:
        healthy = sum(1 for r in results if r.state == HealthState.HEALTHY)
        attn = sum(1 for r in results if r.state == HealthState.NEEDS_ATTENTION)
        rec = sum(1 for r in results if r.state == HealthState.RECOMMENDED)
        total = len(results)
        parts = [f"{total} checks"]
        if healthy:
            parts.append(f"{healthy} healthy")
        if rec:
            parts.append(f"{rec} rec. fix")
        if attn:
            parts.append(f"{attn} needs attn")
        return " · ".join(parts)

    async def _render_results(self, results: list[CheckResult]) -> None:
        """Rebuild the results container with Collapsible widgets per category."""
        container = self.query_one("#results-container", Vertical)
        await container.remove_children()

        if not results:
            await container.mount(Static("No issues found.", classes="no-results"))
            return

        # Group by category preserving display order
        grouped: dict[str, list[CheckResult]] = {}
        for cat in ALL_CATEGORIES:
            grouped[cat] = []
        for result in results:
            if result.category in grouped:
                grouped[result.category].append(result)
            else:
                grouped.setdefault(result.category, []).append(result)

        for cat in ALL_CATEGORIES:
            cat_results = grouped.get(cat, [])
            if not cat_results:
                continue

            cat_label = _CATEGORY_LABELS.get(cat, cat)
            # Build summary suffix
            attn_count = sum(1 for r in cat_results if r.state == HealthState.NEEDS_ATTENTION)
            rec_count = sum(1 for r in cat_results if r.state == HealthState.RECOMMENDED)
            healthy_count = sum(1 for r in cat_results if r.state == HealthState.HEALTHY)
            suffixes: list[str] = []
            if healthy_count:
                suffixes.append(f"{healthy_count} Healthy")
            if rec_count:
                suffixes.append(f"{rec_count} Rec. fix")
            if attn_count:
                suffixes.append(f"{attn_count} Needs attn")
            title = f"{cat_label} ({len(cat_results)} checks)"
            if suffixes:
                title += "  —  " + "  ".join(suffixes)

            collapsible = Collapsible(title=title, id=f"cat-{cat}")
            rows: list[IssueRow] = [IssueRow(r) for r in cat_results]

            await container.mount(collapsible)
            for row in rows:
                await collapsible.mount(row)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-scan":
            self._run_scan()
            return

        if btn_id.startswith("btn-fix-"):
            check_id = btn_id[len("btn-fix-") :]
            self._apply_fix(check_id)
            return

        if btn_id.startswith("btn-recheck-"):
            check_id = btn_id[len("btn-recheck-") :]
            self._recheck_single(check_id)
            return

    @work
    async def _apply_fix(self, check_id: str) -> None:
        """Apply an automatic fix for the given check_id."""
        success = await self._engine.apply_fix(check_id)
        if success:
            self.notify(f"Fix applied for {check_id}. Re-checking…")
            # Find the category for this check_id and re-run it
            result = next((r for r in self._results if r.check_id == check_id), None)
            if result:
                await self._rerun_category(result.category)
        else:
            self.notify(f"Fix could not be applied for {check_id}.", severity="warning")

    @work
    async def _recheck_single(self, check_id: str) -> None:
        """Re-run the health check for a single check_id."""
        result = next((r for r in self._results if r.check_id == check_id), None)
        if result is None:
            return
        await self._rerun_category(result.category)

    async def _rerun_category(self, category: str) -> None:
        """Re-scan a single category and refresh that section of the display."""
        try:
            new_results = await self._engine.run_scan(categories=[category])
        except Exception as exc:
            self.notify(f"Re-check failed: {exc}", severity="error")
            return

        # Replace results for this category
        self._results = [r for r in self._results if r.category != category] + new_results
        await self._render_results(self._results)
        self._set_status(self._summarise(self._results))

    def action_scan(self) -> None:
        """Keyboard shortcut: ctrl+r triggers a full scan."""
        self._run_scan()
