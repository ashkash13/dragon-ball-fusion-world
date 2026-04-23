"""
Screenshot-based state detection for the DBFW code redemption screen.

All coordinates are stored as fractions of the game window's dimensions,
calibrated against a 1456x840 reference screenshot. They scale automatically
to any resolution because we always find the window rect first.

Dialog detection strategy
─────────────────────────
After clicking Confirm:
  1. Poll for the result dialog by watching for a bright white banner to appear
     in the upper-center of the window.
  2. Determine result type:
       SUCCESS     → the dialog body contains a colourful item-image thumbnail.
                     Detected by high colour saturation in the item-image region.
       ALREADY_USED→ failure dialog with one short line of body text.
                     Detected by a low bright-pixel ratio in the body region.
       INVALID     → failure dialog with two lines of body text (longer message).
                     Detected by a higher bright-pixel ratio in the body region.

All thresholds were derived from the reference screenshots and may be tuned
after real-world testing via the constants at the top of this file.
"""
import time

import numpy as np
import pyautogui

from src.logger import get_redeemer_logger as get_logger
from src.redeemer.window import WindowRect

_log = get_logger()

# ── Timing ───────────────────────────────────────────────────────────────────

DIALOG_POLL_INTERVAL = 0.4   # seconds between poll screenshots
DIALOG_TIMEOUT       = 15.0  # seconds to wait before giving up

# ── Relative regions (left, top, width, height) as fractions of window size ──
# Calibrated from 1456 × 840 reference screenshots.

# White banners for each dialog type, sampled separately on every poll.
# The success dialog sits higher on screen than the failure dialog, so they
# occupy different vertical positions and need separate regions.
#   SUCCESS banner:  "Serial code entry successful" — y ≈ 115–185 px (840 ref)
#   FAILURE banner:  "Serial code entry failed"    — y ≈ 210–285 px (840 ref)
BANNER_REGIONS = [
    ("success", (0.237, 0.137, 0.522, 0.083)),  # success dialog banner
    ("failure", (0.237, 0.256, 0.522, 0.083)),  # failure dialog banner
]

# Area containing the body error message text (white text on dark background).
# "Invalid" produces ~2 lines of text; "Already used" produces ~1 line.
BODY_REL       = (0.290, 0.385, 0.420, 0.110)

# Lower half of the body region — specifically where the SECOND line of text
# would appear in an INVALID dialog.  ALREADY_USED only has one line so this
# region stays dark; INVALID has two lines so it will be lit up.
BODY_LOWER_REL = (0.290, 0.440, 0.420, 0.055)

# ── Click targets for the Close button ───────────────────────────────────────
# The success dialog is taller than the failure dialog so its Close button
# sits lower on the screen.

CLOSE_REL_SUCCESS = (0.499, 0.786)
CLOSE_REL_FAILURE = (0.499, 0.613)

# ── Detection thresholds ─────────────────────────────────────────────────────

# How much brighter (0-255) a banner region must be above the calibrated
# baseline to count as "a dialog has appeared".  The baseline is measured
# at startup against the empty input screen and varies per monitor/display
# settings, so this delta is the only value that needs tuning across machines.
# The white dialog banner typically reads 120-160 above a ~10-30 dark baseline,
# so 80 gives comfortable headroom on both sides.
BANNER_DELTA = 80

# Bright-pixel ratio (fraction of pixels with R,G,B all > 180) in the full
# body region.  Kept as a fallback signal alongside the lower-half check.
ALREADY_USED_PIXEL_RATIO_THRESHOLD = 0.050
# Calibrated from real runs:
#   ALREADY_USED observed full_ratio ≈ 0.0427  → 0.0073 below threshold
#   INVALID      observed full_ratio ≈ 0.0563  → 0.0063 above threshold
# Midpoint = 0.0495 → rounded to 0.050 for equal headroom on both sides.

# Bright-pixel ratio in the LOWER half of the body only.
# Even with small or low-contrast fonts, a second line of text will push this
# above ~0.03.  ALREADY_USED (one line) typically reads < 0.01 here.
# Tuned conservatively — check the INFO log ("lower_ratio=") to refine.
# When in doubt we default to INVALID — safer for the lockout budget.
LOWER_HALF_TEXT_THRESHOLD = 0.03


def calibrate_baseline(win: WindowRect) -> float:
    """
    Measure the resting brightness of both banner regions while no dialog is
    showing (call this before the automation loop, with the empty input screen
    visible).

    Returns the highest baseline brightness seen across all banner regions.
    The effective detection threshold will be  baseline + BANNER_DELTA,
    which automatically adapts to any monitor brightness or colour profile.
    """
    readings = []
    for label, rel in BANNER_REGIONS:
        region = win.abs_region(*rel)
        shot = pyautogui.screenshot(region=region)
        arr = np.array(shot, dtype=np.uint8)
        brightness = float(arr.mean())
        _log.debug("  calibrate: %s baseline brightness=%.1f", label, brightness)
        readings.append(brightness)
    baseline = max(readings)
    _log.info(
        "Banner baseline=%.1f  →  detection threshold=%.1f (baseline + %d)",
        baseline, baseline + BANNER_DELTA, BANNER_DELTA,
    )
    return baseline


