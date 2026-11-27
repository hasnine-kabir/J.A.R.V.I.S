from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from jarvis.core.brain import BrainResponse, ToolCall
from jarvis.core.memory import LongTermMemory, ShortTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.skill_registry import SkillRegistry
from jarvis.ui.handsfree import HandsFreeSession, split_wake_word


@pytest.mark.parametrize("heard, woken, command", [
    ("Jarvis what's the weather", True, "what's the weather"),
    ("hey Jarvis, open notepad", True, "open notepad"),
    ("okay jarvis. what time is it?", True, "what time is it"),
    ("what time is it Jarvis", True, "what time is it"),
    ("Jarvis", True, ""),
    ("Jervis open YouTube", True, "open YouTube"),
    ("Jarvis's turn to play music", True, "turn to play music"),
    ("what's for dinner tonight", False, "what's for dinner tonight"),
    ("Jarvisville is a town", False, "Jarvisville is a town"),
])
def test_split_wake_word(heard, woken, command):
    assert split_wake_word(heard, ["jarvis"]) == (woken, command)


def test_custom_wake_word():
    assert split_wake_word("friday open chrome", ["friday"]) == (True, "open chrome")
    assert split_wake_word("Jarvis open chrome", ["friday"])[0] is False


class FakeListener:
    def __init__(self, phrases):
        self.phrases = list(phrases)
        self.waits = []

    def listen(self, wait_seconds=None):
        self.waits.append(wait_seconds)
        if not self.phrases:
            raise KeyboardInterrupt  # end the session like Ctrl+C
        return self.phrases.pop(0)


def make_session(phrases, replies, tmp_path, config_overrides=None):
    values = {"user.name": "Tester", "voice.wake_words": ["jarvis"], "voice.follow_up_seconds": 10}
    values.update(config_overrides or {})
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: values.get(k, d)
    orch = MagicMock()
    orch.process.side_effect = list(replies)
    speaker = MagicMock()
    listener = FakeListener(phrases)
    session = HandsFreeSession(orch, config, speaker, listener, Console(file=open(tmp_path / "out.txt", "w")))
    return session, orch, speaker, listener


def spoken(speaker):
    return [c.args[0] for c in speaker.say.call_args_list]


def test_ignores_speech_without_wake_word(tmp_path):
    session, orch, speaker, _ = make_session(["what a nice day"], [], tmp_path)
    session.run()
    orch.process.assert_not_called()


def test_wake_word_with_command_is_answered_out_loud(tmp_path):
    session, orch, speaker, _ = make_session(["Jarvis what time is it"], ["It's noon."], tmp_path)
    session.run()
    assert orch.process.call_args.args == ("what time is it",)
    assert "It's noon." in spoken(speaker)


def test_wake_word_alone_then_request(tmp_path):
    session, orch, speaker, listener = make_session(["Jarvis", "open notepad"], ["Opened."], tmp_path)
    session.run()
    assert "Yes?" in spoken(speaker)
    assert orch.process.call_args.args == ("open notepad",)
    assert listener.waits[0] is None          # sleeping: wait forever for the wake word
    assert listener.waits[1] is not None      # awake: bounded follow-up window


def test_follow_up_without_wake_word(tmp_path):
    session, orch, _, _ = make_session(
        ["Jarvis what's the weather", "and tomorrow?"], ["Sunny.", "Rainy."], tmp_path
    )
    session.run()
    assert [c.args[0] for c in orch.process.call_args_list] == ["what's the weather", "and tomorrow?"]


def test_goodbye_ends_session(tmp_path):
    session, orch, speaker, listener = make_session(["Jarvis goodbye", "Jarvis open chrome"], [], tmp_path)
    session.run()
    orch.process.assert_not_called()
    assert listener.phrases == ["Jarvis open chrome"]  # stopped listening
    assert spoken(speaker)[-1].startswith("Hands-free mode off")


def test_errors_are_spoken_not_crashing(tmp_path):
    class Overloaded(Exception):
        code = 503

    session, orch, speaker, _ = make_session(
        ["Jarvis hello"], [Overloaded("503 UNAVAILABLE overloaded")], tmp_path
    )
    session.run()
    assert any("overloaded" in s for s in spoken(speaker))


def test_voice_confirmation(tmp_path):
    session, _, speaker, listener = make_session(["yes please"], [], tmp_path)
    assert session._confirm_by_voice("pc_control__run_command", {"command": "x"}) is True
    listener.phrases = ["no"]
    assert session._confirm_by_voice("pc_control__run_command", {"command": "x"}) is False


# ---- safety.confirm_actions -------------------------------------------------------------
def _orchestrator(tmp_path, confirm_actions):
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"safety.confirm_actions": confirm_actions}.get(k, d)
    brain = MagicMock()
    brain.think.return_value = BrainResponse(
        text=None, tool_calls=[ToolCall("pc_control__run_command", {"command": "echo full-access"})]
    )
    brain.send_tool_results.return_value = BrainResponse(text="ok")
    registry = SkillRegistry()
    registry.discover()
    orch = Orchestrator(brain, config, registry, ShortTermMemory(10),
                        LongTermMemory(str(tmp_path / "m.db")))
    return orch, brain


def test_full_access_runs_without_asking(tmp_path):
    orch, brain = _orchestrator(tmp_path, confirm_actions=False)
    confirm = MagicMock(return_value=False)
    orch.set_confirm_callback(confirm)
    orch.process("go")
    confirm.assert_not_called()
    assert "full-access" in brain.send_tool_results.call_args.args[0][0]["output"]


def test_confirm_actions_true_still_asks(tmp_path):
    orch, brain = _orchestrator(tmp_path, confirm_actions=True)
    orch.set_confirm_callback(MagicMock(return_value=False))
    orch.process("go")
    assert "declined" in brain.send_tool_results.call_args.args[0][0]["output"]


def test_open_application_with_target():
    from jarvis.skills.pc_control import PCControlSkill

    with patch("jarvis.skills.pc_control.subprocess.Popen") as popen, \
            patch("jarvis.skills.pc_control.sys.platform", "win32"):
        result = PCControlSkill().execute(
            "open_application", {"app_name": "chrome", "target": "https://youtube.com"}
        )
    assert popen.call_args.args[0] == 'start "" "chrome" "https://youtube.com"'
    assert result == "Opened chrome → https://youtube.com."
