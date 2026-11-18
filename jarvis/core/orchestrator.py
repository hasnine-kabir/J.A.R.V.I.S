from jarvis.core.brain import Brain, Message, BrainResponse
from jarvis.core.memory import ShortTermMemory, LongTermMemory
from jarvis.core.skill_registry import SkillRegistry
from jarvis.config import Config
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.orchestrator")


class Orchestrator:
    def __init__(
        self,
        brain: Brain,
        config: Config,
        skill_registry: SkillRegistry,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
    ):
        self._brain = brain
        self._config = config
        self._skill_registry = skill_registry
        self._short_term_memory = short_term_memory
        self._long_term_memory = long_term_memory
        self._on_action = None  # callback for UI: (action_name, status)

    def set_action_callback(self, callback) -> None:
        """Set callback for skill execution updates: callback(action_name, status)"""
        self._on_action = callback

    def get_system_prompt(self) -> str:
        personality = self._config.get("jarvis.personality", "You are a helpful AI assistant.")
        user_name = self._config.get("user.name", "Sir")

        facts = self._long_term_memory.get_facts()
        facts_text = ""
        if facts:
            facts_text = "\n\nKnown facts about the user:\n"
            facts_text += "\n".join(f"- {f['key']}: {f['value']}" for f in facts)

        last_summary = self._long_term_memory.get_last_session_summary()
        summary_text = ""
        if last_summary:
            summary_text = f"\n\nLast session summary:\n{last_summary}"

        return f"{personality}\n\nThe user's name is {user_name}.{facts_text}{summary_text}"

    def process(self, user_input: str) -> str:
        self._short_term_memory.add(Message(role="user", content=user_input))

        messages = self._short_term_memory.get_messages()
        tool_declarations = self._skill_registry.get_tool_declarations()
        system_prompt = self.get_system_prompt()

        response = self._brain.think(messages, tool_declarations, system_prompt)

        # Handle tool calls (up to 5 rounds to prevent infinite loops)
        rounds = 0
        while response.tool_calls and rounds < 5:
            rounds += 1
            results = []
            for tc in response.tool_calls:
                if self._on_action:
                    self._on_action(tc.name, "running")
                logger.info(f"Executing: {tc.name}({tc.args})")
                output = self._skill_registry.execute(tc.name, tc.args)
                results.append({"name": tc.name, "output": output})
                if self._on_action:
                    self._on_action(tc.name, "done")

            response = self._brain.send_tool_results(results)

        final_text = response.text or ""
        self._short_term_memory.add(Message(role="assistant", content=final_text))
        return final_text

    def shutdown(self) -> None:
        """Save session summary and clean up."""
        messages = self._short_term_memory.get_messages()
        if len(messages) > 2:
            # Build a simple summary from the conversation
            topics = [m.content[:100] for m in messages if m.role == "user"]
            summary = f"User discussed: {'; '.join(topics[:10])}"
            self._long_term_memory.save_session_summary(summary)
        self._long_term_memory.close()
