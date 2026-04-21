from __future__ import annotations

from datetime import UTC, datetime

import structlog

from ignition.schemas.auth import AwsAuthState, AwsProfile, ProfileType
from ignition.schemas.state import AppStateModel

DEMO_TOOL_LIST: list[str] = [
    "git",
    "python",
    "docker",
    "postgresql-client",
    "awscli",
    "terraform",
    "kubectl",
    "helm",
]


def seed_scenario_partially_onboarded(state: AppStateModel) -> AppStateModel:
    """Scenario 1: user has started onboarding but not completed it.

    - Two personas selected (backend + devops)
    - Onboarding phase 3 of 7 (in progress)
    - AWS SSO profile present but session expired
    - Tool bundle not yet accepted
    - Health summary shows mixed state
    """
    log = structlog.get_logger("ignition.core.demo")
    log.info("seeding scenario: partially_onboarded", install_id=state.install_id)

    state.selected_personas = ["backend", "devops"]
    state.onboarding_complete = False
    state.onboarding_phase = 3
    state.accepted_tool_bundle = False

    state.aws_auth = AwsAuthState(
        profiles=[
            AwsProfile(
                name="sso-dev",
                type=ProfileType.SSO,
                region="us-east-1",
                sso_start_url="https://reactor.awsapps.com/start",
                sso_account_id="111122223333",
                sso_role_name="DeveloperAccess",
                is_active=True,
            ),
        ],
        active_profile="sso-dev",
        session_expiry=None,
        last_checked=datetime.now(UTC),
    )

    state.health_summary = {
        "tools": "needs_attention",
        "configs": "recommended",
        "shell_integration": "healthy",
        "permissions": "healthy",
    }

    log.info("scenario seeded: partially_onboarded", phase=state.onboarding_phase)
    return state


def seed_scenario_healthy_devops(state: AppStateModel) -> AppStateModel:
    """Scenario 2: fully onboarded DevOps engineer with healthy environment.

    - Three personas (backend + devops + security)
    - Onboarding complete
    - All tools installed from DEMO_TOOL_LIST
    - Active AWS SSO session with future expiry
    - All health categories healthy
    """
    log = structlog.get_logger("ignition.core.demo")
    log.info("seeding scenario: healthy_devops", install_id=state.install_id)

    state.selected_personas = ["backend", "devops", "security"]
    state.onboarding_complete = True
    state.onboarding_phase = 7
    state.accepted_tool_bundle = True

    state.aws_auth = AwsAuthState(
        profiles=[
            AwsProfile(
                name="sso-dev",
                type=ProfileType.SSO,
                region="us-east-1",
                sso_start_url="https://reactor.awsapps.com/start",
                sso_account_id="111122223333",
                sso_role_name="DeveloperAccess",
                is_active=True,
            ),
            AwsProfile(
                name="sso-staging",
                type=ProfileType.SSO,
                region="us-east-1",
                sso_start_url="https://reactor.awsapps.com/start",
                sso_account_id="444455556666",
                sso_role_name="ReadOnly",
            ),
            AwsProfile(
                name="static-prod",
                type=ProfileType.STATIC,
                region="us-west-2",
            ),
        ],
        active_profile="sso-dev",
        session_expiry=None,
        last_checked=datetime.now(UTC),
    )

    state.health_summary = {
        "tools": "healthy",
        "configs": "healthy",
        "shell_integration": "healthy",
        "permissions": "healthy",
    }

    log.info(
        "scenario seeded: healthy_devops",
        tool_count=len(DEMO_TOOL_LIST),
        personas=state.selected_personas,
    )
    return state


def seed_scenario_needs_attention(state: AppStateModel) -> AppStateModel:
    """Scenario 3: workspace has drifted and requires remediation.

    - Single persona (frontend)
    - Onboarding complete but environment degraded
    - No AWS profile configured
    - Multiple health issues across categories
    - No tool bundle
    """
    log = structlog.get_logger("ignition.core.demo")
    log.info("seeding scenario: needs_attention", install_id=state.install_id)

    state.selected_personas = ["backend", "devops"]
    state.onboarding_complete = True
    state.onboarding_phase = 7
    state.accepted_tool_bundle = False

    state.aws_auth = AwsAuthState(
        profiles=[],
        active_profile=None,
        session_expiry=None,
        last_checked=datetime.now(UTC),
    )

    state.health_summary = {
        "tools": "needs_attention",
        "configs": "needs_attention",
        "shell_integration": "recommended",
        "permissions": "needs_attention",
    }

    log.info(
        "scenario seeded: needs_attention",
        personas=state.selected_personas,
        health_summary=state.health_summary,
    )
    return state


def seed_demo_state(state: AppStateModel) -> AppStateModel:
    """Backwards-compatible alias for seed_scenario_partially_onboarded.

    .. deprecated::
        Call the named scenario functions directly. This alias will be
        removed in a future milestone once all callers are migrated.
    """
    return seed_scenario_partially_onboarded(state)
