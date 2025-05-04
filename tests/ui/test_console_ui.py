import json
from unittest.mock import MagicMock

import pytest
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from streetrace.tools.tool_call_result import ToolCallResult, ToolOutput
from streetrace.ui.colors import Styles
from streetrace.ui.console_ui import ConsoleUI


# Mock the Completer needed by ConsoleUI
@pytest.fixture
def mock_completer() -> MagicMock:
    """Fixture to provide a mock completer."""
    return MagicMock()


@pytest.fixture
def ui(mock_completer: MagicMock) -> ConsoleUI:
    """Fixture to provide a ConsoleUI instance with a mocked console."""
    ui_instance = ConsoleUI(completer=mock_completer)
    # Mock the rich console and capture separately
    ui_instance.console = MagicMock()
    ui_instance.console.capture.return_value.__enter__.return_value = MagicMock()
    ui_instance.console.capture.return_value.__exit__.return_value = None
    return ui_instance


class TestConsoleUIToolRendering:
    """Tests for tool output rendering in ConsoleUI."""

    def test_render_tool_output_text(self, ui: ConsoleUI) -> None:
        """Test rendering plain text output."""
        output = ToolOutput(type="text", content="Simple text result")
        ui._render_tool_output(output)  # noqa: SLF001
        # Check that print was called with the content and the correct style
        ui.console.print.assert_called_once_with(
            "Simple text result",
            style=Styles.RICH_TOOL_OUTPUT_TEXT_STYLE,
        )

    def test_render_tool_output_markdown(self, ui: ConsoleUI) -> None:
        """Test rendering markdown output."""
        output = ToolOutput(type="markdown", content="# Header\n* List item")
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once()
        args, _ = ui.console.print.call_args
        assert isinstance(args[0], Markdown)
        assert args[0].markup == "# Header\n* List item"
        assert args[0].code_theme == Styles.RICH_TOOL_OUTPUT_CODE_THEME

    def test_render_tool_output_diff(self, ui: ConsoleUI) -> None:
        """Test rendering diff output."""
        diff_content = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
        output = ToolOutput(type="diff", content=diff_content)
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once()
        args, _ = ui.console.print.call_args
        assert isinstance(args[0], Syntax)
        assert args[0].code == diff_content
        assert args[0].lexer.aliases[0] == "diff"
        # Access the theme name used during initialization

    def test_render_tool_output_json_dict(self, ui: ConsoleUI) -> None:
        """Test rendering JSON output from a dictionary."""
        json_content = {"key": "value", "nested": [1, 2]}
        expected_str = json.dumps(json_content, indent=2)
        output = ToolOutput(type="json", content=json_content)
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once()
        args, _ = ui.console.print.call_args
        assert isinstance(args[0], Syntax)
        assert args[0].code == expected_str
        assert args[0].lexer.aliases[0] == "json"
        # Access the theme name used during initialization

    def test_render_tool_output_json_string(self, ui: ConsoleUI) -> None:
        """Test rendering JSON output from a string."""
        json_str_content = '{\n  "key": "value"\n}'
        output = ToolOutput(type="json", content=json_str_content)
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once()
        args, _ = ui.console.print.call_args
        assert isinstance(args[0], Syntax)
        assert args[0].code == json_str_content
        assert args[0].lexer.aliases[0] == "json"
        # Access the theme name used during initialization

    def test_render_tool_output_unknown_type(self, ui: ConsoleUI) -> None:
        """Test rendering output with an unknown type."""
        output = ToolOutput(type="weird_format", content="Some data")
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once_with(
            "Some data",
            style=Styles.RICH_TOOL_OUTPUT_TEXT_STYLE,
        )

    def test_render_tool_output_non_string_content(self, ui: ConsoleUI) -> None:
        """Test rendering when content is not a string (e.g., list)."""
        list_content = ["item1", "item2"]
        expected_str = json.dumps(list_content, indent=2)
        output = ToolOutput(type="text", content=list_content)  # Treat as text
        ui._render_tool_output(output)  # noqa: SLF001
        ui.console.print.assert_called_once_with(
            expected_str,
            style=Styles.RICH_TOOL_OUTPUT_TEXT_STYLE,
        )

    # --- Tests for display_tool_result --- #

    def test_display_tool_result_uses_render_helper(self, ui: ConsoleUI) -> None:
        """Test display_tool_result calls _render_tool_output and Panel."""
        tool_name = "my_tool"
        result_content = "Successful output"
        display_content = ToolOutput(type="text", content="Display this!")
        result = ToolCallResult.ok(
            result_content,
            display_output=display_content,
        )

        rendered_output_str = "Rendered: Display this!"
        mock_capture = ui.console.capture.return_value.__enter__.return_value
        mock_capture.get.return_value = rendered_output_str

        ui.display_tool_result(tool_name, result)

        final_call = ui.console.print.call_args_list[-1]
        args, kwargs = final_call
        assert isinstance(args[0], Panel)
        assert args[0].renderable == rendered_output_str
        assert args[0].title == f"Tool Result ({tool_name})"
        assert kwargs.get("style") == Styles.RICH_TOOL_OUTPUT_TEXT_STYLE

    def test_display_tool_result_no_output(self, ui: ConsoleUI) -> None:
        """Test display_tool_result handles no display output."""
        tool_name = "silent_tool"
        result = ToolCallResult.ok(None, display_output=None)

        mock_capture = ui.console.capture.return_value.__enter__.return_value
        mock_capture.get.return_value = ""  # Assume capture returns empty

        ui.console.reset_mock()
        ui.display_tool_result(tool_name, result)

        final_call = ui.console.print.call_args_list[-1]
        args, kwargs = final_call
        assert isinstance(args[0], Panel)
        assert args[0].renderable == ""
        assert args[0].title == f"Tool Result ({tool_name})"
        assert kwargs.get("style") == Styles.RICH_TOOL_OUTPUT_TEXT_STYLE

    # --- Tests for display_tool_error --- #

    def test_display_tool_error(self, ui: ConsoleUI) -> None:
        """Test display_tool_error shows error message in a Panel."""
        tool_name = "error_tool"
        error_content = "Something went wrong"
        result = ToolCallResult.error(
            error_content,
            display_output=ToolOutput(type="text", content=error_content),
        )

        ui.display_tool_error(tool_name, result)

        final_call = ui.console.print.call_args_list[-1]
        args, _ = final_call
        assert isinstance(args[0], Panel)
        assert args[0].renderable == error_content
        assert args[0].title == f"Tool Error ({tool_name})"
        assert args[0].border_style == Styles.RICH_ERROR

    def test_display_tool_error_dict_content(self, ui: ConsoleUI) -> None:
        """Test display_tool_error handles dict content correctly."""
        tool_name = "error_tool_dict"
        error_dict = {"code": 500, "message": "Internal Server Error"}
        expected_str = json.dumps(error_dict, indent=2)
        result = ToolCallResult.error(
            error_dict,
            display_output=ToolOutput(type="json", content=error_dict),
        )

        ui.display_tool_error(tool_name, result)

        final_call = ui.console.print.call_args_list[-1]
        args, _ = final_call
        assert isinstance(args[0], Panel)
        assert args[0].renderable == expected_str
        assert args[0].title == f"Tool Error ({tool_name})"
        assert args[0].border_style == Styles.RICH_ERROR

    def test_display_tool_error_no_message(self, ui: ConsoleUI) -> None:
        """Test display_tool_error handles missing error message."""
        tool_name = "error_tool_silent"
        result = ToolCallResult.error(None, display_output=None)

        ui.display_tool_error(tool_name, result)

        final_call = ui.console.print.call_args_list[-1]
        args, _ = final_call
        assert isinstance(args[0], Panel)
        assert args[0].renderable == "[No error message]"
        assert args[0].title == f"Tool Error ({tool_name})"
        assert args[0].border_style == Styles.RICH_ERROR
