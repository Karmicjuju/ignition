from __future__ import annotations

from pathlib import Path

import pytest

from ignition.app import IgnitionApp
from ignition.core.demo import (
    DEMO_TOOL_LIST,
    seed_demo_state,
    seed_scenario_healthy_devops,
    seed_scenario_needs_attention,
    seed_scenario_partially_onboarded,
)
from ignition.schemas.state import AppStateModel

# ---------------------------------------------------------------------------
# Group 1 — seed_demo_state (backwards-compat alias) unit tests (sync)
# ---------------------------------------------------------------------------


def test_seed_demo_state_sets_personas(isolated_paths: Path) -> None:
    """seed_demo_state is an alias for seed_scenario_partially_onboarded."""
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    # Partially onboarded uses ["backend", "devops"]
    assert state.selected_personas == ["backend", "devops"]


def test_seed_demo_state_partially_onboarded_state(isolated_paths: Path) -> None:
    """seed_demo_state (alias) leaves onboarding incomplete at phase 3."""
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    assert state.onboarding_complete is False
    assert state.onboarding_phase == 3
    assert state.accepted_tool_bundle is False


def test_seed_demo_state_does_not_mutate_install_id(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="test-id")
    seed_demo_state(state)
    assert state.install_id == "test-id"


def test_seed_demo_state_does_not_mutate_demo_mode(isolated_paths: Path) -> None:
    state_true = AppStateModel(install_id="test-id", demo_mode=True)
    seed_demo_state(state_true)
    assert state_true.demo_mode is True

    state_false = AppStateModel(install_id="test-id", demo_mode=False)
    seed_demo_state(state_false)
    assert state_false.demo_mode is False


def test_demo_tool_list_is_nonempty(isolated_paths: Path) -> None:
    assert len(DEMO_TOOL_LIST) > 0
    assert all(isinstance(entry, str) and entry for entry in DEMO_TOOL_LIST)


# ---------------------------------------------------------------------------
# Group 2 — seed_scenario_partially_onboarded (Scenario 1)
# ---------------------------------------------------------------------------


