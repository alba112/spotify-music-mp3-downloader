thonimport json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

def load_input_urls(path: Union[str, Path]) -> List[str]:
    """
    Load Spotify track URLs from a JSON file.

    Supported formats:
      - ["https://open.spotify.com/track/...", "..."]
      - [{"url": "https://open.spotify.com/track/..."}, ...]
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    urls: List[str] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                candidate = item.strip()
                if candidate:
                    urls.append(candidate)
            elif isinstance(item, dict):
                url = str(item.get("url", "")).strip()
                if url:
                    urls.append(url)
    elif isinstance(data, dict):
        # Fallback: treat dict as a mapping of name -> url
        for value in data.values():
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    urls.append(candidate)

    # Remove duplicates while preserving order
    seen = set()
    unique_urls: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    return unique_urls

def load_settings(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load settings from JSON configuration file.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)

    if not isinstance(settings, dict):
        raise ValueError("settings.json must contain a JSON object at the top level")

    return settings

_SANITIZE_RE = re.compile(r"[^\w\-.]+")

def safe_filename(name: str, fallback: str = "file", max_length: int = 120) -> str:
    """
    Convert an arbitrary string into a filesystem-safe filename.

    - Non-alphanumeric characters are replaced with underscores.
    - Leading/trailing whitespace is trimmed.
    - Empty results fall back to the provided fallback.
    - Long names are truncated.
    """
    name = (name or "").strip()
    if not name:
        return fallback

    sanitized = _SANITIZE_RE.sub("_", name)
    if not sanitized:
        sanitized = fallback

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized

def flatten(iterable: Iterable[Iterable[Any]]) -> List[Any]:
    """
    Small helper to flatten a two-level nested iterable into a list.
    """
    return [item for sub in iterable for item in sub]