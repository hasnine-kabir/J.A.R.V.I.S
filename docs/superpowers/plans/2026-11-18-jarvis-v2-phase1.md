# J.A.R.V.I.S v2.0 Phase 1 — Terminal MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully functional LLM-powered terminal assistant with Gemini brain, modular skill system, and persistent memory.

**Architecture:** Modular agent with central orchestrator. The orchestrator receives user input from the terminal UI, passes it to the Gemini brain along with skill schemas and conversation history, executes any tool calls the brain returns, and displays the final response. Skills auto-register by inheriting from BaseSkill.

**Tech Stack:** Python 3.11+, google-generativeai (Gemini API), rich (terminal UI), prompt-toolkit (input), SQLite (memory), pytest (testing), python-dotenv, pyyaml.

## Global Constraints

- Python 3.11+ required (for `Self` type, `StrEnum`, `tomllib`)
- All code in `jarvis/` package — old repo files untouched
- No async in Phase 1 — keep it simple, synchronous everywhere
- All secrets in `.env`, never committed (add to `.gitignore`)
- All config in `config.yaml` at repo root
- Tests in `tests/` mirroring `jarvis/` structure
- Every skill must inherit `BaseSkill` and be auto-discoverable
- Gemini model: `gemini-2.0-flash` (fast, good at function calling, cheap)

## File Map

```
jarvis/
├── __init__.py
├── __main__.py              → entry point
├── config.py                → loads .env + config.yaml
├── core/
│   ├── __init__.py
│   ├── brain.py             → Brain protocol + GeminiBrain
│   ├── memory.py            → ShortTermMemory + LongTermMemory (SQLite)
│   ├── orchestrator.py      → main loop
│   └── skill_registry.py    → auto-discovers and registers skills
├── skills/
│   ├── __init__.py
│   ├── base.py              → BaseSkill, Tool dataclass
│   ├── system_info.py       → CPU, battery, time, weather
│   ├── pc_control.py        → open apps, run commands, manage files
│   ├── screenshot.py        → take screenshots
│   ├── web_search.py        → Google search
│   ├── wikipedia_search.py  → Wikipedia lookups
│   ├── code_helper.py       → read files, explain code
│   ├── notes.py             → save/retrieve notes and facts
│   ├── email_sender.py      → send emails via SMTP
│   └── media.py             → play music, YouTube search
├── ui/
│   ├── __init__.py
│   └── terminal.py          → rich-based terminal interface
└── utils/
    ├── __init__.py
    └── logger.py            → logging setup

tests/
├── conftest.py              → shared fixtures
├── test_config.py
├── core/
│   ├── test_brain.py
│   ├── test_memory.py
│   ├── test_orchestrator.py
│   └── test_skill_registry.py
└── skills/
    ├── test_system_info.py
    ├── test_pc_control.py
    ├── test_screenshot.py
    ├── test_web_search.py
    ├── test_wikipedia_search.py
    ├── test_code_helper.py
    ├── test_notes.py
    ├── test_email_sender.py
    └── test_media.py

config.yaml                  → user preferences
.env                         → secrets (gitignored)
```

---

### Task 1: Project Foundation

**Files:**
- Create: `jarvis/__init__.py`, `jarvis/__main__.py`, `jarvis/config.py`
- Create: `jarvis/core/__init__.py`, `jarvis/skills/__init__.py`, `jarvis/ui/__init__.py`, `jarvis/utils/__init__.py`
- Create: `jarvis/utils/logger.py`
- Create: `config.yaml`, `.env`
- Modify: `.gitignore`
- Create: `requirements-v2.txt`
- Create: `tests/conftest.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `config.get(key: str) -> Any` — dot-notation access to config values
  - `config.GEMINI_API_KEY: str` — env var accessor
  - `config.USER_NAME: str` — from config.yaml
  - `config.LLM_MODEL: str` — from config.yaml
  - `logger: logging.Logger` — configured logger

- [ ] **Step 1: Create requirements-v2.txt**

```
google-generativeai>=0.8.0
rich>=13.0.0
prompt-toolkit>=3.0.0
python-dotenv>=1.0.0
pyyaml>=6.0.0
psutil>=5.9.0
pyautogui>=0.9.50
wikipedia>=1.4.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pyjokes>=0.6.0
geocoder>=1.38.1
pytest>=8.0.0
```

- [ ] **Step 2: Create .env template and update .gitignore**

`.env`:
```
GEMINI_API_KEY=your_gemini_api_key_here
SMTP_EMAIL=
SMTP_PASSWORD=
```

Add to `.gitignore`:
```
.env
memory.db
__pycache__/
*.pyc
```

- [ ] **Step 3: Create config.yaml**

```yaml
user:
  name: Hasnine

jarvis:
  personality: >
    You are J.A.R.V.I.S., a highly intelligent AI assistant inspired by the MCU.
    You are professional yet warm, witty but never sarcastic. You address the user
    by name. You are proactive — if a task has obvious follow-ups, suggest them.
    Keep responses concise unless asked for detail.
  wake_word: "Hey Jarvis"

llm:
  provider: gemini
  model: gemini-2.0-flash
  max_history: 50
```

- [ ] **Step 4: Write the failing test for config**

```python
# tests/test_config.py
import os
import pytest
from jarvis.config import Config


def test_config_loads_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("user:\n  name: TestUser\nllm:\n  model: gemini-2.0-flash\n")
    config = Config(yaml_path=str(yaml_file))
    assert config.get("user.name") == "TestUser"
    assert config.get("llm.model") == "gemini-2.0-flash"


def test_config_loads_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=test-key-123\n")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    config = Config(env_path=str(env_file))
    assert config.gemini_api_key == "test-key-123"


def test_config_get_nested_default():
    config = Config.__new__(Config)
    config._data = {}
    assert config.get("nonexistent.key", "default") == "default"
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jarvis'`

- [ ] **Step 6: Create package structure and implement config**

`jarvis/__init__.py`:
```python
"""J.A.R.V.I.S. — Just A Rather Very Intelligent System"""
__version__ = "2.0.0"
```

`jarvis/core/__init__.py`, `jarvis/skills/__init__.py`, `jarvis/ui/__init__.py`, `jarvis/utils/__init__.py`:
```python
# empty
```

`jarvis/config.py`:
```python
import os
from pathlib import Path
from dotenv import load_dotenv
import yaml


class Config:
    def __init__(self, yaml_path: str = "config.yaml", env_path: str = ".env"):
        load_dotenv(env_path)
        self._data = {}
        yaml_file = Path(yaml_path)
        if yaml_file.exists():
            with open(yaml_file) as f:
                self._data = yaml.safe_load(f) or {}

    @property
    def gemini_api_key(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "")

    @property
    def smtp_email(self) -> str:
        return os.environ.get("SMTP_EMAIL", "")

    @property
    def smtp_password(self) -> str:
        return os.environ.get("SMTP_PASSWORD", "")

    def get(self, key: str, default=None):
        """Dot-notation access: config.get('user.name')"""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
```

