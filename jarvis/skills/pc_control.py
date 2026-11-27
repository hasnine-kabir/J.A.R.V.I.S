import os
import subprocess
import sys
from pathlib import Path

from jarvis.skills.base import BaseSkill, Tool

MAX_OUTPUT = 8000


class PCControlSkill(BaseSkill):
    name = "pc_control"
    description = "Control the PC: open apps/files/folders, run shell commands, list and read files"
    tools = [
        Tool(
            name="run_command",
            description="Run a shell command (Windows cmd.exe; use 'powershell -Command ...' for "
                        "PowerShell) and return its output",
            parameters={"command": {"type": "string", "description": "The command to execute"}},
            required=["command"],
            confirm=True,
        ),
        Tool(
            name="open_application",
            description="Open an application, file, folder or website. Examples: app_name='notepad'; "
                        "app_name='https://youtube.com' (default browser); app_name='chrome', "
                        "target='https://youtube.com'; app_name='C:/Users'",
            parameters={
                "app_name": {"type": "string", "description": "App name, file path, folder or URL"},
                "target": {"type": "string", "description": "Optional file or URL to open with that app"},
            },
            required=["app_name"],
        ),
        Tool(
            name="list_directory",
            description="List files and folders in a directory",
            parameters={"path": {"type": "string", "description": "Directory path; defaults to current directory"}},
        ),
        Tool(
            name="read_file",
            description="Read the contents of a text file (first 10,000 characters)",
            parameters={"path": {"type": "string", "description": "Path to the file"}},
            required=["path"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "run_command":
            return self._run_command(args["command"])
        if action == "open_application":
            return self._open_app(args["app_name"], args.get("target", ""))
        if action == "list_directory":
            return self._list_dir(args.get("path") or ".")
        if action == "read_file":
            return self._read_file(args["path"])
        raise ValueError(f"Unknown action: {action}")

    def _run_command(self, command: str) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            return "Command timed out after 60 seconds."
        except Exception as e:
            return f"Error running command: {e}"
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n... (truncated)"
        status = f"exit code {result.returncode}"
        return f"{output}\n({status})" if output else f"Command finished with {status} (no output)."

    def _open_app(self, app_name: str, target: str = "") -> str:
        app_name, target = app_name.replace('"', ""), target.replace('"', "")
        try:
            if sys.platform == "win32":
                # `start` resolves registered apps (chrome, code, spotify...), files, folders, URLs.
                extra = f' "{target}"' if target else ""
                subprocess.Popen(f'start "" "{app_name}"{extra}', shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app_name] + ([target] if target else []))
            else:
                subprocess.Popen(["xdg-open", target or app_name])
        except Exception as e:
            return f"Failed to open {app_name}: {e}"
        return f"Opened {app_name}{' → ' + target if target else ''}."

    def _list_dir(self, path: str) -> str:
        try:
            p = Path(path).expanduser()
            entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except Exception as e:
            return f"Error listing directory: {e}"
        if not entries:
            return f"{path} is empty."
        lines = [f"{e.name}{os.sep if e.is_dir() else ''}" for e in entries[:300]]
        if len(entries) > 300:
            lines.append(f"... and {len(entries) - 300} more")
        return "\n".join(lines)

    def _read_file(self, path: str) -> str:
        try:
            with open(Path(path).expanduser(), "r", encoding="utf-8", errors="replace") as f:
                content = f.read(10000)
        except Exception as e:
            return f"Error reading file: {e}"
        return content or "(empty file)"
