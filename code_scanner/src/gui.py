"""
Main tkinter GUI for the DBFW Code Scanner.

Camera tab layout:
  ┌──────────────────────────────────────┐
  │         Live camera preview          │
  │  [Capture & Scan]  [View Logs]       │  ← buttons always visible
  │  [cooldown hint if active]           │
  │  ┌──────────────────────────────┐    │
  │  │ scrollable status / error    │    │  ← messages never push buttons off
  │  │ log                          │    │
  │  └──────────────────────────────┘    │
  └──────────────────────────────────────┘
"""
import datetime
import platform
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import cv2
from PIL import Image, ImageTk

from src.config import load_api_key, save_api_key
from src.gemini_client import GeminiClient
from src.logger import get_logger, log_path

# ── Constants ────────────────────────────────────────────────────────────────

WINDOW_TITLE = "DBFW Code Scanner"
PREVIEW_W = 500
PREVIEW_H = 330
SIDEBAR_W = 220

SCAN_COOLDOWN = 7   # seconds between camera scans (gemini-2.5-flash: 10 RPM → min 6s, using 7s)
BATCH_DELAY = 7.0   # seconds between batch images (keeps well under 10 RPM on free tier)

# Laplacian variance threshold for blur detection.
# Typical values: crisp card text ~200+, acceptable ~80–200, blurry <80
BLUR_THRESHOLD = 80


# ── Main application ─────────────────────────────────────────────────────────


class ScannerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(True, True)
        self.minsize(600, 520)

        self._log = get_logger()
        self._log.info("Application started")

        self._codes: list[str] = []
        self._client: GeminiClient | None = None

        self._camera_running = False
        self._camera_thread: threading.Thread | None = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._current_frame: Image.Image | None = None  # preprocessed, ready to scan
        self._scanning = False
        self._last_scan_time: float = 0.0
        self._last_blur_score: float = 999.0
        self._preview_running = False

        api_key = load_api_key()
        if api_key:
            self._client = GeminiClient(api_key)
            self._log.info("Loaded saved API key")
            self._build_main_ui()
        else:
            self._build_setup_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Setup screen ─────────────────────────────────────────────────────────

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

    # ── Main UI ──────────────────────────────────────────────────────────────

    def _build_main_ui(self) -> None:
        self._clear_window()
        self.geometry(f"{PREVIEW_W + SIDEBAR_W + 40}x{PREVIEW_H + 200}")

        left = ttk.Frame(self, padding=(10, 10, 0, 10))
        left.pack(side="left", fill="both", expand=True)

        self._tabs = ttk.Notebook(left)
        self._tabs.pack(fill="both", expand=True)
        self._tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_camera_tab()
        self._build_upload_tab()
        self._build_sidebar()
        self._start_camera()

    # ── Camera tab ───────────────────────────────────────────────────────────

    def _build_camera_tab(self) -> None:
        tab = ttk.Frame(self._tabs, padding=8)
        self._tabs.add(tab, text="  Camera Scanner  ")

        # 1. Preview canvas
        self._canvas = tk.Canvas(tab, width=PREVIEW_W, height=PREVIEW_H, bg="#111111")
        self._canvas.pack()

        # 2. Buttons — always visible immediately below the preview
        btn_row = ttk.Frame(tab)
        btn_row.pack(pady=(8, 2))

        self._scan_btn = ttk.Button(
            btn_row, text="Capture & Scan", command=self._capture_and_scan, state="disabled"
        )
        self._scan_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="View Logs", command=self._show_log_viewer).pack(
            side="left", padx=6
        )

        # 3. Cooldown hint (1 line, only shown during cooldown)
        self._cooldown_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self._cooldown_var, foreground="gray", font=("Helvetica", 9)).pack()

        # 4. Scrollable status / error log
        self._camera_log = scrolledtext.ScrolledText(
            tab, height=5, state="disabled", wrap="word",
            font=("Helvetica", 9), relief="flat", background="#f8f8f8"
        )
        self._camera_log.tag_config("error", foreground="#cc0000")
        self._camera_log.tag_config("success", foreground="#007700")
        self._camera_log.tag_config("info", foreground="#333333")
        self._camera_log.pack(fill="both", expand=True, pady=(4, 0))

        # Seed with initial message
        self._append_camera_log("Starting camera…", "info")

    def _append_camera_log(self, msg: str, level: str = "info") -> None:
        """Append a timestamped line to the camera status log (thread-safe via after)."""
        def _do():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._camera_log.config(state="normal")
            self._camera_log.insert("end", f"[{ts}] {msg}\n", level)
            self._camera_log.see("end")
            self._camera_log.config(state="disabled")
        # Call directly if on main thread, else schedule
        try:
            self.after(0, _do)
        except Exception:
            pass

    # ── Upload tab ───────────────────────────────────────────────────────────

    def _build_upload_tab(self) -> None:
        tab = ttk.Frame(self._tabs, padding=8)
        self._tabs.add(tab, text="  Image Upload  ")

        ttk.Label(
            tab,
            text=(
                "Select images containing Dragon Ball Fusion World cards.\n"
                "Multiple cards per image are supported.\n"
                "Supported formats: JPG, PNG, WEBP, BMP"
            ),
            justify="center",
        ).pack(pady=(16, 10))

        # Buttons first
        btn_row = ttk.Frame(tab)
        btn_row.pack()
        ttk.Button(btn_row, text="Browse Images…", command=self._browse_images).pack(
            side="left", padx=4
        )
        ttk.Button(btn_row, text="Clear List", command=self._clear_file_list).pack(
            side="left", padx=4
        )

        # File list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill="x", pady=8, padx=4)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._file_listbox = tk.Listbox(
            list_frame, height=6, font=("Helvetica", 9),
            yscrollcommand=scrollbar.set, selectmode="extended",
        )
        scrollbar.config(command=self._file_listbox.yview)
        self._file_listbox.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Scan button + log viewer
        btn_row2 = ttk.Frame(tab)
        btn_row2.pack(pady=(0, 4))
        self._scan_images_btn = ttk.Button(
            btn_row2, text="Scan All Images", command=self._scan_uploaded
        )
        self._scan_images_btn.pack(side="left", padx=4)
        ttk.Button(btn_row2, text="View Logs", command=self._show_log_viewer).pack(
            side="left", padx=4
        )

        # Scrollable status log
        self._upload_log = scrolledtext.ScrolledText(
            tab, height=5, state="disabled", wrap="word",
            font=("Helvetica", 9), relief="flat", background="#f8f8f8"
        )
        self._upload_log.tag_config("error", foreground="#cc0000")
        self._upload_log.tag_config("success", foreground="#007700")
        self._upload_log.tag_config("info", foreground="#333333")
        self._upload_log.pack(fill="both", expand=True)

    def _append_upload_log(self, msg: str, level: str = "info") -> None:
        def _do():
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._upload_log.config(state="normal")
            self._upload_log.insert("end", f"[{ts}] {msg}\n", level)
            self._upload_log.see("end")
            self._upload_log.config(state="disabled")
        self.after(0, _do)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sidebar = ttk.Frame(self, padding=10, width=SIDEBAR_W)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)

        ttk.Label(sidebar, text="Collected Codes", font=("Helvetica", 12, "bold")).pack(anchor="w")
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=6)

        list_frame = ttk.Frame(sidebar)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._code_listbox = tk.Listbox(
            list_frame, font=("Courier", 10),
            yscrollcommand=scrollbar.set, selectmode="single", activestyle="none",
        )
        scrollbar.config(command=self._code_listbox.yview)
        self._code_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._count_var = tk.StringVar(value="0 codes")
        ttk.Label(sidebar, textvariable=self._count_var, font=("Helvetica", 9)).pack(
            anchor="w", pady=(4, 2)
        )
        ttk.Button(sidebar, text="Export codes.txt", command=self._export).pack(fill="x", pady=(4, 2))
        ttk.Button(sidebar, text="Remove Selected", command=self._remove_selected).pack(fill="x", pady=2)
        ttk.Button(sidebar, text="Clear All", command=self._clear_codes).pack(fill="x", pady=2)
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(sidebar, text="Change API Key", command=self._change_api_key).pack(fill="x", pady=2)

    # ── Camera logic ─────────────────────────────────────────────────────────

    def _start_camera(self) -> None:
        if self._camera_running:
            return
        self._camera_running = True
        self._preview_running = True
        self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._camera_thread.start()
        self._update_preview()

    def _stop_camera(self) -> None:
        self._camera_running = False

    def _blur_score(self, frame_bgr) -> float:
        """
        Return the Laplacian variance of the frame — a standard focus/sharpness metric.
        Higher = sharper. Below ~80 is noticeably blurry for card text.
        """
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _preprocess_frame(self, frame_bgr):
        """
        Reduce glare and sharpen the image for card scanning.

        Note: no horizontal flip is applied. cv2.VideoCapture returns the raw
        unmirrored sensor frame — flipping it would reverse text orientation and
        cause misreads. Gemini handles any text orientation natively.

        Steps:
          1. CLAHE on the L channel of LAB — boosts local contrast so code text
             stands out even when the card surface has glare.
          2. Unsharp mask — sharpens soft edges to help Gemini distinguish
             similar characters (Z vs 2, B vs 8, etc.).
        """
        # 1. CLAHE contrast enhancement on luminance channel
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l_enhanced, a, b]), cv2.COLOR_LAB2BGR)

        # 2. Unsharp mask — subtract a blurred version to boost fine detail
        blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2)
        sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)

        return sharpened

    def _camera_loop(self) -> None:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        self._log.info("Opening camera (backend=%s)", backend)
        cap = cv2.VideoCapture(0, backend)

        if not cap.isOpened():
            msg = "No camera found. Check your camera connection."
            self._log.error(msg)
            self.after(0, lambda: self._append_camera_log(msg, "error"))
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._log.info("Camera opened successfully")

        self.after(
            0,
            lambda: (
                self._append_camera_log(
                    "Camera ready — hold a card up and click Capture & Scan.", "info"
                ),
                self._scan_btn.config(state="normal"),
            ),
        )

        while self._camera_running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Measure sharpness on the raw frame before preprocessing
            self._last_blur_score = self._blur_score(frame)

            processed = self._preprocess_frame(frame)
            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            preview = Image.fromarray(rgb).resize((PREVIEW_W, PREVIEW_H), Image.LANCZOS)

            # Store full-resolution preprocessed image for scanning
            self._current_frame = Image.fromarray(rgb)

            if not self._frame_queue.full():
                self._frame_queue.put_nowait(preview)

            time.sleep(0.033)  # ~30 fps

        cap.release()
        self._log.info("Camera released")

    def _update_preview(self) -> None:
        if not self._preview_running:
            return
        try:
            img = self._frame_queue.get_nowait()
            imgtk = ImageTk.PhotoImage(image=img)
            self._canvas.imgtk = imgtk
            self._canvas.create_image(0, 0, anchor="nw", image=imgtk)
        except queue.Empty:
            pass
        self.after(33, self._update_preview)

    def _capture_and_scan(self) -> None:
        if self._scanning or self._current_frame is None:
            return

        elapsed = time.time() - self._last_scan_time
        if elapsed < SCAN_COOLDOWN:
            remaining = int(SCAN_COOLDOWN - elapsed) + 1
            self._cooldown_var.set(f"⏳ Wait {remaining}s before next scan")
            return

        # Blur check — warn but still allow the user to proceed
        if self._last_blur_score < BLUR_THRESHOLD:
            self._append_camera_log(
                f"⚠️ Image looks blurry (sharpness score: {self._last_blur_score:.0f}, "
                f"minimum recommended: {BLUR_THRESHOLD}). "
                "Hold the card still and further from the camera, then try again. "
                "Click Capture & Scan again to send anyway.",
                "error",
            )
            # On the second click within 3 seconds, send anyway
            now = time.time()
            if now - getattr(self, "_blur_warn_time", 0) > 3:
                self._blur_warn_time = now
                return

        self._cooldown_var.set("")
        self._scanning = True
        self._scan_btn.config(state="disabled")
        self._append_camera_log(
            f"Sending to Gemini… (sharpness score: {self._last_blur_score:.0f})", "info"
        )
        self._log.info("Camera scan triggered (blur score=%.1f)", self._last_blur_score)

        frame = self._current_frame.copy()
        threading.Thread(target=self._run_camera_scan, args=(frame,), daemon=True).start()

    def _run_camera_scan(self, image: Image.Image) -> None:
        try:
            codes = self._client.extract_codes(image)
            self._last_scan_time = time.time()
            self._log.info("Camera scan result: %s", codes)
            self.after(0, lambda: self._handle_scan_result(codes))
        except Exception as exc:
            self._log.error("Camera scan error: %s", exc, exc_info=True)
            self.after(0, lambda: self._append_camera_log(f"Error: {exc}", "error"))
        finally:
            self.after(
                0,
                lambda: (
                    self._scan_btn.config(state="normal"),
                    setattr(self, "_scanning", False),
                ),
            )

    def _handle_scan_result(self, codes: list[str]) -> None:
        if not codes:
            self._append_camera_log(
                "No code detected — try adjusting position or lighting.", "error"
            )
            return
        added = self._add_codes(codes)
        self._append_camera_log(
            f"Found {len(codes)} code(s). {added} new added to list.", "success"
        )

    # ── Upload logic ─────────────────────────────────────────────────────────

    def _browse_images(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select card images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff"),
                ("All files", "*.*"),
            ],
        )
        existing = set(self._file_listbox.get(0, "end"))
        added = 0
        for p in paths:
            if p not in existing:
                self._file_listbox.insert("end", p)
                added += 1
        count = self._file_listbox.size()
        self._append_upload_log(
            f"{count} file(s) queued.{f'  (+{added} new)' if added else ''}", "info"
        )

    def _clear_file_list(self) -> None:
        self._file_listbox.delete(0, "end")
        self._append_upload_log("File list cleared.", "info")

    def _scan_uploaded(self) -> None:
        paths = list(self._file_listbox.get(0, "end"))
        if not paths:
            messagebox.showinfo("No Files", "Browse and select images first.")
            return
        self._scan_images_btn.config(state="disabled")
        self._append_upload_log(f"Starting batch scan of {len(paths)} image(s)…", "info")
        self._log.info("Batch scan started: %d image(s)", len(paths))
        threading.Thread(target=self._run_batch_scan, args=(paths,), daemon=True).start()

    def _run_batch_scan(self, paths: list[str]) -> None:
        total_added = 0
        for i, path in enumerate(paths, start=1):
            label = Path(path).name
            self.after(
                0, lambda i=i, label=label: self._append_upload_log(
                    f"Scanning {i}/{len(paths)}: {label}", "info"
                )
            )
            try:
                img = Image.open(path).convert("RGB")
                codes = self._client.extract_codes(img)
                added = self._add_codes(codes)
                total_added += added
                self._log.info("Image %s: found %s, added %d", label, codes, added)
                self.after(
                    0, lambda codes=codes, added=added, label=label: self._append_upload_log(
                        f"  {label}: {len(codes)} code(s) found, {added} new.", "success"
                    )
                )
            except Exception as exc:
                self._log.error("Error scanning %s: %s", label, exc, exc_info=True)
                self.after(
                    0, lambda exc=exc, label=label: self._append_upload_log(
                        f"  Error on {label}: {exc}", "error"
                    )
                )
                time.sleep(1)
                continue

            if i < len(paths):
                time.sleep(BATCH_DELAY)

        self._log.info("Batch scan complete. Total new codes: %d", total_added)
        self.after(
            0,
            lambda: (
                self._update_count(),
                self._append_upload_log(
                    f"Done. {total_added} new code(s) added from {len(paths)} image(s).", "success"
                ),
                self._scan_images_btn.config(state="normal"),
            ),
        )

    # ── Code management ──────────────────────────────────────────────────────

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
        idx = sel[0]
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

    # ── Log viewer ───────────────────────────────────────────────────────────

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

    # ── Tab / API key ────────────────────────────────────────────────────────

    def _on_tab_changed(self, _event) -> None:
        if self._tabs.index("current") == 0:
            self._start_camera()
        else:
            self._stop_camera()

    def _change_api_key(self) -> None:
        self._log.info("User requested API key change")
        self._stop_camera()
        self._build_setup_ui()

    # ── Utilities ────────────────────────────────────────────────────────────

    def _clear_window(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def _on_close(self) -> None:
        self._log.info("Application closing")
        self._preview_running = False
        self._camera_running = False
        self.destroy()
