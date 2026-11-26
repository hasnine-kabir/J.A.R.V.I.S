"""Entry point: python -m jarvis [--voice] [--listen]"""
import argparse
import sys
from pathlib import Path

from jarvis.config import PROJECT_ROOT, Config
from jarvis.utils.logger import setup_logger

logger = setup_logger()


def _first_run_setup(config: Config) -> Config:
    """Ask for a Gemini API key on first launch and store it in .env (never printed)."""
    from dotenv import set_key
    from prompt_toolkit import prompt

    print("\nWelcome to J.A.R.V.I.S. v2.0 — first-time setup.")
    print("Jarvis needs a Google Gemini API key. Get one free at https://aistudio.google.com/apikey")
    try:
        key = prompt("Paste your Gemini API key (input hidden): ", is_password=True).strip()
    except (KeyboardInterrupt, EOFError):
        key = ""
    if not key:
        print("No key entered. You can also put GEMINI_API_KEY=... in", config.env_path)
        sys.exit(1)
    env_file = Path(config.env_path)
    env_file.touch(exist_ok=True)
    set_key(str(env_file), "GEMINI_API_KEY", key, quote_mode="never")
    print(f"Saved to {env_file}.\n")
    return Config()


def build_orchestrator(config: Config):
    from jarvis.core.brain import GeminiBrain
    from jarvis.core.memory import LongTermMemory, ShortTermMemory
    from jarvis.core.orchestrator import Orchestrator
    from jarvis.core.skill_registry import SkillRegistry

    brain = GeminiBrain(
        api_key=config.gemini_api_key,
        model=config.get("llm.model", "gemini-2.5-flash"),
    )
    registry = SkillRegistry()
    registry.discover()
    return Orchestrator(
        brain=brain,
        config=config,
        skill_registry=registry,
        short_term_memory=ShortTermMemory(max_messages=config.get("llm.max_history", 50)),
        long_term_memory=LongTermMemory(db_path=str(PROJECT_ROOT / "memory.db")),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jarvis", description="J.A.R.V.I.S. — your AI assistant")
    parser.add_argument("--voice", action="store_true", help="speak replies aloud")
    parser.add_argument("--listen", action="store_true", help="start in microphone (listen) mode")
    parser.add_argument("--ask", metavar="TEXT", help="ask one question, print the answer, exit")
    args = parser.parse_args(argv)

    config = Config()
    if not config.gemini_api_key:
        config = _first_run_setup(config)

    orchestrator = build_orchestrator(config)

    if args.ask:
        from jarvis.utils.errors import friendly_error

        orchestrator.set_confirm_callback(lambda name, a: False)  # never run risky tools unattended
        try:
            print(orchestrator.process(args.ask))
        except Exception as e:
            logger.exception("--ask failed")
            print(friendly_error(e, config.get("llm.model", "")))
            sys.exit(1)
        finally:
            orchestrator.shutdown()
        return

    speaker = listener = None
    try:
        from jarvis.voice.speaker import Speaker

        speaker = Speaker(voice=config.get("voice.name", ""), rate=config.get("voice.rate", 185))
    except Exception as e:
        logger.warning(f"Text-to-speech unavailable: {e}")
    try:
        from jarvis.voice.listener import Listener

        listener = Listener(language=config.get("voice.language", "en-US"))
    except Exception as e:
        logger.warning(f"Microphone input unavailable: {e}")

    from jarvis.ui.terminal import TerminalUI

    voice_default = bool(config.get("voice.enabled", False)) or args.voice
    ui = TerminalUI(
        orchestrator=orchestrator,
        config=config,
        speaker=speaker,
        listener=listener,
    )
    ui._voice_on = bool(speaker) and voice_default
    ui._listen_mode = bool(listener) and args.listen
    ui.run()


if __name__ == "__main__":
    main()
