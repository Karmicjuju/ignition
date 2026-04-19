from __future__ import annotations

from pydantic import BaseModel, Field

ONBOARDING_SCHEMA_VERSION = 1


class PersonaInfo(BaseModel):
    schema_version: int = ONBOARDING_SCHEMA_VERSION
    id: str
    name: str
    description: str
    recommended_tools: list[str] = Field(default_factory=list)


PERSONAS: list[PersonaInfo] = [
    PersonaInfo(
        id="backend",
        name="Backend Engineer",
        description="Builds and maintains server-side services, APIs, and data pipelines.",
        recommended_tools=["git", "python", "docker", "postgresql-client", "awscli"],
    ),
    PersonaInfo(
        id="frontend",
        name="Frontend Engineer",
        description="Builds web UIs and client-side applications.",
        recommended_tools=["git", "node", "pnpm", "awscli"],
    ),
    PersonaInfo(
        id="devops",
        name="DevOps / Platform Engineer",
        description="Manages infrastructure, CI/CD pipelines, and platform reliability.",
        recommended_tools=["git", "terraform", "kubectl", "awscli", "docker", "helm"],
    ),
    PersonaInfo(
        id="security",
        name="Security Engineer",
        description="Reviews code and infrastructure for vulnerabilities and manages secrets.",
        recommended_tools=["git", "awscli", "trivy", "vault"],
    ),
    PersonaInfo(
        id="contractor",
        name="Contractor",
        description="External collaborator with scoped access to Reactor systems.",
        recommended_tools=["git", "awscli"],
    ),
]
