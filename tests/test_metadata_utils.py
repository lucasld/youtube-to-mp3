"""Tests for metadata and validation helpers."""

from youtube_to_mp3.album_cover_retriever import AlbumMatcher
from youtube_to_mp3.extractor import TrackMetadata
from youtube_to_mp3.metadata import MetadataCleaner, MetadataFormatter
from youtube_to_mp3.utils.validation import URLValidator


def test_metadata_cleaner_applies_defaults():
    raw = TrackMetadata(
        title="  Example Song  ",
        artist="",
        album="  Example Album  ",
        genre=None,
        year=1899,
        track_number=0,
        total_tracks=2,
        duration=185,
        source_url="https://example.test",
    )

    cleaned = MetadataCleaner.clean_track(raw, default_genre="Unknown")

    assert cleaned.title == "Example Song"
    assert cleaned.artist == "Unknown Artist"
    assert cleaned.album == "Example Album"
    assert cleaned.genre == "Unknown"
    assert cleaned.year is None
    assert cleaned.track_number is None
    assert cleaned.total_tracks == 2


def test_metadata_formatter_duration():
    metadata = TrackMetadata(
        title="Song", artist="Artist", duration=245, source_url="https://example.test"
    )
    formatted = MetadataFormatter.format_track_info(metadata)
    assert formatted["Duration"] == "04:05"


def test_url_validator_classifies_urls():
    video_url = "https://youtu.be/dQw4w9WgXcQ"
    playlist_url = "https://www.youtube.com/playlist?list=PL12345"
    mobile_url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
    invalid_url = "https://example.com/video"

    assert URLValidator.is_valid_youtube_url(video_url)
    assert URLValidator.classify_url(video_url)[0] == "video"

    assert URLValidator.is_valid_youtube_url(playlist_url)
    assert URLValidator.classify_url(playlist_url)[0] == "playlist"

    assert URLValidator.is_valid_youtube_url(mobile_url)
    assert URLValidator.classify_url(mobile_url)[0] == "video"

    assert not URLValidator.is_valid_youtube_url(invalid_url)
    assert URLValidator.classify_url(invalid_url)[0] == "invalid"


def test_album_matcher_normalize_album_name():
    """Test album name normalization."""
    # Test basic normalization
    assert AlbumMatcher.normalize_album_name("  Album Name  ") == "Album Name"

    # Test parentheses removal
    assert AlbumMatcher.normalize_album_name("Album Name (Deluxe)") == "Album Name"

    # Test brackets removal
    assert AlbumMatcher.normalize_album_name("Album Name [Remastered]") == "Album Name"

    # Test combined
    assert AlbumMatcher.normalize_album_name("  Album Name (Deluxe) [Remastered]  ") == "Album Name"


def test_album_matcher_album_names_match():
    """Test album name matching with different confidence levels."""
    # Exact match
    assert AlbumMatcher.album_names_match("Album Name", "Album Name") == (True, "exact")

    # Partial match
    assert AlbumMatcher.album_names_match("Album Name Deluxe", "Album Name") == (True, "partial")
    assert AlbumMatcher.album_names_match("Album Name", "Album Name Deluxe") == (True, "partial")

    # Word overlap (should work with default threshold)
    assert AlbumMatcher.album_names_match("Album One Two", "Album Two Three") == (True, "word_overlap")

    # No match
    assert AlbumMatcher.album_names_match("Completely Different", "Album Name") == (False, "no_match")

    # No album expected
    assert AlbumMatcher.album_names_match("Any Name", "") == (True, "no_album_expected")
