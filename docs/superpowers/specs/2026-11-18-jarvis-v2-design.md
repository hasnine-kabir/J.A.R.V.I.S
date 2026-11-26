# J.A.R.V.I.S v2.0 — Full-Fledged AI Assistant

**Date:** 2026-11-18
**Author:** Hasnine Kabir
**Status:** Approved

## Overview

A complete rebuild of J.A.R.V.I.S from a keyword-matching voice assistant into a proper LLM-powered AI assistant. Gemini API as the brain, modular skill system, persistent memory, with terminal-first interface and voice layered on top.

## Architecture: Modular Agent (Approach B)

```
jarvis/
├── __main__.py              → entry point (python -m jarvis)
├── config.py                → loads .env, user preferences
├── core/
│   ├── brain.py             → LLM interface (Gemini, pluggable)
│   ├── memory.py            → conversation history + long-term memory (SQLite)
│   ├── orchestrator.py      → main loop: input → brain → skill execution → response
│   └── skill_registry.py    → discovers and registers skills
├── skills/
│   ├── base.py              → base Skill class all skills inherit from
│   ├── web_search.py        → Google search, browse URLs
│   ├── pc_control.py        → open apps, manage files, run commands
│   ├── system_info.py       → CPU, battery, time, weather
│   ├── media.py             → play music, YouTube search/download
│   ├── email_sender.py      → send emails via SMTP
│   ├── calendar_manager.py  → reminders, schedule (Google Calendar API)
│   ├── code_helper.py       → read repos, explain code, write snippets
│   ├── smart_home.py        → smart home control (Home Assistant API)
│   ├── wikipedia_search.py  → Wikipedia lookups
│   ├── notes.py             → take notes, remember things (persisted)
│   └── screenshot.py        → take and save screenshots
├── voice/
│   ├── listener.py          → speech-to-text (Google STT / Whisper)
│   ├── speaker.py           → text-to-speech (edge-tts / pyttsx3)
│   └── wake_word.py         → "Hey Jarvis" detection (pvporcupine / vosk)
├── ui/
│   ├── terminal.py          → rich terminal interface (phase 1)
│   └── gui.py               → desktop GUI (phase 3, later)
└── utils/
    └── logger.py            → logging
```

Old files (`jarvis.py`, `helpers.py`, etc.) remain untouched. New code lives in the `jarvis/` package.

## Core Brain

The brain takes user input + conversation history + available skills, sends to Gemini, gets back either a text response or tool calls.

### Flow

```
User input
    → Orchestrator packages: system prompt + history + skill schemas + message
    → Gemini API (function calling)
    → Returns: text response OR tool calls
    → Orchestrator executes tool calls via skill registry
    → Feeds results back to Gemini
    → Gemini generates natural language response
    → Response displayed to user
```

### Pluggable LLM Design

`brain.py` defines a `Brain` protocol:

```python
class Brain(Protocol):
    def think(self, messages: list[Message], tools: list[Tool]) -> Response: ...
```

`GeminiBrain` implements this protocol. Future providers (Claude, OpenAI, Ollama) implement the same interface.

### System Prompt

Defines Jarvis's personality, user's name, preferences, and behavioral rules. Stored in config, fully customizable. Loaded with long-term memory facts at startup.

## Skill System

### Base Skill

Every skill inherits from `BaseSkill`:

```python
class BaseSkill:
    name: str                    # "pc_control"
    description: str             # "Controls applications and files on the PC"
    tools: list[Tool]            # list of actions Gemini can call

    def execute(self, action: str, args: dict) -> str:
        # run the action, return result as string
```

### Auto-Discovery

`skill_registry.py` scans the `skills/` folder on startup, imports all modules, finds classes inheriting `BaseSkill`, and registers them. No manual wiring needed. Adding a skill = adding a file.

### Skill Definitions as Gemini Tools

Each skill's `tools` list gets converted to Gemini function declarations. Gemini decides which skills to call based on user intent. No keyword matching.

### Phase 1 Skills (Terminal MVP)

