thonimport asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, quote

import aiohttp

SPOTIFY_OEMBED_ENDPOINT = "https://open.spotify.com/oembed"

@dataclass
class MediaInfo:
    url: str
    quality: str
    extension: str
    type: str

@dataclass
class TrackResult:
    url: str  # original URL
    result_url: str
    title: str
    thumbnail: str
    duration: str
    medias: List[MediaInfo]
    type: str
    error: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "result": {
                "url": self.result_url,
                "title": self.title,
                "thumbnail": self.thumbnail,
                "duration": self.duration,
                "medias": [asdict(m) for m in self.medias],
                "type": self.type,
                "error": self.error,
            },
        }

def _extract_track_id(spotify_url: str) -> Optional[str]:
    """
    Extract track ID from standard Spotify track URLs like:
    https://open.spotify.com/track/<id>?...

    Returns None if it cannot detect a valid track id.
    """
    parsed = urlparse(spotify_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "track":
        return parts[1]
    return None

async def _fetch_oembed_metadata(
    session: aiohttp.ClientSession,
    url: str,
    timeout: float,
    logger: logging.Logger,
) -> Dict[str, Any]:
    params = {"url": url, "format": "json"}
    try:
        async with session.get(SPOTIFY_OEMBED_ENDPOINT, params=params, timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning(
                    "Non-200 response from Spotify oEmbed for %s: %s",
                    url,
                    resp.status,
                )
                return {}
            return await resp.json()
    except asyncio.TimeoutError:
        logger.error("Timeout while fetching oEmbed metadata for %s", url)
    except aiohttp.ClientError as exc:
        logger.error("HTTP error while fetching oEmbed metadata for %s: %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while fetching metadata for %s: %s", url, exc)

    return {}

def _build_media_info(track_id: str) -> MediaInfo:
    """
    Build a realistic MP3 stream URL. In a real implementation, this would call a
    third-party service or your own backend that provides MP3 streams for
    the given Spotify track ID.
    """
    stream_url = (
        "https://cdn2.meow.gs/api/stream?"
        f"id={quote(track_id)}&source=spotify&exp=9999999999999"
    )
    return MediaInfo(
        url=stream_url,
        quality="audio",
        extension="mp3",
        type="audio",
    )

async def _process_single_track(
    session: aiohttp.ClientSession,
    url: str,
    timeout: float,
    logger: logging.Logger,
) -> Dict[str, Any]:
    metadata = await _fetch_oembed_metadata(session, url, timeout, logger)
    track_id = _extract_track_id(url) or "unknown"

    title = metadata.get("title", f"Spotify Track {track_id}")
    thumbnail = metadata.get("thumbnail_url", "")
    duration = ""  # oEmbed does not expose duration; left blank intentionally

    medias: List[MediaInfo] = []
    error = False

    if track_id == "unknown":
        logger.warning("Could not determine track ID from URL: %s", url)
        error = True
    else:
        medias.append(_build_media_info(track_id))

    track = TrackResult(
        url=url,
        result_url=url,
        title=title,
        thumbnail=thumbnail,
        duration=duration,
        medias=medias,
        type="single",
        error=error,
    )
    return track.to_dict()

async def fetch_tracks_metadata(
    urls: List[str],
    timeout: float,
    concurrent_requests: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch metadata for a batch of Spotify track URLs concurrently.

    Returns a list of dicts shaped exactly like the README example.
    """
    logger = logging.getLogger("spotify_downloader")
    semaphore = asyncio.Semaphore(concurrent_requests)

    async with aiohttp.ClientSession() as session:
        async def bound_process(u: str) -> Dict[str, Any]:
            async with semaphore:
                return await _process_single_track(session, u, timeout, logger)

        tasks = [bound_process(u) for u in urls]
        results = await asyncio.gather(*tasks)
    return results