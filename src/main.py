thonimport argparse
import asyncio
import logging
from pathlib import Path
from typing import List

from downloader.spotify_handler import fetch_tracks_metadata
from downloader.mp3_exporter import export_tracks_with_downloads
from utils.parser import load_input_urls, load_settings
from utils.error_handler import setup_logging

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent

async def async_main(input_file: Path, settings_file: Path) -> None:
    logger = setup_logging()
    logger.info("Starting Spotify Music MP3 Downloader")

    if not input_file.exists():
        logger.error("Input file does not exist: %s", input_file)
        raise SystemExit(1)

    if not settings_file.exists():
        logger.error("Settings file does not exist: %s", settings_file)
        raise SystemExit(1)

    try:
        settings = load_settings(settings_file)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unable to load settings: %s", exc)
        raise SystemExit(1)

    try:
        urls: List[str] = load_input_urls(input_file)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unable to load input URLs: %s", exc)
        raise SystemExit(1)

    if not urls:
        logger.warning("No valid Spotify URLs found in input file: %s", input_file)
        raise SystemExit(1)

    logger.info("Loaded %d Spotify URLs", len(urls))

    http_timeout = float(settings.get("http_timeout", 30.0))
    concurrent_requests = int(settings.get("concurrent_requests", 10))

    logger.info(
        "Fetching metadata with timeout=%s seconds and concurrency=%s",
        http_timeout,
        concurrent_requests,
    )

    track_results = await fetch_tracks_metadata(
        urls=urls,
        timeout=http_timeout,
        concurrent_requests=concurrent_requests,
    )

    project_root = get_project_root()
    await export_tracks_with_downloads(
        tracks=track_results,
        settings=settings,
        project_root=project_root,
    )

    logger.info("All done.")

def main() -> None:
    project_root = get_project_root()
    default_input = project_root / "data" / "sample_input.json"
    default_settings = project_root / "src" / "config" / "settings.json"

    parser = argparse.ArgumentParser(
        description="Spotify Music MP3 Downloader - batch fetch metadata and audio.",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=str(default_input),
        help=f"Path to JSON file containing Spotify track URLs (default: {default_input})",
    )
    parser.add_argument(
        "-s",
        "--settings",
        type=str,
        default=str(default_settings),
        help=f"Path to settings.json configuration file (default: {default_settings})",
    )

    args = parser.parse_args()

    try:
        asyncio.run(async_main(Path(args.input), Path(args.settings)))
    except KeyboardInterrupt:
        logging.getLogger("spotify_downloader").warning("Interrupted by user.")
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("spotify_downloader").exception("Fatal error: %s", exc)
        raise SystemExit(1)

if __name__ == "__main__":
    main()