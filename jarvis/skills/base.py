from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_declaration(self, skill_name: str) -> dict:
        """Convert to Gemini function declaration format."""
        return {
            "name": f"{skill_name}__{self.name}",
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required,
            },
        }


class BaseSkill(ABC):
    name: str = ""
    description: str = ""
    tools: list[Tool] = []

    @abstractmethod
    def execute(self, action: str, args: dict) -> str:
        """Execute an action with the given arguments. Return result as string."""
        ...