def test_scenario_1_personas(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s1")
    seed_scenario_partially_onboarded(state)
    assert state.selected_personas == ["backend", "devops"]


def test_scenario_1_onboarding_incomplete(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s1")
    seed_scenario_partially_onboarded(state)
    assert state.onboarding_complete is False
    assert state.onboarding_phase == 3
    assert state.accepted_tool_bundle is False


def test_scenario_1_aws_profile_present(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s1")
    seed_scenario_partially_onboarded(state)
    assert state.aws_auth is not None
    assert len(state.aws_auth.profiles) >= 1
    # SSO expired (no session_expiry set)
    assert state.aws_auth.session_expiry is None


def test_scenario_1_health_summary_has_tools_key(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s1")
    seed_scenario_partially_onboarded(state)
    assert "tools" in state.health_summary
    # tools category is degraded in partially-onboarded scenario
    assert state.health_summary["tools"] in ("needs_attention", "recommended", "healthy")


def test_scenario_1_does_not_mutate_install_id(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s1-fixed")
    seed_scenario_partially_onboarded(state)
    assert state.install_id == "s1-fixed"


# ---------------------------------------------------------------------------
# Group 3 — seed_scenario_healthy_devops (Scenario 2)
# ---------------------------------------------------------------------------


def test_scenario_2_personas(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2")
    seed_scenario_healthy_devops(state)
    assert "backend" in state.selected_personas
    assert "devops" in state.selected_personas


def test_scenario_2_onboarding_complete(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2")
    seed_scenario_healthy_devops(state)
    assert state.onboarding_complete is True
    assert state.onboarding_phase == 7
    assert state.accepted_tool_bundle is True


def test_scenario_2_all_health_healthy(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2")
    seed_scenario_healthy_devops(state)
    for category, status in state.health_summary.items():
        assert status == "healthy", f"Expected healthy for {category}, got {status}"


def test_scenario_2_aws_active_profile(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2")
    seed_scenario_healthy_devops(state)
    assert state.aws_auth is not None
    assert state.aws_auth.active_profile is not None
    assert len(state.aws_auth.profiles) >= 1


def test_scenario_2_multiple_aws_profiles(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2")
    seed_scenario_healthy_devops(state)
    assert state.aws_auth is not None
    # Healthy devops scenario has 3 profiles
    assert len(state.aws_auth.profiles) == 3


def test_scenario_2_does_not_mutate_install_id(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s2-fixed")
    seed_scenario_healthy_devops(state)
    assert state.install_id == "s2-fixed"


# ---------------------------------------------------------------------------
# Group 4 — seed_scenario_needs_attention (Scenario 3)
# ---------------------------------------------------------------------------


def test_scenario_3_personas(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s3")
    seed_scenario_needs_attention(state)
    assert "backend" in state.selected_personas
    assert "devops" in state.selected_personas


def test_scenario_3_onboarding_complete(isolated_paths: Path) -> None:
    """Scenario 3 is fully onboarded but environment has degraded."""
    state = AppStateModel(install_id="s3")
    seed_scenario_needs_attention(state)
    assert state.onboarding_complete is True
    assert state.onboarding_phase == 7


def test_scenario_3_health_has_needs_attention(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s3")
    seed_scenario_needs_attention(state)
    # At least one category should be needs_attention
    statuses = set(state.health_summary.values())
    assert "needs_attention" in statuses


def test_scenario_3_no_aws_profile(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s3")
    seed_scenario_needs_attention(state)
    assert state.aws_auth is not None
    assert len(state.aws_auth.profiles) == 0
    assert state.aws_auth.active_profile is None


def test_scenario_3_does_not_mutate_install_id(isolated_paths: Path) -> None:
    state = AppStateModel(install_id="s3-fixed")
    seed_scenario_needs_attention(state)
    assert state.install_id == "s3-fixed"


# ---------------------------------------------------------------------------
# Group 5 — Cross-scenario isolation
# ---------------------------------------------------------------------------


def test_scenarios_are_independent(isolated_paths: Path) -> None:
    """Running multiple scenarios on separate state objects produces independent results."""
    s1 = AppStateModel(install_id="iso-s1")
    s2 = AppStateModel(install_id="iso-s2")

    seed_scenario_partially_onboarded(s1)
    seed_scenario_healthy_devops(s2)

    # s1 should still be incomplete
    assert s1.onboarding_complete is False
    # s2 should be complete
    assert s2.onboarding_complete is True


def test_seed_demo_state_is_alias_for_scenario_1(isolated_paths: Path) -> None:
    """seed_demo_state and seed_scenario_partially_onboarded produce identical state."""
    s_alias = AppStateModel(install_id="alias")
    s_direct = AppStateModel(install_id="direct")

    seed_demo_state(s_alias)
    seed_scenario_partially_onboarded(s_direct)

    assert s_alias.selected_personas == s_direct.selected_personas
    assert s_alias.onboarding_complete == s_direct.onboarding_complete
    assert s_alias.onboarding_phase == s_direct.onboarding_phase


# ---------------------------------------------------------------------------
# Group 2 — Demo banner async Textual pilot tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_demo_banner_visible_in_demo_mode(isolated_paths: Path) -> None:
    async with IgnitionApp(demo_mode=True).run_test() as pilot:
        await pilot.pause()
        results = pilot.app.query("#demo-banner")
        assert len(results) > 0
        widget = results.first()
        assert widget.display is True


@pytest.mark.asyncio
async def test_demo_banner_absent_in_normal_mode(isolated_paths: Path) -> None:
    async with IgnitionApp(demo_mode=False).run_test() as pilot:
        await pilot.pause()
        results = pilot.app.query("#demo-banner")
        assert len(results) == 0
