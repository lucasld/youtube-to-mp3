"""Tests for the YouTube extractor module."""

import pytest
from youtube_to_mp3.extractor import YouTubeExtractor, TrackMetadata, PlaylistInfo


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
