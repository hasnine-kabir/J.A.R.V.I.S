"""Web UI: FastAPI + a WebSocket that streams Jarvis's replies to the browser.

Run with `python -m jarvis --web`. One `JarvisService` owns the orchestrator,
voice and hands-free loop; every open browser tab receives the same events.

Browser -> server  {"type": "chat", "text"} | {"type": "listen"} | {"type": "handsfree", "on"}
                   {"type": "voice", "on"} | {"type": "stop_speaking"} | {"type": "clear"}
                   {"type": "model", "name"} | {"type": "confirm", "id", "ok"}
Server -> browser  status | user | state | token | tool | done | error | heard | confirm | cleared
"""
import asyncio
import contextlib
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jarvis.utils.errors import friendly_error
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.web")

STATIC = Path(__file__).parent / "static"
VERSION = "2.1"


class Hub:
    """Fan-out of events to every connected browser tab, callable from any thread."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[asyncio.Queue] = set()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._clients.add(q)
        return q

    def disconnect(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    def broadcast(self, event: dict) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        for q in list(self._clients):
            self._loop.call_soon_threadsafe(q.put_nowait, event)


class JarvisService:
    """Everything the UI can ask Jarvis to do. Methods block; call them from worker threads."""

    def __init__(self, orchestrator, config, speaker=None, listener=None, hub: Hub | None = None):
        from jarvis.voice.stream import SpeechQueue

        self.orch = orchestrator
        self.config = config
        self.speaker = speaker
        self.listener = listener
        self.hub = hub or Hub()
        self.voice_replies = bool(config.get("voice.enabled", False)) and speaker is not None
        self.handsfree = False
        self._turn_lock = threading.Lock()
        self._mic_lock = threading.Lock()
        self._hf_stop = threading.Event()
        self._pending: dict[str, tuple[threading.Event, list]] = {}
        self._turn = None
        self._state = "idle"
        self.speech = SpeechQueue(speaker, self._speech_state) if speaker else None
        orchestrator.set_action_callback(self._on_action)
        orchestrator.set_confirm_callback(self._confirm)

    # ---- state ---------------------------------------------------------------------------
    def emit(self, event: dict) -> None:
        self.hub.broadcast(event)

    def set_state(self, state: str) -> None:
        """idle | sleeping | listening | thinking | speaking  (drives the orb in the UI)."""
        self._state = state
        self.emit({"type": "state", "state": state})

    def _speech_state(self, state: str) -> None:
        if state == "speaking":
            self.set_state("speaking")
        elif self._state == "speaking":
            self.set_state("sleeping" if self.handsfree else "idle")

    def status(self) -> dict:
        brain = self.orch._brain
        pool = getattr(brain, "keys", None)
        skills = [
            {"name": s.name, "description": s.description, "tools": [t.name for t in s.tools]}
            for s in self.orch._skill_registry.get_all_skills()
        ]
        return {
            "type": "status",
            "version": VERSION,
            "user": self.config.get("user.name", "Sir"),
            "model": getattr(brain, "model", ""),
            "models": getattr(brain, "models", [getattr(brain, "model", "")]),
            "keys": pool.status() if pool else [],
            "skills": skills,
            "tts": self.speaker is not None,
            "mic": self.listener is not None,
            "voice_replies": self.voice_replies,
            "handsfree": self.handsfree,
            "confirm_actions": bool(self.config.get("safety.confirm_actions", True)),
            "wake_word": (self.config.get("voice.wake_words", ["jarvis"]) or ["jarvis"])[0],
            "state": self._state,
        }

    def history(self) -> list[dict]:
        return [{"role": m.role, "text": m.content}
                for m in self.orch._short_term_memory.get_messages()]

    # ---- orchestrator callbacks ------------------------------------------------------------
    def _on_action(self, name: str, status: str) -> None:
        self.emit({"type": "tool", "turn": self._turn, "name": name, "status": status})

    def _confirm(self, name: str, args: dict) -> bool:
        cid = uuid.uuid4().hex[:8]
        done, answer = threading.Event(), [False]
        self._pending[cid] = (done, answer)
        self.emit({"type": "confirm", "id": cid, "name": name, "args": args})
        done.wait(timeout=120)
        self._pending.pop(cid, None)
        self.emit({"type": "confirm_closed", "id": cid})
        return bool(answer[0])

    def answer_confirm(self, cid: str, ok: bool) -> None:
        pending = self._pending.get(cid)
        if pending:
            pending[1][0] = bool(ok)
            pending[0].set()

    # ---- chat ------------------------------------------------------------------------------
    def chat(self, text: str, source: str = "text") -> str:
        """Run one turn, streaming tokens to the UI. Voice turns are always answered aloud."""
        text = text.strip()
        if not text:
            return ""
        with self._turn_lock:
            turn = self._turn = uuid.uuid4().hex[:8]
            self.emit({"type": "user", "turn": turn, "text": text, "source": source})
            self.set_state("thinking")
            speak = self.speech is not None and (self.voice_replies or source == "voice")
            if speak:
                self.speech.stop()
            streamed: list[str] = []

            def on_text(fragment: str) -> None:
                streamed.append(fragment)
                self.emit({"type": "token", "turn": turn, "text": fragment})
                if speak:
                    self.speech.feed(fragment)

            started = time.perf_counter()
            error = False
            try:
                reply = self.orch.process(text, on_text=on_text)
            except Exception as e:
                logger.exception("web chat failed")
                reply, error = friendly_error(e, getattr(self.orch._brain, "model", "")), True
            elapsed = int((time.perf_counter() - started) * 1000)
            self.emit({"type": "done", "turn": turn, "text": reply, "ms": elapsed, "error": error,
                       "model": getattr(self.orch._brain, "model", "")})
            if speak:
                if "".join(streamed).strip() == reply.strip():
                    self.speech.flush()
                else:  # nothing (or something else) was streamed: speak the final answer
                    self.speech.stop()
                    self.speech.say(reply)
            if not (speak and self.speech.speaking):
                self.set_state("sleeping" if self.handsfree else "idle")
            self._turn = None
            return reply

    def stop_speaking(self) -> None:
        if self.speech:
            self.speech.stop()

    def clear(self) -> None:
        self.orch._short_term_memory.clear()
        self.emit({"type": "cleared"})

    def set_model(self, name: str) -> None:
        brain = self.orch._brain
        if name and hasattr(brain, "set_model"):
            brain.set_model(name)
        self.emit(self.status())

    def set_voice(self, on: bool) -> None:
        self.voice_replies = bool(on) and self.speaker is not None
        if not self.voice_replies:
            self.stop_speaking()
        self.emit(self.status())

    # ---- microphone ------------------------------------------------------------------------
    def listen_once(self) -> None:
        """Push-to-talk: record one request and answer it out loud."""
        if not self.listener or self.handsfree or not self._mic_lock.acquire(blocking=False):
            return
        try:
            self.stop_speaking()
            self.set_state("listening")
            try:
                heard = self.listener.listen(wait_seconds=8)
            except Exception as e:
                self.emit({"type": "error", "text": f"Microphone problem: {e}"})
                heard = ""
            self.emit({"type": "heard", "text": heard, "ignored": False})
        finally:
            self._mic_lock.release()
        if heard:
            self.chat(heard, source="voice")
        else:
            self.set_state("idle")

    def start_handsfree(self) -> None:
        if self.handsfree or not (self.listener and self.speech):
            self.emit(self.status())
            return
        self.handsfree = True
        self._hf_stop.clear()
        threading.Thread(target=self._handsfree_loop, name="jarvis-handsfree", daemon=True).start()
        self.emit(self.status())

    def stop_handsfree(self) -> None:
        self._hf_stop.set()
        self.handsfree = False
        self.emit(self.status())

    def _say_and_wait(self, text: str) -> None:
        self.emit({"type": "notice", "text": text})
        self.speech.say(text)
        self.speech.wait(30)

    def _handsfree_loop(self) -> None:
        from jarvis.ui.handsfree import CANCEL_PHRASES, STOP_PHRASES, _normalize, split_wake_word

        wake_words = list(self.config.get("voice.wake_words", ["jarvis"]) or ["jarvis"])
        follow_up = float(self.config.get("voice.follow_up_seconds", 10))
        awake_until = 0.0
        with self._mic_lock:
            try:
                while not self._hf_stop.is_set():
                    awake = time.monotonic() < awake_until
                    self.set_state("listening" if awake else "sleeping")
                    # Short windows so switching hands-free off takes effect quickly.
                    window = min(3.0, max(1.0, awake_until - time.monotonic())) if awake else 3.0
                    try:
                        heard = self.listener.listen(wait_seconds=window)
                    except ConnectionError as e:
                        self.emit({"type": "error", "text": f"{e}. Retrying…"})
                        self._hf_stop.wait(5)
                        continue
                    if self._hf_stop.is_set():
                        break
                    if not heard:
                        if awake and time.monotonic() >= awake_until:
                            awake_until = 0.0
                        continue
                    woken, command = split_wake_word(heard, wake_words)
                    if not woken and not awake:
                        self.emit({"type": "heard", "text": heard, "ignored": True})
                        continue
                    plain = _normalize(command)
                    if plain in STOP_PHRASES:
                        self._say_and_wait("Hands-free mode off.")
                        break
                    if plain in CANCEL_PHRASES:
                        self._say_and_wait("Alright.")
                        awake_until = 0.0
                        continue
                    if not command:
                        self._say_and_wait("Yes?")
                        awake_until = time.monotonic() + follow_up
                        continue
                    self.chat(command, source="voice")
                    self.speech.wait(120)  # never listen while talking (it would hear itself)
                    awake_until = time.monotonic() + follow_up
            except Exception:
                logger.exception("hands-free loop crashed")
            finally:
                self.handsfree = False
                self.set_state("idle")
                self.emit(self.status())


def vitals() -> dict:
    import psutil

    mem = psutil.virtual_memory()
    data = {"cpu": psutil.cpu_percent(interval=None), "ram": mem.percent,
            "ram_total_gb": round(mem.total / 2**30, 1)}
    with contextlib.suppress(Exception):
        battery = psutil.sensors_battery()
        if battery:
            data["battery"] = round(battery.percent)
            data["plugged"] = bool(battery.power_plugged)
    return data


def create_app(service: JarvisService, on_shutdown=None) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_app):
        service.hub.attach(asyncio.get_running_loop())
        yield
        service.stop_handsfree()
        if on_shutdown:
            await asyncio.to_thread(on_shutdown)

    app = FastAPI(title="J.A.R.V.I.S.", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/status")
    async def get_status():
        return service.status()

    @app.get("/api/history")
    async def get_history():
        return service.history()

    @app.get("/api/vitals")
    async def get_vitals():
        return await asyncio.to_thread(vitals)

    @app.get("/api/memory")
    async def get_memory():
        mem = service.orch._long_term_memory
        return {"facts": mem.get_facts(), "notes": mem.get_notes()}

    @app.delete("/api/notes/{note_id}")
    async def delete_note(note_id: int):
        return {"ok": service.orch._long_term_memory.delete_note(note_id)}

    @app.delete("/api/facts/{key}")
    async def delete_fact(key: str):
        return {"ok": service.orch._long_term_memory.delete_fact(key)}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        queue = service.hub.connect()
        await socket.send_json(service.status())

        async def sender():
            while True:
                await socket.send_json(await queue.get())

        send_task = asyncio.create_task(sender())
        try:
            while True:
                msg = await socket.receive_json()
                handle(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            send_task.cancel()
            service.hub.disconnect(queue)

    def background(fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def handle(msg: dict) -> None:
        kind = msg.get("type")
        if kind == "chat":
            background(service.chat, str(msg.get("text", "")))
        elif kind == "confirm":
            service.answer_confirm(str(msg.get("id")), bool(msg.get("ok")))
        elif kind == "listen":
            background(service.listen_once)
        elif kind == "handsfree":
            background(service.start_handsfree if msg.get("on") else service.stop_handsfree)
        elif kind == "voice":
            service.set_voice(bool(msg.get("on")))
        elif kind == "stop_speaking":
            service.stop_speaking()
        elif kind == "clear":
            service.clear()
        elif kind == "model":
            background(service.set_model, str(msg.get("name", "")))
        elif kind == "ping":
            service.emit({"type": "pong"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.exception_handler(Exception)(
        lambda _req, exc: JSONResponse({"error": str(exc)}, status_code=500)
    )
    return app


def run(orchestrator, config, speaker=None, listener=None) -> None:
    import uvicorn

    host = config.get("web.host", "127.0.0.1")
    port = int(config.get("web.port", 8765))
    service = JarvisService(orchestrator, config, speaker, listener)

    def shutdown():
        service.stop_speaking()
        orchestrator.shutdown()
        if speaker:
            speaker.close()

    app = create_app(service, on_shutdown=shutdown)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    print(f"J.A.R.V.I.S. web UI running at {url}  (Ctrl+C to stop)")
    if config.get("web.open_browser", True):
        import webbrowser

        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning", ws_ping_interval=20)
