"""Tests for YAML agent models."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from streetrace.agents.yaml_models import (
    AdkConfig,
    HttpServerConfig,
    McpToolSpec,
    StdioServerConfig,
    StreetraceToolSpec,
    ToolSpec,
    TransportType,
    YamlAgentDocument,
    YamlAgentSpec,
    expand_env_vars,
)


class TestEnvironmentExpansion:
    """Test environment variable expansion."""

    def test_expand_env_vars_simple(self):
        """Test simple environment variable expansion."""
        os.environ["TEST_VAR"] = "test_value"
        result = expand_env_vars("${TEST_VAR}")
        assert result == "test_value"

    def test_expand_env_vars_with_default(self):
        """Test environment variable expansion with default value."""
        result = expand_env_vars("${NONEXISTENT_VAR:-default_value}")
        assert result == "default_value"

    def test_expand_env_vars_existing_with_default(self):
        """Test that existing env vars take precedence over defaults."""
        os.environ["EXISTING_VAR"] = "existing_value"
        result = expand_env_vars("${EXISTING_VAR:-default_value}")
        assert result == "existing_value"

    def test_expand_env_vars_multiple(self):
        """Test multiple environment variables in one string."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = expand_env_vars("${VAR1} and ${VAR2}")
        assert result == "value1 and value2"

    def test_expand_env_vars_no_expansion(self):
        """Test strings without env vars are unchanged."""
        result = expand_env_vars("plain text")
        assert result == "plain text"


class TestServerConfigs:
    """Test server configuration models."""

    def test_stdio_server_config_minimal(self):
        """Test minimal stdio server configuration."""
        config = StdioServerConfig(command="npx")
        assert config.type == TransportType.STDIO
        assert config.command == "npx"
        assert config.args == []
        assert config.env == {}

    def test_stdio_server_config_full(self):
        """Test full stdio server configuration."""
        config = StdioServerConfig(
            command="node",
            args=["server.js", "--port", "8080"],
            env={"NODE_ENV": "production"},
        )
        assert config.command == "node"
        assert config.args == ["server.js", "--port", "8080"]
        assert config.env == {"NODE_ENV": "production"}

    def test_stdio_server_config_env_expansion(self):
        """Test environment variable expansion in stdio config."""
        os.environ["TEST_CMD"] = "test_command"
        os.environ["TEST_ARG"] = "test_arg"

        config = StdioServerConfig(
            command="${TEST_CMD}",
            args=["${TEST_ARG}", "static_arg"],
            env={"VAR": "${TEST_ARG:-default}"},
        )
        assert config.command == "test_command"
        assert config.args == ["test_arg", "static_arg"]
        assert config.env == {"VAR": "test_arg"}

    def test_http_server_config_minimal(self):
        """Test minimal HTTP server configuration."""
        config = HttpServerConfig(type=TransportType.HTTP, url="https://example.com")
        assert config.type == TransportType.HTTP
        assert config.url == "https://example.com"
        assert config.headers == {}
        assert config.timeout == 10

    def test_http_server_config_full(self):
        """Test full HTTP server configuration."""
        config = HttpServerConfig(
            type=TransportType.SSE,
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer token123"},
            timeout=30,
        )
        assert config.type == TransportType.SSE
        assert config.url == "https://api.example.com/mcp"
        assert config.headers == {"Authorization": "Bearer token123"}
        assert config.timeout == 30

    def test_http_server_config_env_expansion(self):
        """Test environment variable expansion in HTTP config."""
        os.environ["API_URL"] = "https://api.test.com"
        os.environ["AUTH_TOKEN"] = "secret123"  # noqa: S105

        config = HttpServerConfig(
            type=TransportType.HTTP,
            url="${API_URL}",
            headers={"Authorization": "Bearer ${AUTH_TOKEN}"},
        )
        assert config.url == "https://api.test.com"
        assert config.headers == {"Authorization": "Bearer secret123"}


