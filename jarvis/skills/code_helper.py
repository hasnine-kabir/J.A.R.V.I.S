from pathlib import Path

from jarvis.skills.base import BaseSkill, Tool

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    ".superpowers", "dist", "build", ".pytest_cache",
}
MAX_LINES = 400


class CodeHelperSkill(BaseSkill):
    name = "code_helper"
    description = "Help with code: read source files with line numbers, explore project trees, write files"
    tools = [
        Tool(
            name="read_code",
            description="Read a source file with line numbers",
            parameters={"path": {"type": "string", "description": "Path to the source file"}},
            required=["path"],
        ),
        Tool(
            name="list_project",
            description="Show the folder/file tree of a project directory",
            parameters={
                "path": {"type": "string", "description": "Project root; defaults to the current directory"},
                "max_depth": {"type": "integer", "description": "Maximum depth (default 3)"},
            },
        ),
        Tool(
            name="write_file",
            description="Create or overwrite a text/code file with the given content",
            parameters={
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Full file content"},
            },
            required=["path", "content"],
            confirm=True,
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "read_code":
            return self._read_code(args["path"])
        if action == "list_project":
            return self._list_project(args.get("path") or ".", int(args.get("max_depth") or 3))
        if action == "write_file":
            return self._write_file(args["path"], args["content"])
        raise ValueError(f"Unknown action: {action}")

    def _read_code(self, path: str) -> str:
        try:
            lines = Path(path).expanduser().read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            return f"Error reading file: {e}"
        out = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines[:MAX_LINES])]
        if len(lines) > MAX_LINES:
            out.append(f"... ({len(lines) - MAX_LINES} more lines)")
        return "\n".join(out) or "(empty file)"

    def _list_project(self, path: str, max_depth: int = 3) -> str:
        root = Path(path).expanduser()
        if not root.is_dir():
            return f"Not a directory: {path}"
        lines: list[str] = [root.resolve().name + "/"]
        self._walk(root, lines, "", 0, max_depth)
        if len(lines) > 500:
            lines = lines[:500] + ["... (truncated)"]
        return "\n".join(lines)

    def _walk(self, path: Path, lines: list, prefix: str, depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            entries = [e for e in path.iterdir() if e.name not in IGNORE_DIRS]
        except (PermissionError, OSError):
            return
        entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
        for i, entry in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                self._walk(entry, lines, prefix + ("    " if last else "│   "), depth + 1, max_depth)

    def _write_file(self, path: str, content: str) -> str:
        try:
            target = Path(path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"
        return f"Wrote {len(content)} characters to {target}"
