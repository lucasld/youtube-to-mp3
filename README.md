# YouTube to MP3: Metadata Extraction & Matching Engine

Technical project exploring YouTube data scraping, asynchronous processing, and fuzzy metadata matching. This codebase serves as a reference for implementing multi-tier fallback systems and complex data extraction.

<p align="center">
  <img src="assets/ui.png" alt="YouTube to MP3 UI" width="600">
</p>

## Getting Started

1. Clone the repository and install dependencies:
```bash
pip install -e "."
```

2. To run the system in interactive mode:
```bash
youtube-to-mp3
```

3. To process a specific URL directly:
```bash
youtube-to-mp3 [URL]
```

### Options
- `--output-dir PATH`: Specify where the downloaded files should be saved.
- `--config PATH`: Path to a custom configuration file.

## Technical Architecture
The system is designed with a clean separation of concerns, utilizing an asynchronous pipeline to coordinate extraction, downloading, and tagging.

### Multi-Tier Metadata Retrieval
The core of the project implements a robust waterfall strategy:
- **YouTube Structured Data**: Traverses `ytInitialData` to extract music claims directly from the source.
- **Async API Fallbacks**: If structured data is missing, the system queries:
    - **MusicBrainz**: Release and recording-level fuzzy searches.
    - **iTunes**: Tertiary fallback for artwork and verified metadata.
- **Fuzzy Matching**: A custom matching system utilizes word-overlap ratios and name normalization to ensure accuracy.

### Performance & Efficiency
- **Asynchronous Pipeline**: Uses `asyncio` to manage non-blocking operations.
- **Connection Pooling**: Implements `requests.Session` for persistent connections.
- **Intelligent Caching**: Centralized cache prevents redundant external API lookups.

## Libraries
- **yt-dlp**: YouTube data extraction.
- **mutagen**: ID3v2 tag manipulation and cover art embedding.
- **textual**: Reactive CLI/TUI experience.
- **asyncio**: High-concurrency network tasks.
- **requests**: HTTP communication and session management.

## Disclaimer
This project is for educational purposes only. It is not intended to be used, distributed, or commercialized. The developer does not support or encourage the use of this software to violate the Terms of Service of any third-party platform. All responsibility for any actions taken using the concepts or code within this repository resides solely with the individual user. This software is provided as is without warranty of any kind.
