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
