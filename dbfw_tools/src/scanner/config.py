"""
Manages persistent configuration (API key) stored in the user's home directory.
"""
import json
from pathlib import Path

_CONFIG_DIR  = Path.home() / ".dbfw_tools"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def load_api_key() -> str:
    """Return the saved Gemini API key, or an empty string if not set."""
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            return data.get("api_key", "")
        except Exception:
            return ""
    return ""


def save_api_key(key: str) -> None:
    """Persist the Gemini API key to disk."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps({"api_key": key}, indent=2), encoding="utf-8"
    )
