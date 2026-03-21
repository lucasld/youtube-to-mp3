"""Tests for downloader logging and error handling."""

from __future__ import annotations

from yt_dlp.utils import DownloadError

from youtube_to_mp3.downloader import AudioDownloader


def test_format_download_error_special_cases_http_403() -> None:
    downloader = AudioDownloader()

    result = downloader._format_download_error(DownloadError("HTTP Error 403: Forbidden"))

    assert result == (
        "HTTP Error 403: Forbidden (YouTube rejected this stream; retry or update yt-dlp)"
    )


def test_format_download_error_preserves_other_messages() -> None:
    downloader = AudioDownloader()

    result = downloader._format_download_error(DownloadError("network timeout"))

    assert result == "network timeout"
