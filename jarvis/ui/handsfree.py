"""Hands-free voice mode: always listening, wake word, spoken replies.

Flow:
  - Listen continuously. Utterances that don't contain the wake word are ignored.
  - "Jarvis, what's the weather?"  -> answers immediately.
  - "Jarvis."                       -> "Yes?" and listens for the request.
  - After each reply there is a follow-up window where no wake word is needed.
  - "Goodbye" / "stop listening" / Ctrl+C ends the session.
Speech output and listening never overlap, so Jarvis doesn't hear itself.
"""
import re
import time

from rich.console import Console

from jarvis.utils.errors import friendly_error
from jarvis.voice.stream import SpeechQueue
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.handsfree")

# Common mis-hearings of "Jarvis" by speech recognition.
DEFAULT_ALIASES = ["jarvis", "jarvi", "jarves", "jervis", "javis", "jarvin", "charvis", "jarviz"]
STOP_PHRASES = {"goodbye", "good bye", "bye", "stop listening", "exit", "quit",
                "go to sleep", "sleep", "shut down", "turn off"}
CANCEL_PHRASES = {"never mind", "nevermind", "cancel", "nothing", "forget it"}


def split_wake_word(text: str, wake_words: list[str]) -> tuple[bool, str]:
    """Return (woken, command). The command is the text with the wake word removed."""
    words = {w.lower() for w in wake_words} | (
        set(DEFAULT_ALIASES) if any(w.lower() == "jarvis" for w in wake_words) else set()
    )
    alt = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    pattern = re.compile(rf"\b(?:(?:hey|hi|ok|okay|yo)\s+)?(?:{alt})(?:'s)?\b[\s,.!?:;-]*", re.I)
    match = pattern.search(text)
    if not match:
        return False, text.strip()
    command = (text[: match.start()] + " " + text[match.end():]).strip(" ,.!?;:-")
    return True, " ".join(command.split())


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


class HandsFreeSession:
    def __init__(self, orchestrator, config, speaker, listener, console: Console | None = None):
        self._orch = orchestrator
        self._config = config
        self._speaker = speaker
        self._listener = listener
        self._console = console or Console()
        self._wake_words = list(config.get("voice.wake_words", ["jarvis"]) or ["jarvis"])
        self._follow_up = float(config.get("voice.follow_up_seconds", 10))
        self._name = config.get("user.name", "Sir")
        self._speech = SpeechQueue(speaker) if speaker else None

    # ---- helpers --------------------------------------------------------------------------
    def say(self, text: str) -> None:
        self._console.print(f"[bold cyan]JARVIS >[/] {text}")
        if self._speaker:
            self._speaker.say(text)

    def _confirm_by_voice(self, action_name: str, args: dict) -> bool:
        what = action_name.split("__")[-1].replace("_", " ")
        self.say(f"Should I {what}? Say yes or no.")
        answer = _normalize(self._listener.listen(wait_seconds=8))
        self._console.print(f"[dim]heard: {answer or '(nothing)'}[/]")
        return answer.startswith(("yes", "yeah", "yep", "sure", "do it", "go ahead", "ok", "okay"))

    def _on_action(self, action_name: str, status: str) -> None:
        if status == "running":
            self._console.print(f"  [yellow]⚙ {action_name.replace('__', ' → ')}[/]")

    def _hear(self, wait_seconds: float | None) -> str:
        label = "Listening…" if wait_seconds is not None else f"Say \"{self._wake_words[0].title()}\"…"
        with self._console.status(f"[cyan]{label}[/]"):
            return self._listener.listen(wait_seconds=wait_seconds)

    def _answer(self, command: str) -> None:
        """Think and talk at the same time: speech starts with the first finished sentence."""
        streamed: list[str] = []

        def on_text(fragment: str) -> None:
            streamed.append(fragment)
            if self._speech:
                self._speech.feed(fragment)

        try:
            with self._console.status("[cyan]Thinking…[/]"):
                reply = self._orch.process(command, on_text=on_text)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            logger.exception("hands-free process() failed")
            reply = friendly_error(e, self._config.get("llm.model", ""))
        self._console.print(f"[bold cyan]JARVIS >[/] {reply}")
        if not self._speech:
            return
        if streamed and "".join(streamed).strip() == reply.strip():
            self._speech.flush()
        else:  # nothing streamed (or an error): speak the final text
            self._speech.stop()
            self._speech.say(reply)
        self._speech.wait()  # never listen while talking, or Jarvis hears itself

    # ---- main loop ------------------------------------------------------------------------
    def run(self) -> None:
        self._orch.set_action_callback(self._on_action)
        self._orch.set_confirm_callback(self._confirm_by_voice)
        self._console.rule("[bold cyan]Hands-free mode[/]")
        self._console.print(
            f"[dim]Say \"{self._wake_words[0].title()}\" followed by your request. "
            "Say \"goodbye\" or press Ctrl+C to stop.[/]"
        )
        self.say(f"Hands-free mode is on, {self._name}. Just say my name when you need me.")

        awake_until = 0.0
        while True:
            awake = time.monotonic() < awake_until
            try:
                heard = self._hear(max(1.0, awake_until - time.monotonic()) if awake else None)
            except KeyboardInterrupt:
                break
            except ConnectionError as e:
                self._console.print(f"[red]{e}. Retrying in 5 s…[/]")
                time.sleep(5)
                continue
            if not heard:
                if awake and time.monotonic() >= awake_until:
                    self._console.print("[dim](going back to sleep — say my name to wake me)[/]")
                    awake_until = 0.0
                continue

            woken, command = split_wake_word(heard, self._wake_words)
            if not woken and not awake:
                self._console.print(f"[dim]ignored: {heard}[/]")
                continue
            self._console.print(f"[bold green]YOU >[/] {heard}")

            plain = _normalize(command)
            if plain in STOP_PHRASES:
                break
            if plain in CANCEL_PHRASES:
                self.say("Alright.")
                awake_until = 0.0
                continue
            if not command:
                self.say("Yes?")
                awake_until = time.monotonic() + self._follow_up
                continue

            try:
                self._answer(command)
            except KeyboardInterrupt:
                if self._speech:
                    self._speech.stop()
                self._console.print("[dim](stopped)[/]")
            awake_until = time.monotonic() + self._follow_up

        try:
            self.say(f"Hands-free mode off. Goodbye, {self._name}.")
        except KeyboardInterrupt:
            pass
