from types import SimpleNamespace
from unittest.mock import MagicMock

from google.genai import types

from jarvis.core.brain import BrainResponse, GeminiBrain, Message, ToolCall


def _response(*parts):
    content = types.Content(role="model", parts=list(parts))
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def _brain(*responses):
    client = MagicMock()
    client.models.generate_content.side_effect = list(responses)
    return GeminiBrain(api_key="fake", model="test-model", client=client), client


def test_message_creation():
    msg = Message(role="user", content="Hello")
    assert (msg.role, msg.content) == ("user", "Hello")


def test_brain_response_defaults():
    resp = BrainResponse(text="Hi")
    assert resp.tool_calls == []
    resp = BrainResponse(text=None, tool_calls=[ToolCall(name="a__b", args={})])
    assert resp.tool_calls[0].name == "a__b"


def test_text_response():
    brain, client = _brain(_response(types.Part.from_text(text="Hello, Hasnine!")))
    resp = brain.think([Message("user", "Hi")], [], "You are Jarvis.")
    assert resp.text == "Hello, Hasnine!"
    assert resp.tool_calls == []
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["config"].system_instruction == "You are Jarvis."
    assert kwargs["config"].tools is None


def test_history_is_rebuilt_not_accumulated():
    brain, client = _brain(
        _response(types.Part.from_text(text="one")),
        _response(types.Part.from_text(text="two")),
    )
    brain.think([Message("user", "a")], [], "sys")
    history = [Message("user", "a"), Message("assistant", "one"), Message("user", "b")]
    brain.think(history, [], "sys")
    contents = client.models.generate_content.call_args.kwargs["contents"]
    # 3 history messages + the model reply appended after the call
    assert [c.role for c in contents] == ["user", "model", "user", "model"]


def test_tool_call_then_result():
    brain, client = _brain(
        _response(types.Part.from_function_call(name="system_info__cpu_usage", args={})),
        _response(types.Part.from_text(text="CPU is at 25%.")),
    )
    decls = [{"name": "system_info__cpu_usage", "description": "CPU",
              "parameters": {"type": "object", "properties": {}, "required": []}}]
    resp = brain.think([Message("user", "Check CPU")], decls, "sys")
    assert resp.text is None
    assert resp.tool_calls == [ToolCall(name="system_info__cpu_usage", args={})]
    tool = client.models.generate_content.call_args.kwargs["config"].tools[0]
    assert tool.function_declarations[0].name == "system_info__cpu_usage"

    final = brain.send_tool_results([{"name": "system_info__cpu_usage", "output": "CPU: 25%"}])
    assert final.text == "CPU is at 25%."
    contents = client.models.generate_content.call_args.kwargs["contents"]
    # user, model(function_call), user(function_response), model(text)
    assert contents[2].parts[0].function_response.name == "system_info__cpu_usage"
    assert contents[2].parts[0].function_response.response == {"result": "CPU: 25%"}


def test_empty_candidates_returns_empty_text():
    brain, _ = _brain(SimpleNamespace(candidates=[]))
    assert brain.think([Message("user", "hi")], [], "sys").text == ""