- [ ] **Step 7: Create logger**

`jarvis/utils/logger.py`:
```python
import logging
import sys


def setup_logger(name: str = "jarvis", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger
```

- [ ] **Step 8: Create entry point stub**

`jarvis/__main__.py`:
```python
"""Entry point: python -m jarvis"""
from jarvis.config import Config
from jarvis.utils.logger import setup_logger


def main():
    logger = setup_logger()
    config = Config()
    logger.info("J.A.R.V.I.S. v2.0 starting up...")
    logger.info(f"Welcome, {config.get('user.name', 'Sir')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: 3 PASSED

- [ ] **Step 10: Verify entry point runs**

Run: `python -m jarvis`
Expected: prints startup log with user name

- [ ] **Step 11: Commit**

```bash
git add jarvis/ tests/ config.yaml .env requirements-v2.txt .gitignore
git commit -m "feat: project foundation — config, logger, package structure"
```

---

### Task 2: Skill Framework

**Files:**
- Create: `jarvis/skills/base.py`
- Create: `jarvis/core/skill_registry.py`
- Create: `tests/core/test_skill_registry.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `class Tool` — dataclass with `name: str`, `description: str`, `parameters: dict`
  - `class BaseSkill` — abstract base with `name: str`, `description: str`, `tools: list[Tool]`, `execute(action: str, args: dict) -> str`
  - `class SkillRegistry` — `discover() -> None`, `get_all_skills() -> list[BaseSkill]`, `get_skill(name: str) -> BaseSkill`, `get_tool_declarations() -> list[dict]`

- [ ] **Step 1: Write the failing test for BaseSkill**

```python
# tests/core/test_skill_registry.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_skill_registry.py::test_base_skill_execute -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement BaseSkill and Tool**

`jarvis/skills/base.py`:
```python
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
```

- [ ] **Step 4: Run BaseSkill tests to verify they pass**

Run: `python -m pytest tests/core/test_skill_registry.py::test_base_skill_execute tests/core/test_skill_registry.py::test_base_skill_unknown_action tests/core/test_skill_registry.py::test_tool_to_gemini_declaration -v`
Expected: 3 PASSED

- [ ] **Step 5: Write the failing test for SkillRegistry**

Add to `tests/core/test_skill_registry.py`:
```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/core/test_skill_registry.py::test_registry_register_and_get -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 7: Implement SkillRegistry**

`jarvis/core/skill_registry.py`:
```python
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
```

- [ ] **Step 8: Run all registry tests**

Run: `python -m pytest tests/core/test_skill_registry.py -v`
Expected: 8 PASSED

- [ ] **Step 9: Commit**

```bash
git add jarvis/skills/base.py jarvis/core/skill_registry.py tests/core/
git commit -m "feat: skill framework — BaseSkill, Tool, SkillRegistry with auto-discovery"
```

---

### Task 3: Gemini Brain

**Files:**
- Create: `jarvis/core/brain.py`
- Create: `tests/core/test_brain.py`

**Interfaces:**
- Consumes: `Tool.to_declaration()` from Task 2, `Config` from Task 1
- Produces:
  - `class Message` — dataclass with `role: str`, `content: str`
  - `class ToolCall` — dataclass with `name: str`, `args: dict`
  - `class BrainResponse` — dataclass with `text: str | None`, `tool_calls: list[ToolCall]`
  - `class Brain(Protocol)` — `think(messages: list[Message], tool_declarations: list[dict], system_prompt: str) -> BrainResponse`
  - `class GeminiBrain` — implements Brain using `google-generativeai`

- [ ] **Step 1: Write the failing test for Brain data classes and protocol**

```python
# tests/core/test_brain.py
import pytest
from unittest.mock import patch, MagicMock
from jarvis.core.brain import Message, ToolCall, BrainResponse, GeminiBrain


def test_message_creation():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_brain_response_text_only():
    resp = BrainResponse(text="Hello!", tool_calls=[])
    assert resp.text == "Hello!"
    assert resp.tool_calls == []


def test_brain_response_with_tool_calls():
    resp = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="system_info__cpu_usage", args={})]
    )
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "system_info__cpu_usage"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_brain.py::test_message_creation -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement data classes**

Add to top of `jarvis/core/brain.py`:
```python
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Message:
    role: str  # "user", "assistant", "tool_result"
    content: str


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class BrainResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
```

- [ ] **Step 4: Run data class tests**

Run: `python -m pytest tests/core/test_brain.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Write the failing test for GeminiBrain**

Add to `tests/core/test_brain.py`:
```python
def test_gemini_brain_text_response():
    brain = GeminiBrain(api_key="fake-key", model="gemini-2.0-flash")

    mock_part = MagicMock()
    mock_part.function_call = None
    mock_part.text = "Hello, Hasnine!"

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    with patch.object(brain, "_chat") as mock_chat:
        mock_chat.send_message.return_value = mock_response
        response = brain.think(
            messages=[Message(role="user", content="Hi")],
            tool_declarations=[],
            system_prompt="You are Jarvis.",
        )
    assert response.text == "Hello, Hasnine!"
    assert response.tool_calls == []


def test_gemini_brain_tool_call_response():
    brain = GeminiBrain(api_key="fake-key", model="gemini-2.0-flash")

    mock_fc = MagicMock()
    mock_fc.name = "system_info__cpu_usage"
    mock_fc.args = {}

    mock_part = MagicMock()
    mock_part.function_call = mock_fc
    mock_part.text = ""

    mock_response = MagicMock()
    mock_response.parts = [mock_part]

    with patch.object(brain, "_chat") as mock_chat:
        mock_chat.send_message.return_value = mock_response
        response = brain.think(
            messages=[Message(role="user", content="Check CPU")],
            tool_declarations=[{"name": "system_info__cpu_usage", "description": "Get CPU stats", "parameters": {"type": "object", "properties": {}}}],
            system_prompt="You are Jarvis.",
        )
    assert response.text is None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "system_info__cpu_usage"
```

- [ ] **Step 6: Implement GeminiBrain**

