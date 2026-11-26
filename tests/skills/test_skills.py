"""Unit tests for the built-in skills. Network, GUI and process launching are mocked."""
from unittest.mock import MagicMock, patch

import pytest

from jarvis.core.memory import LongTermMemory
from jarvis.skills.code_helper import CodeHelperSkill
from jarvis.skills.email_sender import EmailSenderSkill
from jarvis.skills.media import MediaSkill
from jarvis.skills.notes import NotesSkill
from jarvis.skills.pc_control import PCControlSkill
from jarvis.skills.screenshot import ScreenshotSkill
from jarvis.skills.system_info import SystemInfoSkill
from jarvis.skills.web_search import WebSearchSkill
from jarvis.skills.wikipedia_search import WikipediaSearchSkill


# ---- system_info -------------------------------------------------------------------------
def test_system_info_cpu_and_time():
    skill = SystemInfoSkill()
    assert "CPU:" in skill.execute("cpu_usage", {})
    assert skill.execute("current_time", {}).startswith("It's ")
    assert "GB free" in skill.execute("disk_usage", {})


def test_system_info_weather_for_city():
    geo = MagicMock(json=lambda: {"results": [{"latitude": 23.8, "longitude": 90.4, "name": "Dhaka", "country": "Bangladesh"}]})
    fc = MagicMock(json=lambda: {"current": {"temperature_2m": 30, "apparent_temperature": 34,
                                             "relative_humidity_2m": 70, "weather_code": 2, "wind_speed_10m": 9}})
    with patch("jarvis.skills.system_info.requests.get", side_effect=[geo, fc]):
        result = SystemInfoSkill().execute("weather", {"city": "Dhaka"})
    assert result.startswith("Dhaka, Bangladesh: partly cloudy, 30°C")


def test_system_info_weather_failure_is_reported():
    with patch("jarvis.skills.system_info.requests.get", side_effect=OSError("offline")):
        assert "Weather unavailable" in SystemInfoSkill().execute("weather", {})


# ---- screenshot --------------------------------------------------------------------------
def test_screenshot_saves(tmp_path):
    target = tmp_path / "sub" / "shot.png"
    with patch("jarvis.skills.screenshot.pyautogui") as gui:
        result = ScreenshotSkill().execute("take_screenshot", {"path": str(target)})
    gui.screenshot.return_value.save.assert_called_once_with(str(target))
    assert str(target) in result
    assert target.parent.is_dir()


# ---- pc_control --------------------------------------------------------------------------
def test_pc_control_run_command():
    assert "hello" in PCControlSkill().execute("run_command", {"command": "echo hello"})


def test_pc_control_list_and_read(tmp_path):
    (tmp_path / "a.txt").write_text("content!", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    skill = PCControlSkill()
    listing = skill.execute("list_directory", {"path": str(tmp_path)})
    assert listing.splitlines()[0].startswith("folder") and "a.txt" in listing
    assert skill.execute("read_file", {"path": str(tmp_path / "a.txt")}) == "content!"
    assert "Error" in skill.execute("read_file", {"path": str(tmp_path / "missing.txt")})


def test_pc_control_open_app_uses_popen():
    with patch("jarvis.skills.pc_control.subprocess.Popen") as popen:
        assert PCControlSkill().execute("open_application", {"app_name": "notepad"}) == "Opened notepad."
    popen.assert_called_once()


def test_risky_tools_require_confirmation():
    assert next(t for t in PCControlSkill.tools if t.name == "run_command").confirm
    assert next(t for t in EmailSenderSkill.tools if t.name == "send_email").confirm
    assert next(t for t in CodeHelperSkill.tools if t.name == "write_file").confirm


# ---- web_search --------------------------------------------------------------------------
DDG_HTML = """
<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2F">Python.org</a>
<a class="result__snippet">The official home of Python.</a></div>
"""


def test_web_search_parses_results():
    resp = MagicMock(text=DDG_HTML)
    with patch("jarvis.skills.web_search.requests.post", return_value=resp):
        result = WebSearchSkill().execute("search", {"query": "python"})
    assert "1. Python.org" in result
    assert "https://python.org/" in result
    assert "official home" in result


def test_web_read_page_strips_scripts():
    resp = MagicMock(text="<html><body><script>x()</script><main>Hello   world</main></body></html>")
    with patch("jarvis.skills.web_search.requests.get", return_value=resp):
        assert WebSearchSkill().execute("read_page", {"url": "https://x"}) == "Hello world"


def test_web_open_url():
    with patch("jarvis.skills.web_search.webbrowser.open") as wb:
        WebSearchSkill().execute("open_url", {"url": "https://example.com"})
    wb.assert_called_once_with("https://example.com")


# ---- wikipedia ---------------------------------------------------------------------------
def test_wikipedia_summary():
    with patch("jarvis.skills.wikipedia_search.wikipedia.summary", return_value="Python is a language."):
        assert WikipediaSearchSkill().execute("search", {"query": "Python"}) == "Python is a language."


def test_wikipedia_disambiguation():
    import wikipedia

    err = wikipedia.exceptions.DisambiguationError("Python", ["Python (language)", "Python (snake)"])
    with patch("jarvis.skills.wikipedia_search.wikipedia.summary", side_effect=err):
        result = WikipediaSearchSkill().execute("search", {"query": "Python"})
    assert "ambiguous" in result and "Python (snake)" in result


# ---- code_helper -------------------------------------------------------------------------
def test_code_helper_read_list_write(tmp_path):
    skill = CodeHelperSkill()
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    assert "1 | print('hi')" in skill.execute("read_code", {"path": str(tmp_path / "main.py")})
    tree = skill.execute("list_project", {"path": str(tmp_path)})
    assert "main.py" in tree and "node_modules" not in tree
    out = tmp_path / "new" / "x.py"
    skill.execute("write_file", {"path": str(out), "content": "x = 1\n"})
    assert out.read_text(encoding="utf-8") == "x = 1\n"


# ---- notes -------------------------------------------------------------------------------
@pytest.fixture
def notes(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "t.db"))
    yield NotesSkill(memory=mem), mem
    mem.close()


