"""
File-based logger for DBFW Code Scanner.
Writes to ~/.dbfw_scanner/scanner.log with automatic rotation (max 1MB, 3 backups).
"""
import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path.home() / ".dbfw_scanner"
_LOG_FILE = _LOG_DIR / "scanner.log"

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=1_000_000,  # 1 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    _logger = logging.getLogger("dbfw_scanner")
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)
    return _logger


def log_path() -> Path:
    return _LOG_FILE
