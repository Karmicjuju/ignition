from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ignition.core.activity import ActivityLog
from ignition.schemas.activity import ActivityEvent, Outcome
from ignition.schemas.state import AppStateModel

_OUTCOME_ICON: dict[Outcome, str] = {
    Outcome.SUCCESS: "✓",
    Outcome.FAILURE: "✗",
    Outcome.PENDING: "…",
    Outcome.CANCELLED: "-",
}

_SEPARATOR_ID_PREFIX = "sep-"
_ROW_ID_PREFIX = "row-"


def _day_label(event_ts: datetime) -> str:
    """Return 'Today', 'Yesterday', or a YYYY-MM-DD string."""
    now = datetime.now(UTC)
    event_date = event_ts.astimezone(UTC).date()
    today = now.date()
    if event_date == today:
        return "Today"
    delta = today - event_date
    if delta.days == 1:
        return "Yesterday"
    return event_date.strftime("%Y-%m-%d")


class _ActivityRow(Static):
    """A single expandable activity event row."""

    DEFAULT_CSS = """
    _ActivityRow {
        padding: 0 2;
        height: auto;
    }

    _ActivityRow.--selected {
        background: $accent 20%;
    }

    _ActivityRow .detail-text {
        color: $text-secondary;
        padding: 0 4;
    }
    """

    def __init__(self, event: ActivityEvent, *, row_index: int) -> None:
        super().__init__(id=f"{_ROW_ID_PREFIX}{row_index}")
        self._event = event
        self._expanded = False
        self._index = row_index
        self._selected = False

    def render(self) -> str:
        icon = _OUTCOME_ICON.get(self._event.outcome, "?")
        ts = self._event.timestamp.astimezone(UTC).strftime("%H:%M")
        event_label = self._event.event_type.value.replace("_", " ")
        base = f"{icon} {ts}  {self._event.summary}  [{event_label}]"
        if self._expanded and self._event.detail:
            return base + f"\n    {self._event.detail}"
        return base

    def toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self.refresh()

    def set_selected(self, value: bool) -> None:
        self._selected = value
        if value:
            self.add_class("--selected")
        else:
            self.remove_class("--selected")


class _DaySeparator(Static):
    """Non-selectable day group header."""

    DEFAULT_CSS = """
    _DaySeparator {
        color: $text-secondary;
        text-style: bold;
        padding: 1 2 0 2;
    }
    """


class ActivityScreen(Screen[None]):
    """Chronological activity feed with day grouping, j/k navigation, and expand/collapse."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("j", "nav_down", "Down", show=False),
        Binding("k", "nav_up", "Up", show=False),
        Binding("enter", "toggle_expand", "Expand/Collapse", show=True),
    ]

    DEFAULT_CSS = """
    ActivityScreen {
        background: $background;
    }

    #activity-scroll {
        height: 1fr;
        padding: 0;
    }

    #activity-feed {
        height: auto;
    }

    #activity-empty {
        color: $text-secondary;
        padding: 2;
        text-align: center;
    }
    """

    def __init__(self, state: AppStateModel, activity_log: ActivityLog | None = None) -> None:
        super().__init__()
        self._state = state
        self._activity_log = activity_log or ActivityLog()
        self._rows: list[_ActivityRow] = []
        self._cursor: int = 0  # index into self._rows

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="activity-scroll"):
            yield Vertical(id="activity-feed")
        yield Footer()

    def on_mount(self) -> None:
        self._build_feed()

    def _build_feed(self) -> None:
        feed = self.query_one("#activity-feed", Vertical)
        feed.remove_children()
        self._rows.clear()
        self._cursor = 0

        events = list(reversed(self._activity_log.get_all()))

        if not events:
            feed.mount(Static("No activity recorded yet.", id="activity-empty"))
            return

        current_day: str | None = None

        for row_index, event in enumerate(events):
            day = _day_label(event.timestamp)
            if day != current_day:
                current_day = day
                sep_id = f"{_SEPARATOR_ID_PREFIX}{day.replace(' ', '-')}"
                feed.mount(_DaySeparator(day, id=sep_id))

            row = _ActivityRow(event, row_index=row_index)
            self._rows.append(row)
            feed.mount(row)

        # Highlight first row
        if self._rows:
            self._rows[0].set_selected(True)

    def action_nav_down(self) -> None:
        if not self._rows:
            return
        if self._cursor < len(self._rows) - 1:
            self._rows[self._cursor].set_selected(False)
            self._cursor += 1
            self._rows[self._cursor].set_selected(True)
            self._rows[self._cursor].scroll_visible()

    def action_nav_up(self) -> None:
        if not self._rows:
            return
        if self._cursor > 0:
            self._rows[self._cursor].set_selected(False)
            self._cursor -= 1
            self._rows[self._cursor].set_selected(True)
            self._rows[self._cursor].scroll_visible()

    def action_toggle_expand(self) -> None:
        if not self._rows:
            return
        self._rows[self._cursor].toggle_expand()
