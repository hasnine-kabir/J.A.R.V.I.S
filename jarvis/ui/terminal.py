import datetime
import json

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from jarvis.config import PROJECT_ROOT, Config
from jarvis.core.orchestrator import Orchestrator
from jarvis.utils.errors import friendly_error
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.ui")

custom_theme = Theme({
    "jarvis": "bold cyan",
    "user": "bold green",
    "action": "yellow",
    "error": "bold red",
    "info": "dim",
})

EXIT_WORDS = {"exit", "quit", "goodbye", "bye", "sleep", "/exit", "/quit"}

HELP = """[bold]Just talk to Jarvis in plain English.[/] Examples:
  what's the weather in Dhaka?      open notepad        check my CPU
  remember my exam is on Friday     what do you know about me?
  search the web for the latest Python release and summarize it
  show me the structure of E:/GITHUB/J.A.R.V.I.S

[bold]Commands[/]
  /help           this help
  /voice on|off   speak replies aloud
  /listen         push-to-talk: press Enter on an empty line, then speak
  /handsfree      always listening: say "Jarvis, ..." and it answers out loud
  /notes          show saved notes        /facts   show what Jarvis knows about you
  /clear          forget the current conversation (long-term memory is kept)
  /keys           show your Gemini API keys and which one is in use
  /addkey         add more Gemini API keys (used when one runs out)
  exit            quit"""


