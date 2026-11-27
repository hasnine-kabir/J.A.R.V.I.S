"""Web UI server: static files, REST endpoints and the streaming WebSocket."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from jarvis.core.brain import BrainResponse, ToolCall
from jarvis.core.memory import LongTermMemory, ShortTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.skill_registry import SkillRegistry
from jarvis.web.server import JarvisService, create_app


class StreamingBrain:
    model = "test-model"
    models = ["test-model", "backup"]

    def __init__(self):
        self.keys = MagicMock()
        self.keys.status.return_value = ["key 1 (…abcd): active"]
        self.switched = None

    def think(self, messages, tools, system_prompt, on_text=None):
        if "cpu" in messages[-1].content:
            return BrainResponse(None, [ToolCall("system_info__current_time", {})])
        for piece in ["Hello ", "from ", "Jarvis."]:
            if on_text:
                on_text(piece)
        return BrainResponse("Hello from Jarvis.")

    def send_tool_results(self, results, on_text=None):
        return BrainResponse(f"Tool said: {results[0]['output'][:5]}")

    def set_model(self, name):
        self.switched = name


@pytest.fixture
def client(tmp_path):
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {
        "user.name": "Tester", "safety.confirm_actions": False}.get(k, d)
    registry = SkillRegistry()
    registry.discover()
    memory = LongTermMemory(str(tmp_path / "m.db"))
    memory.save_fact("color", "blue")
    memory.save_note("buy milk")
    brain = StreamingBrain()
    orch = Orchestrator(brain, config, registry, ShortTermMemory(20), memory)
    service = JarvisService(orch, config)
    with TestClient(create_app(service)) as c:
        c.brain = brain
        yield c


def _until(ws, kind):
    events = []
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["type"] == kind:
            return events


def test_index_and_static(client):
    page = client.get("/")
    assert page.status_code == 200 and "J.A.R.V.I.S." in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200


def test_status_and_vitals(client):
    status = client.get("/api/status").json()
    assert status["user"] == "Tester"
    assert status["model"] == "test-model"
    assert status["keys"] == ["key 1 (…abcd): active"]
    assert any(s["name"] == "system_info" for s in status["skills"])
    vitals = client.get("/api/vitals").json()
    assert 0 <= vitals["cpu"] <= 100 and 0 <= vitals["ram"] <= 100


def test_memory_endpoints(client):
    mem = client.get("/api/memory").json()
    assert mem["facts"] == [{"key": "color", "value": "blue"}]
    note_id = mem["notes"][0]["id"]
    assert client.delete(f"/api/notes/{note_id}").json() == {"ok": True}
    assert client.delete("/api/facts/color").json() == {"ok": True}
    assert client.get("/api/memory").json() == {"facts": [], "notes": []}


def test_chat_streams_tokens_then_done(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "status"
        ws.send_json({"type": "chat", "text": "hello"})
        events = _until(ws, "done")
    kinds = [e["type"] for e in events]
    assert kinds[0] == "user"
    tokens = "".join(e["text"] for e in events if e["type"] == "token")
    assert tokens == "Hello from Jarvis."
    done = events[-1]
    assert done["text"] == "Hello from Jarvis." and done["error"] is False and done["ms"] >= 0
    history = client.get("/api/history").json()
    assert history == [{"role": "user", "text": "hello"}, {"role": "assistant", "text": "Hello from Jarvis."}]


def test_tool_events_are_reported(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "text": "check cpu"})
        events = _until(ws, "done")
    tools = [(e["name"], e["status"]) for e in events if e["type"] == "tool"]
    assert tools == [("system_info__current_time", "running"), ("system_info__current_time", "done")]
    assert events[-1]["text"].startswith("Tool said:")


def test_model_switch_and_clear(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "model", "name": "backup"})
        _until(ws, "status")
        assert client.brain.switched == "backup"
        ws.send_json({"type": "clear"})
        _until(ws, "cleared")
