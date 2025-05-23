"""Token and cost data for the current app run."""

from typing import TypeVar

from pydantic import BaseModel, Field


class UsageAndCost(BaseModel):
    """Token usage and cost as reported by the model."""

    completion_tokens: int | None = None
    prompt_tokens: int | None = None
    # cost can be unknown which is different from 0
    cost: float | None = None

    @property
    def cost_str(self) -> str:
        """2 decimal str representation of cost, or '-.--' if None."""
        if self.cost is None:
            return "-.--"
        return f"{self.cost:.2f}"

    @property
    def completion_tokens_str(self) -> str:
        """Str representation of completion_tokens, or '-' if None."""
        if self.completion_tokens is None:
            return "-"
        return str(self.completion_tokens)

    @property
    def prompt_tokens_str(self) -> str:
        """Str representation of prompt_tokens, or '-' if None."""
        if self.prompt_tokens is None:
            return "-"
        return str(self.prompt_tokens)

    def __add__(self, other: "UsageAndCost | None") -> "UsageAndCost":
        """Add all values."""
        if not other:
            return self

        TNum = TypeVar("TNum", int, float)

        def add(one: TNum | None, another: TNum | None) -> TNum | None:
            if one is not None and another is not None:
                return one + another
            return one or another

        return UsageAndCost(
            completion_tokens=add(self.completion_tokens, other.completion_tokens),
            prompt_tokens=add(self.prompt_tokens, other.prompt_tokens),
            cost=add(self.cost, other.cost),
        )


class TotalUsageAndCost(BaseModel):
    """Token and dollar data for the current app run."""

    turn_usage: UsageAndCost = Field(default_factory=UsageAndCost)
    app_run_usage: UsageAndCost = Field(default_factory=UsageAndCost)

    def add_usage(self, change: UsageAndCost) -> None:
        """Add costs to stats."""
        self.turn_usage = (self.turn_usage or UsageAndCost()) + change
        self.app_run_usage = (self.app_run_usage or UsageAndCost()) + change

    def reset_turn(self) -> None:
        """Reset current turn to zero in the beginning of a new turn."""
        self.turn_usage = UsageAndCost()
