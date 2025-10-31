"""Download summary screen."""

from __future__ import annotations

import asyncio
from typing import List

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..pipeline import DownloadOutcome, ExtractionResult
from ..utils.filesystem import open_file, open_folder


class DownloadSummaryScreen(Screen):
    """Display download results and offer follow-up actions."""

    BINDINGS = [
        Binding("enter", "new_download", "New Download"),
        Binding("o", "open_file_or_folder", "Open File/Folder"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(
        self,
        extraction: ExtractionResult,
        outcomes: List[DownloadOutcome],
        output_directory,
    ) -> None:
        super().__init__()
        self.extraction = extraction
        self.outcomes = outcomes
        self.output_directory = output_directory
        self.successes = [outcome for outcome in outcomes if outcome.success]
        self.failures = [outcome for outcome in outcomes if not outcome.success]

    def compose(self):
        success_count = len(self.successes)
        failure_count = len(self.failures)
        header = "Playlist" if self.extraction.is_playlist else "Track"

        with Vertical(id="summary-container"):
            yield Static(f"{header} download complete", id="summary-title")
            yield Static(f"Saved files to: {self.output_directory}")
            yield Static(
                f"Successful downloads: {success_count} | Failed downloads: {failure_count}"
            )

            if self.successes:
                yield Static("Completed:")
                for outcome in self.successes:
                    title = (
                        f"{outcome.job.metadata.artist} - {outcome.job.metadata.title}"
                    )
                    cover_status = self._format_cover_status(outcome)
                    yield Static(f"  ✔ {title}{cover_status}")

            if self.failures:
                yield Static("Failed:")
                for outcome in self.failures:
                    title = (
                        f"{outcome.job.metadata.artist} - {outcome.job.metadata.title}"
                    )
                    detail = outcome.error or "Unknown error"
                    yield Static(f"  ✖ {title} ({detail})")

            with Horizontal(id="summary-buttons"):
                if self.successes:
                    yield Button("Open File", id="open-file", variant="primary")
                else:
                    yield Button("Open Folder", id="open-folder", variant="primary")
                yield Button("New Download", id="new-download", variant="default")
                yield Button("Quit", id="quit-app", variant="default")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id in ("open-folder", "open-file"):
            await self.action_open_file_or_folder()
        elif button_id == "new-download":
            await self.action_new_download()
        elif button_id == "quit-app":
            self.app.exit()

    async def action_open_file_or_folder(self) -> None:
        """Open the first successful download file, or the folder if no successes."""
        if self.successes:
            # Open and select the first successful file
            first_success = self.successes[0]
            await asyncio.to_thread(open_file, first_success.job.output_path)
        else:
            # No successful downloads, just open the folder
            await asyncio.to_thread(open_folder, self.output_directory)

    async def action_new_download(self) -> None:
        app = self.app
        await app.reset_to_input()

    async def action_close(self) -> None:
        app = self.app
        await app.reset_to_input()

    def _format_cover_status(self, outcome) -> str:
        """Format album cover status for display."""
        if not outcome.job.metadata.album:
            return " (no album cover - no album specified)"

        if outcome.cover_success:
            source = outcome.cover_source or "unknown"
            confidence = outcome.cover_confidence or "unknown"
            return f" (album cover: {source} - {confidence})"
        else:
            return " (no album cover found)"


__all__ = ["DownloadSummaryScreen"]
