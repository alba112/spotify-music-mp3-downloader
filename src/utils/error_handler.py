thonimport logging
from logging import Logger
from typing import Optional

class DownloadError(Exception):
    """Raised when a media download fails in a non-recoverable way."""

def setup_logging(level: int = logging.INFO) -> Logger:
    """
    Configure a sensible default logger for the application and return it.
    Calling this multiple times is safe; basicConfig is a no-op if handlers exist.
    """
    logger = logging.getLogger("spotify_downloader")
    if not logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        logger.setLevel(level)
    return logger

def handle_exception(
    logger: Logger,
    exc: BaseException,
    context: Optional[str] = None,
    level: int = logging.ERROR,
) -> None:
    """
    Log an exception with optional context.

    Example:
        handle_exception(logger, exc, "Downloading track XYZ")
    """
    if context:
        logger.log(level, "Error in %s: %s", context, exc, exc_info=True)
    else:
        logger.log(level, "Error: %s", exc, exc_info=True)