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
