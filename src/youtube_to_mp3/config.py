"""Configuration loading utilities for the YouTube to MP3 converter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .utils.filesystem import get_music_directory, ensure_directory

_DEFAULT_CONFIG_PATH = Path("~/.config/youtube-to-mp3/config.json").expanduser()

# Constants for album cover retrieval and other operations
MAX_COVER_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit for cover images
COVER_REQUEST_TIMEOUT = 10  # seconds
ALBUM_NAME_WORD_OVERLAP_RATIO = 0.5  # Minimum word overlap for album matching
DEFAULT_SEARCH_LIMIT = 5
EXTENDED_SEARCH_LIMIT = 10
ARTIST_ALBUMS_SEARCH_LIMIT = 20
ITUNES_SMALL_IMAGE_SIZE = 100
ITUNES_LARGE_IMAGE_SIZE = 600


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    output_directory: Path = field(
        default_factory=lambda: get_music_directory() / "YouTube"
    )
    audio_format: str = "mp3"
    audio_quality: str = "192"
    rate_limit_delay: float = 1.5
    auto_confirm_correct_metadata: bool = False
    default_genre: str = "Unknown"
    filename_template: str = "{artist} - {title}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create a config instance from raw dictionary data."""
        config = cls()

        if "output_directory" in data and data["output_directory"]:
            config.output_directory = Path(data["output_directory"]).expanduser()

        config.audio_format = data.get("audio_format", config.audio_format)
        config.audio_quality = data.get("audio_quality", config.audio_quality)
        config.rate_limit_delay = float(
            data.get("rate_limit_delay", config.rate_limit_delay)
        )
        config.auto_confirm_correct_metadata = bool(
            data.get(
                "auto_confirm_correct_metadata", config.auto_confirm_correct_metadata
            )
        )
        config.default_genre = data.get("default_genre", config.default_genre)
        config.filename_template = data.get(
            "filename_template", config.filename_template
        )

        return config

    def merge_overrides(self, overrides: Dict[str, Any]) -> None:
        """Merge CLI or runtime overrides into this config."""
        if "output_directory" in overrides and overrides["output_directory"]:
            self.output_directory = Path(overrides["output_directory"]).expanduser()

        if "rate_limit_delay" in overrides and overrides["rate_limit_delay"]:
            self.rate_limit_delay = float(overrides["rate_limit_delay"])

        if "audio_quality" in overrides and overrides["audio_quality"]:
            self.audio_quality = str(overrides["audio_quality"])

        if "filename_template" in overrides and overrides["filename_template"]:
            self.filename_template = str(overrides["filename_template"])

        if "default_genre" in overrides and overrides["default_genre"]:
            self.default_genre = str(overrides["default_genre"])

    def ensure_output_directory(self) -> Path:
        """Ensure the output directory exists and return it."""
        ensure_directory(self.output_directory)
        return self.output_directory


def _load_config_file(path: Path) -> Dict[str, Any]:
    """Load configuration data from a JSON file."""
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        # Fall back to defaults if parsing fails; higher layers can warn if desired.
        return {}

    return {}


def load_config(
    explicit_path: Optional[Path] = None, overrides: Optional[Dict[str, Any]] = None
) -> AppConfig:
    """Load application configuration from disk and apply overrides."""
    config_path = explicit_path.expanduser() if explicit_path else _DEFAULT_CONFIG_PATH
    raw_data = _load_config_file(config_path)

    config = AppConfig.from_dict(raw_data)

    if overrides:
        config.merge_overrides(overrides)

    return config


__all__ = ["AppConfig", "load_config"]
