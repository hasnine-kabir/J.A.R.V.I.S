"""LLM brain. Provider-neutral data types + the Gemini implementation."""
from dataclasses import dataclass, field
from typing import Protocol

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.brain")


@dataclass
class Message:
    role: str  # "user" or "assistant"
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
    """Gemini via the `google-genai` SDK.

    Stateless between user turns: every `think()` rebuilds the conversation
    from the messages it is given. Within one turn, `send_tool_results()`
    continues the same exchange so the model sees its own function calls
    (including any thought signatures) followed by the results.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", client=None):
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model
        self._contents: list = []
        self._config = None

    def think(
        self,
        messages: list[Message],
        tool_declarations: list[dict],
        system_prompt: str,
    ) -> BrainResponse:
        from google.genai import types

        self._contents = [
            types.Content(
                role="user" if m.role == "user" else "model",
                parts=[types.Part.from_text(text=m.content)],
            )
            for m in messages
            if m.role in ("user", "assistant") and m.content
        ]
        tools = None
        if tool_declarations:
            tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=d["name"],
                            description=d.get("description", ""),
                            parameters_json_schema=d.get("parameters"),
                        )
                        for d in tool_declarations
                    ]
                )
            ]
        self._config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        return self._generate()

    def send_tool_results(self, results: list[dict]) -> BrainResponse:
        from google.genai import types

        parts = [
            types.Part.from_function_response(
                name=r["name"], response={"result": str(r["output"])}
            )
            for r in results
        ]
        self._contents.append(types.Content(role="user", parts=parts))
        return self._generate()

    def _generate(self) -> BrainResponse:
        response = self._client.models.generate_content(
            model=self._model, contents=self._contents, config=self._config
        )
        candidates = getattr(response, "candidates", None) or []
        content = candidates[0].content if candidates else None
        if content is not None:
            # Keep the model's turn verbatim so follow-up tool results line up.
            self._contents.append(content)
        return self._parse_parts(getattr(content, "parts", None) or [])

    @staticmethod
    def _parse_parts(parts) -> BrainResponse:
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc is not None and getattr(fc, "name", None):
                tool_calls.append(ToolCall(name=fc.name, args=dict(fc.args or {})))
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                text_parts.append(part.text)
        if tool_calls:
            return BrainResponse(text=None, tool_calls=tool_calls)
        return BrainResponse(text="\n".join(text_parts))
