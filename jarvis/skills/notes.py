from jarvis.core.memory import LongTermMemory
from jarvis.skills.base import BaseSkill, Tool


class NotesSkill(BaseSkill):
    name = "notes"
    description = "Long-term memory: save and recall notes, reminders and facts about the user"
    tools = [
        Tool(
            name="save_note",
            description="Save a note or reminder the user asked you to remember",
            parameters={"content": {"type": "string", "description": "The note text"}},
            required=["content"],
        ),
        Tool(name="get_notes", description="List all saved notes, newest first"),
        Tool(
            name="delete_note",
            description="Delete a saved note by its id (ids are shown by get_notes)",
            parameters={"note_id": {"type": "integer", "description": "Note id"}},
            required=["note_id"],
        ),
        Tool(
            name="save_fact",
            description="Save a lasting fact about the user, e.g. key='favorite_color', value='blue'",
            parameters={
                "key": {"type": "string", "description": "Short snake_case key"},
                "value": {"type": "string", "description": "The fact"},
            },
            required=["key", "value"],
        ),
        Tool(name="get_facts", description="List everything known about the user"),
        Tool(
            name="search_memory",
            description="Search notes and facts by keyword",
            parameters={"query": {"type": "string", "description": "Keyword"}},
            required=["query"],
        ),
    ]

    def __init__(self, memory: LongTermMemory | None = None):
        self._memory = memory

    def setup(self, config, memory) -> None:
        if self._memory is None:
            self._memory = memory

    def set_memory(self, memory: LongTermMemory) -> None:
        self._memory = memory

    def execute(self, action: str, args: dict) -> str:
        if not self._memory:
            return "Error: memory system not initialized."
        if action == "save_note":
            self._memory.save_note(args["content"])
            return f"Noted: {args['content']}"
        if action == "get_notes":
            notes = self._memory.get_notes()
            if not notes:
                return "No notes saved yet."
            return "\n".join(f"- [#{n['id']}, {n['created_at'][:10]}] {n['content']}" for n in notes)
        if action == "delete_note":
            ok = self._memory.delete_note(int(args["note_id"]))
            return "Note deleted." if ok else f"No note with id {args['note_id']}."
        if action == "save_fact":
            self._memory.save_fact(args["key"], args["value"])
            return f"Remembered: {args['key']} = {args['value']}"
        if action == "get_facts":
            facts = self._memory.get_facts()
            if not facts:
                return "No facts saved yet."
            return "\n".join(f"- {f['key']}: {f['value']}" for f in facts)
        if action == "search_memory":
            results = self._memory.search(args["query"])
            if not results:
                return f"Nothing found for '{args['query']}'."
            return "\n".join(f"- [{r['type']}] {r['content']}" for r in results)
        raise ValueError(f"Unknown action: {action}")
