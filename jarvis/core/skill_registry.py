import importlib
import inspect
import pkgutil
from jarvis.skills.base import BaseSkill
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.registry")


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def discover(self, package_name: str = "jarvis.skills") -> None:
        """Auto-discover and register all skills in the skills package."""
        package = importlib.import_module(package_name)
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            if module_name == "base":
                continue
            module = importlib.import_module(f"{package_name}.{module_name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    self.register(obj())

    def get_skill(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def get_all_skills(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def get_tool_declarations(self) -> list[dict]:
        """Get all tool declarations for Gemini function calling."""
        declarations = []
        for skill in self._skills.values():
            for tool in skill.tools:
                declarations.append(tool.to_declaration(skill.name))
        return declarations

    def execute(self, tool_name: str, args: dict) -> str:
        """Execute a tool by its full name (skill_name__action_name)."""
        if "__" not in tool_name:
            return f"Error: invalid tool name '{tool_name}'"
        skill_name, action_name = tool_name.split("__", 1)
        skill = self._skills.get(skill_name)
        if not skill:
            return f"Error: skill '{skill_name}' not found"
        try:
            return skill.execute(action_name, args)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
