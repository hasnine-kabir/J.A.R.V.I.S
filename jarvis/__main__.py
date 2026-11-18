"""Entry point: python -m jarvis"""
from jarvis.config import Config
from jarvis.utils.logger import setup_logger


def main():
    logger = setup_logger()
    config = Config()
    logger.info("J.A.R.V.I.S. v2.0 starting up...")
    logger.info(f"Welcome, {config.get('user.name', 'Sir')}")


if __name__ == "__main__":
    main()
