"""Session derivation for nested agent execution.

Provide session ID derivation and get-or-create logic for child
sessions spawned by DSL workflow agent invocations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from streetrace.log import get_logger

if TYPE_CHECKING:
    from google.adk.sessions import Session
    from google.adk.sessions.base_session_service import BaseSessionService

    from streetrace.dsl.runtime.context import WorkflowContext

logger = get_logger(__name__)


class SessionDeriver:
    """Derive and create child sessions for nested agent execution.

    Encapsulate session ID derivation logic that maps parent session +
    flow context into deterministic child session identifiers, and the
    get-or-create pattern for obtaining the actual session objects.
    """

    def __init__(self, session_service: BaseSessionService) -> None:
        """Initialize with session service.

        Args:
            session_service: ADK session service for session operations.

        """
        self._session_service = session_service

    def derive_identifiers(
        self,
        agent_name: str,
        context: WorkflowContext | None,
        fallback_app_name: str,
        *,
        parallel_index: int | None = None,
    ) -> tuple[str, str, str]:
        """Derive session identifiers for a nested agent run.

        Create child session identifiers based on the parent session
        context, ensuring session continuity and persistence.

        Args:
            agent_name: Name of the agent being executed.
            context: Workflow context with parent session info.
            fallback_app_name: App name to use when no parent session.
            parallel_index: Index for parallel execution uniqueness.

        Returns:
            Tuple of (app_name, user_id, session_id).

        """
        import uuid

        parent_session = context.parent_session if context else None

        if parent_session:
            app_name = parent_session.app_name
            user_id = parent_session.user_id
            flow_part = (
                context.current_flow_name
                if context and context.current_flow_name
                else "agent"
            )
            invocation_id = context.next_invocation_id() if context else 1

            if parallel_index is not None:
                session_id = (
                    f"{parent_session.id}:{flow_part}"
                    f":p{parallel_index}:{agent_name}"
                )
            else:
                session_id = (
                    f"{parent_session.id}:{flow_part}"
                    f":{agent_name}:{invocation_id}"
                )
        else:
            # Fallback when no parent session
            app_name = fallback_app_name
            user_id = "workflow_user"
            session_id = f"nested_{agent_name}_{uuid.uuid4().hex[:8]}"

        return app_name, user_id, session_id

    async def get_or_create(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> Session:
        """Get an existing session or create a new one.

        Args:
            app_name: Application name.
            user_id: User identifier.
            session_id: Session identifier.

        Returns:
            The existing or newly created session.

        """
        existing = await self._session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if existing is not None:
            return existing

        return await self._session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state={},
        )
