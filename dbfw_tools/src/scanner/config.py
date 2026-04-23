"""
Manages persistent configuration stored in the user's home directory.

Config file: ~/.dbfw_tools/config.json
Shape:
{
  "api_key": "...",
  "discord_bot_token": "...",
  "discord_channel_id": "...",
  "discord_last_message_id": ""
}
"""
import json
from pathlib import Path

_CONFIG_DIR  = Path.home() / ".dbfw_tools"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _load_all() -> dict:
    """Load the full config dict, returning an empty dict on any error."""
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_all(data: dict) -> None:
    """Write the full config dict to disk."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Gemini API key ────────────────────────────────────────────────────────────

def load_api_key() -> str:
    """Return the saved Gemini API key, or an empty string if not set."""
    return _load_all().get("api_key", "")


def save_api_key(key: str) -> None:
    """Persist the Gemini API key to disk, preserving other config values."""
    data = _load_all()
    data["api_key"] = key
    _save_all(data)


# ── Discord config ────────────────────────────────────────────────────────────

def load_discord_config() -> dict:
    """
    Return the Discord configuration as a dict:
        {
            "bot_token": "...",
            "channel_id": "...",
            "last_message_id": "",
            "last_fetch_display": "never",
        }
    Missing keys default to empty strings / "never".
    """
    data = _load_all()
    return {
        "bot_token":          data.get("discord_bot_token", ""),
        "channel_id":         data.get("discord_channel_id", ""),
        "last_message_id":    data.get("discord_last_message_id", ""),
        "last_fetch_display": data.get("discord_last_fetch_display", "never"),
    }


def save_discord_config(
    bot_token: str,
    channel_id: str,
    last_message_id: str = "",
) -> None:
    """Persist Discord configuration, preserving other config values."""
    data = _load_all()
    data["discord_bot_token"]       = bot_token
    data["discord_channel_id"]      = channel_id
    data["discord_last_message_id"] = last_message_id
    _save_all(data)


def save_discord_last_message_id(message_id: str, fetch_display: str = "") -> None:
    """Update the last-processed Discord message ID and optional display timestamp."""
    data = _load_all()
    data["discord_last_message_id"] = message_id
    if fetch_display:
        data["discord_last_fetch_display"] = fetch_display
    _save_all(data)
