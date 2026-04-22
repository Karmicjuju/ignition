from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ignition.core.install_id import get_or_create_install_id
from ignition.core.logging import get_logger
from ignition.core.paths import state_dir
from ignition.schemas.config import AppConfigModel
from ignition.schemas.telemetry import TelemetryEvent

_BUFFER_MAX = 1000


class TelemetryBuffer:
    """Local NDJSON buffer for anonymous telemetry events.

    Writes are synchronous (< 1 ms). No HTTP upload is performed here —
    the upload pipeline awaits a separate security review.

    The buffer is capped at ``_BUFFER_MAX`` lines. When the cap is exceeded
    the oldest entries are dropped to keep the file bounded.

    Args:
        config: AppConfigModel instance; recording is a no-op when
            ``config.telemetry_enabled`` is ``False``.
    """

    def __init__(self, config: AppConfigModel) -> None:
        self._config = config
        self._log = get_logger("ignition.core.telemetry")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        event_name: str,
        properties: dict[str, object] | None = None,
    ) -> None:
        """Append a single telemetry event to the local buffer.

        Is a no-op when ``config.telemetry_enabled`` is ``False``.
        Validates the event via ``TelemetryEvent`` before writing.
        Enforces the ``_BUFFER_MAX`` cap by dropping the oldest lines.

        Args:
            event_name: Short snake_case event name (e.g. ``"app_launched"``).
            properties: Optional free-form metadata attached to the event.
        """
        if not self._config.telemetry_enabled:
            return

        event = TelemetryEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            install_id=get_or_create_install_id(),
            event_name=event_name,
            properties=properties or {},
        )

        buffer_path = state_dir() / "telemetry_buffer.ndjson"
        line = event.model_dump_json() + "\n"

        try:
            # Append the new line
            with buffer_path.open("a", encoding="utf-8") as fh:
                fh.write(line)

            # Trim if over cap
            self._trim(buffer_path)
        except Exception as exc:
            self._log.warning(
                "telemetry.record_failed",
                event_name=event_name,
                reason=str(exc),
            )

    def flush_pending(self) -> list[TelemetryEvent]:
        """Read all buffered events and return them as validated objects.

        Malformed NDJSON lines are skipped with a warning. The buffer file
        is **not** cleared by this call — use ``clear()`` after processing.

        Returns:
            A list of ``TelemetryEvent`` objects, in insertion order.
        """
        buffer_path = state_dir() / "telemetry_buffer.ndjson"
        if not buffer_path.exists():
            return []

        events: list[TelemetryEvent] = []
        try:
            raw_text = buffer_path.read_text(encoding="utf-8")
        except Exception as exc:
            self._log.warning("telemetry.flush_read_failed", reason=str(exc))
            return []

        for i, line in enumerate(raw_text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(TelemetryEvent.model_validate_json(line))
            except Exception as exc:
                self._log.warning(
                    "telemetry.flush_line_skipped",
                    line_number=i,
                    reason=str(exc),
                )

        return events

    def clear(self) -> None:
        """Truncate the buffer file, removing all buffered events.

        The file is kept on disk (zero bytes) so that subsequent appends
        do not need to create a new file.
        """
        buffer_path = state_dir() / "telemetry_buffer.ndjson"
        try:
            buffer_path.write_text("", encoding="utf-8")
            self._log.info("telemetry.buffer_cleared")
        except Exception as exc:
            self._log.warning("telemetry.clear_failed", reason=str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _trim(self, buffer_path: Path) -> None:
        """Drop oldest lines when the buffer exceeds ``_BUFFER_MAX`` entries.

        Re-reads the file, slices to the newest ``_BUFFER_MAX`` lines,
        and writes back. Callers pass a path already resolved via a
        ``ignition.core.paths`` helper.
        """
        try:
            raw = buffer_path.read_text(encoding="utf-8")
            lines = [ln for ln in raw.splitlines() if ln.strip()]
            if len(lines) <= _BUFFER_MAX:
                return
            trimmed = "\n".join(lines[-_BUFFER_MAX:]) + "\n"
            buffer_path.write_text(trimmed, encoding="utf-8")
            self._log.info(
                "telemetry.buffer_trimmed",
                dropped=len(lines) - _BUFFER_MAX,
                kept=_BUFFER_MAX,
            )
        except Exception as exc:
            self._log.warning("telemetry.trim_failed", reason=str(exc))