class TestToolSpecs:
    """Test tool specification models."""

    def test_streetrace_tool_spec(self):
        """Test StreetRace tool specification."""
        spec = StreetraceToolSpec(module="fs_tool", function="read_file")
        assert spec.module == "fs_tool"
        assert spec.function == "read_file"

    def test_mcp_tool_spec_stdio(self):
        """Test MCP tool specification with stdio server."""
        spec = McpToolSpec(
            name="filesystem",
            server=StdioServerConfig(command="npx", args=["-y", "@mcp/filesystem"]),
            tools=["read_file", "write_file"],
        )
        assert spec.name == "filesystem"
        assert isinstance(spec.server, StdioServerConfig)
        assert spec.tools == ["read_file", "write_file"]

    def test_mcp_tool_spec_http(self):
        """Test MCP tool specification with HTTP server."""
        spec = McpToolSpec(
            name="github",
            server=HttpServerConfig(
                type=TransportType.HTTP,
                url="https://api.github.com/mcp",
            ),
        )
        assert spec.name == "github"
        assert isinstance(spec.server, HttpServerConfig)
        assert spec.tools == []

    def test_tool_spec_streetrace(self):
        """Test tool spec with StreetRace tool."""
        spec = ToolSpec(
            streetrace=StreetraceToolSpec(module="cli_tool", function="execute"),
        )
        assert spec.streetrace is not None
        assert spec.mcp is None

    def test_tool_spec_mcp(self):
        """Test tool spec with MCP tool."""
        spec = ToolSpec(
            mcp=McpToolSpec(
                name="test",
                server=StdioServerConfig(command="test"),
            ),
        )
        assert spec.streetrace is None
        assert spec.mcp is not None

    def test_tool_spec_validation_both(self):
        """Test that tool spec rejects both streetrace and mcp."""
        with pytest.raises(ValidationError, match="cannot have both"):  # type: ignore[type-arg]
            ToolSpec(
                streetrace=StreetraceToolSpec(module="test", function="test"),
                mcp=McpToolSpec(
                    name="test",
                    server=StdioServerConfig(command="test"),
                ),
            )

    def test_tool_spec_validation_neither(self):
        """Test that tool spec requires one of streetrace or mcp."""
        with pytest.raises(ValidationError, match="must have either"):  # type: ignore[type-arg]
            ToolSpec()


