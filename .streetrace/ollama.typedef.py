# type definitions file
# package: ollama

from typing import Any, Iterator, Literal, Mapping, Optional, Sequence, Union
from pydantic import BaseModel

class Message(BaseModel):
  """
  Chat message.
  """

  role: Literal['user', 'assistant', 'system', 'tool']
  "Assumed role of the message. Response messages has role 'assistant' or 'tool'."

  content: Optional[str] = None
  'Content of the message. Response messages contains message fragments when streaming.'

  class ToolCall(BaseModel):
    """
    Model tool calls.
    """

    class Function(BaseModel):
      """
      Tool call function.
      """

      name: str
      'Name of the function.'

      arguments: Mapping[str, Any]
      'Arguments of the function.'

    function: Function
    'Function to be called.'

  tool_calls: Optional[Sequence[ToolCall]] = None
  """
  Tools calls to be made by the model.
  """

class BaseGenerateResponse(BaseModel):
  model: Optional[str] = None
  'Model used to generate response.'

  created_at: Optional[str] = None
  'Time when the request was created.'

  done: Optional[bool] = None
  'True if response is complete, otherwise False. Useful for streaming to detect the final response.'

  done_reason: Optional[str] = None
  'Reason for completion. Only present when done is True.'

  total_duration: Optional[int] = None
  'Total duration in nanoseconds.'

  load_duration: Optional[int] = None
  'Load duration in nanoseconds.'

  prompt_eval_count: Optional[int] = None
  'Number of tokens evaluated in the prompt.'

  prompt_eval_duration: Optional[int] = None
  'Duration of evaluating the prompt in nanoseconds.'

  eval_count: Optional[int] = None
  'Number of tokens evaluated in inference.'

  eval_duration: Optional[int] = None
  'Duration of evaluating inference in nanoseconds.'

class ChatResponse(BaseGenerateResponse):
  """
  Response returned by chat requests.
  """

  message: Message
  'Response message.'

def chat(
    self,
    model: str = '',
    messages: Optional[Sequence[Union[Mapping[str, Any], Message]]] = None,
    **kwargs: Any,
) -> Iterator[ChatResponse]:
    pass