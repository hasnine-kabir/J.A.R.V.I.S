"""Entry point: python -m jarvis"""
from jarvis.config import Config
from jarvis.core.brain import GeminiBrain
from jarvis.core.memory import ShortTermMemory, LongTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.skill_registry import SkillRegistry
from jarvis.ui.terminal import TerminalUI
from jarvis.utils.logger import setup_logger


def main():
    logger = setup_logger()
    config = Config()

    if not config.gemini_api_key:
        print("Error: GEMINI_API_KEY not set in .env file")
        return

    # Initialize components
    brain = GeminiBrain(
        api_key=config.gemini_api_key,
        model=config.get("llm.model", "gemini-2.0-flash"),
    )
    skill_registry = SkillRegistry()
    skill_registry.discover()

    short_mem = ShortTermMemory(max_messages=config.get("llm.max_history", 50))
    long_mem = LongTermMemory()

    orchestrator = Orchestrator(
        brain=brain,
        config=config,
        skill_registry=skill_registry,
        short_term_memory=short_mem,
        long_term_memory=long_mem,
    )

    # Launch terminal
    ui = TerminalUI(orchestrator=orchestrator, config=config)
    ui.run()


if __name__ == "__main__":
    main()
