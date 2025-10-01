"""Tests for YamlAgent class."""



from streetrace.agents.yaml_agent import YamlAgent
from streetrace.agents.yaml_models import YamlAgentDocument, YamlAgentSpec


class TestYamlAgent:
    """Test YamlAgent implementation."""

    def test_user_prompt_property_with_prompt(self):
        """Test user_prompt property when prompt is defined in spec."""
        spec = YamlAgentSpec(
            name="test_agent",
            description="A test agent",
            prompt="Default user prompt for testing",
        )
        doc = YamlAgentDocument(spec=spec)
        agent = YamlAgent(doc)

        assert agent.user_prompt == "Default user prompt for testing"

    def test_user_prompt_property_without_prompt(self):
        """Test user_prompt property when prompt is not defined in spec."""
        spec = YamlAgentSpec(
            name="test_agent",
            description="A test agent",
        )
        doc = YamlAgentDocument(spec=spec)
        agent = YamlAgent(doc)

        assert agent.user_prompt is None

    def test_user_prompt_property_empty_string(self):
        """Test user_prompt property with empty string prompt."""
        spec = YamlAgentSpec(
            name="test_agent",
            description="A test agent",
            prompt="",
        )
        doc = YamlAgentDocument(spec=spec)
        agent = YamlAgent(doc)

        # Empty string should be preserved, not converted to None
        assert agent.user_prompt == ""

    def test_agent_card_creation(self):
        """Test that agent card is created correctly."""
        spec = YamlAgentSpec(
            name="test_agent",
            description="A test agent for card creation",
            prompt="Test prompt",
        )
        doc = YamlAgentDocument(spec=spec)
        agent = YamlAgent(doc)

        card = agent.get_agent_card()
        assert card.name == "test_agent"
        assert card.description == "A test agent for card creation"
        # The prompt should not affect the card
        assert hasattr(card, "skills")
        assert len(card.skills) == 1
        assert card.skills[0].description == "A test agent for card creation"
