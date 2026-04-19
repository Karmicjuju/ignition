from __future__ import annotations

import structlog

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

    log.info("demo state seeded", tool_count=len(DEMO_TOOL_LIST))

    return state
