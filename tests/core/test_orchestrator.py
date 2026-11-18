# tests/core/test_orchestrator.py
import pytest
from unittest.mock import MagicMock
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.brain import Message, BrainResponse, ToolCall
from jarvis.core.memory import ShortTermMemory, LongTermMemory
from jarvis.core.skill_registry import SkillRegistry


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.think.return_value = BrainResponse(text="Hello, Hasnine!", tool_calls=[])
    return brain


@pytest.fixture
def orchestrator(mock_brain, tmp_path):
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "user.name": "Hasnine",
        "jarvis.personality": "You are Jarvis.",
        "llm.max_history": 50,
    }.get(key, default)

    registry = SkillRegistry()
    short_mem = ShortTermMemory(max_messages=50)
    long_mem = LongTermMemory(db_path=str(tmp_path / "test.db"))

    return Orchestrator(
        brain=mock_brain,
        config=config,
        skill_registry=registry,
        short_term_memory=short_mem,
        long_term_memory=long_mem,
    )


def test_orchestrator_simple_response(orchestrator, mock_brain):
    result = orchestrator.process("Hi there")
    assert result == "Hello, Hasnine!"
    mock_brain.think.assert_called_once()


def test_orchestrator_tool_call(orchestrator, mock_brain):
    # First call returns tool call, second returns text
    mock_brain.think.return_value = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="system_info__cpu_usage", args={})]
    )
    mock_brain.send_tool_results.return_value = BrainResponse(
        text="CPU is at 25%.", tool_calls=[]
    )
    orchestrator._skill_registry.register(MagicMock(
        name="system_info",
        execute=MagicMock(return_value="CPU: 25%, Battery: 80%"),
    ))

    result = orchestrator.process("Check CPU")
    assert "25%" in result


def test_orchestrator_stores_messages(orchestrator, mock_brain):
    orchestrator.process("Hello")
    messages = orchestrator._short_term_memory.get_messages()
    assert len(messages) == 2  # user message + assistant response
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
