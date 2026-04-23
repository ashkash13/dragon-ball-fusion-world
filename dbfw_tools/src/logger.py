"""
Shared file-based logger for DBFW Tools.

Both the scanner and redeemer write to ~/.dbfw_tools/ using separate rotating
log files (scanner.log and redeemer.log, 1 MB max, 3 backups each).
"""
import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path.home() / ".dbfw_tools"

_SCANNER_LOG  = _LOG_DIR / "scanner.log"
_REDEEMER_LOG = _LOG_DIR / "redeemer.log"

_scanner_logger:  logging.Logger | None = None
_redeemer_logger: logging.Logger | None = None

_FMT     = "%(asctime)s  %(levelname)-8s  %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _make_logger(name: str, log_file: Path) -> logging.Logger:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


def get_scanner_logger() -> logging.Logger:
    global _scanner_logger
    if _scanner_logger is None:
        _scanner_logger = _make_logger("dbfw_scanner", _SCANNER_LOG)
    return _scanner_logger


def get_redeemer_logger() -> logging.Logger:
    global _redeemer_logger
    if _redeemer_logger is None:
        _redeemer_logger = _make_logger("dbfw_redeemer", _REDEEMER_LOG)
    return _redeemer_logger


def scanner_log_path() -> Path:
    return _SCANNER_LOG


def redeemer_log_path() -> Path:
    return _REDEEMER_LOG
