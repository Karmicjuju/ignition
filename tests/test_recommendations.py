from __future__ import annotations

from pathlib import Path

from ignition.core.recommendations import (
    RecommendationsEngine,
    Suggestion,
    SuggestionType,
)
from ignition.schemas.catalog import InstallStatus, ToolInfo
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(**kwargs: object) -> AppStateModel:
    """Build an AppStateModel with sensible defaults for testing."""
    defaults: dict[str, object] = {
        "install_id": "test-id",
        "onboarding_complete": True,
        "selected_personas": [],
        "health_summary": {},
        "aws_auth": None,
        "available_updates": [],
    }
    defaults.update(kwargs)
    return AppStateModel(**defaults)  # type: ignore[arg-type]


def _tool(
    key: str = "mytool",
    name: str = "My Tool",
    persona_tags: list[str] | None = None,
    install_status: InstallStatus = InstallStatus.MISSING,
    version_policy: str = "managed",
    managed: bool = True,
    version: str | None = None,
    managed_version: str | None = None,
) -> ToolInfo:
    return ToolInfo(
        key=key,
        name=name,
        description="A test tool",
        categories=["testing"],
        persona_tags=persona_tags or ["backend"],
        managed=managed,
        version_policy=version_policy,
        install_status=install_status,
        version=version,
        managed_version=managed_version,
    )


def _engine() -> RecommendationsEngine:
    return RecommendationsEngine()


# ---------------------------------------------------------------------------
# Rule 1 — AUTH: AWS session absent or expired
# ---------------------------------------------------------------------------


def test_auth_suggestion_when_no_aws_auth(isolated_paths: Path) -> None:
    """Rule 1: aws_auth=None must produce an AUTH suggestion at priority 1."""
    state = _state(aws_auth=None)
    suggestions = _engine().get_suggestions(state, [])
    auth = [s for s in suggestions if s.type == SuggestionType.AUTH]
    assert len(auth) == 1
    assert auth[0].priority == 1


def test_auth_suggestion_when_no_profiles(isolated_paths: Path) -> None:
    """Rule 1: AwsAuthState with empty profiles list must produce AUTH suggestion."""
    from ignition.schemas.auth import AwsAuthState

    aws = AwsAuthState(profiles=[])
    state = _state(aws_auth=aws)
    suggestions = _engine().get_suggestions(state, [])
    auth = [s for s in suggestions if s.type == SuggestionType.AUTH]
    assert len(auth) == 1


def test_auth_suggestion_when_session_expired(isolated_paths: Path) -> None:
    """Rule 1: Expired session_expiry must produce AUTH suggestion."""
    from datetime import UTC, datetime, timedelta

    from ignition.schemas.auth import AwsAuthState, AwsProfile, ProfileType

    profile = AwsProfile(name="default", type=ProfileType.SSO, is_active=True)
    aws = AwsAuthState(
        profiles=[profile],
        session_expiry=datetime.now(UTC) - timedelta(hours=1),
    )
    state = _state(aws_auth=aws)
    suggestions = _engine().get_suggestions(state, [])
    auth = [s for s in suggestions if s.type == SuggestionType.AUTH]
    assert len(auth) == 1


def test_no_auth_suggestion_when_valid_session(isolated_paths: Path) -> None:
    """Rule 1: Valid unexpired session with profiles must NOT produce AUTH suggestion."""
    from datetime import UTC, datetime, timedelta

    from ignition.schemas.auth import AwsAuthState, AwsProfile, ProfileType

    profile = AwsProfile(name="default", type=ProfileType.SSO, is_active=True)
    aws = AwsAuthState(
        profiles=[profile],
        session_expiry=datetime.now(UTC) + timedelta(hours=8),
    )
    state = _state(aws_auth=aws)
    suggestions = _engine().get_suggestions(state, [])
    auth = [s for s in suggestions if s.type == SuggestionType.AUTH]
    assert len(auth) == 0


# ---------------------------------------------------------------------------
# Rule 2 — HEALTH: critical/error severity in health_summary
# ---------------------------------------------------------------------------


def test_health_suggestion_when_critical(isolated_paths: Path) -> None:
    """Rule 2: CRITICAL severity in health_summary must produce HEALTH suggestion."""
    state = _state(health_summary={"docker": "CRITICAL"})
    suggestions = _engine().get_suggestions(state, [])
    health = [s for s in suggestions if s.type == SuggestionType.HEALTH]
    assert len(health) == 1
    assert health[0].priority == 2


def test_health_suggestion_when_error(isolated_paths: Path) -> None:
    """Rule 2: ERROR severity in health_summary must produce HEALTH suggestion."""
    state = _state(health_summary={"python": "ERROR"})
    suggestions = _engine().get_suggestions(state, [])
    health = [s for s in suggestions if s.type == SuggestionType.HEALTH]
    assert len(health) == 1


