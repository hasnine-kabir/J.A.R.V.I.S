import datetime
from concurrent.futures import ThreadPoolExecutor

from jarvis.config import Config
from jarvis.core.brain import Brain, Message
from jarvis.core.memory import LongTermMemory, ShortTermMemory
from jarvis.core.skill_registry import SkillRegistry
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.orchestrator")

MAX_TOOL_ROUNDS = 6

BEHAVIOUR_RULES = """
Rules:
- You run on the user's own Windows PC and can act through your tools. Use them whenever
  they help; never claim you did something without calling the tool.
- When the user tells you a lasting personal fact or preference, save it with notes__save_fact.
  When they ask you to remember something, use notes__save_note.
- To open an app, file, folder or website use pc_control__open_application (pass a URL as
  `target`, e.g. app_name='chrome', target='https://youtube.com'). Use run_command only for
  things that really need a shell.
- Keep spoken-style answers short (1-3 sentences) unless the user asks for detail.
- Light markdown is fine (short bullet lists, **bold**, `inline code`). Always put code in a
  fenced block with its language, e.g. ```python. No tables.
"""


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
        self._on_action = None   # callback(action_name, status)
        self._confirm = None     # callback(action_name, args) -> bool

        for skill in self._skill_registry.get_all_skills():
            try:
                skill.setup(config, long_term_memory)
            except Exception as e:
                logger.warning(f"setup() failed for skill {skill.name}: {e}")

    def set_action_callback(self, callback) -> None:
        """callback(action_name, status) where status is 'running' | 'done' | 'declined'."""
        self._on_action = callback

    def set_confirm_callback(self, callback) -> None:
        """callback(action_name, args) -> bool. Without one, risky tools are refused."""
        self._confirm = callback

    def get_system_prompt(self) -> str:
        personality = self._config.get("jarvis.personality", "You are a helpful AI assistant.")
        user_name = self._config.get("user.name", "Sir")
        now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

        facts = self._long_term_memory.get_facts()
        facts_text = ""
        if facts:
            facts_text = "\n\nKnown facts about the user:\n"
            facts_text += "\n".join(f"- {f['key']}: {f['value']}" for f in facts)

        last_summary = self._long_term_memory.get_last_session_summary()
        summary_text = f"\n\nLast session summary:\n{last_summary}" if last_summary else ""

        return (
            f"{personality}\n\nThe user's name is {user_name}. Current local time: {now}."
            f"\n{BEHAVIOUR_RULES}{facts_text}{summary_text}"
        )

    def _notify(self, name: str, status: str) -> None:
        if self._on_action:
            self._on_action(name, status)

    def _run_tool(self, name: str, args: dict) -> str:
        if self._needs_ok(name):
            approved = bool(self._confirm and self._confirm(name, args))
            if not approved:
                self._notify(name, "declined")
                return "The user declined this action. Do not retry it unless they ask."
        self._notify(name, "running")
        logger.info(f"Executing: {name}({args})")
        output = self._skill_registry.execute(name, args)
        self._notify(name, "done")
        return output

    def _needs_ok(self, name: str) -> bool:
        tool = self._skill_registry.get_tool(name)
        return bool(tool is not None and tool.confirm and self._config.get("safety.confirm_actions", True))

    def _run_tools(self, tool_calls) -> list[dict]:
        """Run one round of tool calls - in parallel unless one needs the user's OK."""
        if len(tool_calls) > 1 and not any(self._needs_ok(tc.name) for tc in tool_calls):
            with ThreadPoolExecutor(max_workers=min(8, len(tool_calls))) as pool:
                outputs = list(pool.map(lambda tc: self._run_tool(tc.name, tc.args), tool_calls))
        else:
            outputs = [self._run_tool(tc.name, tc.args) for tc in tool_calls]
        return [{"name": tc.name, "output": out} for tc, out in zip(tool_calls, outputs)]

    def process(self, user_input: str, on_text=None) -> str:
        """Answer one user message. `on_text(fragment)` streams the reply as it is generated."""
        self._short_term_memory.add(Message(role="user", content=user_input))

        messages = self._short_term_memory.get_messages()
        tool_declarations = self._skill_registry.get_tool_declarations()
        response = self._brain.think(messages, tool_declarations, self.get_system_prompt(),
                                     on_text=on_text)

        rounds = 0
        while response.tool_calls and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            response = self._brain.send_tool_results(self._run_tools(response.tool_calls),
                                                     on_text=on_text)

        final_text = (response.text or "").strip()
        if not final_text:
            final_text = "Done." if rounds else "I'm not sure how to respond to that."
        self._short_term_memory.add(Message(role="assistant", content=final_text))
        return final_text

    def _summarize_session(self, messages: list[Message]) -> str:
        transcript = "\n".join(f"{m.role}: {m.content[:300]}" for m in messages[-30:])
        try:
            resp = self._brain.think(
                [Message(role="user", content=transcript)],
                [],
                "Summarize this conversation between a user and their assistant in at most "
                "3 short sentences, focusing on what the user wanted and any open follow-ups.",
            )
            if resp.text and resp.text.strip():
                return resp.text.strip()
        except Exception as e:
            logger.warning(f"LLM session summary failed: {e}")
        topics = [m.content[:100] for m in messages if m.role == "user"]
        return f"User discussed: {'; '.join(topics[:10])}"

    def shutdown(self) -> None:
        """Save a session summary and close storage."""
        messages = self._short_term_memory.get_messages()
        if len(messages) > 2:
            self._long_term_memory.save_session_summary(self._summarize_session(messages))
        self._long_term_memory.close()
