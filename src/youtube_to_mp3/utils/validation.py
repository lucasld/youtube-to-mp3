"""Input validation utilities."""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class URLValidator:
    """Validates YouTube URLs."""

    YOUTUBE_PATTERNS = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    @staticmethod
    def normalize_url(url: str) -> str:
        """Return a URL string with an explicit protocol."""
        if url.startswith(("http://", "https://")):
            return url
        return "https://" + url

    @staticmethod
    def is_valid_youtube_url(url: str) -> bool:
        """Check if a URL is a valid YouTube URL."""
        if not url or not isinstance(url, str):
            return False

        url = url.strip()
        if not url:
            return False

        normalized = URLValidator.normalize_url(url)

        try:
            parsed = urlparse(normalized)
            if parsed.netloc not in ["www.youtube.com", "youtube.com", "youtu.be"]:
                return False

            return any(
                re.match(pattern, normalized)
                for pattern in URLValidator.YOUTUBE_PATTERNS
            )

        except Exception:
            return False

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        normalized = URLValidator.normalize_url(url)
        for pattern in URLValidator.YOUTUBE_PATTERNS[
            :3
        ]:  # Skip embed pattern for extraction
            match = re.search(pattern, normalized)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        """Extract YouTube playlist ID from URL."""
        normalized = URLValidator.normalize_url(url)
        pattern = r"[?&]list=([a-zA-Z0-9_-]+)"
        match = re.search(pattern, normalized)
        return match.group(1) if match else None

    @staticmethod
    def classify_url(url: str) -> Tuple[str, Optional[str]]:
        """Classify a YouTube URL as video, playlist, or invalid."""
        if not URLValidator.is_valid_youtube_url(url):
            return "invalid", None

        playlist_id = URLValidator.extract_playlist_id(url)
        if playlist_id:
            return "playlist", playlist_id

        video_id = URLValidator.extract_video_id(url)
        if video_id:
            return "video", video_id

        return "unknown", None


__all__ = ["URLValidator"]
