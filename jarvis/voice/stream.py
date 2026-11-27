"""Speak streamed text sentence by sentence while the rest is still being generated."""
import queue
import re
import threading

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.voice")

_SENTENCE = re.compile(r"(.+?[.!?;:])(?=\s)|(.+?\n)", re.S)


class SpeechQueue:
    def __init__(self, speaker, on_state=None):
        self._speaker = speaker
        self._on_state = on_state or (lambda state: None)
        self._queue: queue.Queue = queue.Queue()
        self._buffer = ""
        self._generation = 0
        self._busy = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        threading.Thread(target=self._worker, name="jarvis-speech", daemon=True).start()

    # ---- producer side ----------------------------------------------------------------------
    def feed(self, fragment: str) -> None:
        """Add streamed text; complete sentences are queued for speaking right away."""
        self._buffer += fragment
        speakable, self._buffer = self._split(self._buffer)
        for sentence in speakable:
            self._put(sentence)

    def flush(self) -> None:
        """Speak whatever is left in the buffer (end of the reply)."""
        rest, self._buffer = self._buffer, ""
        rest = re.sub(r"```.*", " ", rest, flags=re.S)  # an unfinished code block
        self._put(rest)

    def say(self, text: str) -> None:
        self._buffer = ""
        self.feed(text)
        self.flush()

    def stop(self) -> None:
        """Drop everything queued and cut off the current sentence."""
        self._generation += 1
        self._buffer = ""
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._speaker.stop()
        if not self._busy.is_set():
            self._idle.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until everything queued has been spoken."""
        return self._idle.wait(timeout)

    @property
    def speaking(self) -> bool:
        return not self._idle.is_set()

    # ---- internals --------------------------------------------------------------------------
    @staticmethod
    def _split(text: str) -> tuple[list[str], str]:
        """Return (complete sentences outside code blocks, remainder to keep buffering)."""
        text = re.sub(r"```.*?```", " (code omitted). ", text, flags=re.S)
        fence = text.find("```")
        tail = ""
        if fence != -1:  # a code block is still streaming: hold it back
            text, tail = text[:fence], text[fence:]
        sentences, end = [], 0
        for m in _SENTENCE.finditer(text):
            sentences.append(m.group(0))
            end = m.end()
        return sentences, text[end:] + tail

    def _put(self, text: str) -> None:
        if text and text.strip():
            self._idle.clear()
            self._queue.put((self._generation, text.strip()))

    def _worker(self) -> None:
        while True:
            generation, text = self._queue.get()
            if generation != self._generation:
                self._finish_if_empty()
                continue
            self._busy.set()
            self._on_state("speaking")
            try:
                self._speaker.say(text)
            except Exception as e:  # speech must never take the assistant down
                logger.warning(f"speech failed: {e}")
            finally:
                self._busy.clear()
            self._finish_if_empty()

    def _finish_if_empty(self) -> None:
        if self._queue.empty() and not self._busy.is_set():
            self._idle.set()
            self._on_state("idle")
