"""Command-line interface for YouTube to MP3 converter."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import click

from .app import YouTubeToMp3App
from .config import AppConfig, load_config
from .downloader import DownloadJob
from .logging_setup import configure_logging
from .pipeline import DownloadPipeline, ExtractionResult
from .utils.validation import URLValidator

logger = logging.getLogger(__name__)


def _load_app_config(
    config_path: Optional[str], output_dir: Optional[str]
) -> AppConfig:
    overrides = {}
    if output_dir:
        overrides["output_directory"] = output_dir

    explicit = Path(config_path).expanduser() if config_path else None
    return load_config(explicit_path=explicit, overrides=overrides)


def _print_extraction_summary(extraction: ExtractionResult, config: AppConfig) -> None:
    click.echo("Detected tracks:")
    for idx, track in enumerate(extraction.tracks, start=1):
        prefix = f"{idx}. " if extraction.is_playlist else ""
        details = f" ({track.album})" if track.album else ""
        click.echo(f"  {prefix}{track.artist} - {track.title}{details}")

    click.echo(f"Output directory: {config.output_directory}")


def _console_progress(index: int, total: int, job: DownloadJob) -> None:
    click.echo(f"[{index}/{total}] {job.metadata.artist} - {job.metadata.title}")


def _run_non_interactive(url: str, config: AppConfig) -> None:
    if not URLValidator.is_valid_url(url):
        raise click.BadParameter(
            "Provide a valid YouTube or SoundCloud track or playlist URL."
        )

    pipeline = DownloadPipeline(config)
    extraction = pipeline.extract(url)

    _print_extraction_summary(extraction, config)

    output_dir = config.ensure_output_directory()
    jobs = pipeline.create_download_jobs(
        extraction.tracks,
        output_dir,
        playlist_title=extraction.playlist_title if extraction.is_playlist else None,
    )

    if not jobs:
        click.echo("No tracks selected for download; exiting.")
        return

    outcomes = asyncio.run(pipeline.download(jobs, progress_callback=_console_progress))

    success = [outcome for outcome in outcomes if outcome.success]
    failures = [outcome for outcome in outcomes if not outcome.success]

    click.echo("")
    click.echo(f"Completed {len(success)} of {len(outcomes)} downloads.")

    if failures:
        click.echo("Failures:")
        for failure in failures:
            title = f"{failure.job.metadata.artist} - {failure.job.metadata.title}"
            click.echo(f"  - {title}: {failure.error}")


@click.command()
@click.argument("url", required=False)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    help="Output directory for downloaded files",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable verbose logging to the rotating log file",
)
def main(
    url: Optional[str] = None,
    config_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    debug: bool = False,
) -> None:
    """Download YouTube or SoundCloud audio as tagged MP3 files."""

    log_file = configure_logging(debug=debug)
    logger.info("Starting youtube-to-mp3")
    logger.debug(
        "CLI arguments: url=%s, config_path=%s, output_dir=%s",
        url,
        config_path,
        output_dir,
    )
    logger.info("Log file: %s", log_file)

    config = _load_app_config(
        str(config_path) if config_path else None,
        str(output_dir) if output_dir else None,
    )

    if url:
        _run_non_interactive(url, config)
        return

    app = YouTubeToMp3App(config=config)
    app.run()


if __name__ == "__main__":
    main()
