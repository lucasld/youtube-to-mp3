"""Album cover retrieval with MusicBrainz primary and iTunes fallback."""

from __future__ import annotations

import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from .config import (
    ALBUM_NAME_WORD_OVERLAP_RATIO,
    ARTIST_ALBUMS_SEARCH_LIMIT,
    COVER_REQUEST_TIMEOUT,
    DEFAULT_SEARCH_LIMIT,
    EXTENDED_SEARCH_LIMIT,
    ITUNES_LARGE_IMAGE_SIZE,
    ITUNES_SMALL_IMAGE_SIZE,
    MAX_COVER_FILE_SIZE,
)
from .extractor import TrackMetadata


class AlbumMatcher:
    """Shared utilities for album name matching and normalization."""

    @staticmethod
    def normalize_album_name(album_name: str) -> str:
        """Normalize album name for better matching."""
        album_name = album_name.strip()
        # Remove common suffixes that might vary
        album_name = album_name.split('(')[0].strip()
        album_name = album_name.split('[')[0].strip()
        return album_name

    @staticmethod
    def album_names_match(returned_album: str, expected_album: str) -> Tuple[bool, str]:
        """Check if album names match with confidence level."""
        if not expected_album:
            return True, "no_album_expected"

        expected_norm = AlbumMatcher.normalize_album_name(expected_album.lower())
        returned_norm = AlbumMatcher.normalize_album_name(returned_album.lower())

        # Exact match
        if expected_norm == returned_norm:
            return True, "exact"

        # Contains match
        if expected_norm in returned_norm or returned_norm in expected_norm:
            return True, "partial"

        # Word overlap (at least 50% of words match)
        expected_words = set(expected_norm.split())
        returned_words = set(returned_norm.split())

        if expected_words and returned_words:
            common_words = expected_words.intersection(returned_words)
            overlap_ratio = len(common_words) / max(len(expected_words), len(returned_words))

            if overlap_ratio >= ALBUM_NAME_WORD_OVERLAP_RATIO:
                return True, "word_overlap"

        return False, "no_match"


@dataclass
class CoverResult:
    """Result of cover retrieval."""
    success: bool
    cover_url: Optional[str] = None
    cover_data: Optional[bytes] = None
    release_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    source: Optional[str] = None  # "musicbrainz" or "itunes"
    album_match_confidence: str = "unknown"  # exact, partial, word_overlap,
    # artist_match_only, recording_match, none


