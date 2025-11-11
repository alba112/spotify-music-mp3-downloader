thonimport asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from openpyxl import Workbook

from utils.parser import safe_filename

async def _download_single_track_audio(
    session: aiohttp.ClientSession,
    track: Dict[str, Any],
    output_dir: Path,
    timeout: float,
    logger: logging.Logger,
) -> None:
    result = track.get("result") or {}
    medias = result.get("medias") or []

    if not medias:
        logger.warning("No media streams defined for %s", result.get("url"))
        result["error"] = True
        return

    media = medias[0]
    media_url: str = str(media.get("url", ""))
    extension: str = media.get("extension", "mp3")

    title = result.get("title") or result.get("url") or "spotify_track"
    filename = safe_filename(title, fallback="spotify_track") + f".{extension}"
    file_path = output_dir / filename

    if not media_url:
        logger.warning("Empty media URL for track: %s", title)
        result["error"] = True
        return

    logger.info("Downloading audio for '%s' -> %s", title, file_path)
    try:
        async with session.get(media_url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.error(
                    "Failed to download %s (HTTP %s)",
                    media_url,
                    resp.status,
                )
                result["error"] = True
                return

            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Stream-response to disk
            with open(file_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    if not chunk:
                        continue
                    f.write(chunk)

            logger.info("Successfully downloaded '%s'", file_path)
    except asyncio.TimeoutError:
        logger.error("Timeout downloading %s", media_url)
        result["error"] = True
    except aiohttp.ClientError as exc:
        logger.error("HTTP error downloading %s: %s", media_url, exc)
        result["error"] = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error downloading %s: %s", media_url, exc)
        result["error"] = True

def _flatten_track_for_export(track: Dict[str, Any]) -> Dict[str, Any]:
    url = track.get("url", "")
    result = track.get("result") or {}
    medias = result.get("medias") or []
    media: Optional[Dict[str, Any]] = medias[0] if medias else None

    return {
        "url": url,
        "result.url": result.get("url", ""),
        "result.title": result.get("title", ""),
        "result.thumbnail": result.get("thumbnail", ""),
        "result.duration": result.get("duration", ""),
        "result.medias.url": (media or {}).get("url", ""),
        "result.medias.quality": (media or {}).get("quality", ""),
        "result.medias.extension": (media or {}).get("extension", ""),
        "result.medias.type": (media or {}).get("type", ""),
        "result.type": result.get("type", ""),
        "result.error": bool(result.get("error", False)),
    }

def _export_to_json(tracks: List[Dict[str, Any]], json_path: Path, logger: logging.Logger) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=4, ensure_ascii=False)
    logger.info("Exported JSON data to %s", json_path)

def _export_to_csv(tracks: List[Dict[str, Any]], csv_path: Path, logger: logging.Logger) -> None:
    import csv

    flat_rows = [_flatten_track_for_export(t) for t in tracks]
    fieldnames = list(flat_rows[0].keys()) if flat_rows else []

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)
    logger.info("Exported CSV data to %s", csv_path)

def _export_to_excel(tracks: List[Dict[str, Any]], xlsx_path: Path, logger: logging.Logger) -> None:
    flat_rows = [_flatten_track_for_export(t) for t in tracks]
    if not flat_rows:
        logger.warning("No tracks to export to Excel")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Tracks"

    headers = list(flat_rows[0].keys())
    ws.append(headers)

    for row in flat_rows:
        ws.append([row.get(h, "") for h in headers])

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)
    logger.info("Exported Excel data to %s", xlsx_path)

def _export_to_xml(tracks: List[Dict[str, Any]], xml_path: Path, logger: logging.Logger) -> None:
    from xml.etree.ElementTree import Element, SubElement, ElementTree

    root = Element("tracks")
    for t in tracks:
        flat = _flatten_track_for_export(t)
        track_el = SubElement(root, "track")
        for key, value in flat.items():
            child = SubElement(track_el, key.replace(".", "_"))
            child.text = str(value)

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ElementTree(root)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    logger.info("Exported XML data to %s", xml_path)