def wait_for_dialog(win: WindowRect, baseline: float) -> str:
    """
    Poll until a result dialog appears, then return which type was detected.

    Returns:
        "success"  – the success dialog banner became bright
        "failure"  – the failure dialog banner became bright
        ""         – timed out, no dialog detected

    Because the two dialog types sit at different vertical positions, the
    banner that lights up already tells us the result — no further image
    analysis is needed to distinguish SUCCESS from failure.
    """
    threshold = baseline + BANNER_DELTA
    deadline = time.time() + DIALOG_TIMEOUT
    poll = 0

    while time.time() < deadline:
        poll += 1
        for label, rel in BANNER_REGIONS:
            region = win.abs_region(*rel)
            shot = pyautogui.screenshot(region=region)
            arr = np.array(shot, dtype=np.uint8)
            brightness = float(arr.mean())
            _log.debug(
                "  [poll %d] %s banner brightness=%.1f (threshold=%.1f)",
                poll, label, brightness, threshold,
            )
            if brightness >= threshold:
                _log.debug("  dialog detected on poll %d (%s)", poll, label)
                return label
        time.sleep(DIALOG_POLL_INTERVAL)

    _log.warning(
        "  wait_for_dialog timed out after %ds with no banner detected", DIALOG_TIMEOUT
    )
    return ""


def detect_result(win: WindowRect) -> str:
    """
    Analyse the current screen state and return the redemption result.

    Call this only after wait_for_dialog() has returned True.

    Only call this when wait_for_dialog() returned "failure".
    Returns one of:
        "ALREADY_USED"  – code was valid but already redeemed (safe, not a lockout risk)
        "INVALID"       – code rejected (counts toward the 10-error lockout)
    """
    # Two signals are combined to distinguish ALREADY_USED (1 line) from
    # INVALID (2 lines).  Both are logged at INFO so ratios appear in the
    # normal log for threshold tuning without enabling debug mode.
    #
    # Signal 1 — full body region bright-pixel ratio (original method)
    body_region = win.abs_region(*BODY_REL)
    body_shot   = pyautogui.screenshot(region=body_region)
    body_arr    = np.array(body_shot, dtype=np.uint8)
    bright_mask = (
        (body_arr[:, :, 0] > 180) &
        (body_arr[:, :, 1] > 180) &
        (body_arr[:, :, 2] > 180)
    )
    full_ratio = float(bright_mask.mean())

    # Signal 2 — lower-half region only (where the 2nd line of INVALID text sits)
    lower_region = win.abs_region(*BODY_LOWER_REL)
    lower_shot   = pyautogui.screenshot(region=lower_region)
    lower_arr    = np.array(lower_shot, dtype=np.uint8)
    lower_mask   = (
        (lower_arr[:, :, 0] > 180) &
        (lower_arr[:, :, 1] > 180) &
        (lower_arr[:, :, 2] > 180)
    )
    lower_ratio = float(lower_mask.mean())

    _log.info(
        "  detect_result: full_ratio=%.4f  lower_ratio=%.4f"
        "  (thresholds: full=%.2f  lower=%.3f)",
        full_ratio, lower_ratio,
        ALREADY_USED_PIXEL_RATIO_THRESHOLD, LOWER_HALF_TEXT_THRESHOLD,
    )

    # Decision: use full_ratio only. The lower-half region captures text from
    # both dialog types so it cannot reliably distinguish them without
    # per-machine coordinate recalibration.
    # lower_ratio is still logged so thresholds can be tuned from real runs.
    #
    # Known data point: ALREADY_USED full_ratio ≈ 0.0427.
    # Threshold is set above that with headroom. Refine ALREADY_USED_PIXEL_RATIO_THRESHOLD
    # once INVALID ratio data is available from the INFO log.
    if full_ratio < ALREADY_USED_PIXEL_RATIO_THRESHOLD:
        _log.info("  → ALREADY_USED (full_ratio=%.4f < %.3f)", full_ratio, ALREADY_USED_PIXEL_RATIO_THRESHOLD)
        return "ALREADY_USED"
    else:
        _log.info("  → INVALID (full_ratio=%.4f >= %.3f)", full_ratio, ALREADY_USED_PIXEL_RATIO_THRESHOLD)
        return "INVALID"


def get_close_pos(result: str, win: WindowRect) -> tuple[int, int]:
    """Return the absolute screen coordinate of the Close button for this result."""
    rel = CLOSE_REL_SUCCESS if result == "SUCCESS" else CLOSE_REL_FAILURE
    return win.abs_pos(*rel)
