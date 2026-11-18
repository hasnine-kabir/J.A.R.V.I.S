import pytest
from jarvis.skills.base import BaseSkill, Tool


class MockSkill(BaseSkill):
    name = "mock_skill"
    description = "A mock skill for testing"
    tools = [
        Tool(name="greet", description="Say hello", parameters={"name": {"type": "string", "description": "Name to greet"}}),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "greet":
            return f"Hello, {args['name']}!"
        raise ValueError(f"Unknown action: {action}")


def test_base_skill_execute():
    skill = MockSkill()
    result = skill.execute("greet", {"name": "Hasnine"})
    assert result == "Hello, Hasnine!"


def test_base_skill_unknown_action():
    skill = MockSkill()
    with pytest.raises(ValueError, match="Unknown action"):
        skill.execute("unknown", {})


def test_tool_to_gemini_declaration():
    tool = Tool(
        name="greet",
        description="Say hello",
        parameters={"name": {"type": "string", "description": "Name to greet"}},
    )
    decl = tool.to_declaration("mock_skill")
    assert decl["name"] == "mock_skill__greet"
    assert decl["description"] == "Say hello"
    assert "name" in decl["parameters"]["properties"]


from jarvis.core.skill_registry import SkillRegistry


def test_registry_register_and_get():
    registry = SkillRegistry()
    skill = MockSkill()
    registry.register(skill)
    assert registry.get_skill("mock_skill") is skill


def test_registry_get_all_skills():
    registry = SkillRegistry()
    registry.register(MockSkill())
    skills = registry.get_all_skills()
    assert len(skills) == 1
    assert skills[0].name == "mock_skill"


def test_registry_get_tool_declarations():
    registry = SkillRegistry()
    registry.register(MockSkill())
    declarations = registry.get_tool_declarations()
    assert len(declarations) == 1
    assert declarations[0]["name"] == "mock_skill__greet"


def test_registry_execute():
    registry = SkillRegistry()
    registry.register(MockSkill())
    result = registry.execute("mock_skill__greet", {"name": "Hasnine"})
    assert result == "Hello, Hasnine!"


def test_registry_execute_unknown_tool():
    registry = SkillRegistry()
    result = registry.execute("nonexistent__action", {})
    assert "error" in result.lower()
