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


def seed_demo_state(state: AppStateModel) -> AppStateModel:
    """Seeds state with realistic demo data for presentations."""
    log = structlog.get_logger("ignition.core.demo")

    log.info(
        "seeding demo state",
        install_id=state.install_id,
        personas=["backend", "devops"],
    )

    state.selected_personas = ["backend", "devops"]
    state.onboarding_complete = True
    state.onboarding_phase = 3
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

    log.info("demo state seeded", tool_count=len(DEMO_TOOL_LIST))

    return state
