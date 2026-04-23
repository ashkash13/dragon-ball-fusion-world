"""
Combined GUI for Dragon Ball Fusion World Tools.

Two tabs inside a ttk.Notebook:
  Scanner   — image upload → Gemini OCR → collected codes list → export
  Redeemer  — codes file picker → countdown → live progress → summary

Scanner → Redeemer handoff
──────────────────────────
After exporting a codes file in the Scanner tab, the app automatically
switches to the Redeemer tab and pre-fills the file path so the user
only has to click Proceed.
"""
import datetime
import io
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

from src.logger import (
    get_scanner_logger, get_redeemer_logger,
    scanner_log_path, redeemer_log_path,
)
from src.scanner.config import (
    load_api_key, save_api_key,
    load_discord_config, save_discord_config, save_discord_last_message_id,
)
from src.scanner.discord_client import DiscordClient, DiscordError
from src.scanner.gemini_client import GeminiClient
from src.redeemer.redeemer import Redeemer, validate_codes_file
from src.redeemer.window import find_game_window, WindowRect

# ── Optional drag-and-drop support ────────────────────────────────────────────

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    TkinterDnD = None
    DND_FILES = None
    _DND_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────

# OAuth2 invite link for the shared DBFW Discord bot.
# Users click this to add the bot to their server — no bot creation required.
DISCORD_BOT_INVITE_URL = (
    "https://discord.com/oauth2/authorize"
    "?client_id=1485769708367249528&permissions=76800&scope=bot"
)

WINDOW_TITLE      = "Dragon Ball Fusion World Tools"
WINDOW_W          = 1020
WINDOW_H          = 600
SIDEBAR_W         = 220
PREVIEW_SIZE      = 180   # px — square thumbnail canvas
BATCH_DELAY       = 7.0   # seconds between images (keeps under 10 RPM free tier)
COUNTDOWN_SECONDS = 5

STATUS_ICONS = {
    "pending":  "[ ]",
    "scanning": "[~]",
    "done":     "[✓]",
    "error":    "[!]",
}
STATUS_COLORS = {
    "pending":  "#888888",
    "scanning": "#0055cc",
    "done":     "#007700",
    "error":    "#cc0000",
}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

_REDEEMER_RESULT_COLOURS = {
    "SUCCESS":      "#007700",
    "ALREADY_USED": "#cc7700",
    "INVALID":      "#cc0000",
    "TIMEOUT":      "#cc0000",
    "ERROR":        "#cc0000",
    "info":         "#333333",
    "warn":         "#cc7700",
}

# ── Conditional base class ────────────────────────────────────────────────────

_BaseClass = TkinterDnD.Tk if _DND_AVAILABLE else tk.Tk


# ═════════════════════════════════════════════════════════════════════════════
# Scanner tab
# ═════════════════════════════════════════════════════════════════════════════

