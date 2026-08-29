"""Validation and classification for supported media URLs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import ParseResult, parse_qs, urlparse


class MediaSource(str, Enum):
    """Media services supported by the application."""

    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"


class MediaKind(str, Enum):
    """Kinds of media accepted by the download flow."""

    TRACK = "track"
    COLLECTION = "collection"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class URLClassification:
    """Parsed information about a supported media URL."""

    source: MediaSource
    kind: MediaKind
    media_id: Optional[str] = None


class URLValidator:
    """Validate YouTube and SoundCloud URLs without network requests."""

    @staticmethod
    def normalize_url(url: str) -> str:
        """Return a stripped URL with an explicit HTTPS scheme."""
        normalized = url.strip()
        if normalized.startswith(("http://", "https://")):
            return normalized
        return "https://" + normalized

    @classmethod
    def classify(cls, url: str) -> Optional[URLClassification]:
        """Classify a supported URL, or return ``None`` when it is invalid."""
        if not isinstance(url, str) or not url.strip():
            return None

        try:
            parsed = urlparse(cls.normalize_url(url))
        except ValueError:
            return None

        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            return None

        host = (parsed.hostname or "").lower()
        if cls._is_youtube_host(host):
            return cls._classify_youtube(parsed)
        if cls._is_soundcloud_host(host):
            return cls._classify_soundcloud(parsed)
        return None

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Return whether the URL belongs to a supported media service."""
        return cls.classify(url) is not None

    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        """Return whether the URL is a supported YouTube URL."""
        classification = cls.classify(url)
        return (
            classification is not None and classification.source is MediaSource.YOUTUBE
        )

    @classmethod
    def is_valid_soundcloud_url(cls, url: str) -> bool:
        """Return whether the URL is a supported SoundCloud URL."""
        classification = cls.classify(url)
        return (
            classification is not None
            and classification.source is MediaSource.SOUNDCLOUD
        )

    @classmethod
    def classify_url(cls, url: str) -> tuple[str, Optional[str]]:
        """Return the legacy media kind and identifier tuple."""
        classification = cls.classify(url)
        if classification is None:
            return "invalid", None
        if classification.kind is MediaKind.COLLECTION:
            kind = "playlist"
        elif classification.kind is MediaKind.TRACK:
            kind = "video" if classification.source is MediaSource.YOUTUBE else "track"
        else:
            kind = classification.kind.value
        return kind, classification.media_id

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extract a YouTube video identifier."""
        classification = cls.classify(url)
        if (
            classification is not None
            and classification.source is MediaSource.YOUTUBE
            and classification.kind is MediaKind.TRACK
        ):
            return classification.media_id
        return None

    @classmethod
    def extract_playlist_id(cls, url: str) -> Optional[str]:
        """Extract a YouTube playlist identifier."""
        classification = cls.classify(url)
        if (
            classification is not None
            and classification.source is MediaSource.YOUTUBE
            and classification.kind is MediaKind.COLLECTION
        ):
            return classification.media_id
        return None

    @classmethod
    def _classify_youtube(cls, parsed: ParseResult) -> Optional[URLClassification]:
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        playlist_id = query.get("list", [None])[0]
        if playlist_id:
            return URLClassification(
                MediaSource.YOUTUBE, MediaKind.COLLECTION, playlist_id
            )

        video_id: Optional[str]
        if host == "youtu.be":
            video_id = path.lstrip("/").split("/", 1)[0]
        elif path == "/watch":
            video_id = query.get("v", [None])[0]
        elif path.startswith(("/embed/", "/shorts/", "/live/")):
            video_id = path.split("/", 2)[2]
        elif path == "/playlist":
            return None
        else:
            return None

        if video_id and cls._is_youtube_id(video_id):
            return URLClassification(MediaSource.YOUTUBE, MediaKind.TRACK, video_id)
        return None

    @staticmethod
    def _classify_soundcloud(parsed: ParseResult) -> Optional[URLClassification]:
        host = (parsed.hostname or "").lower()
        if host == "on.soundcloud.com":
            if parsed.path.strip("/"):
                return URLClassification(MediaSource.SOUNDCLOUD, MediaKind.UNKNOWN)
            return None

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[1].lower() == "sets":
            return URLClassification(
                MediaSource.SOUNDCLOUD,
                MediaKind.COLLECTION,
                "/".join((parts[0], parts[2])),
            )
        if len(parts) >= 2 and parts[1].lower() not in {"likes", "reposts", "tracks"}:
            return URLClassification(
                MediaSource.SOUNDCLOUD,
                MediaKind.TRACK,
                "/".join(parts[:2]),
            )
        return None

    @staticmethod
    def _is_youtube_id(value: str) -> bool:
        return len(value) == 11 and all(
            character.isalnum() or character in {"_", "-"} for character in value
        )

    @staticmethod
    def _is_youtube_host(host: str) -> bool:
        return host in {"youtu.be", "youtube.com"} or host.endswith(".youtube.com")

    @staticmethod
    def _is_soundcloud_host(host: str) -> bool:
        return host == "soundcloud.com" or host.endswith(".soundcloud.com")


__all__ = [
    "MediaKind",
    "MediaSource",
    "URLClassification",
    "URLValidator",
]
