"""End-to-end extraction and download pipeline utilities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .album_cover_retriever import CoverResult
from .config import AppConfig
from .downloader import AudioDownloader, DownloadJob, ProgressCallback
from .extractor import PlaylistInfo, TrackMetadata, YouTubeExtractor
from .metadata import MetadataCleaner
from .utils.filesystem import sanitize_filename


@dataclass
class ExtractionResult:
    """Container for extracted metadata."""

    url: str
    tracks: List[TrackMetadata]
    is_playlist: bool
    playlist_title: Optional[str] = None
    playlist_url: Optional[str] = None


@dataclass
class AlbumCoverCache:
    """Cache for album covers to avoid duplicate API calls."""

    def __init__(self):
        self._cache: Dict[str, CoverResult] = {}

    def get_cover(self, artist: str, album: str) -> Optional[CoverResult]:
        """Get cached cover for artist/album combination."""
        key = f"{artist}|{album}".lower().strip()
        return self._cache.get(key)

    def set_cover(self, artist: str, album: str, cover_result: CoverResult) -> None:
        """Cache cover for artist/album combination."""
        key = f"{artist}|{album}".lower().strip()
        self._cache[key] = cover_result

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


@dataclass
class DownloadOutcome:
    """Outcome of an individual download."""

    job: DownloadJob
    success: bool
    error: Optional[str] = None
    cover_success: bool = False
    cover_source: Optional[str] = None
    cover_confidence: Optional[str] = None


class DownloadPipeline:
    """Coordinates metadata extraction and downloads."""

    def __init__(
        self,
        config: AppConfig,
        extractor: Optional[YouTubeExtractor] = None,
        downloader: Optional[AudioDownloader] = None,
    ) -> None:
        self.config = config
        self.extractor = extractor or YouTubeExtractor()
        self.downloader = downloader or AudioDownloader(
            rate_limit_delay=config.rate_limit_delay,
            audio_quality=config.audio_quality,
            filename_template=config.filename_template,
        )
        self.cover_cache = AlbumCoverCache()

    def extract(self, url: str) -> ExtractionResult:
        """Extract metadata for a YouTube URL."""
        info = self.extractor.extract_metadata(url)

        if isinstance(info, PlaylistInfo):
            tracks = [
                MetadataCleaner.clean_track(
                    track, default_genre=self.config.default_genre
                )
                for track in info.tracks
            ]
            return ExtractionResult(
                url=url,
                tracks=tracks,
                is_playlist=True,
                playlist_title=info.title,
                playlist_url=info.url,
            )

        cleaned_track = MetadataCleaner.clean_track(
            info, default_genre=self.config.default_genre
        )
        return ExtractionResult(url=url, tracks=[cleaned_track], is_playlist=False)

    def create_download_jobs(
        self,
        tracks: List[TrackMetadata],
        base_dir: Path,
        playlist_title: Optional[str] = None,
    ) -> List[DownloadJob]:
        """Create download jobs for the provided tracks."""
        target_dir = base_dir

        if playlist_title:
            playlist_folder = sanitize_filename(playlist_title)
            if playlist_folder:
                target_dir = base_dir / playlist_folder

        jobs: List[DownloadJob] = []
        for metadata in tracks:
            if not metadata.selected:
                continue

            url = metadata.source_url
            if not url:
                raise ValueError("Missing source URL for track; cannot download")

            output_path = self.downloader.create_output_path(metadata, target_dir)
            jobs.append(
                DownloadJob(url=url, metadata=metadata, output_path=output_path)
            )

        return jobs

    async def download(
        self,
        jobs: List[DownloadJob],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[DownloadOutcome]:
        """Download jobs asynchronously via a background thread."""

        if not jobs:
            return []

        # Pre-cache album covers for all unique artist/album combinations
        await self._pre_cache_album_covers(jobs)

        def _run_download() -> List[DownloadOutcome]:
            outcomes: List[DownloadOutcome] = []
            total = len(jobs)

            for index, job in enumerate(jobs, start=1):
                if progress_callback:
                    progress_callback(index, total, job)

                download_result = self.downloader.download_track_with_cache(job, self.cover_cache)

                if progress_callback:
                    progress_callback(index, total, job)

                cover_result = download_result.cover_result
                outcomes.append(
                    DownloadOutcome(
                        job=job,
                        success=download_result.success,
                        error=download_result.error,
                        cover_success=cover_result.success if cover_result else False,
                        cover_source=cover_result.source if cover_result else None,
                        cover_confidence=(
                            cover_result.album_match_confidence if cover_result else None
                        ),
                    )
                )

            return outcomes

        return await asyncio.to_thread(_run_download)

    async def _pre_cache_album_covers(self, jobs: List[DownloadJob]) -> None:
        """Pre-cache album covers for all unique artist/album combinations."""
        # Find unique artist/album combinations that need cover retrieval
        unique_albums: Dict[tuple[str, str], None] = {}

        for job in jobs:
            metadata = job.metadata
            if metadata.artist and metadata.album:
                # Only cache if we don't already have this combination
                key = (metadata.artist, metadata.album)
                if key not in unique_albums and not self.cover_cache.get_cover(*key):
                    unique_albums[key] = None

        # Retrieve covers for unique combinations
        if unique_albums:
            def _retrieve_covers():
                for artist, album in unique_albums.keys():
                    metadata = TrackMetadata(artist=artist, album=album)
                    cover_result = self.downloader.cover_retriever.retrieve_cover(metadata)
                    self.cover_cache.set_cover(artist, album, cover_result)

            await asyncio.to_thread(_retrieve_covers)


__all__ = ["DownloadPipeline", "ExtractionResult", "DownloadOutcome", "AlbumCoverCache"]
