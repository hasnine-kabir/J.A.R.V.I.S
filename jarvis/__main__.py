"""Entry point: python -m jarvis [--web] [--voice] [--listen] [--handsfree]"""
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


def _mic_test(config: Config) -> None:
    from jarvis.voice.listener import Listener

    listener = Listener(language=config.get("voice.language", "en-US"),
                        min_threshold=config.get("voice.mic_threshold", 200))
    print("Mic test: stay quiet for a moment, then say \"Jarvis, what time is it?\" at normal volume.")
    input("Press Enter, then speak... ")
    background, loudest = listener.measure(4.0)
    print(f"Background noise level: {background:.0f}   Your voice peaked at: {loudest:.0f}")
    print(f"Speech is detected above:  {max(listener._min_threshold, background * 3):.0f}"
          "  (voice.mic_threshold in config.yaml)")
    if loudest < 100:
        print("-> The mic barely hears anything. Check it's not muted and is the default recording "
              "device (Windows Settings > System > Sound > Input), and raise its volume.")
    elif loudest < max(listener._min_threshold, background * 3) * 1.5:
        suggested = int(max(50, loudest / 2.5))
        print(f"-> Your voice is close to the detection level. Set voice.mic_threshold: {suggested} "
              "in config.yaml, or raise the mic volume.")
    else:
        print("-> Looks good. Now testing recognition: say \"Jarvis, what time is it?\"")
        heard = listener.listen(wait_seconds=8)
        print(f"Heard: {heard!r}" if heard else "Didn't catch any words - try speaking a bit closer.")


def build_orchestrator(config: Config):
    from jarvis.core.brain import GeminiBrain
    from jarvis.core.memory import LongTermMemory, ShortTermMemory
    from jarvis.core.orchestrator import Orchestrator
    from jarvis.core.skill_registry import SkillRegistry

    brain = GeminiBrain(
        api_key=config.gemini_api_keys,
        model=config.get("llm.model", "gemini-3.5-flash-lite"),
        fallback_models=config.get("llm.fallback_models", []),
        thinking_level=config.get("llm.thinking_level", "minimal"),
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
    parser.add_argument("--handsfree", action="store_true",
                        help="always listen: say 'Jarvis ...' and it answers out loud")
    parser.add_argument("--web", action="store_true", help="open the Jarvis web UI in your browser")
    parser.add_argument("--port", type=int, help="web UI port (default from config.yaml, 8765)")
    parser.add_argument("--no-browser", action="store_true", help="with --web: don't open a browser tab")
    parser.add_argument("--mic-test", action="store_true", help="check that the microphone hears you")
    parser.add_argument("--add-key", action="store_true", help="add more Gemini API keys, then exit")
    args = parser.parse_args(argv)

    config = Config()
    if args.mic_test:
        _mic_test(config)
        return
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

        listener = Listener(language=config.get("voice.language", "en-US"),
                            min_threshold=config.get("voice.mic_threshold", 200))
    except Exception as e:
        logger.warning(f"Microphone input unavailable: {e}")

    if args.web:
        from jarvis.web.server import run

        if args.port:
            config._data.setdefault("web", {})["port"] = args.port
        if args.no_browser:
            config._data.setdefault("web", {})["open_browser"] = False
        run(orchestrator, config, speaker, listener)
        return

    if args.handsfree:
        from jarvis.ui.handsfree import HandsFreeSession

        if not (speaker and listener):
            print("Hands-free mode needs a working microphone and speakers. See jarvis.log for details.")
            orchestrator.shutdown()
            sys.exit(1)
        try:
            HandsFreeSession(orchestrator, config, speaker, listener).run()
        finally:
            orchestrator.shutdown()
            speaker.close()
        return

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