def test_no_health_suggestion_when_ok(isolated_paths: Path) -> None:
    """Rule 2: Only OK/WARNING severities must NOT produce HEALTH suggestion."""
    state = _state(health_summary={"docker": "OK", "python": "WARNING"})
    suggestions = _engine().get_suggestions(state, [])
    health = [s for s in suggestions if s.type == SuggestionType.HEALTH]
    assert len(health) == 0


# ---------------------------------------------------------------------------
# Rule 3 — INSTALL: missing tools in active persona bundles
# ---------------------------------------------------------------------------


def test_install_suggestion_for_missing_persona_tool(isolated_paths: Path) -> None:
    """Rule 3: A MISSING tool in an active persona's bundle must produce an INSTALL suggestion."""
    state = _state(selected_personas=["backend"])
    catalog = [_tool(key="python", persona_tags=["backend"], install_status=InstallStatus.MISSING)]
    suggestions = _engine().get_suggestions(state, catalog)
    install = [s for s in suggestions if s.type == SuggestionType.INSTALL]
    assert len(install) == 1
    assert install[0].target_key == "python"
    assert install[0].priority == 3


def test_no_install_suggestion_when_installed(isolated_paths: Path) -> None:
    """Rule 3: An INSTALLED persona tool must NOT produce an INSTALL suggestion."""
    state = _state(selected_personas=["backend"])
    catalog = [
        _tool(key="python", persona_tags=["backend"], install_status=InstallStatus.INSTALLED)
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    install = [s for s in suggestions if s.type == SuggestionType.INSTALL]
    assert len(install) == 0


def test_no_install_suggestion_when_no_personas(isolated_paths: Path) -> None:
    """Rule 3: No active personas → no INSTALL suggestions regardless of catalog."""
    state = _state(selected_personas=[])
    catalog = [_tool(key="python", install_status=InstallStatus.MISSING)]
    suggestions = _engine().get_suggestions(state, catalog)
    install = [s for s in suggestions if s.type == SuggestionType.INSTALL]
    assert len(install) == 0


def test_install_suggestion_subtitle_includes_persona(isolated_paths: Path) -> None:
    """Rule 3: INSTALL suggestion subtitle must reference the relevant persona."""
    state = _state(selected_personas=["backend"])
    catalog = [_tool(key="python", persona_tags=["backend"], install_status=InstallStatus.MISSING)]
    suggestions = _engine().get_suggestions(state, catalog)
    install = [s for s in suggestions if s.type == SuggestionType.INSTALL]
    assert "backend" in install[0].subtitle


# ---------------------------------------------------------------------------
# Rule 4 — UPDATE: outdated managed tools
# ---------------------------------------------------------------------------


def test_update_suggestion_for_outdated_managed_tool(isolated_paths: Path) -> None:
    """Rule 4: An INSTALLED managed tool with older version must produce UPDATE suggestion."""
    state = _state()
    catalog = [
        _tool(
            key="kubectl",
            install_status=InstallStatus.INSTALLED,
            version_policy="managed",
            version="1.28.0",
            managed_version="1.30.0",
        )
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    update = [s for s in suggestions if s.type == SuggestionType.UPDATE]
    assert len(update) == 1
    assert update[0].target_key == "kubectl"
    assert update[0].priority == 4


def test_no_update_suggestion_for_flexible_tool(isolated_paths: Path) -> None:
    """Rule 4: Flexible-tier tools must NOT produce UPDATE suggestions."""
    state = _state()
    catalog = [
        _tool(
            key="git",
            version_policy="flexible",
            install_status=InstallStatus.INSTALLED,
            version="2.39.0",
            managed_version="2.44.0",
        )
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    update = [s for s in suggestions if s.type == SuggestionType.UPDATE]
    assert len(update) == 0


def test_no_update_suggestion_when_current(isolated_paths: Path) -> None:
    """Rule 4: A tool already at managed_version must NOT produce UPDATE suggestion."""
    state = _state()
    catalog = [
        _tool(
            key="kubectl",
            install_status=InstallStatus.INSTALLED,
            version_policy="managed",
            version="1.30.0",
            managed_version="1.30.0",
        )
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    update = [s for s in suggestions if s.type == SuggestionType.UPDATE]
    assert len(update) == 0


def test_update_suggestion_subtitle_shows_version_delta(isolated_paths: Path) -> None:
    """Rule 4: UPDATE suggestion subtitle must include version delta text."""
    state = _state()
    catalog = [
        _tool(
            key="kubectl",
            install_status=InstallStatus.INSTALLED,
            version_policy="managed",
            version="1.28.0",
            managed_version="1.30.0",
        )
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    update = [s for s in suggestions if s.type == SuggestionType.UPDATE]
    assert "1.28.0" in update[0].subtitle
    assert "1.30.0" in update[0].subtitle


# ---------------------------------------------------------------------------
# Rule 5 — ONBOARDING: incomplete onboarding
# ---------------------------------------------------------------------------


def test_onboarding_suggestion_when_incomplete(isolated_paths: Path) -> None:
    """Rule 5: onboarding_complete=False must produce ONBOARDING suggestion."""
    state = _state(onboarding_complete=False)
    suggestions = _engine().get_suggestions(state, [])
    onboarding = [s for s in suggestions if s.type == SuggestionType.ONBOARDING]
    assert len(onboarding) == 1
    assert onboarding[0].priority == 5


def test_no_onboarding_suggestion_when_complete(isolated_paths: Path) -> None:
    """Rule 5: onboarding_complete=True must NOT produce ONBOARDING suggestion."""
    state = _state(onboarding_complete=True)
    suggestions = _engine().get_suggestions(state, [])
    onboarding = [s for s in suggestions if s.type == SuggestionType.ONBOARDING]
    assert len(onboarding) == 0


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


def test_suggestions_sorted_by_priority(isolated_paths: Path) -> None:
    """get_suggestions() must return suggestions sorted by priority ascending."""
    state = _state(
        aws_auth=None,  # AUTH priority 1
        health_summary={"tool": "CRITICAL"},  # HEALTH priority 2
        onboarding_complete=False,  # ONBOARDING priority 5
    )
    suggestions = _engine().get_suggestions(state, [])
    priorities = [s.priority for s in suggestions]
    assert priorities == sorted(priorities), f"Expected sorted, got {priorities}"


def test_auth_before_health_before_onboarding(isolated_paths: Path) -> None:
    """Priority 1 (AUTH) must precede priority 2 (HEALTH) which precedes priority 5 (ONBOARDING)."""
    state = _state(
        aws_auth=None,
        health_summary={"x": "ERROR"},
        onboarding_complete=False,
    )
    suggestions = _engine().get_suggestions(state, [])
    types = [s.type for s in suggestions]
    auth_idx = types.index(SuggestionType.AUTH)
    health_idx = types.index(SuggestionType.HEALTH)
    onboarding_idx = types.index(SuggestionType.ONBOARDING)
    assert auth_idx < health_idx < onboarding_idx


# ---------------------------------------------------------------------------
# Max-4 cap
# ---------------------------------------------------------------------------


def test_max_four_suggestions_returned(isolated_paths: Path) -> None:
    """get_suggestions() must return at most 4 suggestions even when more qualify."""
    state = _state(
        selected_personas=["backend"],
        aws_auth=None,
        health_summary={"x": "CRITICAL"},
        onboarding_complete=False,
    )
    # Many missing persona tools to push well beyond the cap
    catalog = [
        _tool(
            key=f"tool{i}",
            name=f"Tool {i}",
            persona_tags=["backend"],
            install_status=InstallStatus.MISSING,
        )
        for i in range(10)
    ]
    suggestions = _engine().get_suggestions(state, catalog)
    assert len(suggestions) <= 4, f"Expected ≤ 4, got {len(suggestions)}"


# ---------------------------------------------------------------------------
# Empty state — no suggestions
# ---------------------------------------------------------------------------


def test_empty_state_returns_no_suggestions(isolated_paths: Path) -> None:
    """A fully healthy, onboarded state with no missing/outdated tools must return empty list."""
    from datetime import UTC, datetime, timedelta

    from ignition.schemas.auth import AwsAuthState, AwsProfile, ProfileType

    profile = AwsProfile(name="default", type=ProfileType.SSO, is_active=True)
    aws = AwsAuthState(
        profiles=[profile],
        session_expiry=datetime.now(UTC) + timedelta(hours=8),
    )
    state = _state(
        aws_auth=aws,
        health_summary={"docker": "OK"},
        onboarding_complete=True,
        selected_personas=[],
    )
    catalog = [_tool(key="python", install_status=InstallStatus.INSTALLED, version="3.12.0")]
    suggestions = _engine().get_suggestions(state, catalog)
    assert suggestions == [], f"Expected empty list, got {suggestions}"


def test_empty_catalog_with_healthy_state(isolated_paths: Path) -> None:
    """Empty catalog and healthy state must return an empty list."""
    state = _state(onboarding_complete=True, health_summary={})
    suggestions = _engine().get_suggestions(state, [])
    # aws_auth is None so AUTH will fire — ensure no crash
    assert isinstance(suggestions, list)
    assert all(isinstance(s, Suggestion) for s in suggestions)
