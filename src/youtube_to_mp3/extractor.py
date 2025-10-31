"""YouTube metadata extraction functionality."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import yt_dlp


@dataclass
class TrackMetadata:
    """Metadata for a single track."""

    title: str
    artist: str
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    duration: Optional[int] = None
    source_url: Optional[str] = None
    selected: bool = True
    thumbnail_url: Optional[str] = None
    original_title: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlaylistInfo:
    """Information about a playlist."""

    title: str
    tracks: List[TrackMetadata]
    is_album: bool = False
    url: Optional[str] = None
    total_tracks: int = 0


class YouTubeExtractor:
    """Extracts metadata from YouTube URLs using yt-dlp."""

    def __init__(self):
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

    def extract_metadata(self, url: str) -> Union[TrackMetadata, PlaylistInfo]:
        """
        Extract metadata from a YouTube URL.

        Returns TrackMetadata for single videos, PlaylistInfo for playlists.
        """
        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Check if it's a playlist
                if "entries" in info:
                    return self._extract_playlist_info(info)
                else:
                    return self._extract_track_metadata(info)

        except Exception as e:
            # Fallback: try to extract basic info from URL patterns
            return self._fallback_metadata_extraction(url, str(e))

    def _extract_track_metadata(self, info: Dict[str, Any]) -> TrackMetadata:
        """Extract metadata from a single video info dict."""
        title = info.get("title", "Unknown Title")
        uploader = info.get("uploader", "Unknown Artist")
        duration = info.get("duration")
        source_url = info.get("webpage_url") or info.get("url")
        thumbnail = info.get("thumbnail")

        parsed = self.parse_title(title)

        metadata = TrackMetadata(
            title=parsed.get("title", title),
            artist=parsed.get("artist", uploader),
            album=parsed.get("album"),
            genre=parsed.get("genre"),
            duration=duration,
            source_url=source_url,
            thumbnail_url=thumbnail,
            original_title=title,
        )

        if info.get("release_year"):
            metadata.year = info.get("release_year")

        if info.get("track"):
            metadata.title = info.get("track")

        if info.get("artist"):
            metadata.artist = info.get("artist")

        # Use album info from extra data if available
        if not metadata.album and info.get("album"):
            metadata.album = info.get("album")

        metadata.extra = {
            "album": info.get("album"),
            "channel": info.get("channel"),
            "channel_url": info.get("channel_url"),
        }

        return metadata

    def _extract_playlist_info(self, info: Dict[str, Any]) -> PlaylistInfo:
        """Extract metadata from a playlist info dict."""
        playlist_title = info.get("title", "Unknown Playlist")
        entries = [entry for entry in info.get("entries", []) if entry]
        total_entries = len(entries)

        # Check if this is an album based on multiple heuristics
        is_album = self._is_album_playlist(info, entries)

        tracks: List[TrackMetadata] = []
        for i, entry in enumerate(entries, 1):
            metadata = self._extract_track_metadata(entry)
            metadata.track_number = i
            metadata.total_tracks = total_entries
            metadata.extra["playlist_index"] = entry.get("playlist_index")

            # For albums, propagate playlist title as album name if track doesn't have one
            if is_album and not metadata.album:
                metadata.album = playlist_title

            tracks.append(metadata)

        return PlaylistInfo(
            title=playlist_title,
            tracks=tracks,
            is_album=is_album,
            url=info.get("webpage_url"),
            total_tracks=total_entries,
        )

    def _is_album_playlist(self, info: Dict[str, Any], entries: List[Dict[str, Any]]) -> bool:
        """Determine if a playlist represents an album using multiple heuristics."""
        # Direct playlist type indicator
        if info.get("playlist_type") == "album":
            return True

        # Check if most tracks have the same album name
        album_names = set()
        for entry in entries[:10]:  # Check first 10 entries for performance
            album = entry.get("album")
            if album:
                album_names.add(album.lower().strip())

        # If most tracks share the same album name, it's likely an album
        if len(album_names) == 1 and len(entries) > 3:
            return True

        # Check playlist title patterns that suggest albums
        title_lower = info.get("title", "").lower()
        album_indicators = ["album", "lp", "ep", "single", "compilation"]
        if any(indicator in title_lower for indicator in album_indicators):
            return True

        # Check if tracks have sequential track numbers
        track_numbers = []
        for entry in entries[:10]:
            track_num = entry.get("track_number") or entry.get("playlist_index")
            if track_num:
                track_numbers.append(track_num)

        # If we have sequential track numbers, likely an album
        if len(track_numbers) >= 3:
            track_numbers.sort()
            if track_numbers == list(range(min(track_numbers), max(track_numbers) + 1)):
                return True

        return False

    def parse_title(self, title: str) -> Dict[str, str]:
        """
        Parse a YouTube video title to extract music metadata.

        Handles patterns like:
        - "Artist - Song Title"
        - "Artist - Song Title (Official Video)"
        - "Song Title - Artist"
        """
        # Clean the title
        clean_title = self._clean_title(title)

        # Try different separator patterns
        separators = [
            r"\s*-\s*",  # "Artist - Title"
            r"\s*–\s*",  # "Artist – Title" (em dash)
            r"\s*\|\s*",  # "Artist | Title"
            r"\s*:\s*",  # "Artist: Title"
        ]

        for sep in separators:
            if re.search(sep, clean_title):
                parts = re.split(sep, clean_title, maxsplit=1)
                if len(parts) == 2:
                    part1, part2 = parts

                    # Heuristic: shorter part is likely artist
                    if len(part1.split()) <= 3:
                        return {"artist": part1.strip(), "title": part2.strip()}
                    else:
                        return {"title": part1.strip(), "artist": part2.strip()}

        # No separator found, return original title
        return {"title": clean_title}

    def _clean_title(self, title: str) -> str:
        """Clean up common YouTube title artifacts."""
        # Remove common suffixes
        patterns = [
            r"\s*\((Official|Music|Lyric|Audio|HD|4K)\s+(Video|Audio|Music Video|Lyric Video)\)",
            r"\s*\|.*$",  # Remove everything after pipe
        ]

        clean = title
        for pattern in patterns:
            clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)

        return clean.strip()

    def _fallback_metadata_extraction(self, url: str, error: str) -> TrackMetadata:
        """Fallback metadata extraction when yt-dlp fails."""
        # Try to extract video ID from URL
        video_id = self._extract_video_id(url)
        if video_id:
            return TrackMetadata(
                title=f"YouTube Video {video_id}", artist="Unknown Artist"
            )

        return TrackMetadata(title="Unknown Title", artist="Unknown Artist")

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/v\/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None


__all__ = ["TrackMetadata", "PlaylistInfo", "YouTubeExtractor"]
