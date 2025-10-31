"""Download progress screen."""

from __future__ import annotations

import asyncio
from typing import List, Sequence, TYPE_CHECKING, cast

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Log, ProgressBar, Static

from ..downloader import DownloadJob
from ..pipeline import DownloadOutcome

if TYPE_CHECKING:  # pragma: no cover - type hint support
    from ..app import YouTubeToMp3App


class DownloadProgressScreen(Screen[List[DownloadOutcome]]):
    """Visualise download progress and emit results when finished."""

    def __init__(self, jobs: Sequence[DownloadJob], headline: str) -> None:
        super().__init__()
        self.jobs = list(jobs)
        self.headline = headline
        self.progress = ProgressBar(total=len(self.jobs))
        self.log_widget = Log()
        self._completed = 0

    def compose(self):
        with Vertical(id="progress-container"):
            yield Static(self.headline, id="progress-title")
            yield self.progress
            yield self.log_widget

    async def on_mount(self) -> None:
        await asyncio.sleep(0)
        asyncio.create_task(self._run_downloads())

    async def _run_downloads(self) -> None:
        app = cast("YouTubeToMp3App", self.app)

        def progress_callback(index: int, total: int, job: DownloadJob) -> None:
            app.call_from_thread(self._handle_progress_update, index, total, job)

        outcomes = await app.perform_download(self.jobs, progress_callback)
        self.dismiss(outcomes)
        await app.handle_download_complete(outcomes)

    def _handle_progress_update(self, index: int, total: int, job: DownloadJob) -> None:
        if job.status == "pending":
            self.log_widget.write(
                f"[{index}/{total}] Starting {job.metadata.artist} - {job.metadata.title}"
            )
        else:
            if job.status == "completed":
                self.log_widget.write(
                    f"[{index}/{total}] Finished {job.metadata.artist} - {job.metadata.title}"
                )
            else:
                self.log_widget.write(
                    f"[{index}/{total}] Failed {job.metadata.artist} - "
                    f"{job.metadata.title}: {job.error}"
                )
            self._completed += 1
            self.progress.advance(1)


__all__ = ["DownloadProgressScreen"]
