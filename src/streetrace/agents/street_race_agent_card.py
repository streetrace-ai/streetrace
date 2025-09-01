"""Key agent information to be published to the A2A network."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from a2a.types import AgentCapabilities, AgentProvider, AgentSkill, SecurityScheme

# ruff: noqa: N815 for compatibility with a2a.types.AgentCard


class StreetRaceAgentCard(BaseModel):
    """Key agent information to be published to the A2A network.

    This is a proxy for A2A AgentCard that allows specifying Agent info without infra
    details. Infra details are provided by the infrastructure code.
    """

    capabilities: "AgentCapabilities"
    """
    Optional capabilities supported by the agent.
    """
    defaultInputModes: list[str]
    """
    The set of interaction modes that the agent supports across all skills.
    This can be overridden per-skill.
    Supported mime types for input.
    """
    defaultOutputModes: list[str]
    """
    Supported mime types for output.
    """
    description: str
    """
    A human-readable description of the agent.
    Used to assist users and other agents in understanding what the agent can do.
    """
    documentationUrl: str | None = None
    """
    A URL to documentation for the agent.
    """
    name: str
    """
    Human readable name of the agent.
    """
    provider: "AgentProvider | None" = None
    """
    The service provider of the agent
    """
    security: list[dict[str, list[str]]] | None = None
    """
    Security requirements for contacting the agent.
    """
    securitySchemes: dict[str, "SecurityScheme"] | None = None
    """
    Security scheme details used for authenticating with this agent.
    """
    skills: list["AgentSkill"]
    """
    Skills are a unit of capability that an agent can perform.
    """
    supportsAuthenticatedExtendedCard: bool | None = None
    """
    true if the agent supports providing an extended agent card for authenticated users.
    Defaults to false if not specified.
    """
    version: str
    """
    The version of the agent - format is up to the provider.
    """


# Try to rebuild the model with a2a.types imports
try:
    # Attempt to import specific types to resolve forward references
    # These imports are needed at runtime for model_rebuild(), not just type checking
    from a2a.types import (  # noqa: TC002
        AgentCapabilities,
        AgentProvider,
        AgentSkill,
        SecurityScheme,
    )

    StreetRaceAgentCard.model_rebuild()
except ImportError:
    # a2a.types not available, model will need to be rebuilt later
    pass