def _export_to_html(tracks: List[Dict[str, Any]], html_path: Path, logger: logging.Logger) -> None:
    flat_rows = [_flatten_track_for_export(t) for t in tracks]
    if not flat_rows:
        logger.warning("No tracks to export to HTML")
        return

    headers = list(flat_rows[0].keys())

    def escape(s: Any) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    rows_html = []
    for row in flat_rows:
        cells = "".join(f"<td>{escape(row.get(h, ''))}</td>" for h in headers)
        rows_html.append(f"<tr>{cells}</tr>")

    header_cells = "".join(f"<th>{escape(h)}</th>" for h in headers)
    table_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Spotify Tracks Export</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 10px; font-size: 14px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    tr:nth-child(even) {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>Spotify Tracks Export</h1>
  <table>
    <thead>
      <tr>{header_cells}</tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
""".strip()

    html_path.parent.mkdir(parents=True, exist_ok=True)
    with html_path.open("w", encoding="utf-8") as f:
        f.write(table_html)
    logger.info("Exported HTML data to %s", html_path)

async def export_tracks_with_downloads(
    tracks: List[Dict[str, Any]],
    settings: Dict[str, Any],
    project_root: Path,
) -> None:
    """
    Download audio files for all tracks (where possible) and export metadata
    in multiple formats.
    """
    logger = logging.getLogger("spotify_downloader")
    http_timeout = float(settings.get("http_timeout", 30.0))
    concurrent_downloads = int(settings.get("concurrent_downloads", 5))

    export_cfg = settings.get("export", {})
    output_dir = Path(export_cfg.get("audio_output_dir", "data/downloads"))
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    export_json_path = export_cfg.get("output_json", "data/output_sample.json")
    export_csv_path = export_cfg.get("output_csv")
    export_excel_path = export_cfg.get("output_excel")
    export_xml_path = export_cfg.get("output_xml")
    export_html_path = export_cfg.get("output_html")

    if not Path(export_json_path).is_absolute():
        export_json_path = project_root / export_json_path
    else:
        export_json_path = Path(export_json_path)

    export_paths = {
        "csv": Path(export_csv_path) if export_csv_path else None,
        "excel": Path(export_excel_path) if export_excel_path else None,
        "xml": Path(export_xml_path) if export_xml_path else None,
        "html": Path(export_html_path) if export_html_path else None,
    }

    logger.info("Preparing to download audio files to %s", output_dir)

    semaphore = asyncio.Semaphore(concurrent_downloads)
    async with aiohttp.ClientSession() as session:
        async def bound_download(t: Dict[str, Any]) -> None:
            async with semaphore:
                await _download_single_track_audio(
                    session=session,
                    track=t,
                    output_dir=output_dir,
                    timeout=http_timeout,
                    logger=logger,
                )

        download_tasks = [bound_download(t) for t in tracks]
        await asyncio.gather(*download_tasks)

    # Export metadata
    _export_to_json(tracks, export_json_path, logger)

    if export_paths["csv"] is not None:
        csv_path = export_paths["csv"]
        if not csv_path.is_absolute():
            csv_path = project_root / csv_path
        _export_to_csv(tracks, csv_path, logger)

    if export_paths["excel"] is not None:
        xlsx_path = export_paths["excel"]
        if not xlsx_path.is_absolute():
            xlsx_path = project_root / xlsx_path
        _export_to_excel(tracks, xlsx_path, logger)

    if export_paths["xml"] is not None:
        xml_path = export_paths["xml"]
        if not xml_path.is_absolute():
            xml_path = project_root / xml_path
        _export_to_xml(tracks, xml_path, logger)

    if export_paths["html"] is not None:
        html_path = export_paths["html"]
        if not html_path.is_absolute():
            html_path = project_root / html_path
        _export_to_html(tracks, html_path, logger)