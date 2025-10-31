"""Metadata parsing and validation utilities."""

from __future__ import annotations

from typing import Dict, Optional

from .extractor import TrackMetadata


class MetadataCleaner:
    """Sanitize and normalize metadata values."""

    @staticmethod
    def clean_track(
        metadata: TrackMetadata, default_genre: Optional[str] = None
    ) -> TrackMetadata:
        """Return a sanitized copy of the provided metadata."""
        cleaned = TrackMetadata(
            title=MetadataCleaner._clean_string(metadata.title) or "Unknown Title",
            artist=MetadataCleaner._clean_string(metadata.artist) or "Unknown Artist",
            album=MetadataCleaner._clean_optional_string(metadata.album),
            genre=MetadataCleaner._clean_optional_string(metadata.genre)
            or default_genre,
            year=MetadataCleaner._validate_year(metadata.year),
            track_number=MetadataCleaner._validate_track_number(metadata.track_number),
            total_tracks=MetadataCleaner._validate_track_number(metadata.total_tracks),
            duration=metadata.duration,
            source_url=metadata.source_url,
            selected=metadata.selected,
            thumbnail_url=metadata.thumbnail_url,
            original_title=metadata.original_title,
            extra=dict(metadata.extra),
        )

        return cleaned

    @staticmethod
    def _clean_string(value: Optional[str]) -> str:
        """Clean a string value."""
        if not value:
            return ""
        return value.strip()

    @staticmethod
    def _clean_optional_string(value: Optional[str]) -> Optional[str]:
        """Clean an optional string value."""
        if not value:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _validate_year(year: Optional[int]) -> Optional[int]:
        """Validate a year value."""
        if year is None:
            return None
        if 1900 <= year <= 2100:
            return year
        return None

    @staticmethod
    def _validate_track_number(track_num: Optional[int]) -> Optional[int]:
        """Validate a track number."""
        if track_num is None:
            return None
        if 1 <= track_num <= 999:
            return track_num
        return None


class MetadataFormatter:
    """Formats metadata for display and storage."""

    @staticmethod
    def format_track_info(metadata: TrackMetadata) -> Dict[str, str]:
        """Format track metadata for display."""
        return {
            "Title": metadata.title,
            "Artist": metadata.artist,
            "Album": metadata.album or "Not set",
            "Genre": metadata.genre or "Not set",
            "Year": str(metadata.year) if metadata.year else "Not set",
            "Track": (
                f"{metadata.track_number}/{metadata.total_tracks}"
                if metadata.track_number and metadata.total_tracks
                else "Not set"
            ),
            "Duration": MetadataFormatter._format_duration(metadata.duration),
        }

    @staticmethod
    def _format_duration(seconds: Optional[int]) -> str:
        """Format duration in seconds to MM:SS."""
        if not seconds:
            return "Unknown"

        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:02}:{remaining_seconds:02}"


__all__ = ["MetadataCleaner", "MetadataFormatter"]