class TerminalUI:
    def __init__(self, orchestrator: Orchestrator, config: Config, speaker=None, listener=None):
        self._orchestrator = orchestrator
        self._config = config
        self._console = Console(theme=custom_theme)
        self._session = PromptSession(history=FileHistory(str(PROJECT_ROOT / ".jarvis_history")))
        self._speaker = speaker
        self._listener = listener
        self._voice_on = speaker is not None
        self._listen_mode = False
        self._status = None
        self._live = None
        self._orchestrator.set_action_callback(self._on_action)
        self._orchestrator.set_confirm_callback(self._confirm)

    # ---- callbacks from the orchestrator -------------------------------------------------
    def _on_action(self, action_name: str, status: str) -> None:
        clean_name = action_name.replace("__", " → ")
        if status == "running":
            self._console.print(f"  ⚙ {clean_name}", style="action")
        elif status == "declined":
            self._console.print(f"  ✗ {clean_name} (declined)", style="error")

    def _confirm(self, action_name: str, args: dict) -> bool:
        if self._live:
            self._live.stop()
            self._live = None
        if self._status:
            self._status.stop()
        try:
            pretty = json.dumps(args, indent=2, ensure_ascii=False)
            self._console.print(Panel(
                pretty, title=f"Jarvis wants to run {action_name.replace('__', ' → ')}",
                border_style="yellow",
            ))
            answer = self._session.prompt("Allow? [y/N] ").strip().lower()
            return answer in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False
        finally:
            if self._status:
                self._status.start()

    # ---- output ---------------------------------------------------------------------------
    def _greet(self) -> None:
        hour = datetime.datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        user_name = self._config.get("user.name", "Sir")
        skills = len(self._orchestrator._skill_registry.get_all_skills())
        self._console.print(Panel(
            Text.from_markup(
                f"[bold cyan]J.A.R.V.I.S.[/]  v2.0  ·  {self._config.get('llm.model', '')}  ·  {skills} skills\n"
                f"{greeting}, {user_name}.  [dim]Type /help for examples, exit to quit.[/]"
            ),
            border_style="cyan",
        ))

    def display_response(self, text: str, speak: bool = True) -> None:
        self._console.print()
        self._console.print("[jarvis]JARVIS >[/]", end=" ")
        self._console.print(Markdown(text))
        self._console.print()
        if speak and self._voice_on and self._speaker:
            self._speaker.say(text)

    # ---- input ----------------------------------------------------------------------------
    def get_input(self) -> str:
        prompt = "YOU (Enter = speak) > " if self._listen_mode else "YOU > "
        text = self._session.prompt(prompt).strip()
        if not text and self._listen_mode:
            return self._listen_once()
        return text

    def _listen_once(self) -> str:
        if not self._listener:
            self._console.print("[error]Microphone input is not available.[/]")
            return ""
        with self._console.status("[cyan]Listening… speak now[/]"):
            try:
                text = self._listener.listen()
            except Exception as e:
                self._console.print(f"[error]Microphone error: {e}[/]")
                return ""
        if text:
            self._console.print(f"[user]YOU (voice) >[/] {text}")
        else:
            self._console.print("[info]Didn't catch that.[/]")
        return text

    def _handle_command(self, cmd: str) -> bool:
        """Return True if the input was a local command."""
        parts = cmd.lower().split()
        if not parts or not parts[0].startswith("/"):
            return False
        name = parts[0]
        if name == "/help":
            self._console.print(HELP)
        elif name == "/voice":
            if not self._speaker:
                self._console.print("[error]Text-to-speech is not available on this system.[/]")
            else:
                self._voice_on = (parts[1] != "off") if len(parts) > 1 else not self._voice_on
                self._console.print(f"[info]Voice replies {'on' if self._voice_on else 'off'}.[/]")
        elif name == "/listen":
            if not self._listener:
                self._console.print("[error]Microphone input is not available.[/]")
            else:
                self._listen_mode = not self._listen_mode
                self._console.print(
                    f"[info]Listen mode {'on — press Enter on an empty line to talk' if self._listen_mode else 'off'}.[/]"
                )
        elif name == "/handsfree":
            if not (self._listener and self._speaker):
                self._console.print("[error]Hands-free mode needs a working microphone and speakers.[/]")
            else:
                from jarvis.ui.handsfree import HandsFreeSession

                HandsFreeSession(self._orchestrator, self._config, self._speaker,
                                 self._listener, self._console).run()
                # back to text mode: restore the keyboard callbacks
                self._orchestrator.set_action_callback(self._on_action)
                self._orchestrator.set_confirm_callback(self._confirm)
                self._console.print("[info]Back to text mode.[/]")
        elif name in ("/notes", "/facts"):
            tool = "notes__get_notes" if name == "/notes" else "notes__get_facts"
            self._console.print(self._orchestrator._skill_registry.execute(tool, {}))
        elif name == "/keys":
            brain = self._orchestrator._brain
            pool = getattr(brain, "keys", None)
            for line in (pool.status() if pool else ["(key info unavailable)"]):
                self._console.print(f"  {line}")
        elif name == "/addkey":
            from jarvis.__main__ import ask_for_keys, save_keys

            new = ask_for_keys("Add Gemini API keys.")
            pool = getattr(self._orchestrator._brain, "keys", None)
            if new and pool is not None:
                total = save_keys(self._config, new)
                pool.add(new)
                self._console.print(f"[info]Saved. Jarvis now has {total} key(s).[/]")
        elif name == "/clear":
            self._orchestrator._short_term_memory.clear()
            self._console.print("[info]Conversation cleared.[/]")
        else:
            self._console.print(f"[error]Unknown command {name}. Try /help.[/]")
        return True

    def _stop_live(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None
        if self._status:
            self._status.stop()
            self._status = None

    def _ask(self, user_input: str) -> None:
        """Send one message; the reply is rendered live as it streams in."""
        streamed: list[str] = []
        self._status = self._console.status("[cyan]Thinking…[/]")
        self._status.start()

        def on_text(fragment: str) -> None:
            streamed.append(fragment)
            if self._live is None:
                if self._status:
                    self._status.stop()
                    self._status = None
                self._console.print()
                self._console.print("[jarvis]JARVIS >[/]")
                self._live = Live(console=self._console, refresh_per_second=15,
                                  vertical_overflow="visible")
                self._live.start()
            self._live.update(Markdown("".join(streamed)))

        response = self._orchestrator.process(user_input, on_text=on_text)
        if self._live is None:  # nothing was streamed (e.g. a non-streaming fallback)
            self._stop_live()
            self.display_response(response)
            return
        self._live.update(Markdown(response))
        self._stop_live()
        self._console.print()
        if self._voice_on and self._speaker:
            self._speaker.say(response)

    def run(self) -> None:
        self._greet()
        self.display_response("How can I help you today?", speak=False)

        while True:
            try:
                user_input = self.get_input()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_input:
                continue
            if user_input.lower().strip(" .!") in EXIT_WORDS:
                break
            if self._handle_command(user_input):
                continue

            try:
                self._ask(user_input)
            except KeyboardInterrupt:
                self._console.print("[info]Interrupted.[/]")
            except Exception as e:
                logger.exception("process() failed")
                self._console.print(f"[error]{friendly_error(e, self._config.get('llm.model', ''))}[/]")
            finally:
                self._stop_live()

        user_name = self._config.get("user.name", "Sir")
        with self._console.status("[cyan]Saving memory…[/]"):
            self._orchestrator.shutdown()
        self.display_response(f"Goodbye, {user_name}.")
