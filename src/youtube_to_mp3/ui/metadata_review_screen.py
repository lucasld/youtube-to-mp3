"""Metadata review screen for confirming and editing tracks."""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional, TYPE_CHECKING, Callable, cast

from textual import events
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from ..metadata import MetadataCleaner
from ..pipeline import ExtractionResult
from ..extractor import TrackMetadata

if TYPE_CHECKING:  # pragma: no cover - for typing only
    from ..app import YouTubeToMp3App


class TrackEditModal(Screen):
    """Modal dialog for editing a single track's metadata."""

    def __init__(
        self,
        metadata: TrackMetadata,
        callback: Callable[[Optional[TrackMetadata]], None]
    ) -> None:
        super().__init__()
        self.metadata = metadata
        self.callback = callback

    def compose(self):
        with Vertical(id="edit-container"):
            yield Static("Edit Track Metadata", id="edit-title")
            yield Input(id="title", placeholder="Title")
            yield Input(id="artist", placeholder="Artist")
            yield Input(id="album", placeholder="Album")
            yield Input(id="genre", placeholder="Genre")
            yield Input(id="year", placeholder="Year")
            yield Input(id="track_number", placeholder="Track Number")
            yield Input(id="total_tracks", placeholder="Total Tracks")
            with Horizontal(id="edit-buttons"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        self.query_one("#title", Input).value = self.metadata.title
        self.query_one("#artist", Input).value = self.metadata.artist
        self.query_one("#album", Input).value = self.metadata.album or ""
        self.query_one("#genre", Input).value = self.metadata.genre or ""
        self.query_one("#year", Input).value = self._optional_int_to_str(
            self.metadata.year
        )
        self.query_one("#track_number", Input).value = self._optional_int_to_str(
            self.metadata.track_number
        )
        self.query_one("#total_tracks", Input).value = self._optional_int_to_str(
            self.metadata.total_tracks
        )
        self.query_one("#title", Input).focus()

    def _optional_int_to_str(self, value: Optional[int]) -> str:
        return "" if value is None else str(value)

    def _parse_int(self, value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            updated = replace(
                self.metadata,
                title=self.query_one("#title", Input).value.strip() or "Unknown Title",
                artist=self.query_one("#artist", Input).value.strip()
                or "Unknown Artist",
                album=self._clean_optional(self.query_one("#album", Input).value),
                genre=self._clean_optional(self.query_one("#genre", Input).value),
                year=self._parse_int(self.query_one("#year", Input).value),
                track_number=self._parse_int(
                    self.query_one("#track_number", Input).value
                ),
                total_tracks=self._parse_int(
                    self.query_one("#total_tracks", Input).value
                ),
            )
            updated = MetadataCleaner.clean_track(updated)
            self.callback(updated)
            self.app.pop_screen()
        else:
            self.callback(None)
            self.app.pop_screen()

    def _clean_optional(self, value: str) -> Optional[str]:
        value = value.strip()
        return value or None


class BulkEditModal(Screen):
    """Modal dialog for editing multiple tracks at once."""

    def __init__(self, callback: Callable[[Optional[dict]], None]) -> None:
        super().__init__()
        self.callback = callback

    def compose(self):
        with Vertical(id="bulk-container"):
            yield Static("Bulk Edit Metadata", id="bulk-title")
            yield Static("Leave a field blank to keep current values.")
            yield Input(id="album", placeholder="Album")
            yield Input(id="genre", placeholder="Genre")
            yield Input(id="year", placeholder="Year")
            with Horizontal(id="bulk-buttons"):
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            album = self.query_one("#album", Input).value.strip()
            genre = self.query_one("#genre", Input).value.strip()
            year_str = self.query_one("#year", Input).value.strip()
            year = None
            if year_str:
                try:
                    year = int(year_str)
                except ValueError:
                    year = None
            self.callback(
                {
                    "album": album or None,
                    "genre": genre or None,
                    "year": year,
                }
            )
            self.app.pop_screen()
        else:
            self.callback(None)
            self.app.pop_screen()


class MetadataReviewScreen(Screen):
    """Screen for reviewing and editing extracted metadata."""

    BINDINGS = [
        Binding("space", "toggle_select", "Toggle Select", show=False),
        Binding("e", "edit_track", "Edit Track"),
        Binding("b", "bulk_edit", "Bulk Edit"),
        Binding("enter", "download", "Download"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, extraction: ExtractionResult) -> None:
        super().__init__()
        self.extraction = extraction
        self.table: DataTable = DataTable(zebra_stripes=True)

    def compose(self):
        with Vertical(id="metadata-container"):
            title = "Playlist" if self.extraction.is_playlist else "Track"
            yield Static(f"Review {title} Metadata", id="metadata-title")
            yield Static(
                "Use Space to toggle selection, E to edit a track, B for bulk edits.",
                id="metadata-instructions",
            )
            yield self.table
            with Horizontal(id="metadata-buttons"):
                yield Button("Download Selected", id="download", variant="primary")
                yield Button("Edit Track", id="edit", variant="default")
                yield Button("Bulk Edit", id="bulk", variant="default")
                yield Button("Back", id="back", variant="default")

    def on_mount(self) -> None:
        self.table.focus()
        self._setup_table()

    def _setup_table(self) -> None:
        self.table.clear(columns=True)
        self.table.add_columns(
            ("#", "index"),
            ("Download", "selected"),
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
            ("Year", "year"),
            ("Duration", "duration"),
        )

        for idx, track in enumerate(self.extraction.tracks):
            self.table.add_row(*self._row_values(idx, track), key=str(idx))

    def _row_values(self, index: int, track: TrackMetadata) -> List[str]:
        duration = (
            ""
            if track.duration is None
            else f"{track.duration // 60:02}:{track.duration % 60:02}"
        )
        year = "" if track.year is None else str(track.year)
        album = track.album or ""
        selected = "✔" if track.selected else ""
        return [
            str(index + 1),
            selected,
            track.title,
            track.artist,
            album,
            year,
            duration,
        ]

    def _refresh_row(self, row_index: int) -> None:
        row_key = str(row_index)
        track = self.extraction.tracks[row_index]
        for column_key, value in zip(
            ["index", "selected", "title", "artist", "album", "year", "duration"],
            self._row_values(row_index, track),
        ):
            self.table.update_cell(row_key, column_key, value)

    def _require_current_track(self) -> Optional[int]:
        row_index = self.table.cursor_row
        if row_index is None:
            self.notify("Select a track first.", severity="warning")
            return None
        return row_index

    async def action_toggle_select(self) -> None:
        row_index = self._require_current_track()
        if row_index is None:
            return
        track = self.extraction.tracks[row_index]
        track.selected = not track.selected
        self._refresh_row(row_index)

    async def action_edit_track(self) -> None:
        row_index = self._require_current_track()
        if row_index is None:
            return

        track = self.extraction.tracks[row_index]

        def edit_callback(result: Optional[TrackMetadata]) -> None:
            if result:
                cleaned = self._clean_track(result)
                self.extraction.tracks[row_index] = cleaned
                self._refresh_row(row_index)

        await self.app.push_screen(TrackEditModal(track, edit_callback))

    async def action_bulk_edit(self) -> None:
        selected_indexes = [
            idx for idx, track in enumerate(self.extraction.tracks) if track.selected
        ]
        if not selected_indexes:
            self.notify(
                "Select at least one track to apply bulk edits.", severity="warning"
            )
            return

        def bulk_callback(result: Optional[dict]) -> None:
            if not result:
                return
            for idx in selected_indexes:
                track = self.extraction.tracks[idx]
                updated = replace(
                    track,
                    album=result.get("album", track.album),
                    genre=result.get("genre", track.genre),
                    year=result.get("year", track.year),
                )
                self.extraction.tracks[idx] = self._clean_track(updated)
                self._refresh_row(idx)

        await self.app.push_screen(BulkEditModal(bulk_callback))

    async def action_download(self) -> None:
        selected = [track for track in self.extraction.tracks if track.selected]
        if not selected:
            self.notify("Select at least one track to download.", severity="warning")
            return

        app = cast("YouTubeToMp3App", self.app)
        await app.start_download_from_review(self.extraction)

    async def action_back(self) -> None:
        app = cast("YouTubeToMp3App", self.app)
        await app.reset_to_input()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            await self.action_download()
        elif event.button.id == "edit":
            await self.action_edit_track()
        elif event.button.id == "bulk":
            await self.action_bulk_edit()
        elif event.button.id == "back":
            await self.action_back()

    async def on_key(self, event: events.Key) -> None:
        if event.key == " ":
            await self.action_toggle_select()

    def _clean_track(self, metadata: TrackMetadata) -> TrackMetadata:
        app = self.app
        default_genre = None
        try:  # pragma: no branch - attribute access helper
            default_genre = getattr(
                cast("YouTubeToMp3App", app).config, "default_genre", None
            )
        except AttributeError:  # pragma: no cover - defensive
            default_genre = None
        return MetadataCleaner.clean_track(metadata, default_genre=default_genre)
