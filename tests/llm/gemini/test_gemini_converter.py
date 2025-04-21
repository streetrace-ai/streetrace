import unittest

from google.genai import types

from streetrace.llm.gemini.converter import GeminiHistoryConverter, GeminiChunkWrapper
from streetrace.llm.wrapper import Role  # Import Role Enum
from streetrace.llm.wrapper import ToolOutput  # Import ToolOutput model
from streetrace.llm.wrapper import (
    ContentPartText,
    ContentPartToolCall,
    ContentPartToolResult,
    History,
    Message,
    ToolCallResult,
)


class TestGenerateContentPartWrapper(unittest.TestCase):
    """Tests for the GeminiChunkWrapper class."""

    def test_get_text_with_text(self):
        """Test retrieving text when the part contains text."""
        part = types.Part(text="Hello")
        wrapper = GeminiChunkWrapper(part)
        self.assertEqual(wrapper.get_text(), "Hello")

    def test_get_text_without_text(self):
        """Test retrieving text when the part does not contain text."""
        part = types.Part(
            function_call=types.FunctionCall(
                name="test_func", args={"arg1": "val1"}, id="call_1"
            )
        )
        wrapper = GeminiChunkWrapper(part)
        self.assertEqual(wrapper.get_text(), "")

    def test_get_tool_calls_with_call(self):
        """Test retrieving tool calls when the part contains a function call."""
        func_call = types.FunctionCall(
            name="test_func", args={"arg1": "val1"}, id="call_1"
        )
        part = types.Part(function_call=func_call)
        wrapper = GeminiChunkWrapper(part)
        expected_tool_calls = [
            ContentPartToolCall(
                id="call_1", name="test_func", arguments={"arg1": "val1"}
            )
        ]
        self.assertEqual(wrapper.get_tool_calls(), expected_tool_calls)

    def test_get_tool_calls_without_call(self):
        """Test retrieving tool calls when the part does not contain a function call."""
        part = types.Part(text="Hello")
        wrapper = GeminiChunkWrapper(part)
        self.assertEqual(wrapper.get_tool_calls(), [])

    def test_get_finish_message(self):
        """Test retrieving the finish message (always None for Gemini Parts)."""
        part = types.Part(text="Hello")
        wrapper = GeminiChunkWrapper(part)
        self.assertIsNone(wrapper.get_finish_message())


