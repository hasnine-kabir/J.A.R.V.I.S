from dataclasses import dataclass, field
from typing import Protocol
import google.generativeai as genai
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.brain")


@dataclass
class Message:
    role: str  # "user", "assistant", "tool_result"
    content: str


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class BrainResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Brain(Protocol):
    def think(
        self,
        messages: list[Message],
        tool_declarations: list[dict],
        system_prompt: str,
    ) -> BrainResponse: ...

    def send_tool_results(self, results: list[dict]) -> BrainResponse: ...


class GeminiBrain:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = None
        self._chat = None

    def _ensure_chat(self, system_prompt: str, tool_declarations: list[dict]):
        """Create or recreate the model and chat with current tools."""
        tools = None
        if tool_declarations:
            tools = [{"function_declarations": tool_declarations}]
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            tools=tools,
        )
        self._chat = self._model.start_chat()

    def think(
        self,
        messages: list[Message],
        tool_declarations: list[dict],
        system_prompt: str,
    ) -> BrainResponse:
        # Only initialise a real chat session when one hasn't been injected
        # (e.g. by tests via patch.object or direct assignment).
        if self._chat is None:
            self._ensure_chat(system_prompt, tool_declarations)

        # Replay conversation history (all messages except the last)
        for msg in messages[:-1]:
            if msg.role == "user":
                self._chat.history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                self._chat.history.append({"role": "model", "parts": [msg.content]})

        # Send the latest user message
        last_message = messages[-1].content if messages else ""
        response = self._chat.send_message(last_message)
        return self._parse_response(response)

    def send_tool_results(self, results: list[dict]) -> BrainResponse:
        """Send tool execution results back to Gemini and get the final response."""
        from google.protobuf.struct_pb2 import Struct

        parts = []
        for result in results:
            s = Struct()
            s.update({"result": result["output"]})
            parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=result["name"], response=s
                    )
                )
            )
        response = self._chat.send_message(parts)
        return self._parse_response(response)

    def _parse_response(self, response) -> BrainResponse:
        tool_calls = []
        text_parts = []

        for part in response.parts:
            if part.function_call and part.function_call.name:
                tool_calls.append(
                    ToolCall(
                        name=part.function_call.name,
                        args=dict(part.function_call.args)
                        if part.function_call.args
                        else {},
                    )
                )
            elif part.text:
                text_parts.append(part.text)

        if tool_calls:
            return BrainResponse(text=None, tool_calls=tool_calls)
        return BrainResponse(text="\n".join(text_parts) if text_parts else "")
