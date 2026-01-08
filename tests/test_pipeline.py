"""Tests for the download pipeline utilities."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from youtube_to_mp3.album_cover_retriever import CoverResult
from youtube_to_mp3.config import AppConfig
from youtube_to_mp3.downloader import DownloadJob, DownloadResult
from youtube_to_mp3.extractor import PlaylistInfo, TrackMetadata
from youtube_to_mp3.pipeline import AlbumCoverCache, DownloadPipeline


class StubExtractor:
    """A stub extractor returning canned metadata."""

    def __init__(self, playlist: bool = False) -> None:
        self.playlist = playlist

    def extract_metadata(self, url: str):  # noqa: D401 - part of stub interface
        if self.playlist:
            tracks = [
                TrackMetadata(title="Song 1", artist="Artist", source_url=f"{url}/1"),
                TrackMetadata(title="Song 2", artist="Artist", source_url=f"{url}/2"),
            ]
            return PlaylistInfo(
                title="My Playlist",
                tracks=tracks,
                is_album=False,
                url=url,
                total_tracks=2,
            )
        return TrackMetadata(title="Solo", artist="Artist", source_url=url)


class FakeDownloader:
    """Downloader that records jobs without hitting the network."""

    def __init__(self) -> None:
        self.downloaded: list[DownloadJob] = []

    def create_output_path(self, metadata: TrackMetadata, base_dir: Path) -> Path:
        return base_dir / f"{metadata.title}.mp3"

    def download_track(self, job: DownloadJob) -> DownloadResult:
        job.status = "completed"
        job.error = None
        self.downloaded.append(job)
        return DownloadResult(success=True)

    def download_track_with_cache(self, job: DownloadJob, cover_cache=None) -> DownloadResult:
        return self.download_track(job)


def test_pipeline_downloads_tracks(tmp_path: Path):
    config = AppConfig(output_directory=tmp_path)
    extractor = StubExtractor()
    downloader = FakeDownloader()
    pipeline = DownloadPipeline(config, extractor=extractor, downloader=downloader)  # type: ignore[arg-type]

    extraction = pipeline.extract("https://youtu.be/example")
    assert len(extraction.tracks) == 1

    jobs = pipeline.create_download_jobs(extraction.tracks, tmp_path)
    assert jobs[0].output_path.name.endswith(".mp3")

    progress_events: list[tuple[int, str]] = []

    def progress_callback(index: int, total: int, job: DownloadJob) -> None:
        progress_events.append((index, job.status))

    outcomes = asyncio.run(pipeline.download(jobs, progress_callback=progress_callback))

    assert len(outcomes) == 1
    assert outcomes[0].success
    assert progress_events == [(1, "in_progress"), (1, "completed")]


def test_pipeline_validates_missing_source_url(tmp_path: Path):
    config = AppConfig(output_directory=tmp_path)
    extractor = StubExtractor()
    pipeline = DownloadPipeline(config, extractor=extractor)

    extraction = pipeline.extract("https://youtu.be/example")
    extraction.tracks[0].source_url = None

    with pytest.raises(ValueError):
        pipeline.create_download_jobs(extraction.tracks, tmp_path)


def test_album_cover_cache():
    """Test album cover cache functionality."""
    cache = AlbumCoverCache()

    # Test cache miss
    result = cache.get_cover("Artist", "Album")
    assert result is None

    # Test cache set and get
    cover_result = CoverResult(success=True, cover_url="http://example.com/cover.jpg")
    cache.set_cover("Artist", "Album", cover_result)

    cached_result = cache.get_cover("Artist", "Album")
    assert cached_result is not None
    assert cached_result.success is True
    assert cached_result.cover_url == "http://example.com/cover.jpg"

    # Test case insensitive matching
    cached_result_upper = cache.get_cover("ARTIST", "ALBUM")
    assert cached_result_upper is not None

    # Test different artist/album returns None
    different_result = cache.get_cover("Different Artist", "Album")
    assert different_result is None

    # Test cache clear
    cache.clear()
    cleared_result = cache.get_cover("Artist", "Album")
    assert cleared_result is None
