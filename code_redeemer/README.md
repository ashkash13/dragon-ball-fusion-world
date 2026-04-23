# DBFW Code Redeemer

Automatically enters Dragon Ball Fusion World serial codes into the game client.
Reads a `codes.txt` file (exported from **DBFW Code Scanner**) and types each
code into the game one by one.

---

## Requirements

- Python 3.11+
- Dragon Ball Fusion World installed and running on the same machine
- A codes file with one `XXXX-XXXX-XXXX-XXXX` code per line

---

## Installation

```bash
cd code_redeemer
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### macOS only — additional step

```bash
pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa
```

You will also need to grant **Accessibility** permission the first time:
> System Settings → Privacy & Security → Accessibility → add Terminal (or the built app)

---

## Before you launch the redeemer

**The order of steps matters.** The tool does not launch the game for you.

1. **Launch Dragon Ball Fusion World** and log in.
2. At the bottom of the screen, click **"Enter a code"**.
3. Make sure the **"Serial code"** tab is selected (not "Gift code").
4. Confirm the four `Enter text…` input boxes are visible and empty.
5. **Do not click inside any input box yet** — leave focus outside of them.
6. Leave the game window at its normal size. Do not move or resize it once the
   redeemer starts.

> **Important:** The game enforces a **6-hour lockout** after 10 consecutive
> invalid codes. The redeemer stops automatically after 3 consecutive invalid
> results to keep you well clear of this limit.

---

## Running

```bash
python main.py
```

**Step 1 — Pick a file**
Click **Browse…** and select your `codes.txt`. The tool validates the file and
shows how many codes were found. Click **Proceed →**.

**Step 2 — Countdown**
A 5-second countdown begins. During this time:
- Click on the game window to bring it to the front.
- Do **not** click inside an input box — the redeemer will do that itself.

**Step 3 — Automation**
The tool enters each code automatically. A live log shows every result:

| Result | Meaning |
|---|---|
| `SUCCESS` | Code accepted, item received |
| `ALREADY_USED` | Code was valid but already redeemed |
| `INVALID` | Code was rejected (counts toward lockout limit) |
| `TIMEOUT` | Game did not respond in time |

**Emergency stop:** Move your mouse to the **top-left corner** of your screen
at any time. You can also click **Stop** in the tool window.

**Step 4 — Summary**
Results are saved to a timestamped file alongside your codes file, e.g.:
```
codes_results_2026-03-19_143000.txt
```

---

## Building a distributable executable

**Windows**
```bat
build_windows.bat
```
Produces `dist\DBFWRedeemer.exe` — share this single file.

**macOS**
```bash
chmod +x build_mac.sh
./build_mac.sh
```
Produces `dist/DBFWRedeemer` — the recipient still needs to grant Accessibility
permission on first launch.

---

## Troubleshooting

**"Game Not Found" when clicking Proceed**
The tool searches for a window titled `DBSCGFW`. Make sure the game is running
and not minimised, then try again.

**Clicks land in the wrong place**
The click targets are calculated as proportional offsets within the game window.
If they are slightly off, the constants at the top of `src/redeemer.py`
(`INPUT_BOX_REL`, `CONFIRM_BTN_REL`) and `src/detector.py` (`CLOSE_REL_*`) can
be adjusted. Run with a single known code first to observe behaviour.

**Detection always returns INVALID even for good codes**
The screenshot-based state detection uses brightness and colour thresholds
calibrated to a reference resolution. If your monitor DPI or game resolution
differs significantly, tweak the thresholds in `src/detector.py`:
- `BANNER_BRIGHTNESS_THRESHOLD`
- `ITEM_SATURATION_THRESHOLD`
- `ALREADY_USED_PIXEL_RATIO_THRESHOLD`

**macOS: nothing happens after countdown**
Confirm Accessibility permission has been granted (see Installation above).
Without it, `pyautogui` cannot send mouse clicks or keystrokes.
