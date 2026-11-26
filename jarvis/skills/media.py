import os
import random
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

from jarvis.skills.base import BaseSkill, Tool

AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma"}


def _open_with_default_app(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class MediaSkill(BaseSkill):
    name = "media"
    description = "Play local music and search YouTube"
    tools = [
        Tool(
            name="play_music",
            description="Play a music file, or a random song from a folder. "
                        "Without a path, uses the user's Music folder.",
            parameters={"path": {"type": "string", "description": "Optional file or folder path"}},
        ),
        Tool(
            name="search_youtube",
            description="Open YouTube search results for a query in the browser",
            parameters={"query": {"type": "string", "description": "What to search for"}},
            required=["query"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "play_music":
            return self._play(args.get("path") or str(Path.home() / "Music"))
        if action == "search_youtube":
            return self._search_youtube(args["query"])
        raise ValueError(f"Unknown action: {action}")

    def _play(self, path: str) -> str:
        p = Path(path).expanduser()
        if p.is_dir():
            songs = [f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXT]
            if not songs:
                return f"No audio files found in {p}."
            p = random.choice(songs)
        if not p.exists():
            return f"File not found: {p}"
        try:
            _open_with_default_app(str(p))
        except Exception as e:
            return f"Failed to play: {e}"
        return f"Now playing: {p.name}"

    def _search_youtube(self, query: str) -> str:
        webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
        return f"Opened YouTube search for: {query}"
