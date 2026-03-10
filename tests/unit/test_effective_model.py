"""Tests for Args.effective_model property.

Validates that the model resolution follows the priority:
1. CLI --model flag (highest)
2. STREETRACE_MODEL environment variable (fallback)
3. None (neither set)
"""


import pytest

from streetrace.args import Args


@pytest.fixture
def args_with_model() -> Args:
    """Create Args with --model set."""
    return Args(model="anthropic/claude-sonnet")


@pytest.fixture
def args_without_model() -> Args:
    """Create Args without --model."""
    return Args(model=None)


class TestEffectiveModel:
    """Test effective_model property resolution."""

    def test_returns_cli_model_when_set(self, args_with_model: Args) -> None:
        assert args_with_model.effective_model == "anthropic/claude-sonnet"

    def test_falls_back_to_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        args_without_model: Args,
    ) -> None:
        monkeypatch.setenv("STREETRACE_MODEL", "openai/gpt-4o")
        assert args_without_model.effective_model == "openai/gpt-4o"

    def test_returns_none_when_neither_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
        args_without_model: Args,
    ) -> None:
        monkeypatch.delenv("STREETRACE_MODEL", raising=False)
        assert args_without_model.effective_model is None

    def test_cli_takes_precedence_over_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        args_with_model: Args,
    ) -> None:
        monkeypatch.setenv("STREETRACE_MODEL", "openai/gpt-4o")
        assert args_with_model.effective_model == "anthropic/claude-sonnet"

    def test_empty_cli_model_falls_back_to_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty string model is falsy, should fall back to env var."""
        monkeypatch.setenv("STREETRACE_MODEL", "openai/gpt-4o")
        args = Args(model="")
        assert args.effective_model == "openai/gpt-4o"
