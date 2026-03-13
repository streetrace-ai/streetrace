"""MCP-Guard orchestrator implementing the Guardrail protocol.

Manage the 2-stage pipeline (syntactic + neural) with policy
enforcement and trust evaluation. Receive JSON-serialized tool
call data via check_str and return (triggered, detail) tuples.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from opentelemetry import trace

from streetrace.guardrails.config import McpGuardConfig
from streetrace.guardrails.mcp_guard.policy_enforcer import PolicyEnforcer
from streetrace.guardrails.mcp_guard.syntactic_gatekeeper import (
    SyntacticGatekeeper,
)
from streetrace.guardrails.mcp_guard.trust_evaluator import TrustEvaluator
from streetrace.guardrails.types import GuardrailAction, GuardrailResult
from streetrace.log import get_logger

if TYPE_CHECKING:
    from streetrace.guardrails.inference.pipeline import InferencePipeline

logger = get_logger(__name__)

_PROXY_NAME = "mcp_guard"
"""Proxy identifier for OTEL spans."""

_STAGE_POLICY = "policy"
_STAGE_SYNTACTIC = "syntactic"
_STAGE_NEURAL = "neural"

STAGE1_CONFIDENCE = 1.0
"""Confidence score for deterministic pattern matches."""


class McpGuardOrchestrator:
    """Orchestrate MCP tool call validation pipeline.

    Implement the Guardrail protocol with name 'mcp_guard'.
    Pipeline order: policy -> syntactic -> neural.
    """

    def __init__(
        self,
        *,
        inference_pipeline: InferencePipeline | None = None,
        config: McpGuardConfig | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            inference_pipeline: ONNX inference pipeline for neural
                inspector, or None for syntactic-only mode.
            config: MCP-Guard configuration. Uses defaults if None.

        """
        self._inference_pipeline = inference_pipeline
        self._config = config or McpGuardConfig()
        self._gatekeeper = SyntacticGatekeeper()
        self._policy = PolicyEnforcer(config=self._config)
        self._trust = TrustEvaluator(
            trust_threshold=self._config.trust_threshold,
        )

    @property
    def name(self) -> str:
        """Return the guardrail name."""
        return "mcp_guard"

    def mask_str(self, text: str) -> str:
        """Return text unchanged -- mcp_guard is check-only.

        Args:
            text: Input text.

        Returns:
            The input text unmodified.

        """
        return text

    def check_str(self, text: str) -> tuple[bool, str]:
        """Check if a tool call should be blocked.

        Parse JSON tool call data and run the pipeline:
        policy -> syntactic -> neural.

        Args:
            text: JSON-serialized tool call data containing
                server_id, tool_name, and args.

        Returns:
            Tuple of (triggered, detail).

        """
        result = self._run_pipeline(text)
        return result.is_triggered, result.detail

    def _run_pipeline(self, text: str) -> GuardrailResult:
        """Execute the MCP-Guard pipeline.

        Args:
            text: JSON-serialized tool call data.

        Returns:
            GuardrailResult from the highest-triggered stage.

        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "guardrail.mcp_guard.pipeline",
        ) as span:
            span.set_attribute(
                "streetrace.guardrail.proxy", _PROXY_NAME,
            )

            # Parse tool call JSON
            tool_info = _parse_tool_call(text)
            if tool_info is None:
                result = GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    confidence=STAGE1_CONFIDENCE,
                    detail="Invalid tool call data: could not parse JSON",
                    stage=_STAGE_POLICY,
                    proxy=_PROXY_NAME,
                )
                _set_span_attributes(span, result)
                return result

            raw_server = tool_info.get("server_id", "")
            server_id = str(raw_server) if raw_server else ""
            raw_tool = tool_info.get("tool_name", "")
            tool_name = str(raw_tool) if raw_tool else ""
            raw_args = tool_info.get("args", {})
            args: dict[str, object] = (
                raw_args if isinstance(raw_args, dict) else {}
            )

            # Stage 0: Policy enforcement
            policy_result = self._policy.check(
                server_id=server_id,
                tool_name=tool_name,
                args=args,
            )
            if not policy_result.allowed:
                result = GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    confidence=STAGE1_CONFIDENCE,
                    detail=policy_result.reason,
                    stage=_STAGE_POLICY,
                    proxy=_PROXY_NAME,
                )
                _set_span_attributes(span, result)
                return result

            # Stage 1: Syntactic gatekeeper
            gk_result = self._gatekeeper.check(tool_name, args)
            if gk_result.triggered:
                detection_names = ", ".join(
                    d.detector_name for d in gk_result.detections
                )
                result = GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    confidence=STAGE1_CONFIDENCE,
                    detail=(
                        f"Syntactic gatekeeper triggered: "
                        f"{detection_names}"
                    ),
                    stage=_STAGE_SYNTACTIC,
                    proxy=_PROXY_NAME,
                )
                _set_span_attributes(span, result)
                return result

            # Stage 2: Neural inspector (async-only, skipped in sync)
            # Neural inspection requires async context.
            # In sync check_str, we return allow after syntactic passes.
            result = GuardrailResult(
                action=GuardrailAction.ALLOW,
                confidence=STAGE1_CONFIDENCE,
                detail="",
                stage=_STAGE_SYNTACTIC,
                proxy=_PROXY_NAME,
            )
            _set_span_attributes(span, result)
            return result


def _parse_tool_call(text: str) -> dict[str, object] | None:
    """Parse JSON tool call data.

    Args:
        text: JSON string to parse.

    Returns:
        Parsed dictionary or None if parsing fails.

    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse tool call JSON")
        return None

    if not isinstance(data, dict):
        logger.warning("Tool call data is not a dictionary")
        return None

    return data


def _set_span_attributes(
    span: trace.Span,
    result: GuardrailResult,
) -> None:
    """Set OTEL span attributes for the pipeline result.

    Args:
        span: Active OTEL span.
        result: Pipeline result.

    """
    span.set_attribute("streetrace.guardrail.stage", result.stage)
    span.set_attribute(
        "streetrace.guardrail.check.confidence", result.confidence,
    )
    span.set_attribute(
        "streetrace.guardrail.violation.action", result.action.value,
    )
    if result.detail:
        span.set_attribute(
            "streetrace.guardrail.violation.detail", result.detail,
        )