| Skill | What it does |
|---|---|
| `pc_control` | Open/close apps, run shell commands, manage files |
| `system_info` | CPU, battery, time, weather |
| `web_search` | Google search, summarize results |
| `media` | Play music, YouTube search |
| `wikipedia_search` | Wikipedia lookups |
| `notes` | Remember things, retrieve notes |
| `screenshot` | Take screenshots |
| `email_sender` | Send emails |
| `code_helper` | Read files, explain code, write snippets |

### Phase 2 Skills (After Voice)

| Skill | What it does |
|---|---|
| `calendar_manager` | Google Calendar integration |
| `smart_home` | Home Assistant API control |
| `news` | News headlines with AI summarization |

## Memory System

### Short-Term Memory (Conversation Context)

- Last 50 messages stored in a list, sent to Gemini with each request
- When exceeding 50 messages, older messages get summarized by Gemini into a compact summary kept at the top of context
- Conversation summary persists to database on exit

### Long-Term Memory (SQLite)

```
memory.db
├── facts        → things Jarvis learns about the user
│                  ("user's name is Hasnine", "prefers dark mode")
├── notes        → things user explicitly asks Jarvis to remember
│                  ("remember: dentist appointment Friday")
├── history      → conversation summaries from past sessions
│                  (continuity across sessions)
```

### How Memory Works

- User says "my favorite language is Python" → Gemini detects personal fact → calls `notes` skill `save_fact` action → stored in `facts` table
- User says "remember I need to buy groceries" → Gemini recognizes explicit remember request → calls `notes` skill `save_note` action → stored in `notes` table
- Next session → system prompt includes user facts + last session summary → Jarvis knows who you are

No vector database or embeddings. SQLite + keyword search. Sufficient for personal assistant scale.

## Voice Layer (Phase 2)

Voice wraps around the core as an I/O layer. The brain is input-agnostic.

```
Mic → Wake Word → STT → Orchestrator → Brain → Response → TTS → Speaker
                            ↑
Terminal input ─────────────┘
```

### Listener (Speech-to-Text)
- Primary: Google Speech Recognition (free)
- Upgrade path: OpenAI Whisper local model (offline, more accurate)

### Speaker (Text-to-Speech)
- Primary: `edge-tts` — Microsoft Edge TTS, free, natural sounding
- Fallback: `pyttsx3` for offline use

### Wake Word
- Primary: `pvporcupine` — custom wake words, lightweight
- Alternative: `vosk` — fully offline, free

## Terminal UI (Phase 1)

Using `rich` library for polished terminal output:

- Colored, formatted output with distinct styles for Jarvis responses vs. system actions
- Skill execution shown with spinners and checkmarks
- Status bar with system stats on startup
- Command history via `prompt_toolkit`
- Graceful exit on `exit` / `quit` / `goodbye`

## Configuration

`.env` file for secrets:
```
GEMINI_API_KEY=your_key_here
SMTP_EMAIL=your_email
SMTP_PASSWORD=your_app_password
```

`config.yaml` for preferences:
```yaml
user:
  name: Hasnine
jarvis:
  personality: professional but friendly, like the MCU Jarvis
  voice: enabled/disabled
  wake_word: "Hey Jarvis"
llm:
  provider: gemini
  model: gemini-2.0-flash
```

## Build Phases

### Phase 1: Terminal MVP
- Project structure, config, .env
- Core brain with Gemini API + function calling
- Skill system with auto-discovery
- All Phase 1 skills
- Memory system (SQLite)
- Terminal UI with rich

### Phase 2: Voice
- Speech-to-text listener
- Text-to-speech speaker (edge-tts)
- Wake word detection
- Voice/terminal mode toggle

### Phase 3: GUI (Future)
- Desktop overlay or window
- Both voice and text input
- Visual feedback for skill execution

## Dependencies (New)

```
google-generativeai    # Gemini API
rich                   # terminal UI
prompt-toolkit         # input history, autocomplete
python-dotenv          # .env loading
pyyaml                 # config file
aiohttp                # async HTTP for web search
psutil                 # system info (already in repo)
pyautogui              # screenshots (already in repo)
wikipedia              # wikipedia (already in repo)
edge-tts               # natural TTS (phase 2)
pvporcupine            # wake word (phase 2)
SpeechRecognition      # STT (already in repo)
```