class ScannerTab:
    """
    Manages all scanner UI inside a provided ttk.Frame.
    Not a widget subclass — builds and owns widgets in self._frame.
    """

    def __init__(self, frame: ttk.Frame, app: "_DBFWApp") -> None:
        self._frame = frame
        self._app   = app
        self._log   = get_scanner_logger()

        self._codes: list[str] = []
        self._client: GeminiClient | None = None

        self._file_paths: list[str] = []
        self._file_statuses: dict[str, str] = {}
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._countdown_var = tk.StringVar(value="")

        api_key = load_api_key()
        if api_key:
            self._client = GeminiClient(api_key)
            self._log.info("Loaded saved API key")
            self._build_main_ui()
        else:
            self._build_setup_ui()

    # ── Setup screen ──────────────────────────────────────────────────────────

    def _build_setup_ui(self) -> None:
        self._clear()

        outer = ttk.Frame(self._frame, padding=40)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Scanner Setup", font=("Helvetica", 16, "bold")).pack(pady=(0, 6))
        ttk.Label(
            outer,
            text=(
                "A free Google Gemini API key is required to extract codes from images.\n"
                "Get yours in ~2 minutes at: aistudio.google.com → Get API Key"
            ),
            justify="center",
        ).pack(pady=(0, 18))

        ttk.Label(outer, text="Paste your Gemini API key:").pack(anchor="w")
        self._api_key_var = tk.StringVar()
        entry = ttk.Entry(outer, textvariable=self._api_key_var, width=52, show="*")
        entry.pack(fill="x", pady=(4, 4))
        entry.bind("<Return>", lambda _: self._save_and_continue())

        show_var = tk.BooleanVar(value=False)

        def toggle_show():
            entry.config(show="" if show_var.get() else "*")

        ttk.Checkbutton(outer, text="Show key", variable=show_var, command=toggle_show).pack(
            anchor="w", pady=(0, 12)
        )
        ttk.Button(outer, text="Save & Continue →", command=self._save_and_continue).pack()

        self._setup_status = tk.StringVar()
        self._setup_status_label = ttk.Label(
            outer,
            textvariable=self._setup_status,
            foreground="red",
            wraplength=430,
            justify="center",
        )
        self._setup_status_label.pack(pady=(10, 0), fill="x")
        entry.focus_set()

    def _save_and_continue(self) -> None:
        key = self._api_key_var.get().strip()
        if not key:
            self._setup_status.set("Please enter your API key.")
            return

        self._setup_status.set("Validating key…")
        self._frame.update_idletasks()

        client = GeminiClient(key)
        error = client.validate_key()

        if error is not None:
            if "429" in error or "quota" in error.lower() or "rate" in error.lower():
                self._log.warning("Rate-limited during validation: %s", error)
                self._setup_status_label.config(foreground="orange")
                self._setup_status.set(
                    "Rate limit hit — your key is valid and has been saved. "
                    "The app will open in 3 seconds. Wait a minute before scanning."
                )
                save_api_key(key)
                self._client = client
                self._frame.after(3000, self._build_main_ui)
            else:
                self._log.error("API key validation failed: %s", error)
                self._setup_status_label.config(foreground="red")
                self._setup_status.set(f"Error: {error}")
            return

        self._log.info("API key validated successfully")
        save_api_key(key)
        self._client = client
        self._build_main_ui()

    # ── Main UI ───────────────────────────────────────────────────────────────

    def _build_main_ui(self) -> None:
        self._clear()

        left = ttk.Frame(self._frame, padding=(10, 10, 0, 10))
        left.pack(side="left", fill="both", expand=True)

        self._build_scan_ui(left)
        self._build_sidebar()

    def _build_scan_ui(self, parent: ttk.Frame) -> None:
        # Header
        ttk.Label(parent, text="Scan Card Images", font=("Helvetica", 12, "bold")).pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Label(
            parent,
            text=(
                "Select photos of Dragon Ball Fusion World cards. "
                "Multiple cards per image are supported. "
                "Supported formats: JPG, PNG, WEBP, BMP, TIFF"
            ),
            font=("Helvetica", 9),
            foreground="#555555",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(2, 6))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 6))

        self._build_discord_section(parent)

        # Browse / Clear buttons
        btn_row = ttk.Frame(parent)
        btn_row.pack(anchor="w")
        ttk.Button(btn_row, text="Browse Images…", command=self._browse_images).pack(
            side="left", padx=6, pady=2
        )
        ttk.Button(btn_row, text="Clear List", command=self._clear_file_list).pack(
            side="left", padx=6, pady=2
        )

        if _DND_AVAILABLE:
            ttk.Label(
                parent, text="(or drag & drop images here)",
                font=("Helvetica", 8), foreground="#888888",
            ).pack(anchor="w", padx=6, pady=(0, 4))

        # File list + Preview side by side
        list_and_preview = ttk.Frame(parent)
        list_and_preview.pack(fill="both", expand=False, pady=(0, 4))

        list_frame = ttk.Frame(list_and_preview)
        list_frame.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._file_listbox = tk.Listbox(
            list_frame, height=5, font=("Courier", 9),
            yscrollcommand=scrollbar.set, selectmode="browse", activestyle="none",
        )
        scrollbar.config(command=self._file_listbox.yview)
        self._file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        preview_frame = ttk.LabelFrame(
            list_and_preview, text="Preview",
            width=PREVIEW_SIZE + 16, height=PREVIEW_SIZE + 30,
        )
        preview_frame.pack(side="right", fill="y", padx=(8, 0))
        preview_frame.pack_propagate(False)
        self._preview_canvas = tk.Canvas(
            preview_frame, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
            bg="#dddddd", highlightthickness=0,
        )
        self._preview_canvas.pack(padx=4, pady=4)
        self._preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview", fill="#888888", justify="center",
        )

        if _DND_AVAILABLE:
            self._file_listbox.drop_target_register(DND_FILES)
            self._file_listbox.dnd_bind("<<Drop>>", self._on_dnd_drop)
            self._app.drop_target_register(DND_FILES)
            self._app.dnd_bind("<<Drop>>", self._on_dnd_drop)

        # Scan / Log buttons
        btn_row2 = ttk.Frame(parent)
        btn_row2.pack(anchor="w", pady=(4, 0))
        self._scan_btn = ttk.Button(btn_row2, text="Scan All Images", command=self._scan_uploaded)
        self._scan_btn.pack(side="left", padx=6, pady=2)
        ttk.Button(btn_row2, text="View Logs", command=self._show_log_viewer).pack(
            side="left", padx=6, pady=2
        )

        ttk.Label(
            parent, textvariable=self._countdown_var,
            foreground="#0055cc", font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=6, pady=(2, 0))

        # Dark status log
        self._scan_log = scrolledtext.ScrolledText(
            parent, height=6, state="disabled", wrap="word",
            font=("Courier", 9), relief="flat",
            background="#1e1e1e", foreground="#dddddd",
        )
        self._scan_log.tag_config("error",   foreground="#ff6b6b")
        self._scan_log.tag_config("success", foreground="#6bcb77")
        self._scan_log.tag_config("info",    foreground="#cccccc")
        self._scan_log.pack(fill="both", expand=True)

    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self._frame, bg="#e8e8e8", width=SIDEBAR_W)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)

        inner = ttk.Frame(sidebar, padding=10)
        inner.pack(fill="both", expand=True)

        ttk.Label(inner, text="Collected Codes", font=("Helvetica", 12, "bold")).pack(anchor="w")
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=6)

        list_frame = ttk.Frame(inner)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._code_listbox = tk.Listbox(
            list_frame, font=("Courier", 10),
            yscrollcommand=scrollbar.set, selectmode="extended", activestyle="none",
        )
        scrollbar.config(command=self._code_listbox.yview)
        self._code_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._count_var = tk.StringVar(value="0 codes")
        ttk.Label(inner, textvariable=self._count_var, font=("Helvetica", 9)).pack(
            anchor="w", pady=(4, 2)
        )
        ttk.Button(inner, text="Export codes.txt", command=self._export).pack(fill="x", pady=(4, 2))
        ttk.Button(inner, text="Remove Selected", command=self._remove_selected).pack(fill="x", pady=2)
        ttk.Button(inner, text="Clear All", command=self._clear_codes).pack(fill="x", pady=2)
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(inner, text="Change API Key", command=self._change_api_key).pack(fill="x", pady=2)

    # ── File list state ───────────────────────────────────────────────────────

    def _add_files(self, paths) -> None:
        existing = set(self._file_paths)
        added = 0
        for p in paths:
            p = str(p).strip()
            if p and p not in existing and Path(p).suffix.lower() in _IMAGE_EXTS:
                self._file_paths.append(p)
                self._file_statuses[p] = "pending"
                existing.add(p)
                added += 1
        self._refresh_file_listbox()
        count = len(self._file_paths)
        if count:
            self._append_log(
                f"{count} file(s) queued.{f'  (+{added} new)' if added else ''}", "info"
            )

    def _refresh_file_listbox(self) -> None:
        self._file_listbox.delete(0, "end")
        for i, path in enumerate(self._file_paths):
            status = self._file_statuses.get(path, "pending")
            self._file_listbox.insert("end", f"{STATUS_ICONS[status]} {Path(path).name}")
            self._file_listbox.itemconfigure(i, foreground=STATUS_COLORS[status])

    def _set_file_status(self, path: str, status: str) -> None:
        self._file_statuses[path] = status
        self._refresh_file_listbox()
        if path in self._file_paths:
            idx = self._file_paths.index(path)
            self._file_listbox.selection_clear(0, "end")
            self._file_listbox.selection_set(idx)
            self._file_listbox.see(idx)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _on_file_select(self, event=None) -> None:
        sel = self._file_listbox.curselection()
        if sel and sel[0] < len(self._file_paths):
            self._load_preview(self._file_paths[sel[0]])

    def _load_preview(self, path: str) -> None:
        try:
            img = Image.open(path)
            img.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
            canvas_img = Image.new("RGB", (PREVIEW_SIZE, PREVIEW_SIZE), (220, 220, 220))
            canvas_img.paste(img, ((PREVIEW_SIZE - img.width) // 2, (PREVIEW_SIZE - img.height) // 2))
            self._preview_photo = ImageTk.PhotoImage(canvas_img)
            self._preview_canvas.delete("all")
            self._preview_canvas.create_image(0, 0, anchor="nw", image=self._preview_photo)
        except Exception:
            self._preview_canvas.delete("all")
            self._preview_canvas.create_text(
                PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
                text="Cannot load\npreview", fill="#cc0000", justify="center",
            )

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def _on_dnd_drop(self, event) -> None:
        self._add_files(self._app.tk.splitlist(event.data.strip()))

    # ── Countdown ─────────────────────────────────────────────────────────────

    def _countdown_delay(self, seconds: int) -> None:
        for remaining in range(seconds, 0, -1):
            self._frame.after(0, self._set_countdown_label, remaining)
            time.sleep(1)
        self._frame.after(0, self._set_countdown_label, 0)

    def _set_countdown_label(self, remaining: int) -> None:
        self._countdown_var.set(f"Next image in {remaining}s…" if remaining > 0 else "")

    # ── Scan logic ────────────────────────────────────────────────────────────

    def _browse_images(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select card images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if paths:
            self._add_files(paths)

    def _clear_file_list(self) -> None:
        self._file_paths.clear()
        self._file_statuses.clear()
        self._refresh_file_listbox()
        self._preview_photo = None
        self._preview_canvas.delete("all")
        self._preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview", fill="#888888", justify="center",
        )
        self._append_log("File list cleared.", "info")

    # ── Discord section ───────────────────────────────────────────────────────

    def _build_discord_section(self, parent: ttk.Frame) -> None:
        self._discord_frame = ttk.LabelFrame(parent, text="Discord Channel", padding=(8, 4))
        self._discord_frame.pack(fill="x", pady=(0, 6))
        self._refresh_discord_section()

    def _refresh_discord_section(self) -> None:
        if not hasattr(self, "_discord_frame"):
            return
        for w in self._discord_frame.winfo_children():
            w.destroy()
        self.__dict__.pop("_discord_fetch_btn", None)

        cfg = load_discord_config()
        configured = bool(cfg["bot_token"] and cfg["channel_id"])

        if not configured:
            row = ttk.Frame(self._discord_frame)
            row.pack(fill="x")
            ttk.Label(row, text="Not configured.", foreground="#888888").pack(side="left")
            ttk.Button(
                row, text="Set up Discord →", command=self._show_discord_setup_dialog,
            ).pack(side="left", padx=(8, 0))
        else:
            row1 = ttk.Frame(self._discord_frame)
            row1.pack(fill="x")
            ttk.Label(
                row1, text=f"Channel ID: {cfg['channel_id']}",
                foreground="#555555", font=("Helvetica", 9),
            ).pack(side="left")
            self._discord_fetch_btn = ttk.Button(
                row1, text="Fetch from Discord", command=self._fetch_from_discord,
            )
            self._discord_fetch_btn.pack(side="left", padx=(10, 4))
            ttk.Button(
                row1, text="Settings", command=self._show_discord_setup_dialog,
            ).pack(side="left", padx=4)
            ttk.Label(
                self._discord_frame,
                text=f"Last fetch: {cfg['last_fetch_display']}",
                foreground="#888888", font=("Helvetica", 8),
            ).pack(anchor="w", pady=(2, 0))

    def _show_discord_setup_dialog(self) -> None:
        dlg = tk.Toplevel(self._frame)
        dlg.title("Discord Channel Setup")
        dlg.geometry("520x500")
        dlg.resizable(False, False)
        dlg.transient(self._frame)
        dlg.grab_set()

        outer = ttk.Frame(dlg, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Discord Channel Setup", font=("Helvetica", 13, "bold")).pack(
            pady=(0, 14)
        )

        # ── Step 1: Invite the bot ─────────────────────────────────────────────
        ttk.Label(outer, text="Step 1 — Add the bot to your Discord server",
                  font=("Helvetica", 10, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Click the button below to open Discord in your browser. Select your server and click Authorise.",
            font=("Helvetica", 8), foreground="#555555", wraplength=460,
        ).pack(anchor="w", pady=(2, 6))
        ttk.Button(
            outer, text="Open Invite Link in Browser →",
            command=lambda: webbrowser.open_new(DISCORD_BOT_INVITE_URL),
        ).pack(anchor="w", pady=(0, 12))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 12))

        # ── Step 2: Bot token ──────────────────────────────────────────────────
        cfg = load_discord_config()

        ttk.Label(outer, text="Step 2 — Enter the bot token",
                  font=("Helvetica", 10, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="The bot token is provided by the developer. Treat it like a password — do not share it with anyone else.",
            font=("Helvetica", 8), foreground="#555555", wraplength=460,
        ).pack(anchor="w", pady=(2, 4))
        token_var = tk.StringVar(value=cfg["bot_token"])
        token_entry = ttk.Entry(outer, textvariable=token_var, width=56, show="*")
        token_entry.pack(fill="x", pady=(0, 2))
        show_var = tk.BooleanVar(value=False)

        def toggle_token_show():
            token_entry.config(show="" if show_var.get() else "*")

        ttk.Checkbutton(
            outer, text="Show token", variable=show_var, command=toggle_token_show,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 12))

        # ── Step 3: Channel ID ─────────────────────────────────────────────────
        ttk.Label(outer, text="Step 3 — Enter your channel ID",
                  font=("Helvetica", 10, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="In Discord: Settings → Advanced → enable Developer Mode. Then right-click your channel → Copy Channel ID.",
            font=("Helvetica", 8), foreground="#555555", wraplength=460,
        ).pack(anchor="w", pady=(2, 4))
        channel_var = tk.StringVar(value=cfg["channel_id"])
        ttk.Entry(outer, textvariable=channel_var, width=24).pack(anchor="w", pady=(0, 14))

        # ── Status + buttons ───────────────────────────────────────────────────
        status_var = tk.StringVar()
        status_lbl = ttk.Label(outer, textvariable=status_var, wraplength=460, justify="left")
        status_lbl.pack(fill="x", pady=(0, 8))

        def validate_and_save():
            token = token_var.get().strip()
            channel = channel_var.get().strip()
            if not token or not channel:
                status_var.set("Both bot token and channel ID are required.")
                status_lbl.config(foreground="#cc0000")
                return
            status_var.set("Validating…")
            status_lbl.config(foreground="#555555")
            dlg.update_idletasks()
            client = DiscordClient(token, channel)
            error = client.validate()
            if error:
                status_var.set(f"Error: {error}")
                status_lbl.config(foreground="#cc0000")
                return
            save_discord_config(token, channel, cfg["last_message_id"])
            self._log.info("Discord config saved — channel %s", channel)
            status_var.set("✓ Connected! Settings saved.")
            status_lbl.config(foreground="#007700")
            self._refresh_discord_section()
            dlg.after(1200, dlg.destroy)

        btn_row = ttk.Frame(outer)
        btn_row.pack()
        ttk.Button(btn_row, text="Validate & Save", command=validate_and_save).pack(
            side="left", padx=4
        )
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)
        token_entry.focus_set()

    def _fetch_from_discord(self) -> None:
        if not self._client:
            messagebox.showinfo("Not Ready", "Set up your Gemini API key first.")
            return
        cfg = load_discord_config()
        if not cfg["bot_token"] or not cfg["channel_id"]:
            self._show_discord_setup_dialog()
            return
        self._scan_btn.config(state="disabled")
        if hasattr(self, "_discord_fetch_btn"):
            self._discord_fetch_btn.config(state="disabled", text="Fetching…")
        self._append_log("Fetching images from Discord…", "info")
        self._log.info("Discord fetch started (after=%s)", cfg["last_message_id"] or "none")
        threading.Thread(target=self._run_discord_fetch, args=(cfg,), daemon=True).start()

    def _run_discord_fetch(self, cfg: dict) -> None:
        discord = DiscordClient(cfg["bot_token"], cfg["channel_id"])
        after_id = cfg["last_message_id"] or None

        try:
            messages = discord.fetch_image_messages(after_id=after_id)
        except DiscordError as exc:
            self._log.error("Discord fetch error: %s", exc)
            self._frame.after(0, lambda e=exc: self._append_log(f"Discord error: {e}", "error"))
            self._frame.after(0, self._finish_discord_fetch)
            return

        if not messages:
            self._log.info("Discord fetch: no new images found")
            # Diagnostic: raw fetch to see exactly what the API returns
            try:
                import requests as _req
                raw_resp = _req.get(
                    f"{discord.BASE}/channels/{cfg['channel_id']}/messages",
                    headers={"Authorization": f"Bot {cfg['bot_token']}"},
                    params={"limit": 10},
                    timeout=10,
                )
                status = raw_resp.status_code
                try:
                    body = raw_resp.json()
                except Exception:
                    body = raw_resp.text[:300]

                self._log.debug("Discord raw messages response %d: %s", status, body)

                if status == 403:
                    msg = f"API returned 403 Forbidden — bot is missing Read Message History permission on this channel."
                elif status == 401:
                    msg = "API returned 401 — bot token is invalid."
                elif status == 404:
                    msg = "API returned 404 — channel not found. Double-check the Channel ID."
                elif not raw_resp.ok:
                    msg = f"API returned {status}: {str(body)[:200]}"
                elif isinstance(body, list) and len(body) == 0:
                    msg = "API returned 0 messages. The channel is empty or the bot cannot see any messages."
                elif isinstance(body, list):
                    all_filenames = [
                        a.get("filename", "?")
                        for m in body for a in m.get("attachments", [])
                    ]
                    if all_filenames:
                        msg = (
                            f"API returned {len(body)} message(s) but attachments were filtered out. "
                            f"Found filenames: {all_filenames}. Only .jpg/.jpeg/.png/.webp are supported."
                        )
                    else:
                        msg = (
                            f"API returned {len(body)} message(s) but none had image attachments. "
                            "Make sure you sent the photo as a file/image, not a link or embed."
                        )
                else:
                    msg = f"Unexpected API response: {str(body)[:200]}"

                self._frame.after(0, lambda m=msg: self._append_log(f"Diagnostic: {m}", "error"))
            except Exception as exc:
                self._frame.after(
                    0, lambda e=exc: self._append_log(f"Diagnostic failed: {e}", "error")
                )
            self._frame.after(0, self._finish_discord_fetch)
            return

        self._log.info("Discord fetch: %d message(s) with images", len(messages))
        self._frame.after(
            0, lambda n=len(messages): self._append_log(
                f"Found {n} message(s) with images.", "info"
            )
        )

        total_codes_added = 0
        processed_messages = 0

        for i, msg in enumerate(messages):
            msg_id = msg["id"]
            attachments = msg["attachments"]
            msg_success = True

            for att in attachments:
                url = att["url"]
                filename = att["filename"]
                self._frame.after(
                    0, lambda fn=filename: self._append_log(
                        f"  Scanning discord/{fn}…", "info"
                    )
                )
                try:
                    raw = discord.download_attachment(url)
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                    codes = self._client.extract_codes(img)
                    if codes:
                        self._frame.after(
                            0, lambda fn=filename, c=len(codes): self._append_log(
                                f"  discord/{fn}: {c} code(s) extracted, verifying…", "info"
                            )
                        )
                        codes = self._client.verify_codes(img, codes)
                    added = self._add_codes(codes)
                    total_codes_added += added
                    self._log.info("discord/%s: %d code(s), %d new", filename, len(codes), added)
                    self._frame.after(
                        0, lambda fn=filename, c=len(codes), a=added: self._append_log(
                            f"  discord/{fn}: {c} code(s) verified, {a} new.", "success"
                        )
                    )
                except Exception as exc:
                    self._log.error("discord/%s: %s", filename, exc, exc_info=True)
                    self._frame.after(
                        0, lambda fn=filename, e=exc: self._append_log(
                            f"  Error on discord/{fn}: {e}", "error"
                        )
                    )
                    msg_success = False

            if msg_success:
                try:
                    discord.delete_message(msg_id)
                    fetch_display = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_discord_last_message_id(msg_id, fetch_display)
                    processed_messages += 1
                    self._log.info("Discord message %s deleted", msg_id)
                    self._frame.after(0, self._refresh_discord_section)
                except DiscordError as exc:
                    self._log.error("Could not delete message %s: %s", msg_id, exc)
                    self._frame.after(
                        0, lambda e=exc: self._append_log(
                            f"  Warning: could not delete Discord message ({e})", "error"
                        )
                    )
            else:
                self._frame.after(
                    0, lambda: self._append_log(
                        "  Message preserved (scan error) — retry by fetching again.", "error"
                    )
                )

            if i < len(messages) - 1:
                self._countdown_delay(int(BATCH_DELAY))

        self._log.info(
            "Discord fetch complete: %d/%d messages, %d codes added",
            processed_messages, len(messages), total_codes_added,
        )
        self._frame.after(
            0, lambda n=processed_messages, t=len(messages), c=total_codes_added: self._append_log(
                f"Discord fetch done: {n}/{t} message(s) processed, {c} new code(s) added.",
                "success" if n > 0 else "info",
            )
        )
        self._frame.after(0, self._finish_discord_fetch)

    def _finish_file_scan(self, total_added: int, total_paths: int) -> None:
        self._update_count()
        self._append_log(
            f"Done. {total_added} new code(s) added from {total_paths} image(s).", "success"
        )
        self._scan_btn.config(state="normal", text="Scan All Images")
        if hasattr(self, "_discord_fetch_btn"):
            self._discord_fetch_btn.config(state="normal")

    def _finish_discord_fetch(self) -> None:
        self._scan_btn.config(state="normal")
        if hasattr(self, "_discord_fetch_btn"):
            self._discord_fetch_btn.config(state="normal", text="Fetch from Discord")
        self._update_count()

    def _scan_uploaded(self) -> None:
        paths = list(self._file_paths)
        if not paths:
            messagebox.showinfo("No Files", "Browse and select images first.")
            return
        self._scan_btn.config(state="disabled", text="Scanning…")
        if hasattr(self, "_discord_fetch_btn"):
            self._discord_fetch_btn.config(state="disabled")
        self._append_log(f"Starting scan of {len(paths)} image(s)…", "info")
        self._log.info("Batch scan started: %d image(s)", len(paths))
        threading.Thread(target=self._run_batch_scan, args=(paths,), daemon=True).start()

    def _run_batch_scan(self, paths: list[str]) -> None:
        total_added = 0
        for i, path in enumerate(paths, start=1):
            label = Path(path).name
            self._frame.after(
                0, lambda i=i, label=label: self._append_log(
                    f"Scanning {i}/{len(paths)}: {label}", "info"
                )
            )
            self._frame.after(0, lambda p=path: self._set_file_status(p, "scanning"))
            try:
                img = Image.open(path).convert("RGB")
                codes = self._client.extract_codes(img)
                if codes:
                    self._frame.after(
                        0, lambda c=len(codes), label=label: self._append_log(
                            f"  {label}: {c} code(s) extracted, verifying…", "info"
                        )
                    )
                    codes = self._client.verify_codes(img, codes)
                added = self._add_codes(codes)
                total_added += added
                self._log.info("Image %s: found %s, added %d", label, codes, added)
                self._frame.after(0, lambda p=path: self._set_file_status(p, "done"))
                self._frame.after(
                    0, lambda codes=codes, added=added, label=label: self._append_log(
                        f"  {label}: {len(codes)} code(s) verified, {added} new.", "success"
                    )
                )
            except Exception as exc:
                self._log.error("Error scanning %s: %s", label, exc, exc_info=True)
                self._frame.after(0, lambda p=path: self._set_file_status(p, "error"))
                self._frame.after(
                    0, lambda exc=exc, label=label: self._append_log(
                        f"  Error on {label}: {exc}", "error"
                    )
                )
                time.sleep(1)
                continue

            if i < len(paths):
                self._countdown_delay(int(BATCH_DELAY))

        self._log.info("Batch scan complete. Total new codes: %d", total_added)
        self._frame.after(0, lambda: self._finish_file_scan(total_added, len(paths)))

    # ── Code management ───────────────────────────────────────────────────────

    def _add_codes(self, codes: list[str]) -> int:
        added = 0
        existing = set(self._codes)
        for code in codes:
            if code not in existing:
                self._codes.append(code)
                existing.add(code)
                self._code_listbox.insert("end", code)
                added += 1
        self._update_count()
        return added

    def _update_count(self) -> None:
        n = len(self._codes)
        self._count_var.set(f"{n} code{'s' if n != 1 else ''}")

    def _remove_selected(self) -> None:
        sel = self._code_listbox.curselection()
        if not sel:
            return
        for idx in reversed(sel):
            self._codes.pop(idx)
            self._code_listbox.delete(idx)
        self._update_count()

    def _clear_codes(self) -> None:
        if not self._codes:
            return
        if messagebox.askyesno("Clear All", "Remove all collected codes?"):
            self._codes.clear()
            self._code_listbox.delete(0, "end")
            self._update_count()

    def _export(self) -> None:
        if not self._codes:
            messagebox.showinfo("Nothing to Export", "Collect some codes first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save codes",
            defaultextension=".txt",
            initialfile="codes.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        # Convert codes from "XXXX XXXX XXXX XXXX" (spaces) to "XXXX-XXXX-XXXX-XXXX" (dashes)
        # so the file is directly compatible with the redeemer's validation regex.
        lines = [code.replace(" ", "-") for code in self._codes]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._log.info("Exported %d codes to %s", len(self._codes), path)
        messagebox.showinfo("Exported", f"Saved {len(self._codes)} code(s) to:\n{path}")
        # Handoff: switch to Redeemer tab and pre-fill the exported file
        self._app.handoff_to_redeemer(Path(path))

    # ── Log viewer ────────────────────────────────────────────────────────────

    def _show_log_viewer(self) -> None:
        _show_log_viewer_window(self._frame, scanner_log_path(), "Scanner Log")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _append_log(self, msg: str, level: str = "info") -> None:
        def _do():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._scan_log.config(state="normal")
            self._scan_log.insert("end", f"[{ts}] {msg}\n", level)
            self._scan_log.see("end")
            self._scan_log.config(state="disabled")
        self._frame.after(0, _do)

    def _change_api_key(self) -> None:
        self._log.info("User requested API key change")
        self._build_setup_ui()

    def _clear(self) -> None:
        for widget in self._frame.winfo_children():
            widget.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Redeemer tab
# ═════════════════════════════════════════════════════════════════════════════

class RedeemerTab:
    """
    Manages the 4-screen redeemer flow inside a provided ttk.Frame.
    Screens: file picker → countdown → progress → summary.
    """

    def __init__(self, frame: ttk.Frame) -> None:
        self._frame = frame
        self._log   = get_redeemer_logger()

        self._codes: list[str] = []
        self._codes_path: Path | None = None
        self._win_rect: WindowRect | None = None
        self._redeemer: Redeemer | None = None
        self._results: list[tuple[str, str]] = []

        # All screen content lives in this container so _clear() only wipes it
        self._container = ttk.Frame(self._frame)
        self._container.pack(fill="both", expand=True)

        self._log.info("Redeemer tab initialised")
        self._build_file_picker()

    # ── Screen 1 — File Picker ────────────────────────────────────────────────

    def _build_file_picker(self) -> None:
        self._clear()

        outer = ttk.Frame(self._container, padding=32)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Code Redeemer", font=("Helvetica", 16, "bold")).pack(pady=(0, 4))
        ttk.Label(
            outer,
            text=(
                "Select a codes file exported from the Scanner tab.\n"
                "Expected format: one XXXX-XXXX-XXXX-XXXX code per line."
            ),
            justify="center",
        ).pack(pady=(0, 16))

        self._file_var = tk.StringVar(value="No file selected")
        ttk.Label(
            outer,
            textvariable=self._file_var,
            foreground="gray",
            font=("Courier", 9),
            wraplength=430,
        ).pack(pady=(0, 10))

        btn_row = ttk.Frame(outer)
        btn_row.pack()
        ttk.Button(btn_row, text="Browse…", command=self._browse_file).pack(side="left", padx=4)
        self._proceed_btn = ttk.Button(
            btn_row, text="Proceed →", command=self._proceed, state="disabled"
        )
        self._proceed_btn.pack(side="left", padx=4)

        self._status_var = tk.StringVar()
        self._status_lbl = ttk.Label(
            outer, textvariable=self._status_var, wraplength=440, justify="center"
        )
        self._status_lbl.pack(pady=(12, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(14, 6))
        log_row = ttk.Frame(outer)
        log_row.pack()
        ttk.Label(log_row, text="Logs:", foreground="gray", font=("Helvetica", 8)).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(log_row, text="Open Log Folder", command=self._open_log_folder).pack(
            side="left", padx=4
        )
        ttk.Button(log_row, text="Clear Log", command=self._clear_log).pack(side="left", padx=4)
        ttk.Button(log_row, text="View Log", command=self._show_log_viewer).pack(side="left", padx=4)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select codes file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        self.load_codes_file(Path(path))

    def load_codes_file(self, path: Path) -> None:
        """
        Public method — called by scanner handoff or by the Browse button.
        Validates the file and updates the file picker UI state.
        No-op if the redeemer is currently running (mid-countdown/progress/summary).
        """
        # Only act if the file picker screen is showing (has _file_var)
        if not hasattr(self, "_file_var"):
            return

        try:
            codes = validate_codes_file(path)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            self._proceed_btn.config(state="disabled")
            return

        if not codes:
            self._set_status(
                "No valid codes found in this file.\n"
                "Codes must be in the format XXXX-XXXX-XXXX-XXXX, one per line.",
                error=True,
            )
            self._proceed_btn.config(state="disabled")
            return

        self._codes = codes
        self._codes_path = path
        self._file_var.set(str(path))
        self._set_status(f"Found {len(codes)} valid code(s). Ready to proceed.", error=False)
        self._proceed_btn.config(state="normal")
        self._log.info("Loaded %d codes from %s", len(codes), path)

    def _proceed(self) -> None:
        win = find_game_window()
        if win is None:
            messagebox.showerror(
                "Game Not Found",
                "Could not find the DBSCGFW game window.\n\n"
                "Please:\n"
                "  1. Launch Dragon Ball Fusion World\n"
                "  2. Navigate to Enter a code → Serial code tab\n"
                "  3. Click Proceed again.",
            )
            return
        self._win_rect = win
        self._log.info("Game window found: %s", win)
        self._build_countdown()

    def _open_log_folder(self) -> None:
        folder = redeemer_log_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)

    def _clear_log(self) -> None:
        p = redeemer_log_path()
        if not p.exists() or p.stat().st_size == 0:
            messagebox.showinfo("Clear Log", "Log is already empty.")
            return
        if not messagebox.askyesno("Clear Log", f"Delete all log contents?\n\n{p}"):
            return
        try:
            p.write_text("", encoding="utf-8")
            self._log.info("Log cleared by user")
            messagebox.showinfo("Clear Log", "Log cleared.")
        except Exception as exc:
            messagebox.showerror("Clear Log", f"Could not clear log:\n{exc}")

    def _show_log_viewer(self) -> None:
        _show_log_viewer_window(self._frame, redeemer_log_path(), "Redeemer Log")

    def _set_status(self, msg: str, *, error: bool) -> None:
        self._status_var.set(msg)
        self._status_lbl.config(foreground="#cc0000" if error else "#007700")

    # ── Screen 2 — Countdown ──────────────────────────────────────────────────

    def _build_countdown(self) -> None:
        self._clear()

        outer = ttk.Frame(self._container, padding=32)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Get Ready", font=("Helvetica", 16, "bold")).pack(pady=(0, 8))
        ttk.Label(
            outer,
            text=(
                f"Redeeming {len(self._codes)} code(s).\n\n"
                "Switch to the game now.\n"
                "Click inside the first code input box before the timer hits zero."
            ),
            justify="center",
        ).pack(pady=(0, 14))

        self._countdown_var = tk.StringVar(value=str(COUNTDOWN_SECONDS))
        ttk.Label(
            outer,
            textvariable=self._countdown_var,
            font=("Helvetica", 40, "bold"),
            foreground="#cc4400",
        ).pack()

        ttk.Button(outer, text="Cancel", command=self._build_file_picker).pack(pady=(14, 0))

        self._remaining = COUNTDOWN_SECONDS
        self._tick()

    def _tick(self) -> None:
        if self._remaining <= 0:
            self._start_automation()
            return
        self._countdown_var.set(str(self._remaining))
        self._remaining -= 1
        self._container.after(1000, self._tick)

    # ── Screen 3 — Progress ───────────────────────────────────────────────────

    def _start_automation(self) -> None:
        self._results = []
        self._build_progress()

        self._redeemer = Redeemer(
            codes=self._codes,
            win=self._win_rect,
            on_progress=self._on_code_result,
            on_done=self._on_done,
            on_error=self._on_error,
        )
        self._redeemer.start()

    def _build_progress(self) -> None:
        self._clear()

        outer = ttk.Frame(self._container, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Redeeming Codes…", font=("Helvetica", 14, "bold")).pack(pady=(0, 8))

        self._prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            outer, variable=self._prog_var, maximum=len(self._codes), length=480
        ).pack(fill="x")

        self._prog_label_var = tk.StringVar(value=f"0 / {len(self._codes)}")
        ttk.Label(outer, textvariable=self._prog_label_var, anchor="e").pack(fill="x")

        self._prog_log = scrolledtext.ScrolledText(
            outer, height=10, state="disabled", wrap="word",
            font=("Courier", 9), relief="flat",
            background="#1e1e1e", foreground="#dddddd",
        )
        for tag, colour in _REDEEMER_RESULT_COLOURS.items():
            self._prog_log.tag_config(tag, foreground=colour)
        self._prog_log.pack(fill="both", expand=True, pady=(6, 6))

        ttk.Label(
            outer,
            text="Emergency stop: move mouse to the top-left corner of your screen.",
            foreground="gray",
            font=("Helvetica", 8),
        ).pack()

        self._stop_btn = ttk.Button(outer, text="Stop", command=self._stop_automation)
        self._stop_btn.pack(pady=(6, 0))

        self._redeemer_log_line(
            f"Starting — {len(self._codes)} code(s) to redeem. Do not move the game window.",
            "info",
        )

    def _on_code_result(self, current: int, total: int, code: str, result: str) -> None:
        self._results.append((code, result))

        def _do() -> None:
            self._prog_var.set(current)
            self._prog_label_var.set(f"{current} / {total}")
            tag = result if result in _REDEEMER_RESULT_COLOURS else "info"
            self._redeemer_log_line(f"[{current}/{total}]  {code}  →  {result}", tag)

        self._container.after(0, _do)

    def _on_done(self, summary: dict, results: list[tuple[str, str]]) -> None:
        self._results = results
        self._container.after(0, lambda: self._build_summary(summary))

    def _on_error(self, msg: str) -> None:
        def _do() -> None:
            self._redeemer_log_line(f"⚠  {msg}", "warn")
            if "Stopped:" in msg or "Failsafe" in msg:
                self._stop_btn.config(state="disabled")
        self._container.after(0, _do)

    def _stop_automation(self) -> None:
        if self._redeemer:
            self._redeemer.stop()
        self._stop_btn.config(state="disabled")
        self._redeemer_log_line("Stop requested — finishing current code…", "info")

    def _redeemer_log_line(self, msg: str, tag: str = "info") -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._prog_log.config(state="normal")
        self._prog_log.insert("end", f"[{ts}]  {msg}\n", tag)
        self._prog_log.see("end")
        self._prog_log.config(state="disabled")

    # ── Screen 4 — Summary ────────────────────────────────────────────────────

    def _build_summary(self, summary: dict) -> None:
        results_path = self._write_results()
        self._clear()

        outer = ttk.Frame(self._container, padding=32)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Done!", font=("Helvetica", 16, "bold")).pack(pady=(0, 14))

        rows = [
            ("Successful",       summary.get("SUCCESS", 0),      "#007700"),
            ("Already used",     summary.get("ALREADY_USED", 0), "#cc7700"),
            ("Invalid",          summary.get("INVALID", 0),      "#cc0000"),
            ("Timeout / Error",  summary.get("TIMEOUT", 0) + summary.get("ERROR", 0), "#cc0000"),
        ]
        for label, count, colour in rows:
            row = ttk.Frame(outer)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", width=20, anchor="w").pack(side="left")
            ttk.Label(
                row, text=str(count), foreground=colour, font=("Helvetica", 10, "bold")
            ).pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=10)

        if results_path:
            ttk.Label(
                outer,
                text=f"Results saved to:\n{results_path}",
                foreground="gray",
                font=("Helvetica", 8),
                wraplength=380,
                justify="center",
            ).pack(pady=(0, 14))
        else:
            ttk.Label(
                outer,
                text="(Could not write results file.)",
                foreground="gray",
                font=("Helvetica", 8),
            ).pack(pady=(0, 14))

        btn_row = ttk.Frame(outer)
        btn_row.pack()
        ttk.Button(
            btn_row, text="Redeem Another File", command=self._build_file_picker
        ).pack(side="left", padx=4)

    def _write_results(self) -> Path | None:
        if not self._codes_path or not self._results:
            return None
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out = self._codes_path.parent / f"{self._codes_path.stem}_results_{ts}.txt"
        try:
            lines = [f"{code}  {result}" for code, result in self._results]
            out.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._log.info("Results written to %s", out)
            return out
        except Exception as exc:
            self._log.error("Failed to write results: %s", exc)
            return None

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for widget in self._container.winfo_children():
            widget.destroy()
        # Remove file picker screen attributes so load_codes_file no-ops
        # when a different screen is showing
        for attr in ("_file_var", "_proceed_btn", "_status_var", "_status_lbl"):
            self.__dict__.pop(attr, None)


# ═════════════════════════════════════════════════════════════════════════════
# Shared log viewer helper
# ═════════════════════════════════════════════════════════════════════════════

def _show_log_viewer_window(parent: tk.Widget, log_file: Path, title: str) -> None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("720x480")
    win.resizable(True, True)

    ttk.Label(
        win, text=f"Log file: {log_file}", font=("Helvetica", 9), foreground="gray"
    ).pack(anchor="w", padx=10, pady=(8, 2))

    text = scrolledtext.ScrolledText(win, font=("Courier", 9), state="disabled", wrap="none")
    text.pack(fill="both", expand=True, padx=10, pady=(0, 4))

    def refresh():
        try:
            content = log_file.read_text(encoding="utf-8") if log_file.exists() else "(no log yet)"
        except Exception as exc:
            content = f"Could not read log: {exc}"
        text.config(state="normal")
        text.delete("1.0", "end")
        text.insert("end", content)
        text.see("end")
        text.config(state="disabled")

    def clear_logs():
        if not messagebox.askyesno("Clear Logs", f"Delete all log contents?\n\n{log_file}", parent=win):
            return
        try:
            log_file.write_text("", encoding="utf-8")
            refresh()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not clear log:\n{exc}", parent=win)

    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", padx=10, pady=(0, 8))
    ttk.Button(btn_row, text="Refresh", command=refresh).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Clear Logs", command=clear_logs).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="left", padx=4)
    refresh()


# ═════════════════════════════════════════════════════════════════════════════
# Root application
# ═════════════════════════════════════════════════════════════════════════════

class _DBFWApp(_BaseClass):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(820, 480)
        self.resizable(True, True)

        self._log = get_scanner_logger()
        self._log.info("Application started")

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        scanner_frame  = ttk.Frame(self._notebook)
        redeemer_frame = ttk.Frame(self._notebook)
        self._notebook.add(scanner_frame,  text="   Scanner   ")
        self._notebook.add(redeemer_frame, text="   Redeemer   ")

        self._scanner  = ScannerTab(scanner_frame,  self)
        self._redeemer = RedeemerTab(redeemer_frame)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def handoff_to_redeemer(self, codes_path: Path) -> None:
        """Switch to the Redeemer tab and pre-fill the exported codes file."""
        self._notebook.select(1)
        self._redeemer.load_codes_file(codes_path)

    def _on_close(self) -> None:
        if self._redeemer._redeemer:
            self._redeemer._redeemer.stop()
        self._log.info("Application closing")
        self.destroy()


# Public name used by main.py
DBFWApp = _DBFWApp
