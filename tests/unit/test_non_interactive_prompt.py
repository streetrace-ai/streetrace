"""Tests for non-interactive prompt behavior.

Validates that positional arguments (arbitrary_prompt) behave identically
to the --prompt flag: no confirmation prompt, direct execution.
"""


from streetrace.args import Args


class TestNonInteractivePrompt:
    """Test Args.non_interactive_prompt property."""

    def test_prompt_flag_returns_prompt(self) -> None:
        """--prompt flag returns the prompt string."""
        args = Args(prompt="hello world")
        prompt = args.non_interactive_prompt
        assert prompt == "hello world"

    def test_positional_args_returns_joined_prompt(self) -> None:
        """Positional args are joined into a single prompt string."""
        args = Args(arbitrary_prompt=["Create", "an", "agent"])
        prompt = args.non_interactive_prompt
        assert prompt == "Create an agent"

    def test_prompt_flag_takes_precedence(self) -> None:
        """--prompt flag wins over positional args."""
        args = Args(
            prompt="from flag",
            arbitrary_prompt=["from", "positional"],
        )
        prompt = args.non_interactive_prompt
        assert prompt == "from flag"

    def test_no_prompt_returns_none(self) -> None:
        """No prompt and no positional args returns None."""
        args = Args()
        assert args.non_interactive_prompt is None

    def test_empty_positional_args_returns_none(self) -> None:
        """Empty positional args list returns None."""
        args = Args(arbitrary_prompt=[])
        assert args.non_interactive_prompt is None
