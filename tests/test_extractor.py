"""Tests for the YouTube extractor module."""

import pytest
from yt_dlp.utils import DownloadError

from youtube_to_mp3.extractor import (
    ExtractionError,
    MediaExtractor,
    PlaylistInfo,
    TrackMetadata,
    YouTubeExtractor,
)


class TestYouTubeExtractor:
    """Test the YouTubeExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create an extractor instance for testing."""
        return YouTubeExtractor()

    def test_parse_title_simple(self, extractor):
        """Test parsing a simple 'Artist - Title' format."""
        title = "Artist Name - Song Title"
        result = extractor.parse_title(title)

        assert result["artist"] == "Artist Name"
        assert result["title"] == "Song Title"

    def test_parse_title_with_suffix(self, extractor):
        """Test parsing titles with common YouTube suffixes."""
        title = "Artist Name - Song Title (Official Music Video)"
        result = extractor.parse_title(title)

        assert result["artist"] == "Artist Name"
        assert result["title"] == "Song Title"

    def test_parse_title_no_separator(self, extractor):
        """Test parsing titles without clear separators."""
        title = "Song Title"
        result = extractor.parse_title(title)

        assert result["title"] == "Song Title"
        assert "artist" not in result

    def test_clean_title(self, extractor):
        """Test title cleaning functionality."""
        title = "Artist - Song [Official Video] (HD)"
        result = extractor.parse_title(title)

        # Should still work despite brackets
        assert "artist" in result
        assert result["title"] == "Song [Official Video] (HD)"

    def test_extract_video_id(self, extractor):
        """Test video ID extraction from various URL formats."""
        test_cases = [
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]

        for url, expected_id in test_cases:
            video_id = extractor._extract_video_id(url)
            assert video_id == expected_id


class TestTrackMetadata:
    """Test the TrackMetadata dataclass."""

    def test_track_metadata_creation(self):
        """Test creating a TrackMetadata instance."""
        metadata = TrackMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            genre="Rock",
            year=2023,
            track_number=1,
            total_tracks=10,
            duration=180,
        )

        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.genre == "Rock"
        assert metadata.year == 2023
        assert metadata.track_number == 1
        assert metadata.total_tracks == 10
        assert metadata.duration == 180

    def test_track_metadata_defaults(self):
        """Test TrackMetadata with minimal required fields."""
        metadata = TrackMetadata(title="Test Song", artist="Test Artist")

        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album is None
        assert metadata.genre is None
        assert metadata.year is None
        assert metadata.track_number is None
        assert metadata.total_tracks is None
        assert metadata.duration is None


def test_soundcloud_metadata_uses_provider_fields_without_youtube_scraping(monkeypatch):
    extractor = MediaExtractor()

    def unexpected_request(url: str):
        raise AssertionError(f"YouTube enrichment requested for {url}")

    monkeypatch.setattr(
        extractor, "_get_youtube_structured_metadata", unexpected_request
    )
    metadata = extractor._extract_track_metadata(
        {
            "title": "Raw SoundCloud title",
            "track": "Track title",
            "artist": "Track artist",
            "album": "Track album",
            "release_year": 2024,
            "duration": 183,
            "webpage_url": "https://soundcloud.com/track-artist/track-title",
            "thumbnail": "https://i1.sndcdn.com/artworks-example-large.jpg",
            "extractor_key": "Soundcloud",
        }
    )

    assert metadata.title == "Track title"
    assert metadata.artist == "Track artist"
    assert metadata.album == "Track album"
    assert metadata.source == "soundcloud"
    assert metadata.source_cover_url == metadata.thumbnail_url


def test_extraction_errors_do_not_return_fake_metadata(monkeypatch):
    class FailingYoutubeDL:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url: str, download: bool):
            raise DownloadError("media is unavailable")

    monkeypatch.setattr("youtube_to_mp3.extractor.yt_dlp.YoutubeDL", FailingYoutubeDL)

    with pytest.raises(ExtractionError, match="media is unavailable"):
        MediaExtractor().extract_metadata("https://soundcloud.com/artist/track")


class TestPlaylistInfo:
    """Test the PlaylistInfo dataclass."""

    def test_playlist_info_creation(self):
        """Test creating a PlaylistInfo instance."""
        tracks = [
            TrackMetadata(title="Song 1", artist="Artist"),
            TrackMetadata(title="Song 2", artist="Artist"),
        ]

        playlist = PlaylistInfo(title="Test Playlist", tracks=tracks, is_album=False)

        assert playlist.title == "Test Playlist"
        assert len(playlist.tracks) == 2
        assert playlist.is_album is False
