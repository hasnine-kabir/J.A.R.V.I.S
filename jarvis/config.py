import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    # Treat template placeholders such as "your_gemini_api_key_here" as unset.
    return "" if value.lower().startswith("your_") else value


class Config:
    def __init__(
        self,
        yaml_path: str = str(PROJECT_ROOT / "config.yaml"),
        env_path: str = str(PROJECT_ROOT / ".env"),
    ):
        self.env_path = env_path
        load_dotenv(env_path)
        self._data = {}
        yaml_file = Path(yaml_path)
        if yaml_file.exists():
            with open(yaml_file, encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    @property
    def gemini_api_key(self) -> str:
        return _env("GEMINI_API_KEY")

    @property
    def gemini_api_keys(self) -> list[str]:
        """All keys from GEMINI_API_KEYS (comma/space separated) plus GEMINI_API_KEY."""
        raw = _env("GEMINI_API_KEYS").replace(";", ",").replace(" ", ",")
        keys = [k.strip() for k in raw.split(",") if k.strip() and not k.lower().startswith("your_")]
        single = self.gemini_api_key
        if single:
            keys.append(single)
        return list(dict.fromkeys(keys))

    @property
    def smtp_email(self) -> str:
        return _env("SMTP_EMAIL")

    @property
    def smtp_password(self) -> str:
        return _env("SMTP_PASSWORD")

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
