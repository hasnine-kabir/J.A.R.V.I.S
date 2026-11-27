"""Text-to-speech.

Windows: one long-running PowerShell process using the built-in System.Speech
engine (no Python COM dependencies, no per-sentence startup delay).
Elsewhere: pyttsx3.
"""
import re
import subprocess
import sys

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.voice")

DONE = "__jarvis_spoken__"

_PS_SCRIPT = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8;"
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Rate = {rate};"
    "{select}"
    "while (($line = [Console]::In.ReadLine()) -ne $null) {{"
    "  if ($line.Trim()) {{ $s.Speak($line) }};"
    f"  [Console]::Out.WriteLine('{DONE}'); [Console]::Out.Flush()"
    "}}"
)


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[*_#`>|]", "", text)
    return " ".join(text.split())  # one line: the speech process reads line by line


def _sapi_rate(wpm: int) -> int:
    # SAPI rate is -10..10 where 0 is roughly 175 words per minute.
    return max(-10, min(10, round((wpm - 175) / 20)))


class Speaker:
    def __init__(self, voice: str = "", rate: int = 185):
        self._proc = None
        self._engine = None
        if sys.platform == "win32":
            select = ""
            if voice:
                safe = voice.replace("'", "")
                select = (
                    "$v = $s.GetInstalledVoices() | % { $_.VoiceInfo.Name } | "
                    f"? {{ $_ -like '*{safe}*' }} | Select-Object -First 1;"
                    "if ($v) { $s.SelectVoice($v) };"
                ).replace("{", "{{").replace("}", "}}")
            self._script = _PS_SCRIPT.format(rate=_sapi_rate(rate), select=select)
            self._start()
        else:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", rate)

    def _start(self) -> None:
        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", self._script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def say(self, text: str) -> None:
        """Speak and block until finished. Ctrl+C stops speaking."""
        text = clean_for_speech(text)
        if not text:
            return
        try:
            if self._engine is not None:
                self._engine.say(text)
                self._engine.runAndWait()
                return
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            self._proc.stdin.write((text + "\n").encode("utf-8"))
            self._proc.stdin.flush()
            while True:
                line = self._proc.stdout.readline()
                if not line or DONE in line.decode("utf-8", "replace"):
                    break
        except KeyboardInterrupt:
            self.stop()
            raise
        except Exception as e:  # speech must never crash the assistant
            logger.warning(f"TTS failed: {e}")
            self.stop()

    def stop(self) -> None:
        """Cut off speech immediately (the process restarts on the next say())."""
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
        self._proc = None

    def close(self) -> None:
        self.stop()
