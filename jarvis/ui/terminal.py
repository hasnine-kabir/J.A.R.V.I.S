import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from jarvis.core.orchestrator import Orchestrator
from jarvis.config import Config

custom_theme = Theme({
    "jarvis": "bold cyan",
    "user": "bold green",
    "action": "yellow",
    "error": "bold red",
    "info": "dim",
})


class TerminalUI:
    def __init__(self, orchestrator: Orchestrator, config: Config):
        self._orchestrator = orchestrator
        self._config = config
        self._console = Console(theme=custom_theme)
        self._session = PromptSession(history=FileHistory(".jarvis_history"))
        self._orchestrator.set_action_callback(self._on_action)

    def _on_action(self, action_name: str, status: str) -> None:
        icon = "⚙" if status == "running" else "✓"
        style = "action" if status == "running" else "bold green"
        clean_name = action_name.replace("__", " → ")
        self._console.print(f"  {icon} {clean_name}", style=style)

    def _greet(self) -> None:
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        user_name = self._config.get("user.name", "Sir")

        panel = Panel(
            Text.from_markup(
                f"[bold cyan]J.A.R.V.I.S.[/]  v2.0\n"
                f"{greeting}, {user_name}."
            ),
            border_style="cyan",
        )
        self._console.print(panel)

    def display_response(self, text: str) -> None:
        self._console.print(f"\n[jarvis]JARVIS >[/] {text}\n")

    def get_input(self) -> str:
        return self._session.prompt("YOU > ").strip()

    def run(self) -> None:
        self._greet()
        self.display_response("How can I help you today?")

        while True:
            try:
                user_input = self.get_input()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "goodbye", "sleep"):
                break

            try:
                response = self._orchestrator.process(user_input)
                self.display_response(response)
            except Exception as e:
                self._console.print(f"[error]Error: {e}[/]")

        user_name = self._config.get("user.name", "Sir")
        self.display_response(f"Goodnight, {user_name}.")
        self._orchestrator.shutdown()