class AlbumCoverRetriever:
    """Album cover retriever with MusicBrainz primary and iTunes fallback."""

    def __init__(self):
        self.musicbrainz = MusicBrainzRetriever()
        self.itunes = ITunesRetriever()

    def retrieve_cover(self, metadata: TrackMetadata) -> CoverResult:
        """
        Retrieve album cover using YouTube source (if available), 
        otherwise MusicBrainz primary, iTunes fallback.

        Returns CoverResult with cover_url and optionally downloaded cover_data.
        """
        # Strategy 0: YouTube "Golden Truth" cover (highest priority)
        if hasattr(metadata, "youtube_album_cover_url") and metadata.youtube_album_cover_url:
            cover_data = self._download_cover_data(metadata.youtube_album_cover_url)
            if cover_data:
                return CoverResult(
                    success=True,
                    cover_url=metadata.youtube_album_cover_url,
                    cover_data=cover_data,
                    source="youtube",
                    album_match_confidence="exact"
                )

        if not metadata.artist:
            return CoverResult(
                success=False,
                error="No artist name provided",
                album_match_confidence="none"
            )

        if not metadata.album:
            return self._retrieve_cover_without_album(metadata)

        try:
            # Try MusicBrainz first (primary)
            mb_result = self.musicbrainz.retrieve_cover(metadata)
            if mb_result.success and mb_result.cover_url:
                # Download the cover data immediately
                cover_data = self._download_cover_data(mb_result.cover_url)
                if cover_data:
                    return CoverResult(
                        success=True,
                        cover_url=mb_result.cover_url,
                        cover_data=cover_data,
                        release_info=mb_result.release_info,
                        source="musicbrainz",
                        album_match_confidence=mb_result.album_match_confidence
                    )

            # Fallback to iTunes
            itunes_result = self.itunes.retrieve_cover(metadata)
            if itunes_result.success and itunes_result.cover_url:
                # Download the cover data immediately
                cover_data = self._download_cover_data(itunes_result.cover_url)
                if cover_data:
                    return CoverResult(
                        success=True,
                        cover_url=itunes_result.cover_url,
                        cover_data=cover_data,
                        release_info=itunes_result.release_info,
                        source="itunes",
                        album_match_confidence=itunes_result.album_match_confidence
                    )

            # No cover found from either service
            return CoverResult(
                success=False,
                error="No album cover found from MusicBrainz or iTunes",
                album_match_confidence="none"
            )

        except Exception as e:
            return CoverResult(
                success=False,
                error=f"Unexpected error during cover retrieval: {str(e)}",
                album_match_confidence="error"
            )

    def _retrieve_cover_without_album(self, metadata: TrackMetadata) -> CoverResult:
        """Try to retrieve cover art for singles using track metadata only."""
        if not metadata.title:
            return CoverResult(
                success=False,
                error="No track title provided",
                album_match_confidence="none"
            )

        try:
            mb_result = self.musicbrainz.retrieve_cover_for_recording(metadata)
            if mb_result.success and mb_result.cover_url:
                cover_data = self._download_cover_data(mb_result.cover_url)
                if cover_data:
                    return CoverResult(
                        success=True,
                        cover_url=mb_result.cover_url,
                        cover_data=cover_data,
                        release_info=mb_result.release_info,
                        source="musicbrainz",
                        album_match_confidence=mb_result.album_match_confidence
                    )

            itunes_result = self.itunes.retrieve_cover_for_track(metadata)
            if itunes_result.success and itunes_result.cover_url:
                cover_data = self._download_cover_data(itunes_result.cover_url)
                if cover_data:
                    return CoverResult(
                        success=True,
                        cover_url=itunes_result.cover_url,
                        cover_data=cover_data,
                        release_info=itunes_result.release_info,
                        source="itunes",
                        album_match_confidence=itunes_result.album_match_confidence
                    )

            return CoverResult(
                success=False,
                error="No cover found for track-only search",
                album_match_confidence="none"
            )
        except Exception as e:
            return CoverResult(
                success=False,
                error=f"Unexpected error during track-only cover retrieval: {str(e)}",
                album_match_confidence="error"
            )
    def _download_cover_data(self, url: str) -> Optional[bytes]:
        """Download cover image data."""
        try:
            response = requests.get(url, timeout=COVER_REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()

            # Basic validation - check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                return None

            # Check content length to avoid downloading huge files
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_COVER_FILE_SIZE:
                return None
            data = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                data.extend(chunk)
                if len(data) > MAX_COVER_FILE_SIZE:
                    return None

            return bytes(data)
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception:
            return None


# MusicBrainz implementation (adapted from improved_musicbrainz_retriever.py)
class MusicBrainzRetriever:
    """MusicBrainz album cover retriever."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    COVER_ART_URL = "https://coverartarchive.org"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'YouTubeToMP3/1.0 (https://github.com/lucasld/youtube-to-mp3)'
        })

    def retrieve_cover(self, metadata: TrackMetadata) -> CoverResult:
        """Retrieve cover using MusicBrainz."""
        try:
            # Strategy 1: Direct album search with validation
            result = self._search_album_direct(metadata)
            if result.success:
                return result

            # Strategy 2: Fuzzy album search with validation
            result = self._search_album_fuzzy(metadata)
            if result.success:
                return result

            # Strategy 3: Recording search (fallback)
            result = self._search_recording(metadata)
            if result.success:
                return result

            return CoverResult(success=False, error="No cover found via MusicBrainz")

        except Exception as e:
            return CoverResult(success=False, error=f"MusicBrainz error: {str(e)}")

    def retrieve_cover_for_recording(self, metadata: TrackMetadata) -> CoverResult:
        """Retrieve cover using recording search when no album is available."""
        try:
            result = self._search_recording(metadata)
            if result.success:
                return result
            return CoverResult(success=False, error="No cover found via recording search")
        except Exception as e:
            return CoverResult(success=False, error=f"MusicBrainz error: {str(e)}")
    def _search_album_direct(self, metadata: TrackMetadata) -> CoverResult:
        """Direct album search with validation."""
        if not metadata.album:
            return CoverResult(success=False)

        releases = self._search_releases(
            metadata.artist, metadata.album, limit=DEFAULT_SEARCH_LIMIT
        )

        for release in releases:
            matches, confidence = AlbumMatcher.album_names_match(release['title'], metadata.album)
            if matches:
                cover_url = self._get_cover_url(release['id'])
                if cover_url:
                    return CoverResult(
                        success=True,
                        cover_url=cover_url,
                        release_info={'title': release['title'], 'id': release['id']},
                        album_match_confidence=confidence
                    )

        return CoverResult(success=False)

    def _search_album_fuzzy(self, metadata: TrackMetadata) -> CoverResult:
        """Fuzzy album search with broader matching."""
        if not metadata.album:
            return CoverResult(success=False)

        # Try with just artist name
        releases = self._search_releases(metadata.artist, "", limit=EXTENDED_SEARCH_LIMIT)

        for release in releases:
            matches, confidence = AlbumMatcher.album_names_match(release['title'], metadata.album)
            if matches and confidence in ['exact', 'partial', 'word_overlap']:
                cover_url = self._get_cover_url(release['id'])
                if cover_url:
                    return CoverResult(
                        success=True,
                        cover_url=cover_url,
                        release_info={'title': release['title'], 'id': release['id']},
                        album_match_confidence=confidence
                    )

        return CoverResult(success=False)

    def _search_recording(self, metadata: TrackMetadata) -> CoverResult:
        """Search by recording (track) name."""
        try:
            query = f'artist:"{metadata.artist}" AND recording:"{metadata.title}"'
            params = {'query': query, 'limit': DEFAULT_SEARCH_LIMIT, 'fmt': 'json'}

            response = self.session.get(f"{self.BASE_URL}/recording", params=params)
            response.raise_for_status()

            data = response.json()
            recordings = data.get('recordings', [])

            for recording in recordings:
                release = recording.get('releases', [{}])[0]
                if release and 'id' in release:
                    cover_url = self._get_cover_url(release['id'])
                    if cover_url:
                        return CoverResult(
                            success=True,
                            cover_url=cover_url,
                            release_info={'title': release.get('title', ''), 'id': release['id']},
                            album_match_confidence="recording_match"
                        )

        except Exception:
            pass

        return CoverResult(success=False)

    def _search_releases(self, artist: str, album: str, limit: int = 5) -> List[Dict]:
        """Search for releases by artist and album name."""
        query_parts = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'release:"{album}"')

        if not query_parts:
            return []

        query = ' AND '.join(query_parts)
        params = {'query': query, 'limit': limit, 'fmt': 'json'}

        try:
            response = self.session.get(f"{self.BASE_URL}/release", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('releases', [])
        except Exception:
            return []

    def _get_cover_url(self, release_id: str) -> Optional[str]:
        """Get cover art URL for a release."""
        try:
            response = self.session.get(f"{self.COVER_ART_URL}/release/{release_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()

            data = response.json()
            images = data.get('images', [])

            # Prefer front cover
            for image in images:
                if image.get('front'):
                    return image['image']

            # Fallback to any image
            if images:
                return images[0]['image']

        except Exception:
            pass

        return None


# iTunes implementation (adapted from improved_itunes_retriever.py)
class ITunesRetriever:
    """iTunes album cover retriever."""

    BASE_URL = "https://itunes.apple.com/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'YouTubeToMP3/1.0 (https://github.com/lucasld/youtube-to-mp3)'
        })

    def retrieve_cover(self, metadata: TrackMetadata) -> CoverResult:
        """Retrieve cover using iTunes."""
        try:
            # Strategy 1: Direct album search with validation
            result = self._search_album_direct(metadata)
            if result.success:
                return result

            # Strategy 2: Artist search with validation
            result = self._search_artist_albums(metadata)
            if result.success:
                return result

            return CoverResult(success=False, error="No cover found via iTunes")

        except Exception as e:
            return CoverResult(success=False, error=f"iTunes error: {str(e)}")

    def retrieve_cover_for_track(self, metadata: TrackMetadata) -> CoverResult:
        """Retrieve cover for a single track without album metadata."""
        try:
            if not metadata.title:
                return CoverResult(success=False)

            tracks = self._search_tracks(metadata.artist, metadata.title)
            if not tracks:
                return CoverResult(success=False)

            track = tracks[0]
            return CoverResult(
                success=True,
                cover_url=self._get_best_cover_url(track),
                release_info={
                    'title': track.get('trackName', ''),
                    'artist': track.get('artistName', ''),
                    'year': track.get('releaseDate', '')[:4] if track.get('releaseDate') else None
                },
                album_match_confidence="track_only"
            )
        except Exception:
            return CoverResult(success=False)
    def _search_album_direct(self, metadata: TrackMetadata) -> CoverResult:
        """Direct album search with validation."""
        if not metadata.album:
            return CoverResult(success=False)

        albums = self._search_albums(
            metadata.artist, metadata.album, limit=EXTENDED_SEARCH_LIMIT
        )

        for album in albums:
            matches, confidence = AlbumMatcher.album_names_match(
                album['collectionName'], metadata.album
            )
            if matches and confidence in ['exact', 'partial', 'word_overlap']:
                return CoverResult(
                    success=True,
                    cover_url=self._get_best_cover_url(album),
                    release_info={
                        'title': album['collectionName'],
                        'artist': album.get('artistName', ''),
                        'year': (
                            album.get('releaseDate', '')[:4]
                            if album.get('releaseDate') else None
                        )
                    },
                    album_match_confidence=confidence
                )

        return CoverResult(success=False)

    def _search_artist_albums(self, metadata: TrackMetadata) -> CoverResult:
        """Search artist's albums and find best match."""
        albums = self._search_albums(metadata.artist, "", limit=ARTIST_ALBUMS_SEARCH_LIMIT)

        for album in albums:
            matches, confidence = AlbumMatcher.album_names_match(
                album['collectionName'], metadata.album or ""
            )
            if matches:
                return CoverResult(
                    success=True,
                    cover_url=self._get_best_cover_url(album),
                    release_info={
                        'title': album['collectionName'],
                        'artist': album.get('artistName', ''),
                        'year': (
                            album.get('releaseDate', '')[:4]
                            if album.get('releaseDate') else None
                        )
                    },
                    album_match_confidence=confidence
                )

        # If no good match but we have albums, return the first one as artist_match_only
        if albums:
            album = albums[0]
            return CoverResult(
                success=True,
                cover_url=self._get_best_cover_url(album),
                release_info={
                    'title': album['collectionName'],
                    'artist': album.get('artistName', ''),
                    'year': album.get('releaseDate', '')[:4] if album.get('releaseDate') else None
                },
                album_match_confidence="artist_match_only"
            )

        return CoverResult(success=False)

    def _search_albums(self, artist: str, album: str, limit: int = 10) -> List[Dict]:
        """Search for albums on iTunes."""
        if album:
            term = f"{artist} {album}"
            entity = "album"
        else:
            term = artist
            entity = "album"

        params = {
            'term': term,
            'entity': entity,
            'limit': limit,
            'country': 'us'
        }

        try:
            response = self.session.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception:
            return []

    def _search_tracks(self, artist: str, title: str) -> List[Dict]:
        """Search for tracks on iTunes."""
        term = f"{artist} {title}".strip()
        params = {
            'term': term,
            'entity': 'song',
            'limit': DEFAULT_SEARCH_LIMIT,
            'country': 'us'
        }

        try:
            response = self.session.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception:
            return []
    def _get_best_cover_url(self, album: Dict) -> str:
        """Get the best cover URL from album data."""
        # iTunes provides small images by default, try to get larger versions
        artwork_url = album.get(f'artworkUrl{ITUNES_SMALL_IMAGE_SIZE}', '')
        if artwork_url:
            # Try to get larger version
            old_size = f'{ITUNES_SMALL_IMAGE_SIZE}x{ITUNES_SMALL_IMAGE_SIZE}'
            new_size = f'{ITUNES_LARGE_IMAGE_SIZE}x{ITUNES_LARGE_IMAGE_SIZE}'
            artwork_url = artwork_url.replace(old_size, new_size)
        return artwork_url


__all__ = ["AlbumCoverRetriever", "CoverResult", "AlbumMatcher"]