Complete `jarvis/core/brain.py`:
```python
from dataclasses import dataclass, field
from typing import Protocol
import google.generativeai as genai
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.brain")


@dataclass
class Message:
    role: str  # "user", "assistant", "tool_result"
    content: str


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class BrainResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Brain(Protocol):
    def think(self, messages: list[Message], tool_declarations: list[dict], system_prompt: str) -> BrainResponse: ...
    def send_tool_results(self, results: list[dict]) -> BrainResponse: ...


class GeminiBrain:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = None
        self._chat = None

    def _ensure_chat(self, system_prompt: str, tool_declarations: list[dict]):
        """Create or recreate the model and chat with current tools."""
        tools = None
        if tool_declarations:
            tools = [{"function_declarations": tool_declarations}]
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            tools=tools,
        )
        self._chat = self._model.start_chat()

    def think(self, messages: list[Message], tool_declarations: list[dict], system_prompt: str) -> BrainResponse:
        self._ensure_chat(system_prompt, tool_declarations)

        # Replay conversation history
        for msg in messages[:-1]:
            if msg.role == "user":
                self._chat.history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                self._chat.history.append({"role": "model", "parts": [msg.content]})

        # Send the latest user message
        last_message = messages[-1].content if messages else ""
        response = self._chat.send_message(last_message)
        return self._parse_response(response)

    def send_tool_results(self, results: list[dict]) -> BrainResponse:
        """Send tool execution results back to Gemini and get final response."""
        from google.protobuf.struct_pb2 import Struct

        parts = []
        for result in results:
            s = Struct()
            s.update({"result": result["output"]})
            parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=result["name"], response=s
                    )
                )
            )
        response = self._chat.send_message(parts)
        return self._parse_response(response)

    def _parse_response(self, response) -> BrainResponse:
        tool_calls = []
        text_parts = []

        for part in response.parts:
            if part.function_call and part.function_call.name:
                tool_calls.append(ToolCall(
                    name=part.function_call.name,
                    args=dict(part.function_call.args) if part.function_call.args else {},
                ))
            elif part.text:
                text_parts.append(part.text)

        if tool_calls:
            return BrainResponse(text=None, tool_calls=tool_calls)
        return BrainResponse(text="\n".join(text_parts) if text_parts else "")
```

- [ ] **Step 7: Run all brain tests**

Run: `python -m pytest tests/core/test_brain.py -v`
Expected: 5 PASSED

- [ ] **Step 8: Commit**

```bash
git add jarvis/core/brain.py tests/core/test_brain.py
git commit -m "feat: Gemini brain — LLM protocol, function calling, response parsing"
```

---

### Task 4: Memory System

**Files:**
- Create: `jarvis/core/memory.py`
- Create: `tests/core/test_memory.py`

**Interfaces:**
- Consumes: `Message` from Task 3
- Produces:
  - `class ShortTermMemory` — `add(message: Message)`, `get_messages() -> list[Message]`, `get_summary() -> str`, `clear()`
  - `class LongTermMemory` — `save_fact(key: str, value: str)`, `get_facts() -> list[dict]`, `save_note(content: str)`, `get_notes() -> list[dict]`, `save_session_summary(summary: str)`, `get_last_session_summary() -> str | None`, `search(query: str) -> list[dict]`

- [ ] **Step 1: Write failing tests for ShortTermMemory**