class TestYamlAgentSpec:
    """Test YAML agent specification model."""

    def test_minimal_spec(self):
        """Test minimal valid agent specification."""
        spec = YamlAgentSpec(
            name="test_agent",
            description="A test agent",
        )
        assert spec.version == 1
        assert spec.kind == "agent"
        assert spec.name == "test_agent"
        assert spec.description == "A test agent"
        assert spec.model is None
        assert spec.instruction is None
        assert spec.global_instruction is None
        assert spec.tools == []
        assert spec.sub_agents == []

    def test_full_spec(self):
        """Test full agent specification."""
        spec = YamlAgentSpec(
            name="complex_agent",
            description="A complex agent",
            model="gpt-4",
            instruction="You are a helpful assistant",
            global_instruction="Global system message",
            prompt="Default user prompt for this agent",
            tools=[
                ToolSpec(
                    streetrace=StreetraceToolSpec(
                        module="fs_tool",
                        function="read_file",
                    ),
                ),
            ],
        )
        assert spec.name == "complex_agent"
        assert spec.model == "gpt-4"
        assert spec.instruction == "You are a helpful assistant"
        assert spec.global_instruction == "Global system message"
        assert spec.prompt == "Default user prompt for this agent"
        assert len(spec.tools) == 1

    def test_name_validation_valid(self):
        """Test valid agent names."""
        valid_names = ["agent", "my_agent", "Agent123", "_agent", "a"]
        for name in valid_names:
            spec = YamlAgentSpec(name=name, description="test")
            assert spec.name == name

    def test_name_validation_invalid(self):
        """Test invalid agent names."""
        invalid_names = ["", "123agent", "my-agent", "my.agent", "my agent"]
        for name in invalid_names:
            with pytest.raises(ValidationError):  # type: ignore[type-arg]
                YamlAgentSpec(name=name, description="test")

    def test_instruction_env_expansion(self):
        """Test environment variable expansion in instructions."""
        os.environ["SYSTEM_MSG"] = "Be helpful"
        os.environ["USER_PROMPT"] = "Analyze this code"
        spec = YamlAgentSpec(
            name="test",
            description="test",
            instruction="You are an assistant. ${SYSTEM_MSG:-Be nice}",
            global_instruction="${SYSTEM_MSG}",
            prompt="${USER_PROMPT:-Review the code}",
        )
        assert spec.instruction is not None
        assert "Be helpful" in spec.instruction
        assert spec.global_instruction == "Be helpful"
        assert spec.prompt == "Analyze this code"

        # Test with default value when env var is not set
        del os.environ["USER_PROMPT"]
        spec2 = YamlAgentSpec(
            name="test2",
            description="test",
            prompt="${USER_PROMPT:-Review the code}",
        )
        assert spec2.prompt == "Review the code"

    def test_output_schema_with_tools_validation(self):
        """Test that output_schema cannot coexist with tools."""
        with pytest.raises(ValidationError, match="output_schema.*tools"):  # type: ignore[type-arg]
            YamlAgentSpec(
                name="test",
                description="test",
                adk=AdkConfig(output_schema="TestSchema"),
                tools=[
                    ToolSpec(
                        streetrace=StreetraceToolSpec(module="test", function="test"),
                    ),
                ],
            )

    def test_output_schema_with_sub_agents_validation(self):
        """Test that output_schema cannot coexist with sub_agents."""
        from streetrace.agents.yaml_models import InlineAgentSpec

        with pytest.raises(ValidationError, match="output_schema.*sub_agents"):  # type: ignore[type-arg]
            YamlAgentSpec(
                name="test",
                description="test",
                adk=AdkConfig(output_schema="TestSchema"),
                sub_agents=[
                    InlineAgentSpec(
                        agent=YamlAgentSpec(name="sub", description="sub"),
                    ),
                ],
            )

    def test_attributes_default(self):
        """Test that attributes default to empty dict."""
        spec = YamlAgentSpec(name="test", description="test")
        assert spec.attributes == {}

    def test_attributes_custom(self):
        """Test custom attributes."""
        spec = YamlAgentSpec(
            name="test",
            description="test",
            attributes={
                "streetrace.org.id": "my-org",
                "streetrace.agent.tags": ["red_team", "security"],
                "custom.property": "value",
            },
        )
        assert spec.attributes["streetrace.org.id"] == "my-org"
        assert spec.attributes["streetrace.agent.tags"] == ["red_team", "security"]
        assert spec.attributes["custom.property"] == "value"

    def test_attributes_various_types(self):
        """Test attributes with various value types."""
        spec = YamlAgentSpec(
            name="test",
            description="test",
            attributes={
                "string": "value",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
                "null": None,
            },
        )
        assert spec.attributes["string"] == "value"
        assert spec.attributes["number"] == 42
        assert spec.attributes["float"] == 3.14
        assert spec.attributes["boolean"] is True
        assert spec.attributes["list"] == [1, 2, 3]
        assert spec.attributes["dict"] == {"nested": "value"}
        assert spec.attributes["null"] is None


class TestAgentDocument:
    """Test agent document model."""

    def test_agent_document_creation(self):
        """Test creating an agent document."""
        spec = YamlAgentSpec(name="test", description="test")
        doc = YamlAgentDocument(spec=spec, file_path=Path("/test/agent.yml"))

        assert doc.spec == spec
        assert doc.file_path == Path("/test/agent.yml")
        assert doc.get_name() == "test"
        assert doc.get_description() == "test"

    def test_agent_document_no_path(self):
        """Test agent document without file path."""
        spec = YamlAgentSpec(name="test", description="test")
        doc = YamlAgentDocument(spec=spec)

        assert doc.file_path is None
        assert doc.get_name() == "test"
        assert doc.get_description() == "test"
