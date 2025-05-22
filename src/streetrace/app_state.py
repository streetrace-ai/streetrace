"""Just the app name here (important enough)."""

from pydantic import BaseModel, Field

from streetrace.costs import TotalUsageAndCost

APP_NAME = "StreetRace🚗💨."


class AppState(BaseModel):
    """App state values."""

    current_model: str | None = None
    usage_and_cost: TotalUsageAndCost = Field(default_factory=TotalUsageAndCost)
