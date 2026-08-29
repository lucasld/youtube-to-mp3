"""Metadata extraction for supported media services."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import requests
import yt_dlp
from yt_dlp.utils import DownloadError

from .utils.validation import MediaSource, URLValidator

logger = logging.getLogger(__name__)


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
    source_cover_url: Optional[str] = None
    source: Optional[str] = None
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


class ExtractionError(RuntimeError):
    """Raised when a media service cannot provide usable metadata."""


class MediaExtractor:
    """Extract metadata through yt-dlp with optional provider enrichment."""

    def __init__(self) -> None:
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def extract_metadata(self, url: str) -> Union[TrackMetadata, PlaylistInfo]:
        """
        Extract metadata from a supported media URL.

        Returns TrackMetadata for single videos, PlaylistInfo for playlists.
        """
        try:
            with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not isinstance(info, dict):
                    raise ExtractionError("The media service returned no metadata.")

                if "entries" in info:
                    return self._extract_playlist_info(info)
                return self._extract_track_metadata(info)

        except ExtractionError:
            raise
        except DownloadError as exc:
            logger.warning("Metadata extraction failed for %s: %s", url, exc)
            raise ExtractionError(self._format_extraction_error(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected metadata extraction failure for %s", url)
            raise ExtractionError(f"Could not extract metadata: {exc}") from exc

    def _get_youtube_structured_metadata(
        self, url: str
    ) -> Optional[Dict[str, Optional[str]]]:
        """
        Extract "Golden Truth" music metadata from YouTube's ytInitialData.
        This captures the "Music in this video" section.
        """
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None

            html = response.text
            match = re.search(r"var ytInitialData = ({.*?});", html)
            if not match:
                return None

            data = json.loads(match.group(1))

            # Safe traversal to find the structured description panel
            panels = data.get("engagementPanels", [])
            structured_panel = next(
                (
                    p
                    for p in panels
                    if self._get_path(
                        p, ["engagementPanelSectionListRenderer", "panelIdentifier"]
                    )
                    == "engagement-panel-structured-description"
                ),
                None,
            )

            if not structured_panel:
                return None

            items = self._get_path(
                structured_panel,
                [
                    "engagementPanelSectionListRenderer",
                    "content",
                    "structuredDescriptionContentRenderer",
                    "items",
                ],
                default=[],
            )

            for item in items:
                if "horizontalCardListRenderer" in item:
                    cards = item["horizontalCardListRenderer"].get("cards", [])
                    for card in cards:
                        vm = card.get("videoAttributeViewModel")
                        if vm:
                            # Extract basic fields
                            result: Dict[str, Optional[str]] = {
                                "title": vm.get("title"),
                                "artist": vm.get("subtitle"),
                                "album": None,
                                "album_cover_url": None,
                            }

                            # Get image URL
                            sources = self._get_path(
                                vm, ["image", "sources"], default=[]
                            )
                            if sources:
                                result["album_cover_url"] = sources[0].get("url")

                            # Get explicit Album label
                            try:
                                dialog = self._get_path(
                                    vm,
                                    [
                                        "overflowMenuOnTap",
                                        "innertubeCommand",
                                        "confirmDialogEndpoint",
                                        "content",
                                        "confirmDialogRenderer",
                                    ],
                                )
                                if dialog:
                                    messages = dialog.get("dialogMessages", [])
                                    for msg in messages:
                                        full_text = "".join(
                                            [
                                                r.get("text", "")
                                                for r in msg.get("runs", [])
                                            ]
                                        )
                                        if "Album:" in full_text:
                                            result["album"] = (
                                                full_text.split("Album:")[1]
                                                .strip()
                                                .split("\n")[0]
                                            )
                            except Exception:
                                pass

                            # Fallback for album name
                            if not result["album"]:
                                result["album"] = self._get_path(
                                    vm, ["secondarySubtitle", "content"]
                                )

                            return result

            return None
        except Exception:
            return None

    def _get_path(self, obj: Any, path: List[str], default: Any = None) -> Any:
        """Safely traverse a nested dictionary/list structure."""
        current = obj
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _extract_track_metadata(self, info: Dict[str, Any]) -> TrackMetadata:
        """Extract provider-neutral metadata from a yt-dlp info dictionary."""
        original_title = self._as_text(info.get("title")) or "Unknown Title"
        reported_title = self._as_text(info.get("track"))
        reported_artist = self._as_text(info.get("artist") or info.get("creator"))
        uploader = self._as_text(info.get("uploader")) or "Unknown Artist"
        duration = info.get("duration")
        source_url = self._as_text(
            info.get("webpage_url") or info.get("original_url") or info.get("url")
        )
        thumbnail = self._as_text(info.get("thumbnail"))
        source = self._source_from_info(info, source_url)

        structured = None
        if source is MediaSource.YOUTUBE and source_url:
            structured = self._get_youtube_structured_metadata(source_url)

        parsed = self.parse_title(original_title)
        title = reported_title or parsed.get("title") or original_title
        if source is MediaSource.SOUNDCLOUD:
            artist = reported_artist or uploader
        else:
            artist = reported_artist or parsed.get("artist") or uploader

        metadata = TrackMetadata(
            title=title,
            artist=artist,
            album=self._as_text(info.get("album")),
            genre=self._as_text(info.get("genre")),
            year=self._as_year(info.get("release_year") or info.get("upload_date")),
            track_number=self._as_int(info.get("track_number")),
            duration=self._as_int(duration),
            source_url=source_url,
            thumbnail_url=thumbnail,
            source_cover_url=thumbnail if source is MediaSource.SOUNDCLOUD else None,
            source=source.value if source else None,
            original_title=original_title,
        )

        if structured:
            structured_title = structured.get("title")
            structured_artist = structured.get("artist")
            if structured_title:
                metadata.title = structured_title
            if structured_artist:
                metadata.artist = structured_artist
            metadata.album = structured.get("album") or metadata.album
            metadata.source_cover_url = (
                structured.get("album_cover_url") or metadata.source_cover_url
            )

        metadata.extra = {
            "album": info.get("album"),
            "channel": info.get("channel"),
            "channel_url": info.get("channel_url"),
            "extractor": info.get("extractor_key") or info.get("extractor"),
        }

        return metadata

    def _extract_playlist_info(self, info: Dict[str, Any]) -> PlaylistInfo:
        """Extract metadata from a playlist info dict."""
        playlist_title = info.get("title", "Unknown Playlist")
        entries = [entry for entry in info.get("entries", []) if entry]
        total_entries = len(entries)
        if not entries:
            raise ExtractionError("The playlist does not contain downloadable tracks.")

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

    def _is_album_playlist(
        self, info: Dict[str, Any], entries: List[Dict[str, Any]]
    ) -> bool:
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

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract a YouTube video ID for backward compatibility."""
        return URLValidator.extract_video_id(url)

    @staticmethod
    def _source_from_info(
        info: Dict[str, Any], source_url: Optional[str]
    ) -> Optional[MediaSource]:
        extractor = str(
            info.get("extractor_key") or info.get("extractor") or ""
        ).lower()
        if "soundcloud" in extractor:
            return MediaSource.SOUNDCLOUD
        if "youtube" in extractor:
            return MediaSource.YOUTUBE
        if source_url:
            classification = URLValidator.classify(source_url)
            if classification:
                return classification.source
        return None

    @staticmethod
    def _as_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _as_year(cls, value: Any) -> Optional[int]:
        if isinstance(value, str) and len(value) >= 4:
            value = value[:4]
        year = cls._as_int(value)
        return year if year is not None and 1900 <= year <= 2100 else None

    @staticmethod
    def _format_extraction_error(exc: DownloadError) -> str:
        message = str(exc).removeprefix("ERROR: ").strip()
        if "Unsupported URL" in message:
            return "This URL is not supported by the media extractor."
        return message or "The media service did not return usable metadata."


# Keep the public name for callers that imported it before multi-source support.
YouTubeExtractor = MediaExtractor


__all__ = [
    "ExtractionError",
    "MediaExtractor",
    "PlaylistInfo",
    "TrackMetadata",
    "YouTubeExtractor",
]