```python
# tests/core/test_memory.py
import pytest
from jarvis.core.brain import Message
from jarvis.core.memory import ShortTermMemory, LongTermMemory


def test_short_term_add_and_get():
    mem = ShortTermMemory(max_messages=5)
    mem.add(Message(role="user", content="Hello"))
    mem.add(Message(role="assistant", content="Hi there"))
    messages = mem.get_messages()
    assert len(messages) == 2
    assert messages[0].content == "Hello"


def test_short_term_respects_max():
    mem = ShortTermMemory(max_messages=3)
    for i in range(5):
        mem.add(Message(role="user", content=f"msg {i}"))
    messages = mem.get_messages()
    assert len(messages) == 3
    assert messages[0].content == "msg 2"


def test_short_term_clear():
    mem = ShortTermMemory(max_messages=10)
    mem.add(Message(role="user", content="Hello"))
    mem.clear()
    assert len(mem.get_messages()) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_memory.py::test_short_term_add_and_get -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write failing tests for LongTermMemory**

Add to `tests/core/test_memory.py`:
```python
def test_long_term_save_and_get_fact(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    mem = LongTermMemory(db_path=db_path)
    mem.save_fact("favorite_color", "blue")
    facts = mem.get_facts()
    assert len(facts) == 1
    assert facts[0]["key"] == "favorite_color"
    assert facts[0]["value"] == "blue"


def test_long_term_update_existing_fact(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    mem = LongTermMemory(db_path=db_path)
    mem.save_fact("name", "Hasnine")
    mem.save_fact("name", "Hasnine Kabir")
    facts = mem.get_facts()
    assert len(facts) == 1
    assert facts[0]["value"] == "Hasnine Kabir"


def test_long_term_save_and_get_note(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    mem = LongTermMemory(db_path=db_path)
    mem.save_note("Buy groceries")
    mem.save_note("Call dentist")
    notes = mem.get_notes()
    assert len(notes) == 2


def test_long_term_session_summary(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    mem = LongTermMemory(db_path=db_path)
    mem.save_session_summary("User asked about weather and CPU stats.")
    summary = mem.get_last_session_summary()
    assert "weather" in summary


def test_long_term_search(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    mem = LongTermMemory(db_path=db_path)
    mem.save_note("Buy groceries at the store")
    mem.save_note("Call dentist tomorrow")
    results = mem.search("groceries")
    assert len(results) >= 1
    assert "groceries" in results[0]["content"]
```

- [ ] **Step 4: Implement memory system**

`jarvis/core/memory.py`:
```python
import sqlite3
from datetime import datetime
from jarvis.core.brain import Message
from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.memory")


class ShortTermMemory:
    def __init__(self, max_messages: int = 50):
        self._messages: list[Message] = []
        self._max = max_messages

    def add(self, message: Message) -> None:
        self._messages.append(message)
        if len(self._messages) > self._max:
            self._messages = self._messages[-self._max:]

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()


class LongTermMemory:
    def __init__(self, db_path: str = "memory.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def save_fact(self, key: str, value: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
            (key, value, now, value, now),
        )
        self._conn.commit()

    def get_facts(self) -> list[dict]:
        rows = self._conn.execute("SELECT key, value FROM facts ORDER BY updated_at DESC").fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]

    def save_note(self, content: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute("INSERT INTO notes (content, created_at) VALUES (?, ?)", (content, now))
        self._conn.commit()

    def get_notes(self) -> list[dict]:
        rows = self._conn.execute("SELECT id, content, created_at FROM notes ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "content": r["content"], "created_at": r["created_at"]} for r in rows]

    def save_session_summary(self, summary: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute("INSERT INTO history (summary, created_at) VALUES (?, ?)", (summary, now))
        self._conn.commit()

    def get_last_session_summary(self) -> str | None:
        row = self._conn.execute("SELECT summary FROM history ORDER BY created_at DESC LIMIT 1").fetchone()
        return row["summary"] if row else None

    def search(self, query: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT 'note' as type, content, created_at FROM notes WHERE content LIKE ? "
            "UNION ALL "
            "SELECT 'fact' as type, key || ': ' || value as content, updated_at as created_at FROM facts WHERE key LIKE ? OR value LIKE ? "
            "ORDER BY created_at DESC",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [{"type": r["type"], "content": r["content"]} for r in rows]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 5: Run all memory tests**

Run: `python -m pytest tests/core/test_memory.py -v`
Expected: 8 PASSED

- [ ] **Step 6: Commit**

```bash
git add jarvis/core/memory.py tests/core/test_memory.py
git commit -m "feat: memory system — short-term message buffer + long-term SQLite storage"
```

---

### Task 5: Orchestrator + Terminal UI

**Files:**
- Create: `jarvis/core/orchestrator.py`
- Create: `jarvis/ui/terminal.py`
- Modify: `jarvis/__main__.py`
- Create: `tests/core/test_orchestrator.py`

**Interfaces:**
- Consumes: `Brain`, `BrainResponse`, `Message`, `ToolCall` from Task 3; `SkillRegistry` from Task 2; `ShortTermMemory`, `LongTermMemory` from Task 4; `Config` from Task 1
- Produces:
  - `class Orchestrator` — `process(user_input: str) -> str`, `get_system_prompt() -> str`
  - `class TerminalUI` — `run() -> None`, `display_response(text: str)`, `display_action(action: str, status: str)`, `get_input() -> str`

- [ ] **Step 1: Write failing test for Orchestrator**

```python
# tests/core/test_orchestrator.py
import pytest
from unittest.mock import MagicMock
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.brain import Message, BrainResponse, ToolCall
from jarvis.core.memory import ShortTermMemory, LongTermMemory
from jarvis.core.skill_registry import SkillRegistry


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.think.return_value = BrainResponse(text="Hello, Hasnine!", tool_calls=[])
    return brain


@pytest.fixture
def orchestrator(mock_brain, tmp_path):
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "user.name": "Hasnine",
        "jarvis.personality": "You are Jarvis.",
        "llm.max_history": 50,
    }.get(key, default)

    registry = SkillRegistry()
    short_mem = ShortTermMemory(max_messages=50)
    long_mem = LongTermMemory(db_path=str(tmp_path / "test.db"))

    return Orchestrator(
        brain=mock_brain,
        config=config,
        skill_registry=registry,
        short_term_memory=short_mem,
        long_term_memory=long_mem,
    )


def test_orchestrator_simple_response(orchestrator, mock_brain):
    result = orchestrator.process("Hi there")
    assert result == "Hello, Hasnine!"
    mock_brain.think.assert_called_once()


def test_orchestrator_tool_call(orchestrator, mock_brain):
    # First call returns tool call, second returns text
    mock_brain.think.return_value = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="system_info__cpu_usage", args={})]
    )
    mock_brain.send_tool_results.return_value = BrainResponse(
        text="CPU is at 25%.", tool_calls=[]
    )
    orchestrator._skill_registry.register(MagicMock(
        name="system_info",
        execute=MagicMock(return_value="CPU: 25%, Battery: 80%"),
    ))

    result = orchestrator.process("Check CPU")
    assert "25%" in result


def test_orchestrator_stores_messages(orchestrator, mock_brain):
    orchestrator.process("Hello")
    messages = orchestrator._short_term_memory.get_messages()
    assert len(messages) == 2  # user message + assistant response
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_orchestrator.py::test_orchestrator_simple_response -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Orchestrator**

`jarvis/core/orchestrator.py`:
```python
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
```

- [ ] **Step 4: Run orchestrator tests**

Run: `python -m pytest tests/core/test_orchestrator.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Implement Terminal UI**

`jarvis/ui/terminal.py`:
```python
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
```

- [ ] **Step 6: Wire up __main__.py**

`jarvis/__main__.py`:
```python
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
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 8: Commit**

```bash
git add jarvis/core/orchestrator.py jarvis/ui/terminal.py jarvis/__main__.py tests/core/test_orchestrator.py
git commit -m "feat: orchestrator + terminal UI — main loop with rich interface"
```

---

### Task 6: System Skills (system_info, screenshot, pc_control)

**Files:**
- Create: `jarvis/skills/system_info.py`
- Create: `jarvis/skills/screenshot.py`
- Create: `jarvis/skills/pc_control.py`
- Create: `tests/skills/test_system_info.py`
- Create: `tests/skills/test_pc_control.py`
- Create: `tests/skills/test_screenshot.py`

**Interfaces:**
- Consumes: `BaseSkill`, `Tool` from Task 2
- Produces: Three auto-discoverable skill classes

- [ ] **Step 1: Write failing tests for system_info**

```python
# tests/skills/test_system_info.py
from jarvis.skills.system_info import SystemInfoSkill


def test_system_info_cpu_usage():
    skill = SystemInfoSkill()
    result = skill.execute("cpu_usage", {})
    assert "CPU" in result
    assert "%" in result


def test_system_info_current_time():
    skill = SystemInfoSkill()
    result = skill.execute("current_time", {})
    assert ":" in result  # time format contains colons


def test_system_info_weather():
    skill = SystemInfoSkill()
    result = skill.execute("weather", {})
    # Should return something even if API fails
    assert isinstance(result, str)
    assert len(result) > 0


def test_system_info_has_tools():
    skill = SystemInfoSkill()
    tool_names = [t.name for t in skill.tools]
    assert "cpu_usage" in tool_names
    assert "current_time" in tool_names
    assert "weather" in tool_names
```

- [ ] **Step 2: Implement system_info skill**

`jarvis/skills/system_info.py`:
```python
import datetime
import psutil
import requests
import geocoder
from jarvis.skills.base import BaseSkill, Tool


class SystemInfoSkill(BaseSkill):
    name = "system_info"
    description = "Get system information like CPU usage, battery level, current time, and weather"
    tools = [
        Tool(
            name="cpu_usage",
            description="Get current CPU usage percentage and battery level",
            parameters={},
        ),
        Tool(
            name="current_time",
            description="Get current date and time",
            parameters={},
        ),
        Tool(
            name="weather",
            description="Get current weather for the user's location",
            parameters={},
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "cpu_usage":
            return self._cpu_usage()
        elif action == "current_time":
            return self._current_time()
        elif action == "weather":
            return self._weather()
        raise ValueError(f"Unknown action: {action}")

    def _cpu_usage(self) -> str:
        cpu = psutil.cpu_percent(interval=1)
        battery = psutil.sensors_battery()
        result = f"CPU: {cpu}%"
        if battery:
            result += f", Battery: {battery.percent}%"
            if battery.power_plugged:
                result += " (plugged in)"
        return result

    def _current_time(self) -> str:
        now = datetime.datetime.now()
        return now.strftime("It's %A, %B %d, %Y at %I:%M %p")

    def _weather(self) -> str:
        try:
            g = geocoder.ip("me")
            if not g.latlng:
                return "Could not determine location for weather."
            lat, lon = g.latlng
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            weather = data["current_weather"]
            return (
                f"Temperature: {weather['temperature']}°C, "
                f"Wind speed: {weather['windspeed']} km/h, "
                f"Conditions: {'Clear' if weather['weathercode'] == 0 else 'Cloudy/Other'}"
            )
        except Exception as e:
            return f"Weather unavailable: {e}"
```

- [ ] **Step 3: Write failing tests for screenshot**

```python
# tests/skills/test_screenshot.py
from unittest.mock import patch, MagicMock
from jarvis.skills.screenshot import ScreenshotSkill


def test_screenshot_take(tmp_path):
    skill = ScreenshotSkill()
    with patch("jarvis.skills.screenshot.pyautogui") as mock_gui:
        mock_img = MagicMock()
        mock_gui.screenshot.return_value = mock_img
        result = skill.execute("take_screenshot", {"path": str(tmp_path / "test.png")})
        mock_img.save.assert_called_once()
        assert "saved" in result.lower() or "screenshot" in result.lower()


def test_screenshot_has_tools():
    skill = ScreenshotSkill()
    assert len(skill.tools) >= 1
    assert skill.tools[0].name == "take_screenshot"
```

- [ ] **Step 4: Implement screenshot skill**

`jarvis/skills/screenshot.py`:
```python
import os
import datetime
import pyautogui
from jarvis.skills.base import BaseSkill, Tool


class ScreenshotSkill(BaseSkill):
    name = "screenshot"
    description = "Take screenshots and save them to disk"
    tools = [
        Tool(
            name="take_screenshot",
            description="Take a screenshot and save it. Optionally specify a file path.",
            parameters={
                "path": {"type": "string", "description": "File path to save screenshot. Defaults to desktop."},
            },
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "take_screenshot":
            return self._take(args.get("path", ""))
        raise ValueError(f"Unknown action: {action}")

    def _take(self, path: str) -> str:
        if not path:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"screenshot_{timestamp}.png")
        img = pyautogui.screenshot()
        img.save(path)
        return f"Screenshot saved to {path}"
```

- [ ] **Step 5: Write failing tests for pc_control**

```python
# tests/skills/test_pc_control.py
import os
from unittest.mock import patch
from jarvis.skills.pc_control import PCControlSkill


def test_pc_control_run_command():
    skill = PCControlSkill()
    result = skill.execute("run_command", {"command": "echo hello"})
    assert "hello" in result.lower()


def test_pc_control_list_directory(tmp_path):
    # Create a test file
    (tmp_path / "test.txt").write_text("hello")
    skill = PCControlSkill()
    result = skill.execute("list_directory", {"path": str(tmp_path)})
    assert "test.txt" in result


def test_pc_control_open_app():
    skill = PCControlSkill()
    with patch("jarvis.skills.pc_control.subprocess.Popen") as mock_popen:
        result = skill.execute("open_application", {"app_name": "notepad"})
        assert isinstance(result, str)


def test_pc_control_has_tools():
    skill = PCControlSkill()
    tool_names = [t.name for t in skill.tools]
    assert "run_command" in tool_names
    assert "open_application" in tool_names
    assert "list_directory" in tool_names
```

- [ ] **Step 6: Implement pc_control skill**

`jarvis/skills/pc_control.py`:
```python
import os
import subprocess
from jarvis.skills.base import BaseSkill, Tool


class PCControlSkill(BaseSkill):
    name = "pc_control"
    description = "Control the PC: open applications, run shell commands, manage files and directories"
    tools = [
        Tool(
            name="run_command",
            description="Run a shell command and return its output",
            parameters={
                "command": {"type": "string", "description": "The shell command to execute"},
            },
            required=["command"],
        ),
        Tool(
            name="open_application",
            description="Open an application by name (e.g., 'notepad', 'chrome', 'code')",
            parameters={
                "app_name": {"type": "string", "description": "Name of the application to open"},
            },
            required=["app_name"],
        ),
        Tool(
            name="list_directory",
            description="List files and folders in a directory",
            parameters={
                "path": {"type": "string", "description": "Directory path. Defaults to current directory."},
            },
        ),
        Tool(
            name="read_file",
            description="Read the contents of a text file",
            parameters={
                "path": {"type": "string", "description": "Path to the file to read"},
            },
            required=["path"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "run_command":
            return self._run_command(args["command"])
        elif action == "open_application":
            return self._open_app(args["app_name"])
        elif action == "list_directory":
            return self._list_dir(args.get("path", "."))
        elif action == "read_file":
            return self._read_file(args["path"])
        raise ValueError(f"Unknown action: {action}")

    def _run_command(self, command: str) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout or result.stderr
            return output.strip() if output.strip() else "Command executed successfully (no output)."
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as e:
            return f"Error running command: {e}"

    def _open_app(self, app_name: str) -> str:
        try:
            subprocess.Popen(app_name, shell=True)
            return f"Opened {app_name}."
        except Exception as e:
            return f"Failed to open {app_name}: {e}"

    def _list_dir(self, path: str) -> str:
        try:
            entries = os.listdir(path)
            if not entries:
                return f"{path} is empty."
            return "\n".join(entries)
        except Exception as e:
            return f"Error listing directory: {e}"

    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(10000)  # cap at 10k chars
            return content if content else "(empty file)"
        except Exception as e:
            return f"Error reading file: {e}"
```

- [ ] **Step 7: Run all system skill tests**

Run: `python -m pytest tests/skills/test_system_info.py tests/skills/test_screenshot.py tests/skills/test_pc_control.py -v`
Expected: All PASSED

- [ ] **Step 8: Commit**

```bash
git add jarvis/skills/system_info.py jarvis/skills/screenshot.py jarvis/skills/pc_control.py tests/skills/
git commit -m "feat: system skills — system_info, screenshot, pc_control"
```

---

### Task 7: Knowledge Skills (web_search, wikipedia_search, code_helper)

**Files:**
- Create: `jarvis/skills/web_search.py`
- Create: `jarvis/skills/wikipedia_search.py`
- Create: `jarvis/skills/code_helper.py`
- Create: `tests/skills/test_web_search.py`
- Create: `tests/skills/test_wikipedia_search.py`
- Create: `tests/skills/test_code_helper.py`

**Interfaces:**
- Consumes: `BaseSkill`, `Tool` from Task 2
- Produces: Three auto-discoverable skill classes

- [ ] **Step 1: Write failing tests for web_search**

```python
# tests/skills/test_web_search.py
from unittest.mock import patch, MagicMock
from jarvis.skills.web_search import WebSearchSkill


def test_web_search_google(monkeypatch):
    skill = WebSearchSkill()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><body><div class="BNeawe">Test result snippet</div></body></html>'
    with patch("jarvis.skills.web_search.requests.get", return_value=mock_resp):
        result = skill.execute("google_search", {"query": "python programming"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_web_search_has_tools():
    skill = WebSearchSkill()
    tool_names = [t.name for t in skill.tools]
    assert "google_search" in tool_names
```

- [ ] **Step 2: Implement web_search skill**

`jarvis/skills/web_search.py`:
```python
import webbrowser
import requests
from bs4 import BeautifulSoup
from jarvis.skills.base import BaseSkill, Tool


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web using Google and optionally open results in browser"
    tools = [
        Tool(
            name="google_search",
            description="Search Google and return top result snippets",
            parameters={
                "query": {"type": "string", "description": "Search query"},
            },
            required=["query"],
        ),
        Tool(
            name="open_url",
            description="Open a URL in the default web browser",
            parameters={
                "url": {"type": "string", "description": "URL to open"},
            },
            required=["url"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "google_search":
            return self._search(args["query"])
        elif action == "open_url":
            return self._open_url(args["url"])
        raise ValueError(f"Unknown action: {action}")

    def _search(self, query: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(
                f"https://www.google.com/search?q={query}",
                headers=headers,
                timeout=10,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = []
            for div in soup.find_all("div", class_="BNeawe")[:5]:
                text = div.get_text().strip()
                if text and len(text) > 20:
                    snippets.append(text)
            if snippets:
                return "\n\n".join(snippets[:3])
            return f"No clear snippets found. You can open the search in browser."
        except Exception as e:
            return f"Search failed: {e}"

    def _open_url(self, url: str) -> str:
        try:
            webbrowser.open(url)
            return f"Opened {url} in browser."
        except Exception as e:
            return f"Failed to open URL: {e}"
```

- [ ] **Step 3: Write failing tests for wikipedia_search**

```python
# tests/skills/test_wikipedia_search.py
from unittest.mock import patch
from jarvis.skills.wikipedia_search import WikipediaSearchSkill


def test_wikipedia_search():
    skill = WikipediaSearchSkill()
    with patch("jarvis.skills.wikipedia_search.wikipedia") as mock_wiki:
        mock_wiki.summary.return_value = "Python is a programming language."
        result = skill.execute("search", {"query": "Python programming"})
    assert "Python" in result


def test_wikipedia_disambiguation():
    skill = WikipediaSearchSkill()
    with patch("jarvis.skills.wikipedia_search.wikipedia") as mock_wiki:
        import wikipedia as wiki_mod
        mock_wiki.exceptions = wiki_mod.exceptions
        mock_wiki.summary.side_effect = wiki_mod.exceptions.DisambiguationError("Python", ["Python (programming)", "Python (snake)"])
        result = skill.execute("search", {"query": "Python"})
    assert isinstance(result, str)
```

- [ ] **Step 4: Implement wikipedia_search skill**

`jarvis/skills/wikipedia_search.py`:
```python
import wikipedia
from jarvis.skills.base import BaseSkill, Tool


class WikipediaSearchSkill(BaseSkill):
    name = "wikipedia_search"
    description = "Search Wikipedia for information on any topic"
    tools = [
        Tool(
            name="search",
            description="Search Wikipedia and return a summary",
            parameters={
                "query": {"type": "string", "description": "Topic to search for"},
                "sentences": {"type": "integer", "description": "Number of sentences to return (default 3)"},
            },
            required=["query"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "search":
            return self._search(args["query"], args.get("sentences", 3))
        raise ValueError(f"Unknown action: {action}")

    def _search(self, query: str, sentences: int = 3) -> str:
        try:
            return wikipedia.summary(query, sentences=sentences)
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            return f"Ambiguous query. Did you mean: {', '.join(options)}?"
        except wikipedia.exceptions.PageError:
            return f"No Wikipedia page found for '{query}'."
        except Exception as e:
            return f"Wikipedia search failed: {e}"
```

- [ ] **Step 5: Write failing tests for code_helper**

```python
# tests/skills/test_code_helper.py
import os
from jarvis.skills.code_helper import CodeHelperSkill


def test_code_helper_read_file(tmp_path):
    test_file = tmp_path / "example.py"
    test_file.write_text("def hello():\n    print('world')\n")
    skill = CodeHelperSkill()
    result = skill.execute("read_code", {"path": str(test_file)})
    assert "def hello" in result


def test_code_helper_list_project(tmp_path):
    (tmp_path / "main.py").write_text("pass")
    (tmp_path / "utils.py").write_text("pass")
    (tmp_path / "node_modules").mkdir()
    skill = CodeHelperSkill()
    result = skill.execute("list_project", {"path": str(tmp_path)})
    assert "main.py" in result
    assert "utils.py" in result


def test_code_helper_has_tools():
    skill = CodeHelperSkill()
    tool_names = [t.name for t in skill.tools]
    assert "read_code" in tool_names
    assert "list_project" in tool_names
```

- [ ] **Step 6: Implement code_helper skill**

`jarvis/skills/code_helper.py`:
```python
import os
from pathlib import Path
from jarvis.skills.base import BaseSkill, Tool

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode"}


class CodeHelperSkill(BaseSkill):
    name = "code_helper"
    description = "Help with coding: read source files, explore project structure"
    tools = [
        Tool(
            name="read_code",
            description="Read the contents of a source code file",
            parameters={
                "path": {"type": "string", "description": "Path to the source file"},
            },
            required=["path"],
        ),
        Tool(
            name="list_project",
            description="List the structure of a project directory (files and folders)",
            parameters={
                "path": {"type": "string", "description": "Project root directory path. Defaults to current directory."},
                "max_depth": {"type": "integer", "description": "Maximum depth to traverse (default 3)"},
            },
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "read_code":
            return self._read_code(args["path"])
        elif action == "list_project":
            return self._list_project(args.get("path", "."), args.get("max_depth", 3))
        raise ValueError(f"Unknown action: {action}")

    def _read_code(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50000)  # cap at 50k chars
            lines = content.split("\n")
            numbered = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
            return "\n".join(numbered)
        except Exception as e:
            return f"Error reading file: {e}"

    def _list_project(self, path: str, max_depth: int = 3) -> str:
        lines = []
        root = Path(path)
        self._walk(root, lines, prefix="", depth=0, max_depth=max_depth)
        return "\n".join(lines) if lines else "(empty directory)"

    def _walk(self, path: Path, lines: list, prefix: str, depth: int, max_depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            if entry.name in IGNORE_DIRS:
                continue
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk(entry, lines, prefix + extension, depth + 1, max_depth)
```

- [ ] **Step 7: Run all knowledge skill tests**

Run: `python -m pytest tests/skills/test_web_search.py tests/skills/test_wikipedia_search.py tests/skills/test_code_helper.py -v`
Expected: All PASSED

- [ ] **Step 8: Commit**

```bash
git add jarvis/skills/web_search.py jarvis/skills/wikipedia_search.py jarvis/skills/code_helper.py tests/skills/
git commit -m "feat: knowledge skills — web_search, wikipedia_search, code_helper"
```

---

### Task 8: Personal Skills (notes, email_sender, media)

**Files:**
- Create: `jarvis/skills/notes.py`
- Create: `jarvis/skills/email_sender.py`
- Create: `jarvis/skills/media.py`
- Create: `tests/skills/test_notes.py`
- Create: `tests/skills/test_email_sender.py`
- Create: `tests/skills/test_media.py`

**Interfaces:**
- Consumes: `BaseSkill`, `Tool` from Task 2; `LongTermMemory` from Task 4
- Produces: Three auto-discoverable skill classes

- [ ] **Step 1: Write failing tests for notes skill**

```python
# tests/skills/test_notes.py
from jarvis.skills.notes import NotesSkill
from jarvis.core.memory import LongTermMemory


def test_notes_save_note(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    skill = NotesSkill(memory=mem)
    result = skill.execute("save_note", {"content": "Buy groceries"})
    assert "saved" in result.lower() or "noted" in result.lower()


def test_notes_get_notes(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    skill = NotesSkill(memory=mem)
    skill.execute("save_note", {"content": "Buy groceries"})
    skill.execute("save_note", {"content": "Call dentist"})
    result = skill.execute("get_notes", {})
    assert "groceries" in result
    assert "dentist" in result


def test_notes_save_fact(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    skill = NotesSkill(memory=mem)
    result = skill.execute("save_fact", {"key": "favorite_color", "value": "blue"})
    assert "saved" in result.lower() or "remembered" in result.lower()


def test_notes_get_facts(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    skill = NotesSkill(memory=mem)
    skill.execute("save_fact", {"key": "favorite_color", "value": "blue"})
    result = skill.execute("get_facts", {})
    assert "blue" in result


def test_notes_search(tmp_path):
    mem = LongTermMemory(db_path=str(tmp_path / "test.db"))
    skill = NotesSkill(memory=mem)
    skill.execute("save_note", {"content": "Meeting with John at 3pm"})
    result = skill.execute("search_memory", {"query": "John"})
    assert "John" in result
```

- [ ] **Step 2: Implement notes skill**

`jarvis/skills/notes.py`:
```python
from jarvis.skills.base import BaseSkill, Tool
from jarvis.core.memory import LongTermMemory


class NotesSkill(BaseSkill):
    name = "notes"
    description = "Save and retrieve notes, facts, and memories"
    tools = [
        Tool(
            name="save_note",
            description="Save a note or reminder for the user",
            parameters={
                "content": {"type": "string", "description": "The note content to save"},
            },
            required=["content"],
        ),
        Tool(
            name="get_notes",
            description="Retrieve all saved notes",
            parameters={},
        ),
        Tool(
            name="save_fact",
            description="Save a fact about the user (e.g., preferences, personal info)",
            parameters={
                "key": {"type": "string", "description": "Fact key (e.g., 'favorite_color')"},
                "value": {"type": "string", "description": "Fact value (e.g., 'blue')"},
            },
            required=["key", "value"],
        ),
        Tool(
            name="get_facts",
            description="Retrieve all known facts about the user",
            parameters={},
        ),
        Tool(
            name="search_memory",
            description="Search through all notes and facts",
            parameters={
                "query": {"type": "string", "description": "Search query"},
            },
            required=["query"],
        ),
    ]

    def __init__(self, memory: LongTermMemory | None = None):
        self._memory = memory

    def set_memory(self, memory: LongTermMemory) -> None:
        """Allow orchestrator to inject memory after construction."""
        self._memory = memory

    def execute(self, action: str, args: dict) -> str:
        if not self._memory:
            return "Error: memory system not initialized."
        if action == "save_note":
            self._memory.save_note(args["content"])
            return f"Noted: {args['content']}"
        elif action == "get_notes":
            notes = self._memory.get_notes()
            if not notes:
                return "No notes saved yet."
            return "\n".join(f"- {n['content']}" for n in notes)
        elif action == "save_fact":
            self._memory.save_fact(args["key"], args["value"])
            return f"Remembered: {args['key']} = {args['value']}"
        elif action == "get_facts":
            facts = self._memory.get_facts()
            if not facts:
                return "No facts saved yet."
            return "\n".join(f"- {f['key']}: {f['value']}" for f in facts)
        elif action == "search_memory":
            results = self._memory.search(args["query"])
            if not results:
                return f"Nothing found for '{args['query']}'."
            return "\n".join(f"- [{r['type']}] {r['content']}" for r in results)
        raise ValueError(f"Unknown action: {action}")
```

- [ ] **Step 3: Write failing tests for email_sender**

```python
# tests/skills/test_email_sender.py
from unittest.mock import patch, MagicMock
from jarvis.skills.email_sender import EmailSenderSkill


def test_email_send():
    skill = EmailSenderSkill(smtp_email="test@test.com", smtp_password="pass123")
    with patch("jarvis.skills.email_sender.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        result = skill.execute("send_email", {
            "to": "someone@example.com",
            "subject": "Test",
            "body": "Hello!",
        })
    mock_server.sendmail.assert_called_once()
    assert "sent" in result.lower()


def test_email_send_no_creds():
    skill = EmailSenderSkill(smtp_email="", smtp_password="")
    result = skill.execute("send_email", {
        "to": "someone@example.com",
        "subject": "Test",
        "body": "Hello!",
    })
    assert "not configured" in result.lower() or "error" in result.lower()
```

- [ ] **Step 4: Implement email_sender skill**

`jarvis/skills/email_sender.py`:
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jarvis.skills.base import BaseSkill, Tool


class EmailSenderSkill(BaseSkill):
    name = "email_sender"
    description = "Send emails via Gmail SMTP"
    tools = [
        Tool(
            name="send_email",
            description="Send an email to a recipient",
            parameters={
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body text"},
            },
            required=["to", "subject", "body"],
        ),
    ]

    def __init__(self, smtp_email: str = "", smtp_password: str = ""):
        self._email = smtp_email
        self._password = smtp_password

    def execute(self, action: str, args: dict) -> str:
        if action == "send_email":
            return self._send(args["to"], args["subject"], args["body"])
        raise ValueError(f"Unknown action: {action}")

    def _send(self, to: str, subject: str, body: str) -> str:
        if not self._email or not self._password:
            return "Email not configured. Set SMTP_EMAIL and SMTP_PASSWORD in .env."
        try:
            msg = MIMEMultipart()
            msg["From"] = self._email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.ehlo()
            server.starttls()
            server.login(self._email, self._password)
            server.sendmail(self._email, to, msg.as_string())
            server.close()
            return f"Email sent to {to}."
        except Exception as e:
            return f"Failed to send email: {e}"
```

- [ ] **Step 5: Write failing tests for media**

```python
# tests/skills/test_media.py
import webbrowser
from unittest.mock import patch
from jarvis.skills.media import MediaSkill


def test_media_play_music(tmp_path):
    test_file = tmp_path / "song.mp3"
    test_file.write_text("fake")
    skill = MediaSkill()
    with patch("jarvis.skills.media.os.startfile") as mock_start:
        result = skill.execute("play_music", {"path": str(test_file)})
    assert isinstance(result, str)


def test_media_search_youtube():
    skill = MediaSkill()
    with patch("jarvis.skills.media.webbrowser.open") as mock_open:
        result = skill.execute("search_youtube", {"query": "python tutorial"})
    mock_open.assert_called_once()
    assert "youtube" in result.lower() or "opened" in result.lower()


def test_media_has_tools():
    skill = MediaSkill()
    tool_names = [t.name for t in skill.tools]
    assert "play_music" in tool_names
    assert "search_youtube" in tool_names
```

- [ ] **Step 6: Implement media skill**

`jarvis/skills/media.py`:
```python
import os
import webbrowser
from jarvis.skills.base import BaseSkill, Tool


class MediaSkill(BaseSkill):
    name = "media"
    description = "Play music and search YouTube"
    tools = [
        Tool(
            name="play_music",
            description="Play a music file from the local filesystem",
            parameters={
                "path": {"type": "string", "description": "Path to the music file"},
            },
            required=["path"],
        ),
        Tool(
            name="search_youtube",
            description="Search YouTube for videos and open results in browser",
            parameters={
                "query": {"type": "string", "description": "YouTube search query"},
            },
            required=["query"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "play_music":
            return self._play(args["path"])
        elif action == "search_youtube":
            return self._search_youtube(args["query"])
        raise ValueError(f"Unknown action: {action}")

    def _play(self, path: str) -> str:
        if not os.path.exists(path):
            return f"File not found: {path}"
        try:
            os.startfile(path)
            return f"Now playing: {os.path.basename(path)}"
        except AttributeError:
            # os.startfile is Windows-only; fall back to xdg-open/open
            import subprocess
            subprocess.Popen(["xdg-open", path])
            return f"Now playing: {os.path.basename(path)}"
        except Exception as e:
            return f"Failed to play: {e}"

    def _search_youtube(self, query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Opened YouTube search for: {query}"
```

- [ ] **Step 7: Update orchestrator to inject memory into NotesSkill**

In `jarvis/core/orchestrator.py`, add to `__init__` after storing `long_term_memory`:
```python
        # Inject memory into notes skill if present
        notes_skill = self._skill_registry.get_skill("notes")
        if notes_skill and hasattr(notes_skill, "set_memory"):
            notes_skill.set_memory(self._long_term_memory)
```

Also update `jarvis/core/skill_registry.py` `discover()` to handle skills that need config. In `jarvis/__main__.py`, after `skill_registry.discover()`:
```python
    # Inject dependencies into skills that need them
    notes_skill = skill_registry.get_skill("notes")
    if notes_skill and hasattr(notes_skill, "set_memory"):
        notes_skill.set_memory(long_mem)

    email_skill = skill_registry.get_skill("email_sender")
    if email_skill and hasattr(email_skill, "_email"):
        email_skill._email = config.smtp_email
        email_skill._password = config.smtp_password
```

- [ ] **Step 8: Run all personal skill tests**

Run: `python -m pytest tests/skills/test_notes.py tests/skills/test_email_sender.py tests/skills/test_media.py -v`
Expected: All PASSED

- [ ] **Step 9: Commit**

```bash
git add jarvis/skills/notes.py jarvis/skills/email_sender.py jarvis/skills/media.py jarvis/__main__.py jarvis/core/orchestrator.py tests/skills/
git commit -m "feat: personal skills — notes, email_sender, media"
```

---

### Task 9: Integration Test + End-to-End Verification

**Files:**
- Create: `tests/test_integration.py`
- Modify: `jarvis/__main__.py` (if needed)

**Interfaces:**
- Consumes: everything from Tasks 1-8
- Produces: a fully verified, runnable system

- [ ] **Step 1: Write integration test with mocked Gemini**

```python
# tests/test_integration.py
"""End-to-end integration test with mocked LLM."""
import pytest
from unittest.mock import MagicMock, patch
from jarvis.config import Config
from jarvis.core.brain import GeminiBrain, Message, BrainResponse, ToolCall
from jarvis.core.memory import ShortTermMemory, LongTermMemory
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.skill_registry import SkillRegistry


@pytest.fixture
def system(tmp_path):
    """Build a complete Jarvis system with mocked brain."""
    config = MagicMock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        "user.name": "TestUser",
        "jarvis.personality": "You are Jarvis, a test assistant.",
        "llm.max_history": 50,
    }.get(key, default)
    config.gemini_api_key = "fake-key"
    config.smtp_email = ""
    config.smtp_password = ""

    brain = MagicMock(spec=GeminiBrain)
    registry = SkillRegistry()
    registry.discover()

    short_mem = ShortTermMemory(max_messages=50)
    long_mem = LongTermMemory(db_path=str(tmp_path / "test.db"))

    # Inject memory into notes skill
    notes_skill = registry.get_skill("notes")
    if notes_skill and hasattr(notes_skill, "set_memory"):
        notes_skill.set_memory(long_mem)

    orchestrator = Orchestrator(
        brain=brain,
        config=config,
        skill_registry=registry,
        short_term_memory=short_mem,
        long_term_memory=long_mem,
    )
    return orchestrator, brain, registry, long_mem


def test_simple_conversation(system):
    orchestrator, brain, _, _ = system
    brain.think.return_value = BrainResponse(text="Hello, TestUser!")
    result = orchestrator.process("Hi there")
    assert result == "Hello, TestUser!"


def test_tool_call_flow(system):
    orchestrator, brain, registry, _ = system
    # Brain calls system_info cpu_usage
    brain.think.return_value = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="system_info__cpu_usage", args={})],
    )
    brain.send_tool_results.return_value = BrainResponse(text="CPU is at 30%.")
    result = orchestrator.process("How's my CPU?")
    assert "30%" in result
    brain.send_tool_results.assert_called_once()


def test_notes_round_trip(system):
    orchestrator, brain, _, long_mem = system
    # Brain calls notes save_note
    brain.think.return_value = BrainResponse(
        text=None,
        tool_calls=[ToolCall(name="notes__save_note", args={"content": "Buy milk"})],
    )
    brain.send_tool_results.return_value = BrainResponse(text="Got it, I'll remember that.")
    orchestrator.process("Remember to buy milk")

    # Verify it's in the database
    notes = long_mem.get_notes()
    assert any("milk" in n["content"] for n in notes)


def test_skill_discovery(system):
    _, _, registry, _ = system
    skills = registry.get_all_skills()
    skill_names = [s.name for s in skills]
    # All Phase 1 skills should be discovered
    assert "system_info" in skill_names
    assert "pc_control" in skill_names
    assert "screenshot" in skill_names
    assert "web_search" in skill_names
    assert "wikipedia_search" in skill_names
    assert "code_helper" in skill_names
    assert "notes" in skill_names
    assert "email_sender" in skill_names
    assert "media" in skill_names


def test_memory_persists_across_conversations(system):
    orchestrator, brain, _, long_mem = system
    # First conversation
    brain.think.return_value = BrainResponse(text="Hello!")
    orchestrator.process("Hi")
    orchestrator.process("How are you?")
    orchestrator.shutdown()

    # Verify session summary was saved
    summary = long_mem.get_last_session_summary()
    assert summary is not None
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_integration.py -v`
Expected: All PASSED

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASSED

- [ ] **Step 4: Manual smoke test**

1. Set your real Gemini API key in `.env`
2. Run: `python -m jarvis`
3. Verify: greeting panel appears with your name
4. Type: "What time is it?" — verify Jarvis calls system_info and responds
5. Type: "Remember that my favorite color is blue" — verify Jarvis confirms
6. Type: "What's my favorite color?" — verify Jarvis recalls
7. Type: "Check my CPU" — verify Jarvis reports CPU stats
8. Type: "exit" — verify graceful shutdown

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: integration tests — full system verification with mocked brain"
```

- [ ] **Step 6: Final commit with updated __main__.py if any fixes needed**

```bash
git add -A
git commit -m "chore: Phase 1 complete — J.A.R.V.I.S. v2.0 terminal MVP"
```
