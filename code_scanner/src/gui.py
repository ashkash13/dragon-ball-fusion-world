"""
Main tkinter GUI for the DBFW Code Scanner.

Layout:
  ┌──────────────────────────────────────────────────────────┬──────────────┐
  │  Scan Card Images (header)                               │ Collected    │
  │  [Browse Images…]  [Clear List]                          │ Codes list   │
  │  (or drag & drop images here)                            │              │
  │  ┌─ file list w/ status icons ──┬──── Preview ────────┐  │ [Export]     │
  │  └──────────────────────────────┴────────────────────┘  │ [Remove]     │
  │  [Scan All Images]  [View Logs]                          │ [Clear All]  │
  │  Next image in 5s…                                       │ ──────────── │
  │  ┌─ dark status log ─────────────────────────────────┐   │ [Change Key] │
  │  └────────────────────────────────────────────────────┘  │              │
  └──────────────────────────────────────────────────────────┴──────────────┘
"""
import datetime
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

from src.config import load_api_key, save_api_key
from src.gemini_client import GeminiClient
from src.logger import get_logger, log_path

# ── Optional drag-and-drop support ────────────────────────────────────────────

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    TkinterDnD = None
    DND_FILES = None
    _DND_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────

WINDOW_TITLE = "DBFW Code Scanner"
SIDEBAR_W    = 220
BATCH_DELAY  = 7.0   # seconds between images (keeps well under 10 RPM on free tier)
PREVIEW_SIZE = 200   # px — square thumbnail canvas

WINDOW_W = 980
WINDOW_H = 540

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

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

# ── Conditional base class (TkinterDnD.Tk when available, else tk.Tk) ─────────

_BaseClass = TkinterDnD.Tk if _DND_AVAILABLE else tk.Tk


# ── Main application ──────────────────────────────────────────────────────────