def test_notes_round_trip(notes):
    skill, _ = notes
    assert skill.execute("get_notes", {}) == "No notes saved yet."
    skill.execute("save_note", {"content": "Buy groceries"})
    skill.execute("save_note", {"content": "Meeting with John"})
    listing = skill.execute("get_notes", {})
    assert "groceries" in listing and "John" in listing
    assert "John" in skill.execute("search_memory", {"query": "john"})


def test_notes_delete(notes):
    skill, mem = notes
    skill.execute("save_note", {"content": "temp"})
    note_id = mem.get_notes()[0]["id"]
    assert skill.execute("delete_note", {"note_id": note_id}) == "Note deleted."
    assert mem.get_notes() == []


def test_notes_facts(notes):
    skill, _ = notes
    skill.execute("save_fact", {"key": "favorite_color", "value": "blue"})
    assert "favorite_color: blue" in skill.execute("get_facts", {})


def test_notes_without_memory():
    assert "not initialized" in NotesSkill().execute("get_notes", {})


# ---- email -------------------------------------------------------------------------------
def test_email_send():
    skill = EmailSenderSkill(smtp_email="me@test.com", smtp_password="pw")
    with patch("jarvis.skills.email_sender.smtplib.SMTP") as smtp:
        result = skill.execute("send_email", {"to": "a@b.com", "subject": "Hi", "body": "Hello"})
    server = smtp.return_value
    server.login.assert_called_once_with("me@test.com", "pw")
    server.sendmail.assert_called_once()
    server.close.assert_called_once()
    assert result == "Email sent to a@b.com."


def test_email_not_configured():
    result = EmailSenderSkill().execute("send_email", {"to": "a@b.com", "subject": "s", "body": "b"})
    assert "not configured" in result


def test_email_setup_reads_config():
    skill = EmailSenderSkill()
    skill.setup(MagicMock(smtp_email="x@y.com", smtp_password="p"), None)
    assert (skill._email, skill._password) == ("x@y.com", "p")


# ---- media -------------------------------------------------------------------------------
def test_media_play_file(tmp_path):
    song = tmp_path / "song.mp3"
    song.write_bytes(b"fake")
    with patch("jarvis.skills.media._open_with_default_app") as opener:
        assert MediaSkill().execute("play_music", {"path": str(song)}) == "Now playing: song.mp3"
    opener.assert_called_once_with(str(song))


def test_media_play_random_from_folder(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    with patch("jarvis.skills.media._open_with_default_app"):
        assert MediaSkill().execute("play_music", {"path": str(tmp_path)}) == "Now playing: a.mp3"


def test_media_empty_folder(tmp_path):
    assert "No audio files" in MediaSkill().execute("play_music", {"path": str(tmp_path)})


def test_media_search_youtube():
    with patch("jarvis.skills.media.webbrowser.open") as wb:
        MediaSkill().execute("search_youtube", {"query": "lofi beats"})
    assert wb.call_args.args[0].endswith("search_query=lofi+beats")
