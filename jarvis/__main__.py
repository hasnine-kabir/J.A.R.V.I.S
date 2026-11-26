"""Entry point: python -m jarvis [--voice] [--listen]"""
import argparse
import sys
from pathlib import Path

from jarvis.config import PROJECT_ROOT, Config
from jarvis.utils.logger import setup_logger

logger = setup_logger()


def save_keys(config: Config, new_keys: list[str]) -> int:
    """Merge new keys into GEMINI_API_KEYS in .env. Returns the total number of keys."""
    import os

    from dotenv import set_key, unset_key

    keys = list(dict.fromkeys(config.gemini_api_keys + [k.strip() for k in new_keys if k.strip()]))
    env_file = Path(config.env_path)
    env_file.touch(exist_ok=True)
    set_key(str(env_file), "GEMINI_API_KEYS", ",".join(keys), quote_mode="never")
    if config.gemini_api_key:
        unset_key(str(env_file), "GEMINI_API_KEY")
    # Keep this process in sync (load_dotenv does not override existing variables).
    os.environ["GEMINI_API_KEYS"] = ",".join(keys)
    os.environ.pop("GEMINI_API_KEY", None)
    return len(keys)


def ask_for_keys(intro: str) -> list[str]:
    """Prompt for one or more keys (hidden input). Empty line finishes."""
    from prompt_toolkit import prompt

    print(intro)
    print("Paste one key per line (input is hidden). You can also paste several separated by commas.")
    print("Press Enter on an empty line when you're done.")
    keys: list[str] = []
    while True:
        try:
            line = prompt(f"Gemini API key #{len(keys) + 1}: ", is_password=True).strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            break
        added = [k.strip() for k in line.replace(";", ",").replace(" ", ",").split(",") if k.strip()]
        keys.extend(added)
        print(f"  ✓ got {len(added)} key(s)")
    return keys


def _first_run_setup(config: Config) -> Config:
    keys = ask_for_keys(
        "\nWelcome to J.A.R.V.I.S. v2.0 — first-time setup.\n"
        "Jarvis needs a Google Gemini API key. Get one free at https://aistudio.google.com/apikey\n"
        "Tip: add several keys — when one runs out of quota Jarvis switches to the next."
    )
    if not keys:
        print("No key entered. You can also put GEMINI_API_KEYS=key1,key2 in", config.env_path)
        sys.exit(1)
    total = save_keys(config, keys)
    print(f"Saved {total} key(s) to {config.env_path}.\n")
    return Config()


def build_orchestrator(config: Config):
    from jarvis.core.brain import GeminiBrain
    from jarvis.core.memory import LongTermMemory, ShortTermMemory
    from jarvis.core.orchestrator import Orchestrator
    from jarvis.core.skill_registry import SkillRegistry

    brain = GeminiBrain(
        api_key=config.gemini_api_keys,
        model=config.get("llm.model", "gemini-3.5-flash"),
        fallback_models=config.get("llm.fallback_models", []),
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
    parser.add_argument("--add-key", action="store_true", help="add more Gemini API keys, then exit")
    args = parser.parse_args(argv)

    config = Config()
    if args.add_key:
        keys = ask_for_keys(f"You have {len(config.gemini_api_keys)} Gemini key(s) saved.")
        if keys:
            print(f"Saved. Jarvis now has {save_keys(config, keys)} key(s).")
        return
    if not config.gemini_api_keys:
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
