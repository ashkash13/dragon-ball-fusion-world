"""
Core automation logic for the DBFW Code Redeemer.

validate_codes_file()  – reads a text file and returns all valid codes.
Redeemer               – runs the redemption loop on a background thread,
                         reporting each result via callbacks.

Code entry flow (per code)
──────────────────────────
  1. Click the first input box to focus it.
  2. Type all 16 characters without dashes — the game auto-advances the
     cursor across all four boxes.
  3. Wait a moment for the Confirm button to enable, then click it.
  4. Poll the screen until the result dialog appears.
  5. Read the result (SUCCESS / ALREADY_USED / INVALID).
  6. Click Close to dismiss the dialog.
  7. Pause briefly, then repeat for the next code.

Safety limits
─────────────
  • MAX_CONSECUTIVE_INVALID  – stop if this many back-to-back INVALID results
    occur.  Likely indicates a malformed codes file, not used codes.
  • LOCKOUT_WARN_THRESHOLD   – warn (but continue) once total INVALID errors
    approach the game's 10-error lockout limit.
  • PyAutoGUI failsafe       – move the mouse to the top-left screen corner
    at any time to abort immediately.
"""
import re
import threading
import time
from pathlib import Path
from typing import Callable

import pyautogui

from src.redeemer.detector import calibrate_baseline, detect_result, get_close_pos, wait_for_dialog
from src.logger import get_redeemer_logger as get_logger
from src.redeemer.window import WindowRect

# ── Code validation ───────────────────────────────────────────────────────────

_CODE_RE = re.compile(
    r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
    re.IGNORECASE,
)


