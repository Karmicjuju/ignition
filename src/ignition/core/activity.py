from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from ignition.core import paths
from ignition.core.logging import get_logger
from ignition.schemas.activity import ActivityEvent, EventType, Outcome

_ACTIVITY_CAP = 500


class ActivityLog:
    """Append-only structured activity feed with JSON persistence.

    Events are persisted to ``paths.activity_file()`` as a JSON array.
    The array is capped at ``_ACTIVITY_CAP`` entries (oldest removed first).
    Every ``append()`` call writes the full array atomically.
    """

    def __init__(self) -> None:
        self._log = get_logger("ignition.core.activity")
        self._events: list[ActivityEvent] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        event_type: EventType,
        outcome: Outcome,
        summary: str,
        *,
        tool_key: str | None = None,
        detail: str = "",
    ) -> ActivityEvent:
        """Create and persist a new ActivityEvent.

        Args:
            event_type: The type of event (e.g. TOOL_INSTALL, AUTH_SIGN_IN).
            outcome: The result of the action (SUCCESS, FAILURE, etc.).
            summary: A one-line human-readable description.
            tool_key: Optional tool identifier for tool-related events.
            detail: Optional extended log output or description.

        Returns:
            The newly created ActivityEvent.
        """
        event = ActivityEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            event_type=event_type,
            tool_key=tool_key,
            outcome=outcome,
            summary=summary,
            detail=detail,
        )
        self._events.append(event)

        # Enforce cap — drop oldest entries
        if len(self._events) > _ACTIVITY_CAP:
            self._events = self._events[-_ACTIVITY_CAP:]

        self._persist()

        try:
            from ignition.core.state import load_state, save_state

            state = load_state()
            state.last_activity_event_id = event.id
            save_state(state)
        except Exception as exc:
            self._log.warning("activity.state_update_failed", reason=str(exc))

        self._log.info(
            "activity.appended",
            event_id=event.id,
            event_type=event.event_type,
            outcome=event.outcome,
        )
        return event

    def get_recent(self, n: int = 50) -> list[ActivityEvent]:
        """Return the most recent *n* events, newest last.

        Args:
            n: Maximum number of events to return (default 50).

        Returns:
            A list of ActivityEvent instances, oldest-first within the slice.
        """
        return list(self._events[-n:])

    def get_all(self) -> list[ActivityEvent]:
        """Return all persisted events, oldest first."""
        return list(self._events)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Write the full event array to disk as a JSON array."""
        path = paths.activity_file()
        try:
            payload = [e.model_dump(mode="json") for e in self._events]
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            self._log.warning("activity.persist_failed", reason=str(exc))

    def _load(self) -> list[ActivityEvent]:
        """Load events from disk. Returns an empty list on any error."""
        log = get_logger("ignition.core.activity")
        path = paths.activity_file()
        if not path.exists():
            return []
        try:
            raw: list[Any] = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                log.warning("activity.load_invalid_format", path=str(path))
                return []
            events: list[ActivityEvent] = []
            for item in raw:
                try:
                    events.append(ActivityEvent.model_validate(item))
                except Exception as exc:
                    log.warning("activity.load_event_skipped", reason=str(exc))
            return events
        except Exception as exc:
            log.warning("activity.load_failed", reason=str(exc))
            return []
