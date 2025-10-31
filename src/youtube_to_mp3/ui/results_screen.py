"""Result summary screen after downloads complete."""

from __future__ import annotations

from pathlib import Path
from typing import List, TYPE_CHECKING, cast

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..pipeline import DownloadOutcome, ExtractionResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..app import YouTubeToMp3App


class ResultsScreen(Screen):
    """Show download results and offer next actions."""

    BINDINGS = [
        Binding("enter", "new_download", "New Download"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(
        self,
        extraction: ExtractionResult,
        outcomes: List[DownloadOutcome],
        output_directory: Path,
    ) -> None:
        super().__init__()
        self.extraction = extraction
        self.outcomes = outcomes
        self.output_directory = output_directory

    def compose(self):
        successes = [outcome for outcome in self.outcomes if outcome.success]
        failures = [outcome for outcome in self.outcomes if not outcome.success]

        with Vertical(id="results-container"):
            header = "Playlist" if self.extraction.is_playlist else "Track"
            yield Static(f"{header} download complete", id="results-title")
            yield Static(f"Saved to: {self.output_directory}")
            yield Static(f"Successful downloads: {len(successes)}")
            yield Static(f"Failed downloads: {len(failures)}")

            if failures:
                yield Static("Failed items:", id="results-failures-title")
                for failure in failures:
                    title = (
                        f"{failure.job.metadata.artist} - {failure.job.metadata.title}"
                    )
                    yield Static(f"  - {title}: {failure.error}")

            with Horizontal(id="results-buttons"):
                yield Button("New Download", id="new-download", variant="primary")
                yield Button("Quit", id="quit", variant="default")

    async def action_new_download(self) -> None:
        app = cast("YouTubeToMp3App", self.app)
        await app.reset_to_input()

    async def action_quit(self) -> None:
        self.app.exit()

    async def on_button_pressed(self, event):
        if event.button.id == "new-download":
            await self.action_new_download()
        elif event.button.id == "quit":
            await self.action_quit()