def validate_codes_file(path: Path) -> list[str]:
    """
    Read *path* and return every line that looks like a DBFW redemption code
    (format: XXXX-XXXX-XXXX-XXXX, alphanumeric, case-insensitive).

    Raises ValueError if the file cannot be read.
    Non-matching lines are silently skipped.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Cannot read file: {exc}") from exc

    return [
        line.strip().upper()
        for line in text.splitlines()
        if _CODE_RE.match(line.strip())
    ]


# ── Timing constants ──────────────────────────────────────────────────────────

POST_FOCUS_DELAY   = 0.35   # seconds after clicking the input box
CHAR_INTERVAL      = 0.05   # seconds between keystrokes
POST_TYPE_DELAY    = 0.30   # seconds after last character, before Confirm click
POST_CONFIRM_DELAY = 0.50   # seconds after clicking Confirm before polling starts
                            # (accounts for the "Connecting…" status the game shows)
POST_CLOSE_DELAY   = 0.50   # seconds after closing the dialog, before next code

# ── Relative click targets (fraction of window width / height) ────────────────
# Calibrated from 1456 × 840 reference screenshots.

INPUT_BOX_REL  = (0.187, 0.461)   # centre of the first "Enter text…" box
CONFIRM_BTN_REL = (0.615, 0.902)  # centre of the orange Confirm button

# ── Safety thresholds ─────────────────────────────────────────────────────────

MAX_CONSECUTIVE_INVALID = 3    # stop the run if this many INVALID in a row
LOCKOUT_WARN_THRESHOLD  = 7    # warn user when approaching the 10-error lockout


# ── Redeemer ─────────────────────────────────────────────────────────────────

# Callback type aliases (for documentation)
#   on_progress(current, total, code, result)
#   on_done(summary, results)        summary = {"SUCCESS": n, …}
#                                    results = [("CODE", "RESULT"), …]
#   on_error(message)

class Redeemer:
    """
    Runs the full code-redemption loop on a daemon thread.

    Parameters
    ──────────
    codes        : list of validated codes (XXXX-XXXX-XXXX-XXXX)
    win          : WindowRect for the game window
    on_progress  : called (thread-safe via tkinter.after) for each code result
    on_done      : called once when the loop finishes normally
    on_error     : called if the loop must abort early
    """

    def __init__(
        self,
        codes: list[str],
        win: WindowRect,
        on_progress: Callable[[int, int, str, str], None],
        on_done: Callable[[dict, list[tuple[str, str]]], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._codes = codes
        self._win = win
        self._on_progress = on_progress
        self._on_done = on_done
        self._on_error = on_error
        self._log = get_logger()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        pyautogui.FAILSAFE = True  # top-left corner aborts automation
        pyautogui.PAUSE = 0        # no implicit delay between pyautogui calls
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _run(self) -> None:
        summary: dict[str, int] = {
            "SUCCESS": 0, "ALREADY_USED": 0, "INVALID": 0, "TIMEOUT": 0, "ERROR": 0
        }
        results: list[tuple[str, str]] = []
        consecutive_invalid = 0
        total = len(self._codes)

        # Measure the resting banner brightness before any dialog appears.
        # The detection threshold is set dynamically as baseline + BANNER_DELTA,
        # so it adapts automatically to any monitor brightness or colour profile.
        self._log.info("Calibrating banner baseline...")
        self._baseline = calibrate_baseline(self._win)

        for i, code in enumerate(self._codes, start=1):
            if self._stop.is_set():
                self._log.info("Stop requested at code %d/%d", i, total)
                break

            self._log.info("Redeeming %d/%d: %s", i, total, code)

            try:
                result = self._redeem_one(code)
            except pyautogui.FailSafeException:
                msg = "Failsafe triggered — mouse moved to top-left corner. Automation stopped."
                self._log.warning(msg)
                self._on_error(msg)
                return
            except Exception as exc:
                self._log.error("Unexpected error on %s: %s", code, exc, exc_info=True)
                result = "ERROR"

            summary[result] = summary.get(result, 0) + 1
            results.append((code, result))
            self._on_progress(i, total, code, result)
            self._log.info("%s → %s", code, result)

            # ── Safety checks ─────────────────────────────────────────────
            if result == "INVALID":
                consecutive_invalid += 1
            elif result in ("SUCCESS", "ALREADY_USED"):
                consecutive_invalid = 0

            if consecutive_invalid >= MAX_CONSECUTIVE_INVALID:
                msg = (
                    f"Stopped: {MAX_CONSECUTIVE_INVALID} consecutive INVALID errors. "
                    "Check that your codes file is correct and codes have not expired."
                )
                self._log.error(msg)
                self._on_error(msg)
                self._on_done(summary, results)
                return

            total_invalid = summary.get("INVALID", 0)
            if total_invalid == LOCKOUT_WARN_THRESHOLD:
                self._log.warning(
                    "%d total INVALID codes — approaching the 10-error lockout.", total_invalid
                )
                self._on_error(
                    f"Warning: {total_invalid} invalid codes entered. "
                    "The game locks out further entries after 10 invalid codes for 6 hours."
                )

            # Brief pause before next code (gives game time to settle)
            if i < total and not self._stop.is_set():
                time.sleep(POST_CLOSE_DELAY)

        self._on_done(summary, results)

    # ── Single code ───────────────────────────────────────────────────────────

    def _redeem_one(self, code: str) -> str:
        win = self._win

        # 1. Click the first input box to focus it
        input_pos = win.abs_pos(*INPUT_BOX_REL)
        self._log.debug("  step 1: clicking input box at %s", input_pos)
        pyautogui.click(*input_pos)
        time.sleep(POST_FOCUS_DELAY)

        # 2. Type all 16 characters (no dashes) — game auto-advances between boxes
        raw = code.replace("-", "")
        self._log.debug("  step 2: typing %d chars", len(raw))
        pyautogui.write(raw, interval=CHAR_INTERVAL)
        time.sleep(POST_TYPE_DELAY)

        # 3. Click Confirm (button enables automatically after the 16th character)
        confirm_pos = win.abs_pos(*CONFIRM_BTN_REL)
        self._log.debug("  step 3: clicking Confirm at %s", confirm_pos)
        pyautogui.click(*confirm_pos)

        # Brief wait for the game's "Connecting…" status before polling begins
        time.sleep(POST_CONFIRM_DELAY)

        # 4. Poll for the result dialog
        self._log.debug("  step 4: waiting for result dialog...")
        dialog_type = wait_for_dialog(win, self._baseline)
        if not dialog_type:
            self._log.warning("  step 4: TIMEOUT — dialog never appeared for %s", code)
            return "TIMEOUT"

        # 5 + 6. Determine result, then always click Close regardless of outcome.
        # Using try/finally ensures the dialog is never left open even if result
        # detection raises — an open dialog would block all subsequent codes.
        self._log.debug("  step 5: dialog_type=%s", dialog_type)
        result = "SUCCESS" if dialog_type == "success" else "INVALID"  # safe default
        try:
            if dialog_type != "success":
                result = detect_result(win)
            self._log.debug("  step 5: result=%s", result)
        except Exception as exc:
            self._log.error("  step 5: detection error (%s) — defaulting to %s", exc, result)
        finally:
            close_pos = get_close_pos(result, win)
            self._log.debug("  step 6: clicking Close at %s", close_pos)
            pyautogui.click(*close_pos)
            time.sleep(0.40)  # allow dialog dismiss animation to finish

        self._log.debug("  step 6: done — %s → %s", code, result)
        return result
