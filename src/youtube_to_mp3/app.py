"""Main Textual application for YouTube to MP3 converter."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, List, Optional

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header

from .config import AppConfig, load_config
from .downloader import DownloadJob
from .pipeline import DownloadOutcome, DownloadPipeline, ExtractionResult
from .ui.download_progress_screen import DownloadProgressScreen
from .ui.download_summary_screen import DownloadSummaryScreen
from .ui.metadata_review_screen import MetadataReviewScreen
from .ui.url_input_screen import URLInputScreen


class YouTubeToMp3App(App):
    """Main Textual application for YouTube to MP3 conversion."""

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: $primary;
        color: $text;
    }

    Footer {
        background: $primary;
        color: $text;
    }
    """

    TITLE = "YouTube to MP3 Converter"
    SUB_TITLE = "Transform YouTube content into properly tagged MP3 files"

    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config: AppConfig = config or load_config()
        self.pipeline = DownloadPipeline(self.config)
        self._current_extraction: Optional[ExtractionResult] = None
        self._url_screen: Optional[URLInputScreen] = None
        self._last_output_directory: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    async def on_mount(self) -> None:
        self._url_screen = URLInputScreen()
        await self.push_screen(self._url_screen)

    async def start_metadata_flow(self, url: str) -> None:
        """Extract metadata for the provided URL and show the review screen."""
        try:
            extraction = await asyncio.to_thread(self.pipeline.extract, url)
        except Exception as exc:  # pragma: no cover - surfaced to user
            self.notify(f"Failed to extract metadata: {exc}", severity="error")
            return

        self._current_extraction = extraction
        await self.push_screen(MetadataReviewScreen(extraction))

    async def start_download_from_review(self, extraction: ExtractionResult) -> None:
        """Begin the download flow for the current extraction."""
        output_dir = self.config.ensure_output_directory()
        playlist_title = extraction.playlist_title if extraction.is_playlist else None

        try:
            jobs = self.pipeline.create_download_jobs(
                extraction.tracks, output_dir, playlist_title
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return

        if not jobs:
            self.notify("Select at least one track to download.", severity="warning")
            return

        headline = (
            f"Downloading playlist: {playlist_title}"
            if extraction.is_playlist and playlist_title
            else f"Downloading track: {extraction.tracks[0].title}"
        )

        self._last_output_directory = output_dir

        await self.push_screen(DownloadProgressScreen(jobs, headline))

    async def handle_download_complete(
        self, outcomes: List[DownloadOutcome]
    ) -> None:
        """Show the download summary once progress completes."""
        extraction = self._current_extraction
        output_dir = self._last_output_directory or self.config.output_directory

        if extraction:
            await self.push_screen(
                DownloadSummaryScreen(extraction, outcomes, output_dir)
            )
        else:
            await self.reset_to_input()

    async def perform_download(
        self,
        jobs: List[DownloadJob],
        progress_callback: Callable[[int, int, DownloadJob], None],
    ) -> List[DownloadOutcome]:
        """Delegate download execution to the pipeline."""
        return await self.pipeline.download(jobs, progress_callback=progress_callback)

    async def reset_to_input(self) -> None:
        """Return to the initial URL input screen."""
        # Clear the entire screen stack and create a fresh URL input screen
        self.screen_stack.clear()
        self._url_screen = URLInputScreen()
        await self.push_screen(self._url_screen)
        self._current_extraction = None
        self._last_output_directory = None

    @property
    def output_directory(self) -> Path:
        """Expose the configured output directory."""
        return self.config.output_directory

    def ensure_output_directory(self) -> None:
        """Ensure the output directory exists."""
        self.config.ensure_output_directory()

    async def on_screen_dismissed(self, event: Screen.Dismissed) -> None:
        await super().on_screen_dismissed(event)


__all__ = ["YouTubeToMp3App"]
