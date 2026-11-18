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
