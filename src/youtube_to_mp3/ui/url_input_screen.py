"""URL input screen for the YouTube to MP3 converter."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..utils.validation import URLValidator

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..app import YouTubeToMp3App


class URLInputScreen(Screen):
    """Screen for entering YouTube URLs."""

    BINDINGS = [Binding("escape", "quit", "Quit", show=False)]

    CSS = """
    URLInputScreen {
        background: $surface;
    }

    #url-input {
        width: 80%;
        margin: 1;
    }

    #instructions {
        margin: 2 4;
        text-align: center;
    }

    #button-container {
        margin: 2;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def compose(self):
        with Vertical():
            with Center():
                yield Static("YouTube to MP3 Converter", id="title")
                yield Static(
                    "Paste a YouTube video or playlist URL below.\n"
                    "Press Enter or click Continue to proceed.",
                    id="instructions",
                )

            with Center():
                yield Input(
                    placeholder="https://youtu.be/... or https://www.youtube.com/...",
                    id="url-input",
                )

            with Center():
                with Horizontal(id="button-container"):
                    yield Button("Continue", variant="primary", id="continue-btn")
                    yield Button("Quit", variant="default", id="quit-btn")

            with Center():
                yield Static("", id="status")

    def on_mount(self) -> None:
        input_field = self.query_one("#url-input", Input)
        input_field.focus()
        self._set_status("")

    def on_show(self) -> None:
        """Called when the screen becomes visible."""
        input_field = self.query_one("#url-input", Input)
        input_field.focus()
        self._set_ui_enabled(True)
        self._set_status("")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self._handle_submission(event.value)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-btn":
            input_field = self.query_one("#url-input", Input)
            await self._handle_submission(input_field.value)
        elif event.button.id == "quit-btn":
            self.app.exit()

    async def action_quit(self) -> None:
        self.app.exit()

    async def _handle_submission(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            self.notify("Please enter a URL.", severity="warning")
            return

        if not URLValidator.is_valid_youtube_url(url):
            self.notify(
                "That does not look like a valid YouTube URL.", severity="error"
            )
            return

        self._set_status("Extracting metadata…")
        self._set_ui_enabled(False)

        try:
            await self._start_metadata_flow(url)
        except Exception as exc:  # pragma: no cover - defensive UI guard
            self.notify(str(exc), severity="error")
        finally:
            self._set_ui_enabled(True)
            self._set_status("")

    async def _start_metadata_flow(self, url: str) -> None:
        app = cast("YouTubeToMp3App", self.app)
        await app.start_metadata_flow(url)

    def _set_ui_enabled(self, enabled: bool) -> None:
        for widget in self.query("Button, Input"):
            widget.disabled = not enabled

    def _set_status(self, message: str) -> None:
        status = self.query_one("#status", Static)
        status.update(message)

    async def handle_url_from_clipboard(self, url: str) -> None:
        await self._handle_submission(url)

    def reset(self) -> None:
        """Clear the input and restore focus."""
        input_field = self.query_one("#url-input", Input)
        input_field.value = ""
        input_field.focus()
        self._set_ui_enabled(True)
        self._set_status("")
