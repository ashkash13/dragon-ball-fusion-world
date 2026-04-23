"""
Shared file-based logger for DBFW Tools.

Both the scanner and redeemer write to the configured output directory using
separate rotating log files (scanner.log and redeemer.log, 1 MB max, 3 backups).

Call set_log_dir() before any logger is first used to direct output to a
user-chosen folder.  If called after logger creation, existing file handlers
are swapped to the new location transparently.
"""
import logging
import logging.handlers
from pathlib import Path

_log_dir: Path = Path.home() / ".dbfw_tools"

_scanner_logger:  logging.Logger | None = None
_redeemer_logger: logging.Logger | None = None

_FMT     = "%(asctime)s  %(levelname)-8s  %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def set_log_dir(path: Path) -> None:
    """
    Change the directory where log files are written.

    Safe to call before or after the loggers are first created:
    - Before first use: the new path is used when loggers are initialised.
    - After creation: existing file handlers are replaced with ones pointing
      to the new location.  Old log files are left in place.
    """
    global _log_dir, _scanner_logger, _redeemer_logger
    path = Path(path)
    if path == _log_dir:
        return
    _log_dir = path
    _log_dir.mkdir(parents=True, exist_ok=True)
    if _scanner_logger is not None:
        _swap_handler(_scanner_logger, _log_dir / "scanner.log")
    if _redeemer_logger is not None:
        _swap_handler(_redeemer_logger, _log_dir / "redeemer.log")


def _swap_handler(logger: logging.Logger, log_file: Path) -> None:
    """Replace all file handlers on logger with a new rotating handler at log_file."""
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    logger.addHandler(handler)


def _make_logger(name: str, log_file: Path) -> logging.Logger:
    _log_dir.mkdir(parents=True, exist_ok=True)
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
        _scanner_logger = _make_logger("dbfw_scanner", _log_dir / "scanner.log")
    return _scanner_logger


def get_redeemer_logger() -> logging.Logger:
    global _redeemer_logger
    if _redeemer_logger is None:
        _redeemer_logger = _make_logger("dbfw_redeemer", _log_dir / "redeemer.log")
    return _redeemer_logger


def scanner_log_path() -> Path:
    return _log_dir / "scanner.log"


def redeemer_log_path() -> Path:
    return _log_dir / "redeemer.log"
