"""Microphone speech-to-text.

Records with `sounddevice` (prebuilt wheels, no PyAudio needed), stops after a
short silence, then transcribes with Google's free speech recognition.
"""
import numpy as np

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms


class Listener:
    def __init__(self, language: str = "en-US", max_seconds: float = 15.0, silence_seconds: float = 1.2):
        import sounddevice  # noqa: F401  (fail fast if missing)
        import speech_recognition  # noqa: F401

        self._language = language
        self._max_blocks = int(max_seconds * SAMPLE_RATE / BLOCK)
        self._silence_blocks = int(silence_seconds * SAMPLE_RATE / BLOCK)

    def _record(self) -> bytes:
        import sounddevice as sd

        frames: list[np.ndarray] = []
        noise_floor = None
        started = False
        silent = 0
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK) as stream:
            for i in range(self._max_blocks):
                block, _ = stream.read(BLOCK)
                energy = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
                if i < 3:  # calibrate on the first 300 ms
                    noise_floor = energy if noise_floor is None else max(noise_floor, energy)
                    continue
                threshold = max(300.0, (noise_floor or 0) * 2.5)
                if energy > threshold:
                    started, silent = True, 0
                elif started:
                    silent += 1
                if started:
                    frames.append(block.copy())
                    if silent >= self._silence_blocks:
                        break
                elif i > 8 * SAMPLE_RATE / BLOCK:  # nothing said within 8 s
                    break
        return np.concatenate(frames).tobytes() if frames else b""

    def listen(self) -> str:
        """Record one utterance and return the transcript ('' if nothing understood)."""
        import speech_recognition as sr

        raw = self._record()
        if not raw:
            return ""
        audio = sr.AudioData(raw, SAMPLE_RATE, 2)
        try:
            return sr.Recognizer().recognize_google(audio, language=self._language)
        except sr.UnknownValueError:
            return ""
