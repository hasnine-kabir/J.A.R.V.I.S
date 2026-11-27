import datetime
from pathlib import Path


from jarvis.skills.base import BaseSkill, Tool
from jarvis.utils.lazy import LazyModule

pyautogui = LazyModule("pyautogui")


def _default_folder() -> Path:
    home = Path.home()
    for candidate in (
        home / "Pictures" / "Screenshots",
        home / "OneDrive" / "Pictures" / "Screenshots",
        home / "Pictures",
        home / "Desktop",
    ):
        if candidate.is_dir():
            return candidate
    return Path.cwd()


class ScreenshotSkill(BaseSkill):
    name = "screenshot"
    description = "Take screenshots of the screen and save them as PNG files"
    tools = [
        Tool(
            name="take_screenshot",
            description="Take a screenshot and save it. Optionally give a file path; "
                        "defaults to the Pictures/Screenshots folder.",
            parameters={"path": {"type": "string", "description": "Optional output file path (.png)"}},
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "take_screenshot":
            return self._take(args.get("path", ""))
        raise ValueError(f"Unknown action: {action}")

    def _take(self, path: str) -> str:
        if path:
            target = Path(path).expanduser()
        else:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            target = _default_folder() / f"jarvis_screenshot_{stamp}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot().save(str(target))
        return f"Screenshot saved to {target}"
