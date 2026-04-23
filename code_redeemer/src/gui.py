"""
Main tkinter GUI for the DBFW Code Redeemer.

Four screens in sequence:
  1. File Picker  – browse for a codes file, validate it, show code count.
  2. Countdown    – 5-second timer giving the user time to switch to the game.
  3. Progress     – live log of each code result with a progress bar.
  4. Summary      – totals for each result type and path to the results file.
"""
import datetime
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .logger import get_logger, log_path
from .redeemer import Redeemer, validate_codes_file
from .window import find_game_window, WindowRect

WINDOW_TITLE       = "DBFW Code Redeemer"
COUNTDOWN_SECONDS  = 5

# Colour per result type, used in the live log
_RESULT_COLOURS = {
    "SUCCESS":      "#007700",
    "ALREADY_USED": "#cc7700",
    "INVALID":      "#cc0000",
    "TIMEOUT":      "#cc0000",
    "ERROR":        "#cc0000",
    "info":         "#333333",
    "warn":         "#cc7700",
}


class RedeemerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.resizable(False, False)

        self._log = get_logger()
        self._codes: list[str] = []
        self._codes_path: Path | None = None
        self._win_rect: WindowRect | None = None
        self._redeemer: Redeemer | None = None
        self._results: list[tuple[str, str]] = []

        self._log.info("Application started")
        self._build_file_picker()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =========================================================================
    # Screen 1 — File Picker
    # =========================================================================

    def _build_file_picker(self) -> None:
        self._clear_window()
        self.geometry("500x340")

        outer = ttk.Frame(self, padding=32)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=WINDOW_TITLE, font=("Helvetica", 16, "bold")).pack(pady=(0, 4))
        ttk.Label(
            outer,
            text=(
                "Select a codes file exported from DBFW Code Scanner.\n"
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
            outer,
            textvariable=self._status_var,
            wraplength=440,
            justify="center",
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

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select codes file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        p = Path(path)
        try:
            codes = validate_codes_file(p)
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
        self._codes_path = p
        self._file_var.set(str(p))
        self._set_status(f"Found {len(codes)} valid code(s). Ready to proceed.", error=False)
        self._proceed_btn.config(state="normal")
        self._log.info("Loaded %d codes from %s", len(codes), p)

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
        folder = log_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)

    def _clear_log(self) -> None:
        p = log_path()
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

    def _set_status(self, msg: str, *, error: bool) -> None:
        self._status_var.set(msg)
        self._status_lbl.config(foreground="#cc0000" if error else "#007700")

    # =========================================================================
    # Screen 2 — Countdown
    # =========================================================================

    def _build_countdown(self) -> None:
        self._clear_window()
        self.geometry("480x260")

        outer = ttk.Frame(self, padding=32)
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
        self.after(1000, self._tick)

    # =========================================================================
    # Screen 3 — Progress
    # =========================================================================

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
        self._clear_window()
        self.geometry("540x430")

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Redeeming Codes…", font=("Helvetica", 14, "bold")).pack(pady=(0, 8))

        # Progress bar
        self._prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            outer, variable=self._prog_var, maximum=len(self._codes), length=480
        ).pack(fill="x")

        self._prog_label_var = tk.StringVar(value=f"0 / {len(self._codes)}")
        ttk.Label(outer, textvariable=self._prog_label_var, anchor="e").pack(fill="x")

        # Live log
        self._prog_log = scrolledtext.ScrolledText(
            outer,
            height=13,
            state="disabled",
            wrap="word",
            font=("Courier", 9),
            relief="flat",
            background="#f8f8f8",
        )
        for tag, colour in _RESULT_COLOURS.items():
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

        self._log_line(
            f"Starting — {len(self._codes)} code(s) to redeem. Do not move the game window.",
            "info",
        )

    def _on_code_result(self, current: int, total: int, code: str, result: str) -> None:
        self._results.append((code, result))

        def _do() -> None:
            self._prog_var.set(current)
            self._prog_label_var.set(f"{current} / {total}")
            tag = result if result in _RESULT_COLOURS else "info"
            self._log_line(f"[{current}/{total}]  {code}  →  {result}", tag)

        self.after(0, _do)

    def _on_done(self, summary: dict, results: list[tuple[str, str]]) -> None:
        self._results = results
        self.after(0, lambda: self._build_summary(summary))

    def _on_error(self, msg: str) -> None:
        def _do() -> None:
            self._log_line(f"⚠  {msg}", "warn")
            # If the message is a hard stop (not just a warning), disable Stop
            if "Stopped:" in msg or "Failsafe" in msg:
                self._stop_btn.config(state="disabled")

        self.after(0, _do)

    def _stop_automation(self) -> None:
        if self._redeemer:
            self._redeemer.stop()
        self._stop_btn.config(state="disabled")
        self._log_line("Stop requested — finishing current code…", "info")

    def _log_line(self, msg: str, tag: str = "info") -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._prog_log.config(state="normal")
        self._prog_log.insert("end", f"[{ts}]  {msg}\n", tag)
        self._prog_log.see("end")
        self._prog_log.config(state="disabled")

    # =========================================================================
    # Screen 4 — Summary
    # =========================================================================

    def _build_summary(self, summary: dict) -> None:
        results_path = self._write_results()
        self._clear_window()
        self.geometry("440x360")

        outer = ttk.Frame(self, padding=32)
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
        ttk.Button(btn_row, text="Close", command=self.destroy).pack(side="left", padx=4)

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

    # =========================================================================
    # Utilities
    # =========================================================================

    def _clear_window(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def _on_close(self) -> None:
        if self._redeemer:
            self._redeemer.stop()
        self._log.info("Application closing")
        self.destroy()
