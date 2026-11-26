import logging
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parents[2] / "jarvis.log"


def setup_logger(name: str = "jarvis", level: int = logging.INFO) -> logging.Logger:
    """Log to jarvis.log so log lines never clutter the chat UI."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
