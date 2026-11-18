import pytest
from unittest.mock import patch, MagicMock
from jarvis.core.brain import Message, ToolCall, BrainResponse, GeminiBrain


def test_message_creation():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_brain_response_text_only():
    resp = BrainResponse(text="Hello!", tool_calls=[])
    assert resp.text == "Hello!"
    assert resp.tool_calls == []


def test_brain_response_with_tool_calls():
    resp = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="system_info__cpu_usage", args={})],
    )
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "system_info__cpu_usage"


def test_gemini_brain_text_response():
    brain = GeminiBrain(api_key="fake-key", model="gemini-2.0-flash")

    mock_part = MagicMock()
    mock_part.function_call = None
    mock_part.text = "Hello, Hasnine!"

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    with patch.object(brain, "_chat") as mock_chat:
        mock_chat.send_message.return_value = mock_response
        response = brain.think(
            messages=[Message(role="user", content="Hi")],
            tool_declarations=[],
            system_prompt="You are Jarvis.",
        )
    assert response.text == "Hello, Hasnine!"
    assert response.tool_calls == []


def test_gemini_brain_tool_call_response():
    brain = GeminiBrain(api_key="fake-key", model="gemini-2.0-flash")

    mock_fc = MagicMock()
    mock_fc.name = "system_info__cpu_usage"
    mock_fc.args = {}

    mock_part = MagicMock()
    mock_part.function_call = mock_fc
    mock_part.text = ""

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    with patch.object(brain, "_chat") as mock_chat:
        mock_chat.send_message.return_value = mock_response
        response = brain.think(
            messages=[Message(role="user", content="Check CPU")],
            tool_declarations=[
                {
                    "name": "system_info__cpu_usage",
                    "description": "Get CPU stats",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
            system_prompt="You are Jarvis.",
        )
    assert response.text is None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "system_info__cpu_usage"
