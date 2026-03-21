"""Tests for application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

from youtube_to_mp3 import logging_setup


def _reset_package_logger() -> logging.Logger:
    """Remove existing package handlers to isolate test state."""
    logger = logging.getLogger("youtube_to_mp3")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    return logger


def test_configure_logging_creates_rotating_log_file(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logging_setup, "_default_log_directory", lambda: tmp_path)
    logger = _reset_package_logger()

    try:
        log_file = logging_setup.configure_logging(debug=False)

        assert log_file == tmp_path / "youtube-to-mp3.log"
        assert log_file.exists()
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert logger.handlers[0].level == logging.INFO
    finally:
        _reset_package_logger()


def test_configure_logging_updates_existing_handler_levels(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logging_setup, "_default_log_directory", lambda: tmp_path)
    logger = _reset_package_logger()

    try:
        first = logging_setup.configure_logging(debug=False)
        second = logging_setup.configure_logging(debug=True)

        assert first == second
        assert len(logger.handlers) == 1
        assert logger.level == logging.DEBUG
        assert logger.handlers[0].level == logging.DEBUG
    finally:
        _reset_package_logger()
