"""Microphone speech-to-text.

Records with `sounddevice` (prebuilt wheels, no PyAudio needed). A simple
energy-based voice detector waits for speech, records until a short silence,
then the clip is transcribed with Google's free speech recognition.
"""
import time

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms


class Listener:
    def __init__(self, language: str = "en-US", max_seconds: float = 15.0, silence_seconds: float = 1.0,
                 min_threshold: float = 200.0):
        import sounddevice  # noqa: F401  (fail fast if missing)
        import speech_recognition  # noqa: F401

        self._language = language
        self._max_blocks = int(max_seconds * SAMPLE_RATE / BLOCK)
        self._silence_blocks = int(silence_seconds * SAMPLE_RATE / BLOCK)
        self._noise_floor: float | None = None
        self._min_threshold = float(min_threshold)

    @staticmethod
    def _energy(block: np.ndarray) -> float:
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    def _record(self, wait_seconds: float | None) -> bytes:
        """Wait up to `wait_seconds` (None = forever) for speech, then record one utterance."""
        import sounddevice as sd

        pre_roll: list[np.ndarray] = []  # keep ~300 ms before speech so first syllables aren't cut
        frames: list[np.ndarray] = []
        silent = 0
        deadline = None if wait_seconds is None else time.monotonic() + wait_seconds
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK) as stream:
            if self._noise_floor is None:  # calibrate once on ~0.5 s of room noise
                samples = [self._energy(stream.read(BLOCK)[0]) for _ in range(5)]
                self._noise_floor = float(np.median(samples))
            threshold = self.threshold
            while True:
                block, _ = stream.read(BLOCK)
                loud = self._energy(block) > threshold
                if not frames:
                    if loud:
                        frames = pre_roll + [block.copy()]
                        continue
                    pre_roll = (pre_roll + [block.copy()])[-3:]
                    if deadline is not None and time.monotonic() > deadline:
                        return b""
                    continue
                frames.append(block.copy())
                silent = 0 if loud else silent + 1
                if silent >= self._silence_blocks or len(frames) >= self._max_blocks:
                    break
        speech_blocks = len(frames) - silent
        if speech_blocks < 3:  # < 300 ms: a click or bump, not speech
            return b""
        return np.concatenate(frames).tobytes()

    @property
    def threshold(self) -> float:
        return max(self._min_threshold, (self._noise_floor or 0.0) * 3.0)

    def measure(self, seconds: float = 4.0) -> tuple[float, float]:
        """Return (background level, loudest level) over `seconds` - for the mic test."""
        import sounddevice as sd

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK) as stream:
            levels = [self._energy(stream.read(BLOCK)[0]) for _ in range(int(seconds * 10))]
        return float(np.percentile(levels, 20)), float(max(levels))

    def listen(self, wait_seconds: float | None = 8.0) -> str:
        """Record one utterance and return the transcript ('' if nothing understood)."""
        import speech_recognition as sr

        raw = self._record(wait_seconds)
        if not raw:
            return ""
        audio = sr.AudioData(raw, SAMPLE_RATE, 2)
        try:
            return sr.Recognizer().recognize_google(audio, language=self._language)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise ConnectionError(f"speech recognition service unreachable: {e}") from e
