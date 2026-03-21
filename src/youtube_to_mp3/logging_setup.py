"""Application logging setup."""

from __future__ import annotations

import logging
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .utils.filesystem import ensure_directory


def _default_log_directory() -> Path:
    """Return the default directory for application logs."""
    system = platform.system()

    if system == "Darwin":
        return Path.home() / "Library" / "Logs" / "youtube-to-mp3"
    if system == "Windows":
        local_app_data = Path.home() / "AppData" / "Local"
        return local_app_data / "youtube-to-mp3" / "logs"
    return Path.home() / ".local" / "state" / "youtube-to-mp3" / "logs"


def configure_logging(debug: bool = False) -> Path:
    """Configure rotating file logging for the application."""
    log_dir = _default_log_directory()
    ensure_directory(log_dir)
    log_file = log_dir / "youtube-to-mp3.log"

    app_logger = logging.getLogger("youtube_to_mp3")
    level = logging.DEBUG if debug else logging.INFO
    app_logger.setLevel(level)
    app_logger.propagate = False

    if app_logger.handlers:
        for handler in app_logger.handlers:
            handler.setLevel(level)
        return log_file

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    app_logger.addHandler(file_handler)
    app_logger.info("Logging initialized at %s", log_file)
    return log_file


__all__ = ["configure_logging"]
