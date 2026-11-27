"""Streaming, thinking level, model switching, parallel tools, lazy imports, speech queue."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from google.genai import types

from jarvis.core.brain import BrainResponse, GeminiBrain, Message, ToolCall
from jarvis.core.memory import LongTermMemory, ShortTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.skills.base import BaseSkill, Tool
from jarvis.utils.lazy import LazyModule
from jarvis.voice.stream import SpeechQueue


def _chunk(*parts):
    return SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role="model", parts=list(parts)))])


class ApiError(Exception):
    def __init__(self, code, message=""):
        super().__init__(message or str(code))
        self.code = code


# ---- brain ---------------------------------------------------------------------------------
def test_streaming_emits_fragments_and_keeps_history():
    client = MagicMock()
    client.models.generate_content_stream.return_value = iter([
        _chunk(types.Part.from_text(text="Hello, ")),
        _chunk(types.Part(text="hmm", thought=True)),
        _chunk(types.Part.from_text(text="Hasnine.")),
    ])
    brain = GeminiBrain("k", model="m", client=client)
    seen = []
    resp = brain.think([Message("user", "hi")], [], "sys", on_text=seen.append)
    assert seen == ["Hello, ", "Hasnine."]          # thoughts are not shown
    assert resp.text == "Hello, Hasnine."
    assert brain._contents[-1].role == "model"       # streamed turn kept for tool follow-ups
    client.models.generate_content.assert_not_called()


def test_streamed_function_call():
    client = MagicMock()
    client.models.generate_content_stream.return_value = iter([
        _chunk(types.Part.from_function_call(name="system_info__cpu_usage", args={})),
    ])
    brain = GeminiBrain("k", model="m", client=client)
    resp = brain.think([Message("user", "cpu?")], [], "sys", on_text=lambda t: None)
    assert resp.tool_calls == [ToolCall("system_info__cpu_usage", {})]


def test_thinking_level_is_sent_and_dropped_when_rejected():
    client = MagicMock()
    ok = SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(
        role="model", parts=[types.Part.from_text(text="ok")]))])
    client.models.generate_content.side_effect = [
        ApiError(400, "Thinking level is not supported for this model."), ok, ok]
    brain = GeminiBrain("k", model="m", client=client, thinking_level="minimal")
    assert brain.think([Message("user", "hi")], [], "sys").text == "ok"
    first, second = client.models.generate_content.call_args_list[:2]
    assert first.kwargs["config"].thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert second.kwargs["config"].thinking_config is None
    brain.think([Message("user", "again")], [], "sys")   # remembered: no second failure
    assert client.models.generate_content.call_count == 3


def test_tool_declarations_are_converted_once():
    brain = GeminiBrain("k", model="m", client=MagicMock())
    decls = [{"name": "a__b", "description": "x", "parameters": {"type": "object", "properties": {}}}]
    assert brain._tools(decls) is brain._tools(list(decls))
    assert brain._tools(decls + [{"name": "c__d"}]) is not brain._tools(decls)


def test_no_fallback_once_text_was_streamed():
    client = MagicMock()

    def broken_stream(**_):
        yield _chunk(types.Part.from_text(text="Half an ans"))
        raise ApiError(503, "overloaded")

    client.models.generate_content_stream.side_effect = broken_stream
    brain = GeminiBrain("k", model="m", client=client, fallback_models=["backup"])
    try:
        brain.think([Message("user", "hi")], [], "sys", on_text=lambda t: None)
        raise AssertionError("expected the error to surface")
    except ApiError:
        pass
    assert client.models.generate_content_stream.call_count == 1  # didn't repeat the answer


def test_set_model_keeps_old_one_as_fallback():
    brain = GeminiBrain("k", model="fast", client=MagicMock(), fallback_models=["backup"])
    brain.set_model("smart")
    assert brain.model == "smart"
    assert brain.models == ["smart", "fast", "backup"]


# ---- orchestrator --------------------------------------------------------------------------
class SlowSkill(BaseSkill):
    name = "slow"
    description = "sleeps"
    tools = [Tool("a", "a", {}), Tool("b", "b", {})]

    def execute(self, action, args):
        time.sleep(0.3)
        return f"{action} on {threading.current_thread().name}"


def _orch(tmp_path, brain):
    from jarvis.core.skill_registry import SkillRegistry

    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"safety.confirm_actions": False}.get(k, d)
    registry = SkillRegistry()
    registry.register(SlowSkill())
    return Orchestrator(brain, config, registry, ShortTermMemory(10), LongTermMemory(str(tmp_path / "m.db")))


def test_tools_in_one_round_run_in_parallel(tmp_path):
    brain = MagicMock()
    brain.think.return_value = BrainResponse(None, [ToolCall("slow__a", {}), ToolCall("slow__b", {})])
    brain.send_tool_results.return_value = BrainResponse("done")
    orch = _orch(tmp_path, brain)
    start = time.perf_counter()
    assert orch.process("go") == "done"
    assert time.perf_counter() - start < 0.55        # two 0.3 s tools, not 0.6 s
    results = brain.send_tool_results.call_args.args[0]
    assert [r["name"] for r in results] == ["slow__a", "slow__b"]  # order preserved


def test_on_text_is_passed_to_the_brain(tmp_path):
    brain = MagicMock()
    brain.think.return_value = BrainResponse("hi")
    orch = _orch(tmp_path, brain)
    sink = []
    orch.process("hello", on_text=sink.append)
    assert brain.think.call_args.kwargs["on_text"] == sink.append


# ---- misc ----------------------------------------------------------------------------------
def test_lazy_module_imports_on_first_use():
    lazy = LazyModule("json")
    assert lazy.dumps({"a": 1}) == '{"a": 1}'


def test_memory_works_across_threads(tmp_path):
    mem = LongTermMemory(str(tmp_path / "m.db"))
    t = threading.Thread(target=mem.save_fact, args=("color", "blue"))
    t.start()
    t.join()
    assert mem.get_facts() == [{"key": "color", "value": "blue"}]
    assert mem.delete_fact("color") is True
    assert mem.get_facts() == []


def test_speech_queue_splits_sentences_and_skips_code():
    sentences, rest = SpeechQueue._split("Hi there. Version 3.5 is out! And")
    assert sentences == ["Hi there.", " Version 3.5 is out!"]
    assert rest == " And"
    sentences, rest = SpeechQueue._split("Here you go. ```python\nprint(1)")
    assert sentences == ["Here you go."]
    assert rest.strip().startswith("```")


def test_speech_queue_speaks_while_streaming():
    speaker = MagicMock()
    q = SpeechQueue(speaker)
    q.feed("First sentence. Sec")
    q.feed("ond one")
    assert q.wait(2)
    assert [c.args[0] for c in speaker.say.call_args_list] == ["First sentence."]
    q.flush()
    assert q.wait(2)
    assert speaker.say.call_args_list[-1].args[0] == "Second one"
