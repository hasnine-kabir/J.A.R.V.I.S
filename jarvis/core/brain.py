"""LLM brain. Provider-neutral data types + the Gemini implementation."""
import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.brain")

FALLBACK_COOLDOWN = 300  # seconds to stay on a fallback model before retrying the preferred one


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

    def __init__(self, api_key: str | list[str], model: str = "gemini-3.5-flash",
                 client=None, client_factory=None, fallback_models: list[str] | None = None):
        from jarvis.core.key_pool import KeyPool

        keys = [api_key] if isinstance(api_key, str) else list(api_key)
        if client is not None:  # a single injected client (tests)
            client_factory = lambda _key: client  # noqa: E731
        self.keys = KeyPool(keys, client_factory=client_factory)
        self._model = model
        self._preferred = model
        self._fallbacks = [m for m in (fallback_models or []) if m and m != model]
        self._retry_preferred_at = 0.0
        self._clock = time.monotonic
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

    @property
    def model(self) -> str:
        return self._model

    def _call_model(self):
        return self.keys.call(
            lambda client: client.models.generate_content(
                model=self._model, contents=self._contents, config=self._config
            )
        )

    def _generate(self) -> BrainResponse:
        if self._model != self._preferred and self._clock() >= self._retry_preferred_at:
            self._model = self._preferred  # cooldown over: try the preferred model again
        try:
            response = self._call_model()
        except Exception as e:
            response = self._recover(e)
        candidates = getattr(response, "candidates", None) or []
        content = candidates[0].content if candidates else None
        if content is not None:
            # Keep the model's turn verbatim so follow-up tool results line up.
            self._contents.append(content)
        return self._parse_parts(getattr(content, "parts", None) or [])

    def _recover(self, error: Exception):
        """Retry on a different model when the current one is retired or overloaded."""
        code = getattr(error, "code", None)
        retired = re.search(r"use models/([\w.\-]+)", str(error)) if code == 404 else None
        if retired and retired.group(1) != self._model:
            logger.warning(f"Model {self._model} retired; switching to {retired.group(1)}")
            self._model = self._preferred = retired.group(1)  # permanent for this session
            return self._call_model()
        if not (isinstance(code, int) and code >= 500) or not self._fallbacks:
            raise error
        failed = self._model
        last = error
        for fallback in [m for m in [self._preferred, *self._fallbacks] if m != failed]:
            logger.warning(f"Model {self._model} failed ({code}); trying {fallback}")
            self._model = fallback
            try:
                response = self._call_model()
            except Exception as e:
                last = e
                if not (isinstance(getattr(e, "code", None), int) and e.code >= 500):
                    break
                continue
            # Stay on the working model for a while instead of re-hitting the overloaded one.
            self._retry_preferred_at = self._clock() + FALLBACK_COOLDOWN
            return response
        self._model = self._preferred
        raise last

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
