# YouTube to MP3 Converter

A professional command-line application for downloading YouTube videos and playlists as properly tagged MP3 files with automatic metadata extraction and album cover retrieval.

## Overview

YouTube to MP3 Converter transforms YouTube content into high-quality MP3 files with comprehensive metadata and album artwork. The application features both an interactive terminal user interface and command-line operation for maximum flexibility.

## Key Features

- Intelligent metadata extraction from YouTube titles
- Automatic album cover retrieval from MusicBrainz and iTunes
- Support for individual videos and playlists
- Interactive metadata review and editing
- Cross-platform compatibility (macOS, Linux, Windows)
- Rate limiting to avoid YouTube restrictions
- Professional MP3 tagging with embedded artwork

## Installation

### Requirements
- Python 3.8 or higher
- FFmpeg (for audio conversion)

### Install from Source
```bash
git clone https://github.com/lucasld/youtube-to-mp3.git
cd youtube-to-mp3
pip install -e .
```

## Usage

### Interactive Mode
```bash
youtube-to-mp3
```

### Command Line Mode
```bash
youtube-to-mp3 "https://youtu.be/VIDEO_ID"
youtube-to-mp3 "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

### Options
```bash
youtube-to-mp3 --help
```

## Workflow

1. **Input URL**: Enter a YouTube video or playlist URL
2. **Metadata Extraction**: Automatically parse artist, title, and album information
3. **Review & Edit**: Verify extracted metadata and make corrections if needed
4. **Download**: Convert to MP3 with embedded metadata and album covers
5. **Completion**: Access downloaded files in your music library

## Technical Architecture

### Core Components

- **cli.py**: Command-line interface and argument parsing
- **app.py**: Main Textual application controller
- **pipeline.py**: Orchestrates extraction and download processes with album cover caching
- **extractor.py**: YouTube metadata extraction using yt-dlp with album detection
- **downloader.py**: Audio conversion and metadata embedding with logging
- **album_cover_retriever.py**: Album artwork retrieval from MusicBrainz/iTunes with deduplication
- **metadata.py**: Metadata validation and cleaning utilities
- **ui/**: Textual-based user interface screens
- **utils/**: Cross-platform filesystem, validation, and rate limiting utilities

### Dependencies

- **yt-dlp**: YouTube video extraction and download
- **mutagen**: MP3 metadata and ID3 tag manipulation
- **textual**: Terminal user interface framework
- **requests**: HTTP client for API calls
- **click**: Command-line argument parsing

### Configuration

The application uses sensible defaults but can be configured via `~/.config/youtube-to-mp3/config.json`:

```json
{
  "output_directory": "~/Music/YouTube",
  "audio_quality": "192",
  "rate_limit_delay": 1.5,
  "default_genre": "Unknown"
}
```

## Development

### Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Testing
```bash
pytest
```

### Code Quality
```bash
black src/
isort src/
flake8 src/
```

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is intended for personal use only. Respect copyright laws and YouTube's terms of service. The developers are not responsible for misuse of this software.
