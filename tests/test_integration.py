"""End-to-end: real registry + real skills + real SQLite, with a scripted brain."""
from unittest.mock import MagicMock, patch

import pytest

from jarvis.core.brain import BrainResponse, ToolCall
from jarvis.core.memory import LongTermMemory, ShortTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.skill_registry import SkillRegistry

ALL_SKILLS = {"system_info", "pc_control", "screenshot", "web_search", "wikipedia_search",
              "code_helper", "notes", "email_sender", "media"}


@pytest.fixture
def system(tmp_path):
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "user.name": "TestUser", "jarvis.personality": "You are Jarvis.",
    }.get(key, default)
    config.smtp_email = ""
    config.smtp_password = ""
    brain = MagicMock()
    registry = SkillRegistry()
    registry.discover()
    long_mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    orch = Orchestrator(brain, config, registry, ShortTermMemory(50), long_mem)
    yield orch, brain, registry, long_mem


def test_all_skills_discovered_and_declared(system):
    _, _, registry, _ = system
    assert {s.name for s in registry.get_all_skills()} == ALL_SKILLS
    names = [d["name"] for d in registry.get_tool_declarations()]
    assert len(names) == len(set(names))
    assert all("__" in n for n in names)


def test_notes_round_trip_through_orchestrator(system):
    orch, brain, _, long_mem = system
    brain.think.return_value = BrainResponse(
        text=None, tool_calls=[ToolCall("notes__save_fact", {"key": "favorite_color", "value": "blue"})]
    )
    brain.send_tool_results.return_value = BrainResponse(text="Noted.")
    assert orch.process("My favorite color is blue") == "Noted."
    assert long_mem.get_facts() == [{"key": "favorite_color", "value": "blue"}]
    # The fact now appears in the system prompt for future turns.
    assert "favorite_color: blue" in orch.get_system_prompt()


def test_risky_tool_declined_without_confirmation(system):
    orch, brain, _, _ = system
    brain.think.return_value = BrainResponse(
        text=None, tool_calls=[ToolCall("pc_control__run_command", {"command": "echo hi"})]
    )
    brain.send_tool_results.return_value = BrainResponse(text="Okay, I won't.")
    with patch("jarvis.skills.pc_control.subprocess.run") as run:
        orch.process("run echo hi")
    run.assert_not_called()
    sent = brain.send_tool_results.call_args.args[0]
    assert "declined" in sent[0]["output"]


def test_risky_tool_runs_when_confirmed(system):
    orch, brain, _, _ = system
    asked = []
    orch.set_confirm_callback(lambda name, args: asked.append(name) or True)
    brain.think.return_value = BrainResponse(
        text=None, tool_calls=[ToolCall("pc_control__run_command", {"command": "echo jarvis-ok"})]
    )
    brain.send_tool_results.return_value = BrainResponse(text="Done")
    orch.process("run it")
    assert asked == ["pc_control__run_command"]
    assert "jarvis-ok" in brain.send_tool_results.call_args.args[0][0]["output"]


def test_safe_tool_does_not_ask(system):
    orch, brain, _, _ = system
    confirm = MagicMock(return_value=False)
    orch.set_confirm_callback(confirm)
    brain.think.return_value = BrainResponse(text=None, tool_calls=[ToolCall("system_info__current_time", {})])
    brain.send_tool_results.return_value = BrainResponse(text="It's noon.")
    orch.process("what time is it")
    confirm.assert_not_called()
    assert brain.send_tool_results.call_args.args[0][0]["output"].startswith("It's ")


def test_tool_loop_is_bounded(system):
    orch, brain, _, _ = system
    looping = BrainResponse(text=None, tool_calls=[ToolCall("system_info__current_time", {})])
    brain.think.return_value = looping
    brain.send_tool_results.return_value = looping
    assert orch.process("loop forever") == "Done."
    assert brain.send_tool_results.call_count == 6


def test_shutdown_saves_llm_summary(system, tmp_path):
    orch, brain, _, _ = system
    brain.think.return_value = BrainResponse(text="Hello!")
    orch.process("Hi")
    orch.process("How are you?")
    brain.think.return_value = BrainResponse(text="The user said hello.")
    orch.shutdown()
    reopened = LongTermMemory(db_path=str(tmp_path / "test.db"))
    assert reopened.get_last_session_summary() == "The user said hello."
    reopened.close()
