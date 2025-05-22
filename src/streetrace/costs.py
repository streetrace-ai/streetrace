"""Token and cost data for the current app run."""

from pydantic import BaseModel, Field


class UsageAndCost(BaseModel):
    """Token usage and cost as reported by the model."""

    completion_tokens: int = 0
    prompt_tokens: int = 0
    cost: float = 0

    def __add__(self, other: "UsageAndCost | None") -> "UsageAndCost":
        """Add all values."""
        if not other:
            return self

        return UsageAndCost(
            completion_tokens=self.completion_tokens + other.completion_tokens,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            cost=self.cost + other.cost,
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
