"""
Discord REST API client for fetching image attachments from a channel.

Uses the Discord API v10 directly with `requests` — no async library needed,
which avoids tkinter/asyncio conflicts.

Required bot permissions:
  - View Channel
  - Read Message History
  - Manage Messages  (for delete_message)
"""
import io

import requests

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_SESSION = requests.Session()


class DiscordError(Exception):
    """Raised when the Discord API returns a non-2xx response."""


class DiscordClient:
    BASE = "https://discord.com/api/v10"

    def __init__(self, bot_token: str, channel_id: str) -> None:
        self._token = bot_token.strip()
        self._channel_id = channel_id.strip()
        self._headers = {"Authorization": f"Bot {self._token}"}

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self) -> str | None:
        """
        Verify that the token and channel ID work.

        Returns None on success, or an error string describing the problem.
        Does NOT raise — caller should display the returned string to the user.
        """
        url = f"{self.BASE}/channels/{self._channel_id}"
        try:
            resp = _SESSION.get(url, headers=self._headers, timeout=10)
        except requests.RequestException as exc:
            return f"Network error: {exc}"

        if resp.status_code == 200:
            return None
        if resp.status_code == 401:
            return "Invalid bot token — check that the token is correct."
        if resp.status_code == 403:
            return "Bot does not have permission to access this channel."
        if resp.status_code == 404:
            return "Channel not found — check that the channel ID is correct and the bot has been invited to the server."
        return f"Discord API error {resp.status_code}: {resp.text[:200]}"

    def fetch_image_messages(self, after_id: str | None = None) -> list[dict]:
        """
        Retrieve messages from the channel that contain at least one image
        attachment, optionally only messages newer than *after_id*.

        Returns a list of dicts (sorted oldest-first):
            [{"id": "...", "attachments": [{"url": "...", "filename": "..."}]}, ...]

        Only .jpg/.jpeg/.png/.webp attachments are included.
        Raises DiscordError on API failure.
        """
        params: dict = {"limit": 50}
        if after_id:
            params["after"] = after_id

        url = f"{self.BASE}/channels/{self._channel_id}/messages"
        resp = _SESSION.get(url, headers=self._headers, params=params, timeout=15)
        _raise_for_status(resp)

        messages = resp.json()
        # API returns newest-first; reverse to process oldest-first
        messages = list(reversed(messages))

        import logging
        _diag = logging.getLogger("dbfw.discord")
        _diag.debug("fetch_image_messages: API returned %d message(s)", len(messages))
        for msg in messages:
            atts = msg.get("attachments", [])
            _diag.debug(
                "  msg %s: %d attachment(s) — %s",
                msg["id"],
                len(atts),
                [a.get("filename", "?") for a in atts] or "(none)",
            )

        result = []
        for msg in messages:
            image_attachments = [
                {"url": att["url"], "filename": att["filename"]}
                for att in msg.get("attachments", [])
                if _is_image(att.get("filename", ""))
            ]
            if image_attachments:
                result.append({"id": msg["id"], "attachments": image_attachments})

        _diag.debug("fetch_image_messages: %d message(s) with supported images", len(result))
        return result

    def download_attachment(self, url: str) -> bytes:
        """
        Download a Discord attachment and return its raw bytes.

        The caller can open it with:
            PIL.Image.open(io.BytesIO(client.download_attachment(url)))

        Raises DiscordError on failure.
        """
        resp = _SESSION.get(url, headers=self._headers, timeout=30)
        _raise_for_status(resp)
        return resp.content

    def delete_message(self, message_id: str) -> None:
        """
        Delete a message from the configured channel.

        Raises DiscordError on failure.
        """
        url = f"{self.BASE}/channels/{self._channel_id}/messages/{message_id}"
        resp = _SESSION.delete(url, headers=self._headers, timeout=10)
        # 204 No Content is the success response for DELETE
        if resp.status_code == 204:
            return
        _raise_for_status(resp)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_image(filename: str) -> bool:
    """Return True if the filename has a supported image extension."""
    return any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


def _raise_for_status(resp: requests.Response) -> None:
    """Raise DiscordError with a readable message for non-2xx responses."""
    if resp.status_code < 200 or resp.status_code >= 300:
        try:
            detail = resp.json().get("message", resp.text[:200])
        except Exception:
            detail = resp.text[:200]
        raise DiscordError(f"Discord API {resp.status_code}: {detail}")
