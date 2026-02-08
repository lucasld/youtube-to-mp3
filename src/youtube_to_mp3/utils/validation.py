"""Input validation utilities."""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


class URLValidator:
    """Validates YouTube URLs."""

    YOUTUBE_PATTERNS = [
        r"(?:https?://)?(?:[a-zA-Z0-9_-]+\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:[a-zA-Z0-9_-]+\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
        r"(?:https?://)?(?:[a-zA-Z0-9_-]+\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
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

        try:
            return URLValidator.classify_url(url)[0] != "invalid"
        except Exception:
            return False

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        normalized = URLValidator.normalize_url(url)
        parsed = urlparse(normalized)
        host = parsed.netloc.lower()

        if host == "youtu.be":
            match = re.match(r"/([a-zA-Z0-9_-]{11})", parsed.path)
            return match.group(1) if match else None

        if not URLValidator._is_youtube_host(host):
            return None

        if parsed.path == "/watch":
            query = dict(
                part.split("=", 1)
                for part in parsed.query.split("&")
                if "=" in part
            )
            return query.get("v")

        if parsed.path.startswith("/embed/"):
            match = re.match(r"/embed/([a-zA-Z0-9_-]{11})", parsed.path)
            return match.group(1) if match else None

        return None

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        """Extract YouTube playlist ID from URL."""
        normalized = URLValidator.normalize_url(url)
        parsed = urlparse(normalized)
        if not URLValidator._is_youtube_host(parsed.netloc.lower()):
            return None
        
        # Parse query parameters safely
        params = dict(
            part.split("=", 1)
            for part in parsed.query.split("&")
            if "=" in part
        )
        return params.get("list")

    @staticmethod
    def classify_url(url: str) -> Tuple[str, Optional[str]]:
        """Classify a YouTube URL as video, playlist, or invalid."""
        normalized = URLValidator.normalize_url(url)
        parsed = urlparse(normalized)
        if not URLValidator._is_youtube_host(parsed.netloc.lower()):
            return "invalid", None

        playlist_id = URLValidator.extract_playlist_id(url)
        if playlist_id:
            return "playlist", playlist_id

        video_id = URLValidator.extract_video_id(url)
        if video_id:
            return "video", video_id

        return "unknown", None

    @staticmethod
    def _is_youtube_host(host: str) -> bool:
        """Return True for supported YouTube hostnames."""
        if host == "youtu.be" or host == "youtube.com":
            return True
        return host.endswith(".youtube.com")


__all__ = ["URLValidator"]
