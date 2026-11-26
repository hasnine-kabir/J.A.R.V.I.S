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


def test_entry_point_imports_and_parses_args():
    import jarvis.__main__ as entry

    assert callable(entry.main) and callable(entry.save_keys)


def test_gemini_api_keys_merges_and_dedupes(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEYS", "k1, k2;k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k3")
    config = Config(yaml_path=str(tmp_path / "none.yaml"), env_path=str(tmp_path / "none.env"))
    assert config.gemini_api_keys == ["k1", "k2", "k3"]


def test_placeholder_keys_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEYS", "your_first_key,your_second_key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = Config(yaml_path=str(tmp_path / "none.yaml"), env_path=str(tmp_path / "none.env"))
    assert config.gemini_api_keys == []


def test_save_keys_writes_env(monkeypatch, tmp_path):
    import jarvis.__main__ as entry

    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=old1\nSMTP_EMAIL=\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "old1")
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    config = Config(yaml_path=str(tmp_path / "none.yaml"), env_path=str(env))
    assert entry.save_keys(config, ["new2", "old1"]) == 2
    text = env.read_text(encoding="utf-8")
    assert "GEMINI_API_KEYS=old1,new2" in text
    assert "GEMINI_API_KEY=" not in text.replace("GEMINI_API_KEYS=", "")