class TestGeminiConverter(unittest.TestCase):
    """Tests for the GeminiHistoryConverter class."""

    def setUp(self):
        """Set up the GeminiHistoryConverter instance for tests."""
        self.converter = GeminiHistoryConverter()

    # --- Test _from_content_part ---

    def test_from_content_part_text(self):
        """Test converting ContentPartText to Gemini Part."""
        part = ContentPartText(text="Hello")
        gemini_part = self.converter._from_content_part(part)
        self.assertEqual(gemini_part.text, "Hello")
        self.assertIsNone(gemini_part.function_call)
        self.assertIsNone(gemini_part.function_response)

    def test_from_content_part_tool_call(self):
        """Test converting ContentPartToolCall to Gemini Part."""
        part = ContentPartToolCall(
            id="call_1", name="test_func", arguments={"arg1": "val1"}
        )
        gemini_part = self.converter._from_content_part(part)
        self.assertEqual(gemini_part.function_call.name, "test_func")
        self.assertEqual(gemini_part.function_call.args, {"arg1": "val1"})
        self.assertIsNone(gemini_part.text)
        self.assertIsNone(gemini_part.function_response)

    def test_from_content_part_tool_result_ok(self):
        """Test converting a successful ContentPartToolResult to Gemini Part."""
        result = ToolCallResult.ok(
            output=ToolOutput(type="text", content="Tool output")
        )
        part = ContentPartToolResult(id="call_1", name="test_func", content=result)
        gemini_part = self.converter._from_content_part(part)
        expected_response = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Tool output"},
            "display_output": None,
        }
        self.assertEqual(gemini_part.function_response.name, "test_func")
        self.assertEqual(gemini_part.function_response.response, expected_response)
        self.assertIsNone(gemini_part.text)
        self.assertIsNone(gemini_part.function_call)

    def test_from_content_part_tool_result_error(self):
        """Test converting a failed ContentPartToolResult to Gemini Part."""
        result = ToolCallResult.error(output="Tool error")  # Will wrap in ToolOutput
        part = ContentPartToolResult(id="call_err", name="test_func", content=result)
        gemini_part = self.converter._from_content_part(part)
        expected_response = {
            "success": None,
            "failure": True,
            "output": {"type": "text", "content": "Tool error"},
            "display_output": None,
        }
        self.assertEqual(gemini_part.function_response.name, "test_func")
        self.assertEqual(gemini_part.function_response.response, expected_response)
        self.assertIsNone(gemini_part.text)
        self.assertIsNone(gemini_part.function_call)

    def test_from_content_part_unknown(self):
        """Test converting an unknown ContentPart type."""

        class UnknownPart:
            pass

        part = UnknownPart()
        with self.assertRaisesRegex(
            ValueError, "Unknown content type encountered .*UnknownPart"
        ):
            self.converter._from_content_part(part)

    # --- Test _to_content_part ---

    def test_to_content_part_text(self):
        """Test converting Gemini Part (text) to ContentPartText."""
        gemini_part = types.Part(text="Hello")
        common_part = self.converter._to_content_part(gemini_part)
        self.assertIsInstance(common_part, ContentPartText)
        self.assertEqual(common_part.text, "Hello")

    def test_to_content_part_tool_call(self):
        """Test converting Gemini Part (function call) to ContentPartToolCall."""
        func_call = types.FunctionCall(
            name="test_func", args={"arg1": "val1"}, id="call_1"
        )
        gemini_part = types.Part(function_call=func_call)
        common_part = self.converter._to_content_part(gemini_part)
        self.assertIsInstance(common_part, ContentPartToolCall)
        self.assertEqual(common_part.id, "call_1")
        self.assertEqual(common_part.name, "test_func")
        self.assertEqual(common_part.arguments, {"arg1": "val1"})

    def test_to_content_part_tool_response_ok(self):
        """Test converting Gemini Part (function response) for success."""
        gemini_response_dict = {
            "success": True,
            "output": {"type": "text", "content": "Success"},
        }
        func_response = types.FunctionResponse(
            name="test_func", response=gemini_response_dict, id="resp_1"
        )
        gemini_part = types.Part(function_response=func_response)
        common_part = self.converter._to_content_part(gemini_part)

        self.assertIsInstance(common_part, ContentPartToolResult)
        self.assertEqual(common_part.id, "resp_1")
        self.assertEqual(common_part.name, "test_func")
        self.assertTrue(common_part.content.success)
        self.assertIsNone(common_part.content.failure)
        self.assertIsInstance(common_part.content.output, ToolOutput)
        self.assertEqual(common_part.content.output.type, "text")
        self.assertEqual(common_part.content.output.content, "Success")
        self.assertIsNone(common_part.content.display_output)

    def test_to_content_part_tool_response_error(self):
        """Test converting Gemini Part (function response) for failure."""
        gemini_response_dict = {
            "failure": True,
            "output": {"type": "text", "content": "An error occurred"},
        }
        func_response = types.FunctionResponse(
            name="test_func", response=gemini_response_dict, id="resp_err"
        )
        gemini_part = types.Part(function_response=func_response)
        common_part = self.converter._to_content_part(gemini_part)

        self.assertIsInstance(common_part, ContentPartToolResult)
        self.assertEqual(common_part.id, "resp_err")
        self.assertEqual(common_part.name, "test_func")
        self.assertTrue(common_part.content.failure)
        self.assertIsNone(common_part.content.success)
        self.assertIsInstance(common_part.content.output, ToolOutput)
        self.assertEqual(common_part.content.output.type, "text")
        self.assertEqual(common_part.content.output.content, "An error occurred")
        self.assertIsNone(common_part.content.display_output)

    def test_to_content_part_tool_response_validation_error(self):
        """Test conversion failure if response doesn't match ToolCallResult model."""
        func_response = types.FunctionResponse(
            name="test_func", response={"invalid_key": "value"}, id="resp_1"
        )
        gemini_part = types.Part(function_response=func_response)
        # Fix: Expect ValueError from manual parsing
        with self.assertRaisesRegex(
            ValueError, "ToolCallResult\\s+output\\s+Field required"
        ):
            self.converter._to_content_part(gemini_part)

    def test_to_content_part_unknown(self):
        """Test converting an unknown Gemini Part type."""
        gemini_part = types.Part()
        with self.assertRaisesRegex(ValueError, "Unknown content type encountered"):
            self.converter._to_content_part(gemini_part)

    # --- Test create_provider_history ---

    def test_from_history_empty(self):
        """Test converting an empty History object."""
        history = History(context=None, conversation=[])
        provider_history = self.converter.create_provider_history(history)
        self.assertEqual(provider_history, [])

    def test_from_history_with_context(self):
        """Test converting History with context."""
        history = History(context="System prompt", conversation=[])
        provider_history = self.converter.create_provider_history(history)
        self.assertEqual(len(provider_history), 1)
        self.assertEqual(provider_history[0].role, "user")
        self.assertEqual(len(provider_history[0].parts), 1)
        self.assertEqual(provider_history[0].parts[0].text, "System prompt")

    def test_from_history_with_conversation(self):
        """Test converting History with a conversation."""
        tool_result_ok = ToolCallResult.ok(
            output=ToolOutput(type="text", content="Result")
        )
        history = History(
            context="System prompt",
            conversation=[
                Message(role=Role.USER, content=[ContentPartText(text="User query")]),
                Message(
                    role=Role.MODEL,
                    content=[
                        ContentPartText(text="Model response"),
                        ContentPartToolCall(id="c1", name="func", arguments={"a": 1}),
                    ],
                ),
                Message(
                    role=Role.TOOL,
                    content=[
                        ContentPartToolResult(
                            id="c1", name="func", content=tool_result_ok
                        )
                    ],
                ),
            ],
        )
        provider_history = self.converter.create_provider_history(history)
        self.assertEqual(len(provider_history), 4)

        self.assertEqual(provider_history[0].role, "user")
        self.assertEqual(provider_history[1].role, "user")
        self.assertEqual(provider_history[2].role, "model")
        self.assertEqual(provider_history[3].role, "tool")

        tool_response_part = provider_history[3].parts[0]
        self.assertEqual(tool_response_part.function_response.name, "func")
        expected_response_dict = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Result"},
            "display_output": None,
        }
        self.assertEqual(
            tool_response_part.function_response.response, expected_response_dict
        )

    # --- Test to_history ---

    def test_to_history_empty(self):
        """Test converting an empty provider history."""
        provider_history = []
        common_history = self.converter.to_history(provider_history)
        self.assertEqual(common_history, [])

    def test_to_history_with_context(self):
        """Test converting provider history including a leading context message."""
        # This test now assumes the converter *does not* skip context messages
        provider_history = [
            types.Content(
                role="user", parts=[types.Part(text="System prompt")]
            ),  # Context
            types.Content(role="user", parts=[types.Part(text="Real user message")]),
        ]
        common_history = self.converter.to_history(provider_history)
        # Fix: Expect 2 messages since context skipping was removed
        self.assertEqual(len(common_history), 2)
        # Check first message (originally context)
        self.assertEqual(common_history[0].role, Role.USER)
        self.assertIsInstance(common_history[0].content[0], ContentPartText)
        self.assertEqual(common_history[0].content[0].text, "System prompt")
        # Check second message
        self.assertEqual(common_history[1].role, Role.USER)
        self.assertIsInstance(common_history[1].content[0], ContentPartText)
        self.assertEqual(common_history[1].content[0].text, "Real user message")

    def test_to_history_no_context(self):
        """Test converting provider history without leading context."""
        func_call = types.FunctionCall(name="f1", args={}, id="c1")
        # Simulate Gemini response as serialized ToolCallResult
        gemini_response_dict = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "ok"},
            "display_output": None,
        }
        func_resp = types.FunctionResponse(
            name="f1", response=gemini_response_dict, id="c1"
        )
        provider_history = [
            types.Content(role="user", parts=[types.Part(text="User query")]),
            types.Content(role="model", parts=[types.Part(function_call=func_call)]),
            types.Content(role="tool", parts=[types.Part(function_response=func_resp)]),
        ]
        common_history = self.converter.to_history(provider_history)
        self.assertEqual(len(common_history), 3)

        self.assertEqual(common_history[0].role, Role.USER)
        self.assertEqual(common_history[1].role, Role.MODEL)

        tool_msg_content = common_history[2].content[0]
        self.assertEqual(common_history[2].role, Role.TOOL)
        self.assertIsInstance(tool_msg_content, ContentPartToolResult)
        self.assertEqual(tool_msg_content.name, "f1")
        self.assertEqual(tool_msg_content.id, "c1")
        self.assertTrue(tool_msg_content.content.success)
        self.assertIsNone(tool_msg_content.content.failure)
        self.assertIsInstance(tool_msg_content.content.output, ToolOutput)
        self.assertEqual(tool_msg_content.content.output.type, "text")
        self.assertEqual(tool_msg_content.content.output.content, "ok")

    # --- Test to_history_item ---

    def test_to_history_item_empty(self):
        """Test converting an empty list to a history item."""
        item = self.converter.to_history_item([])
        self.assertIsNone(item)

    def test_to_history_item_from_chunks(self):
        """Test converting a list of GeminiChunkWrapper chunks."""
        chunks = [
            GeminiChunkWrapper(types.Part(text="Part 1")),
            GeminiChunkWrapper(
                types.Part(
                    function_call=types.FunctionCall(name="f1", args={"a": 1}, id="c1")
                )
            ),
            GeminiChunkWrapper(types.Part(text="Part 2")),
        ]
        item = self.converter.to_history_item(chunks)
        self.assertIsNotNone(item)
        self.assertEqual(item.role, "model")
        self.assertEqual(len(item.parts), 3)
        self.assertEqual(item.parts[0].text, "Part 1")
        self.assertEqual(item.parts[1].function_call.name, "f1")
        self.assertEqual(item.parts[1].function_call.args, {"a": 1})
        self.assertEqual(item.parts[2].text, "Part 2")

    def test_to_history_item_from_tool_results(self):
        """Test converting a list of ContentPartToolResult."""
        result1 = ToolCallResult.ok(output=ToolOutput(type="text", content="Res1"))
        result2 = ToolCallResult.error(output="Err2")  # Error implies failure
        results = [
            ContentPartToolResult(id="c1", name="f1", content=result1),
            ContentPartToolResult(id="c2", name="f2", content=result2),
        ]
        item = self.converter.to_history_item(results)
        self.assertIsNotNone(item)
        self.assertEqual(item.role, "tool")
        self.assertEqual(len(item.parts), 2)

        part1 = item.parts[0]
        self.assertEqual(part1.function_response.name, "f1")
        expected_resp1 = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "Res1"},
            "display_output": None,
        }
        self.assertEqual(part1.function_response.response, expected_resp1)

        part2 = item.parts[1]
        self.assertEqual(part2.function_response.name, "f2")
        expected_resp2 = {
            "success": None,
            "failure": True,
            "output": {"type": "text", "content": "Err2"},
            "display_output": None,
        }
        self.assertEqual(part2.function_response.response, expected_resp2)

    # --- Test _content_blocks_to_message ---

    def test_content_blocks_to_message_empty(self):
        """Test _content_blocks_to_message with empty list."""
        item = self.converter._content_blocks_to_message([])
        # Fix: Expect None for empty input based on implementation change
        self.assertIsNone(item)

    def test_content_blocks_to_message_mixed(self):
        """Test _content_blocks_to_message with mixed content."""
        chunks = [
            GeminiChunkWrapper(types.Part(text="Text")),
            GeminiChunkWrapper(
                types.Part(
                    function_call=types.FunctionCall(name="f1", args={}, id="c1")
                )
            ),
        ]
        item = self.converter._content_blocks_to_message(chunks)
        self.assertEqual(item.role, "model")
        self.assertEqual(len(item.parts), 2)
        self.assertEqual(item.parts[0].text, "Text")
        self.assertEqual(item.parts[1].function_call.name, "f1")

    # --- Test _tool_results_to_message ---

    def test_tool_results_to_message_empty(self):
        """Test _tool_results_to_message with empty list."""
        item = self.converter._tool_results_to_message([])
        self.assertIsNone(item)

    def test_tool_results_to_message_single(self):
        """Test _tool_results_to_message with a single result."""
        result = ToolCallResult.ok(output=ToolOutput(type="text", content="R1"))
        results = [ContentPartToolResult(id="c1", name="f1", content=result)]
        item = self.converter._tool_results_to_message(results)

        self.assertEqual(item.role, "tool")
        self.assertEqual(len(item.parts), 1)
        self.assertEqual(item.parts[0].function_response.name, "f1")
        expected_resp = {
            "success": True,
            "failure": None,
            "output": {"type": "text", "content": "R1"},
            "display_output": None,
        }
        self.assertEqual(item.parts[0].function_response.response, expected_resp)

    # --- Test create_chunk_wrapper ---

    def test_create_chunk_wrapper(self):
        """Test creating a chunk wrapper."""
        gemini_part = types.Part(text="Hello")
        wrapper = self.converter.create_chunk_wrapper(gemini_part)
        self.assertIsInstance(wrapper, GeminiChunkWrapper)
        self.assertEqual(wrapper.raw, gemini_part)


if __name__ == "__main__":
    unittest.main()
