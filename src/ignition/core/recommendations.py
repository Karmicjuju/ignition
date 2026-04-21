from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ignition.core.logging import get_logger
from ignition.schemas.catalog import InstallStatus, ToolInfo
from ignition.schemas.state import AppStateModel

_MAX_SUGGESTIONS = 4

# Channel order for comparisons: lower index = more stable
_CHANNEL_ORDER = ("stable", "beta", "experimental")


class SuggestionType(StrEnum):
    INSTALL = "install"
    UPDATE = "update"
    AUTH = "auth"
    HEALTH = "health"
    ONBOARDING = "onboarding"


@dataclass
class Suggestion:
    """A single actionable recommendation for the user."""

    type: SuggestionType
    priority: int  # 1 = highest priority
    title: str  # one-line action text
    subtitle: str  # secondary label (e.g. "recommended for backend")
    target_key: str | None = field(default=None)  # tool_key for INSTALL/UPDATE suggestions


class RecommendationsEngine:
    """Produces ranked, persona-aware suggestions based on current app state.

    Suggestion rules (in priority order):
      1. AWS session expired or not configured → AUTH, priority 1
      2. Health issues with severity CRITICAL or ERROR → HEALTH, priority 2
      3. Tools in active persona bundles that are MISSING → INSTALL per tool, priority 3
      4. Tools that are OUTDATED (managed tier) → UPDATE per tool, priority 4
      5. Onboarding incomplete → ONBOARDING, priority 5

    At most _MAX_SUGGESTIONS (4) suggestions are returned, sorted by priority ascending.
    """

    def __init__(self) -> None:
        self._log = get_logger("ignition.core.recommendations")

    def get_suggestions(
        self,
        state: AppStateModel,
        catalog: list[ToolInfo],
    ) -> list[Suggestion]:
        """Return up to 4 suggestions sorted by priority (lowest number = first).

        Args:
            state: Current AppStateModel including persona selections, health summary,
                   AWS auth state, and onboarding status.
            catalog: Full tool catalogue (already channel-filtered if desired).

        Returns:
            A list of Suggestion, at most _MAX_SUGGESTIONS entries, sorted by priority.
        """
        suggestions: list[Suggestion] = []

        # Rule 1 — AWS auth missing or expired (priority 1)
        if self._needs_auth(state):
            suggestions.append(
                Suggestion(
                    type=SuggestionType.AUTH,
                    priority=1,
                    title="Configure AWS access",
                    subtitle="AWS session not configured or expired",
                    target_key=None,
                )
            )

        # Rule 2 — Health issues (priority 2)
        if self._has_health_issues(state):
            suggestions.append(
                Suggestion(
                    type=SuggestionType.HEALTH,
                    priority=2,
                    title="Review system health",
                    subtitle="Critical or error-level issues detected",
                    target_key=None,
                )
            )

        # Rule 3 — Missing persona tools (priority 3)
        persona_set = set(state.selected_personas)
        if persona_set:
            for tool in catalog:
                if len(suggestions) >= _MAX_SUGGESTIONS:
                    break
                if not set(tool.persona_tags) & persona_set:
                    continue
                if tool.install_status != InstallStatus.MISSING:
                    continue
                persona_labels = sorted(set(tool.persona_tags) & persona_set)
                subtitle = f"recommended for {', '.join(persona_labels)}"
                suggestions.append(
                    Suggestion(
                        type=SuggestionType.INSTALL,
                        priority=3,
                        title=f"Install {tool.name}",
                        subtitle=subtitle,
                        target_key=tool.key,
                    )
                )

        # Rule 4 — Outdated managed tools (priority 4)
        if len(suggestions) < _MAX_SUGGESTIONS:
            from packaging.version import Version

            for tool in catalog:
                if len(suggestions) >= _MAX_SUGGESTIONS:
                    break
                if tool.version_policy == "flexible":
                    continue
                if tool.install_status != InstallStatus.INSTALLED:
                    continue
                if tool.version is None or tool.managed_version is None:
                    continue
                try:
                    if Version(tool.version) < Version(tool.managed_version):
                        suggestions.append(
                            Suggestion(
                                type=SuggestionType.UPDATE,
                                priority=4,
                                title=f"Update {tool.name}",
                                subtitle=f"{tool.version} → {tool.managed_version} available",
                                target_key=tool.key,
                            )
                        )
                except Exception:
                    pass

        # Rule 5 — Onboarding incomplete (priority 5)
        if not state.onboarding_complete and len(suggestions) < _MAX_SUGGESTIONS:
            suggestions.append(
                Suggestion(
                    type=SuggestionType.ONBOARDING,
                    priority=5,
                    title="Complete onboarding",
                    subtitle="Finish setup to unlock all features",
                    target_key=None,
                )
            )

        # Sort by priority and cap at _MAX_SUGGESTIONS
        suggestions.sort(key=lambda s: s.priority)
        result = suggestions[:_MAX_SUGGESTIONS]

        self._log.info(
            "recommendations.generated",
            count=len(result),
            personas=list(persona_set),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _needs_auth(self, state: AppStateModel) -> bool:
        """Return True when AWS auth is absent, has no profiles, or session is expired."""
        from ignition.schemas.auth import AwsAuthState

        aws = state.aws_auth
        if aws is None:
            return True
        if not isinstance(aws, AwsAuthState):
            return True
        # No profiles configured at all
        if not aws.profiles:
            return True
        # Session expiry known and in the past
        if aws.session_expiry is not None:
            from datetime import UTC, datetime

            if aws.session_expiry < datetime.now(UTC):
                return True
        return False

    def _has_health_issues(self, state: AppStateModel) -> bool:
        """Return True when any health_summary entry is CRITICAL or ERROR."""
        for severity in state.health_summary.values():
            if severity.upper() in ("CRITICAL", "ERROR"):
                return True
        return False