class ScannerApp(_BaseClass):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(True, True)
        self.minsize(780, 460)

        self._log = get_logger()
        self._log.info("Application started")

        self._codes: list[str] = []
        self._client: GeminiClient | None = None

        # File list state (authoritative; listbox is a view over these)
        self._file_paths: list[str] = []
        self._file_statuses: dict[str, str] = {}

        # Preview state — must hold reference to prevent GC blanking the canvas
        self._preview_photo: ImageTk.PhotoImage | None = None

        # Countdown StringVar created here so _countdown_delay can use it
        # regardless of which screen is currently visible
        self._countdown_var = tk.StringVar(value="")

        api_key = load_api_key()
        if api_key:
            self._client = GeminiClient(api_key)
            self._log.info("Loaded saved API key")
            self._build_main_ui()
        else:
            self._build_setup_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Setup screen ──────────────────────────────────────────────────────────

    def _build_setup_ui(self) -> None:
        self._clear_window()
        self.geometry("520x380")

        outer = ttk.Frame(self, padding=40)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="DBFW Code Scanner", font=("Helvetica", 18, "bold")).pack(pady=(0, 6))
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
        self.update_idletasks()

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
                self.after(3000, self._build_main_ui)
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
        self._clear_window()
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")

        left = ttk.Frame(self, padding=(10, 10, 0, 10))
        left.pack(side="left", fill="both", expand=True)

        self._build_scan_ui(left)
        self._build_sidebar()

    # ── Scan UI ───────────────────────────────────────────────────────────────

    def _build_scan_ui(self, parent: ttk.Frame) -> None:
        # Header
        ttk.Label(
            parent,
            text="Scan Card Images",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", pady=(4, 0))
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

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 8))

        # Browse / Clear buttons
        btn_row = ttk.Frame(parent)
        btn_row.pack(anchor="w")
        ttk.Button(btn_row, text="Browse Images…", command=self._browse_images).pack(
            side="left", padx=6, pady=2
        )
        ttk.Button(btn_row, text="Clear List", command=self._clear_file_list).pack(
            side="left", padx=6, pady=2
        )

        # Drop zone hint (only shown when tkinterdnd2 is available)
        if _DND_AVAILABLE:
            ttk.Label(
                parent,
                text="(or drag & drop images here)",
                font=("Helvetica", 8),
                foreground="#888888",
            ).pack(anchor="w", padx=6, pady=(0, 4))

        # File list + Preview side by side
        list_and_preview = ttk.Frame(parent)
        list_and_preview.pack(fill="both", expand=False, pady=(0, 4))

        # Left: file listbox with status icons
        list_frame = ttk.Frame(list_and_preview)
        list_frame.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._file_listbox = tk.Listbox(
            list_frame, height=6, font=("Courier", 9),
            yscrollcommand=scrollbar.set, selectmode="browse",
            activestyle="none",
        )
        scrollbar.config(command=self._file_listbox.yview)
        self._file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        # Right: preview pane
        preview_frame = ttk.LabelFrame(
            list_and_preview, text="Preview",
            width=PREVIEW_SIZE + 16, height=PREVIEW_SIZE + 30,
        )
        preview_frame.pack(side="right", fill="y", padx=(8, 0))
        preview_frame.pack_propagate(False)

        self._preview_canvas = tk.Canvas(
            preview_frame,
            width=PREVIEW_SIZE,
            height=PREVIEW_SIZE,
            bg="#dddddd",
            highlightthickness=0,
        )
        self._preview_canvas.pack(padx=4, pady=4)
        self._preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview",
            fill="#888888",
            justify="center",
        )

        # Register drag-and-drop targets
        if _DND_AVAILABLE:
            self._file_listbox.drop_target_register(DND_FILES)
            self._file_listbox.dnd_bind("<<Drop>>", self._on_dnd_drop)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_dnd_drop)

        # Scan / Log buttons
        btn_row2 = ttk.Frame(parent)
        btn_row2.pack(anchor="w", pady=(4, 0))
        self._scan_btn = ttk.Button(
            btn_row2, text="Scan All Images", command=self._scan_uploaded
        )
        self._scan_btn.pack(side="left", padx=6, pady=2)
        ttk.Button(btn_row2, text="View Logs", command=self._show_log_viewer).pack(
            side="left", padx=6, pady=2
        )

        # Countdown label (empty when idle)
        ttk.Label(
            parent,
            textvariable=self._countdown_var,
            foreground="#0055cc",
            font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=6, pady=(2, 0))

        # Dark scrollable status log
        self._scan_log = scrolledtext.ScrolledText(
            parent, height=7, state="disabled", wrap="word",
            font=("Courier", 9), relief="flat",
            background="#1e1e1e", foreground="#dddddd",
        )
        self._scan_log.tag_config("error",   foreground="#ff6b6b")
        self._scan_log.tag_config("success", foreground="#6bcb77")
        self._scan_log.tag_config("info",    foreground="#cccccc")
        self._scan_log.pack(fill="both", expand=True)

    def _append_log(self, msg: str, level: str = "info") -> None:
        def _do():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._scan_log.config(state="normal")
            self._scan_log.insert("end", f"[{ts}] {msg}\n", level)
            self._scan_log.see("end")
            self._scan_log.config(state="disabled")
        self.after(0, _do)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        # Use a plain tk.Frame with a subtle background to visually separate the sidebar
        sidebar = tk.Frame(self, bg="#e8e8e8", width=SIDEBAR_W)
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

    # ── File list state management ─────────────────────────────────────────────

    def _add_files(self, paths) -> None:
        """Shared logic for both Browse and drag-and-drop. Deduplicates, filters by extension."""
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
        """Rebuild the listbox entirely from _file_paths + _file_statuses."""
        self._file_listbox.delete(0, "end")
        for i, path in enumerate(self._file_paths):
            status = self._file_statuses.get(path, "pending")
            self._file_listbox.insert("end", f"{STATUS_ICONS[status]} {Path(path).name}")
            self._file_listbox.itemconfigure(i, foreground=STATUS_COLORS[status])

    def _set_file_status(self, path: str, status: str) -> None:
        """Update a single file's status and refresh the listbox."""
        self._file_statuses[path] = status
        self._refresh_file_listbox()
        # Re-select the same row so the selection doesn't jump away
        if path in self._file_paths:
            idx = self._file_paths.index(path)
            self._file_listbox.selection_clear(0, "end")
            self._file_listbox.selection_set(idx)
            self._file_listbox.see(idx)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _on_file_select(self, event=None) -> None:
        sel = self._file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._file_paths):
            self._load_preview(self._file_paths[idx])

    def _load_preview(self, path: str) -> None:
        try:
            img = Image.open(path)
            img.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
            # Pad thumbnail to a square gray background
            canvas_img = Image.new("RGB", (PREVIEW_SIZE, PREVIEW_SIZE), (220, 220, 220))
            offset_x = (PREVIEW_SIZE - img.width) // 2
            offset_y = (PREVIEW_SIZE - img.height) // 2
            canvas_img.paste(img, (offset_x, offset_y))
            # Store as instance attr — PhotoImage is GC'd if only held locally
            self._preview_photo = ImageTk.PhotoImage(canvas_img)
            self._preview_canvas.delete("all")
            self._preview_canvas.create_image(0, 0, anchor="nw", image=self._preview_photo)
        except Exception:
            self._preview_canvas.delete("all")
            self._preview_canvas.create_text(
                PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
                text="Cannot load\npreview",
                fill="#cc0000",
                justify="center",
            )

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def _on_dnd_drop(self, event) -> None:
        """Handle file drops from the OS file manager."""
        # tk.splitlist handles both {braced paths with spaces} (Windows) and
        # space-separated paths (macOS) correctly via Tcl's native list parsing.
        paths = self.tk.splitlist(event.data.strip())
        self._add_files(paths)

    # ── Countdown timer ───────────────────────────────────────────────────────

    def _countdown_delay(self, seconds: int) -> None:
        """Called from the batch daemon thread. Ticks down 1s at a time,
        posting a GUI update each tick via after(0, ...)."""
        for remaining in range(seconds, 0, -1):
            self.after(0, self._set_countdown_label, remaining)
            time.sleep(1)
        self.after(0, self._set_countdown_label, 0)

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
        # Reset preview pane
        self._preview_photo = None
        self._preview_canvas.delete("all")
        self._preview_canvas.create_text(
            PREVIEW_SIZE // 2, PREVIEW_SIZE // 2,
            text="Select an image\nto preview",
            fill="#888888",
            justify="center",
        )
        self._append_log("File list cleared.", "info")

    def _scan_uploaded(self) -> None:
        paths = list(self._file_paths)
        if not paths:
            messagebox.showinfo("No Files", "Browse and select images first.")
            return
        self._scan_btn.config(state="disabled", text="Scanning…")
        self._append_log(f"Starting scan of {len(paths)} image(s)…", "info")
        self._log.info("Batch scan started: %d image(s)", len(paths))
        threading.Thread(target=self._run_batch_scan, args=(paths,), daemon=True).start()

    def _run_batch_scan(self, paths: list[str]) -> None:
        total_added = 0
        for i, path in enumerate(paths, start=1):
            label = Path(path).name
            self.after(
                0, lambda i=i, label=label: self._append_log(
                    f"Scanning {i}/{len(paths)}: {label}", "info"
                )
            )
            self.after(0, lambda p=path: self._set_file_status(p, "scanning"))

            try:
                img = Image.open(path).convert("RGB")
                codes = self._client.extract_codes(img)
                added = self._add_codes(codes)
                total_added += added
                self._log.info("Image %s: found %s, added %d", label, codes, added)
                self.after(0, lambda p=path: self._set_file_status(p, "done"))
                self.after(
                    0, lambda codes=codes, added=added, label=label: self._append_log(
                        f"  {label}: {len(codes)} code(s) found, {added} new.", "success"
                    )
                )
            except Exception as exc:
                self._log.error("Error scanning %s: %s", label, exc, exc_info=True)
                self.after(0, lambda p=path: self._set_file_status(p, "error"))
                self.after(
                    0, lambda exc=exc, label=label: self._append_log(
                        f"  Error on {label}: {exc}", "error"
                    )
                )
                time.sleep(1)
                continue

            if i < len(paths):
                self._countdown_delay(int(BATCH_DELAY))

        self._log.info("Batch scan complete. Total new codes: %d", total_added)
        self.after(
            0,
            lambda: (
                self._update_count(),
                self._append_log(
                    f"Done. {total_added} new code(s) added from {len(paths)} image(s).",
                    "success",
                ),
                self._scan_btn.config(state="normal", text="Scan All Images"),
            ),
        )

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
        # Delete in reverse order so earlier indices stay valid as items are removed
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
        Path(path).write_text("\n".join(self._codes) + "\n", encoding="utf-8")
        self._log.info("Exported %d codes to %s", len(self._codes), path)
        messagebox.showinfo("Exported", f"Saved {len(self._codes)} code(s) to:\n{path}")

    # ── Log viewer ────────────────────────────────────────────────────────────

    def _show_log_viewer(self) -> None:
        win = tk.Toplevel(self)
        win.title("Scanner Log")
        win.geometry("720x480")
        win.resizable(True, True)

        ttk.Label(
            win, text=f"Log file: {log_path()}", font=("Helvetica", 9), foreground="gray"
        ).pack(anchor="w", padx=10, pady=(8, 2))

        text = scrolledtext.ScrolledText(
            win, font=("Courier", 9), state="disabled", wrap="none"
        )
        text.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        def refresh():
            try:
                content = (
                    log_path().read_text(encoding="utf-8")
                    if log_path().exists()
                    else "(no log yet)"
                )
            except Exception as exc:
                content = f"Could not read log: {exc}"
            text.config(state="normal")
            text.delete("1.0", "end")
            text.insert("end", content)
            text.see("end")
            text.config(state="disabled")

        def clear_logs():
            if not messagebox.askyesno(
                "Clear Logs",
                f"Delete all log contents?\n\n{log_path()}",
                parent=win,
            ):
                return
            try:
                log_path().write_text("", encoding="utf-8")
                self._log.info("Logs cleared by user")
                refresh()
            except Exception as exc:
                messagebox.showerror("Error", f"Could not clear log:\n{exc}", parent=win)

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(btn_row, text="Refresh", command=refresh).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Clear Logs", command=clear_logs).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="left", padx=4)
        refresh()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _change_api_key(self) -> None:
        self._log.info("User requested API key change")
        self._build_setup_ui()

    def _clear_window(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def _on_close(self) -> None:
        self._log.info("Application closing")
        self.destroy()
