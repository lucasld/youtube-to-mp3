"""Audio download and conversion functionality."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import yt_dlp
from mutagen.id3 import ID3, TALB, TCON, TIT2, TPE1, TRCK, TYER, APIC
from mutagen.mp3 import MP3

from .extractor import TrackMetadata
from .album_cover_retriever import AlbumCoverRetriever, CoverResult
from .utils.filesystem import sanitize_filename

if TYPE_CHECKING:
    from .pipeline import AlbumCoverCache

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[int, int, "DownloadJob"], None]


@dataclass
class DownloadResult:
    """Result of a single download operation."""
    success: bool
    error: Optional[str] = None
    cover_result: Optional[CoverResult] = None


@dataclass
class DownloadJob:
    """Represents a single download job."""

    url: str
    metadata: TrackMetadata
    output_path: Path
    status: str = "pending"
    error: Optional[str] = None


class AudioDownloader:
    """Handles audio download and conversion to the desired format."""

    def __init__(
        self,
        rate_limit_delay: float = 1.5,
        audio_quality: str = "192",
        filename_template: str = "{artist} - {title}",
    ):
        self.rate_limit_delay = rate_limit_delay
        self.audio_quality = audio_quality
        self.filename_template = filename_template
        self._last_request_time = 0.0
        self.cover_retriever = AlbumCoverRetriever()

    def download_track(self, job: DownloadJob) -> DownloadResult:
        """Download and convert a single track."""
        return self.download_track_with_cache(job, None)

    def download_track_with_cache(
        self, job: DownloadJob, cover_cache: Optional["AlbumCoverCache"]
    ) -> DownloadResult:
        """Download and convert a single track with optional cover cache."""
        try:
            self._apply_rate_limit()

            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            ydl_opts = self._get_ydl_opts(job.output_path)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([job.url])

            cover_result = self._embed_metadata_with_cache(
                job.output_path, job.metadata, cover_cache
            )

            job.status = "completed"
            job.error = None
            return DownloadResult(success=True, cover_result=cover_result)

        except Exception as exc:  # pragma: no cover - defensive guard
            job.status = "error"
            job.error = str(exc)
            return DownloadResult(success=False, error=str(exc))

    def _get_ydl_opts(self, output_path: Path) -> Dict[str, Any]:
        """Get yt-dlp options for audio conversion."""
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.audio_quality,
                }
            ],
            "outtmpl": str(output_path.with_suffix("").with_suffix(".%(ext)s")),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "overwrites": True,
        }

    def _embed_metadata(self, mp3_path: Path, metadata: TrackMetadata) -> Optional[CoverResult]:
        """Embed metadata and album cover into MP3 file. Returns cover result."""
        return self._embed_metadata_with_cache(mp3_path, metadata, None)

    def _embed_metadata_with_cache(
        self,
        mp3_path: Path,
        metadata: TrackMetadata,
        cover_cache: Optional["AlbumCoverCache"]
    ) -> Optional[CoverResult]:
        """Embed metadata and album cover into MP3 file with optional cache."""
        cover_result = None

        try:
            audio = MP3(mp3_path, ID3=ID3)

            if audio.tags is None:
                audio.add_tags()

            # Embed basic metadata
            audio.tags.add(TIT2(text=metadata.title))
            audio.tags.add(TPE1(text=metadata.artist))

            if metadata.album:
                audio.tags.add(TALB(text=metadata.album))
            if metadata.genre:
                audio.tags.add(TCON(text=metadata.genre))
            if metadata.year:
                audio.tags.add(TYER(text=str(metadata.year)))
            if metadata.track_number and metadata.total_tracks:
                track_info = f"{metadata.track_number}/{metadata.total_tracks}"
                audio.tags.add(TRCK(text=track_info))

            # Retrieve and embed album cover
            cover_result = self._embed_album_cover_with_cache(audio, metadata, cover_cache)

            audio.save()

        except Exception as exc:  # pragma: no cover - best effort tagging
            logger.warning(f"Could not embed metadata in {mp3_path}: {exc}")

        return cover_result

    def _embed_album_cover(self, audio: MP3, metadata: TrackMetadata) -> CoverResult:
        """Retrieve and embed album cover into MP3 file. Returns cover result."""
        return self._embed_album_cover_with_cache(audio, metadata, None)

    def _embed_album_cover_with_cache(
        self,
        audio: MP3,
        metadata: TrackMetadata,
        cover_cache: Optional["AlbumCoverCache"]
    ) -> CoverResult:
        """Retrieve and embed album cover into MP3 file with optional cache."""
        try:
            # Try to get cover from cache first
            cover_result = None
            if cover_cache and metadata.artist and metadata.album:
                cover_result = cover_cache.get_cover(metadata.artist, metadata.album)

            # If not in cache, retrieve it
            if not cover_result:
                cover_result = self.cover_retriever.retrieve_cover(metadata)
                # Cache the result for future use
                if cover_cache and metadata.artist and metadata.album:
                    cover_cache.set_cover(metadata.artist, metadata.album, cover_result)

            if cover_result.success and cover_result.cover_data:
                # Create APIC frame for album cover
                # Determine MIME type from data (basic check)
                mime_type = self._guess_mime_type(cover_result.cover_data)

                # Remove any existing APIC frames to avoid duplicates
                audio.tags.delall("APIC")

                # Add the cover art
                apic = APIC(
                    encoding=3,  # UTF-8
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=cover_result.cover_data
                )
                audio.tags.add(apic)

                source = cover_result.source or "unknown"
                confidence = cover_result.album_match_confidence
                logger.info(f"Embedded album cover from {source} ({confidence})")
            else:
                logger.info(f"No album cover found for '{metadata.album}'")

            return cover_result

        except Exception as exc:  # pragma: no cover - best effort cover embedding
            logger.warning(f"Could not embed album cover: {exc}")
            return CoverResult(
                success=False,
                error=f"Cover embedding failed: {str(exc)}",
                album_match_confidence="error"
            )

    def _guess_mime_type(self, image_data: bytes) -> str:
        """Guess MIME type from image data."""
        if len(image_data) < 12:
            return "image/jpeg"

        # Check for JPEG
        if image_data[:2] == b'\xff\xd8':
            return "image/jpeg"

        # Check for PNG
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"

        # Check for GIF
        if image_data[:6] in (b'GIF87a', b'GIF89a'):
            return "image/gif"

        # Default to JPEG
        return "image/jpeg"

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting to avoid YouTube bot detection."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def create_output_path(self, metadata: TrackMetadata, base_dir: Path) -> Path:
        """Create the output file path for a track."""
        filename = self._render_filename(metadata)
        sanitized = sanitize_filename(filename)
        return (base_dir / sanitized).with_suffix(".mp3")

    def _render_filename(self, metadata: TrackMetadata) -> str:
        """Render a filename from the configured template."""
        mapping = {
            "artist": metadata.artist or "Unknown Artist",
            "title": metadata.title or "Unknown Title",
            "album": metadata.album or "",
            "year": str(metadata.year) if metadata.year else "",
            "track_number": str(metadata.track_number) if metadata.track_number else "",
            "total_tracks": str(metadata.total_tracks) if metadata.total_tracks else "",
        }

        class _SafeDict(dict):
            def __missing__(self, key: str) -> str:  # pragma: no cover - defensive
                return ""

        rendered = self.filename_template.format_map(_SafeDict(mapping))
        return rendered.strip() or "Track"



__all__ = ["DownloadJob", "AudioDownloader", "ProgressCallback"]
