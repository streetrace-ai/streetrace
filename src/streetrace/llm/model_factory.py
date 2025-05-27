from google.adk.models.base_llm import BaseLlm


class ModelFactory:
    """Factory class to create and manage models for the StreetRace application."""

    def __init__(self, model_config) -> None:
        """Initialize the ModelFactory with a model configuration."""
        self.model_config = model_config

    def get_default_model(self) -> str | BaseLlm:
        """Return the default model based on the configuration."""
        return self.model_config.get("default_model", "gpt-3.5-turbo")

    def get_model(self, model_name: str) -> str | BaseLlm:
        """Return a specific model based on the name."""
        return self.model_config.get(model_name)
