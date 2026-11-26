"""Text-to-speech.

Windows: the built-in System.Speech engine via PowerShell (no Python COM deps).
Elsewhere: pyttsx3.
"""
import re
import subprocess
import sys

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.voice")

_PS_SCRIPT = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Rate = {rate};"
    "{select}"
    "$s.Speak([Console]::In.ReadToEnd())"
)


def _clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    text = re.sub(r"https?://\S+", "a link", text)
    return re.sub(r"[*_#`>|]", "", text).strip()


def _sapi_rate(wpm: int) -> int:
    # SAPI rate is -10..10 where 0 is roughly 175 words per minute.
    return max(-10, min(10, round((wpm - 175) / 20)))


class Speaker:
    def __init__(self, voice: str = "", rate: int = 185):
        self._process = None
        if sys.platform == "win32":
            select = ""
            if voice:
                safe = voice.replace("'", "")
                select = (
                    "$v = $s.GetInstalledVoices() | % {{ $_.VoiceInfo.Name }} | "
                    f"? {{ $_ -like '*{safe}*' }} | Select-Object -First 1;"
                    "if ($v) {{ $s.SelectVoice($v) }};"
                ).replace("{{", "{").replace("}}", "}")
            self._script = _PS_SCRIPT.format(rate=_sapi_rate(rate), select=select)
            self._engine = None
        else:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", rate)

    def say(self, text: str) -> None:
        text = _clean_for_speech(text)
        if not text:
            return
        try:
            if self._engine is not None:
                self._engine.say(text)
                self._engine.runAndWait()
                return
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", self._script],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._process.communicate(text.encode("utf-8"), timeout=300)
        except KeyboardInterrupt:
            self.stop()
            raise
        except Exception as e:  # speech must never crash the assistant
            logger.warning(f"TTS failed: {e}")
        finally:
            self._process = None

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.kill()
