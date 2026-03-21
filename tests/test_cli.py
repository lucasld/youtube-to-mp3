"""Tests for CLI wiring."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from youtube_to_mp3.cli import main
from youtube_to_mp3.config import AppConfig


def test_cli_debug_option_configures_logging_and_runs_app(monkeypatch) -> None:
    config = AppConfig(output_directory=Path("/tmp/youtube-to-mp3-tests"))
    calls: dict[str, object] = {}

    def fake_configure_logging(debug: bool) -> Path:
        calls["debug"] = debug
        return Path("/tmp/youtube-to-mp3.log")

    def fake_load_app_config(config_path, output_dir):
        calls["config_path"] = config_path
        calls["output_dir"] = output_dir
        return config

    class FakeApp:
        def __init__(self, config: AppConfig) -> None:
            calls["app_config"] = config

        def run(self) -> None:
            calls["ran"] = True

    monkeypatch.setattr("youtube_to_mp3.cli.configure_logging", fake_configure_logging)
    monkeypatch.setattr("youtube_to_mp3.cli._load_app_config", fake_load_app_config)
    monkeypatch.setattr("youtube_to_mp3.cli.YouTubeToMp3App", FakeApp)

    result = CliRunner().invoke(main, ["--debug"])

    assert result.exit_code == 0
    assert calls == {
        "debug": True,
        "config_path": None,
        "output_dir": None,
        "app_config": config,
        "ran": True,
    }
