# DBFW Code Scanner

A desktop application for extracting redemption codes from **Dragon Ball Fusion World** cards.

Scan cards live with your webcam or upload photos of your card collection — the app uses Google's Gemini AI vision model to read the 16-character codes accurately, then lets you export them all to a plain text file.

> This is one part of the [dragon-ball-fusion-world](../) tooling suite.
> The exported `codes.txt` is the input for the upcoming Code Redeemer tool.

---

## Features

- **Camera Scanner** — live webcam preview with one-click capture and scan
- **Image Upload** — batch-process photos containing multiple cards in any orientation
- **Glare correction** — CLAHE contrast enhancement reduces glare on light card backgrounds
- **Mirror correction** — automatically un-mirrors the webcam image so card text reads correctly
- **Duplicate detection** — each unique code is only added to your list once
- **Export** — save all collected codes to `codes.txt`, one code per line
- **In-app log viewer** — timestamped scrollable log for reviewing errors and scan results
- **Cross-platform** — runs on Windows and macOS
- **No ongoing costs** — uses the free tier of Google Gemini (1,500 scans/day)

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| pip | bundled with Python | — |
| Webcam | any | Only needed for Camera Scanner mode |
| Internet connection | — | Required to call the Gemini API |
| Google Gemini API key | free | See setup instructions below |

---

## Getting a Free Gemini API Key

1. Go to **[aistudio.google.com](https://aistudio.google.com)**
2. Sign in with your Google account (free)
3. Click **Get API Key** → **Create API key**
4. Copy the key — you will paste it into the app on first launch

> **Free tier limits:** 15 requests per minute, 1,500 requests per day.
> For casual scanning this is effectively unlimited.

---

## Installation (Run from Source)

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd dragon-ball-fusion-world/code_scanner

# 2. Create and activate a virtual environment (recommended)

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate.bat

# Windows (Git Bash)
source .venv/Scripts/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

On first launch you will be prompted to paste your Gemini API key. The key is saved locally to `~/.dbfw_scanner/config.json` and is never sent anywhere except directly to Google's API.

---

## Usage

### Camera Scanner

1. Open the **Camera Scanner** tab (default)
2. Hold a Dragon Ball Fusion World card up to your webcam so the code is clearly visible
3. Click **Capture & Scan**
4. The detected code appears in the **Collected Codes** list on the right
5. Repeat for each card
6. When finished, click **Export codes.txt**

**Tips for best results:**
- The app automatically corrects webcam mirror effects and applies glare reduction
- Good lighting still makes a difference — avoid reflections pointing directly at the camera
- Keep the card roughly parallel to the camera (flat, not at an extreme angle)
- The full code must be visible in the frame
- There is a 5-second cooldown between scans to stay within the free API rate limit

### Image Upload

1. Open the **Image Upload** tab
2. Click **Browse Images…** and select one or more photos
3. Each image can contain multiple cards in any orientation
4. Click **Scan All Images** — the app processes each image in order
5. All found codes are added to the **Collected Codes** list (duplicates ignored)
6. Click **Export codes.txt** when done

**Supported formats:** JPG, JPEG, PNG, WEBP, BMP, TIFF

### Managing Collected Codes

| Action | How |
|---|---|
| Remove one code | Click it in the list → click **Remove Selected** |
| Clear everything | Click **Clear All** |
| Export to file | Click **Export codes.txt** → choose save location |

### Viewing Logs

Click **View Logs** (next to the scan buttons) to open a live-refreshable log window showing all scan results, errors, and API responses with timestamps. The log file is stored at `~/.dbfw_scanner/scanner.log`.

---

## Building a Standalone Executable

These scripts package the app into a single binary that can be shared with others. The recipient does **not** need Python installed.

> **Note:** You must build on the target platform — build the `.exe` on Windows, build the macOS binary on a Mac.
> Run all build commands from inside the `code_scanner/` directory.

### Windows → `DBFWScanner.exe`

```bat
cd dragon-ball-fusion-world\code_scanner
build_windows.bat
```

The output is at `dist\DBFWScanner.exe`. Share this file directly.

### macOS → `DBFWScanner`

```bash
cd dragon-ball-fusion-world/code_scanner
./build_mac.sh
```

The output is at `dist/DBFWScanner`. To share it:

```bash
zip -j DBFWScanner_mac.zip dist/DBFWScanner
```

> **macOS Gatekeeper:** First-time users may see a warning because the binary is unsigned.
> To open it: right-click the file → **Open** → **Open** in the dialog.

### Executable Size

Expect the final binary to be approximately **300–500 MB** because it bundles Python, OpenCV, and all dependencies. This is normal for PyInstaller-packaged Python applications.

---

## Project Structure

```
code_scanner/
├── main.py                  # Entry point — run this to launch the app
├── requirements.txt         # Python dependencies
├── build_windows.bat        # Windows build script (produces DBFWScanner.exe)
├── build_mac.sh             # macOS build script (produces DBFWScanner binary)
├── codes.txt                # Last exported codes output
└── src/
    ├── __init__.py
    ├── config.py            # API key persistence (~/.dbfw_scanner/config.json)
    ├── gemini_client.py     # Gemini API wrapper + response parsing
    ├── gui.py               # Full tkinter GUI (camera + upload + sidebar + log)
    └── logger.py            # Rotating file logger (~/.dbfw_scanner/scanner.log)
```

---

## How It Works

1. **Image capture** — OpenCV reads frames from the webcam (Camera mode) or PIL opens a file (Upload mode)
2. **Preprocessing** — the frame is flipped horizontally (mirror correction) and CLAHE contrast enhancement is applied to the luminance channel to reduce glare on light card backgrounds
3. **Gemini vision** — the image is sent to `gemini-2.0-flash` with a prompt asking it to extract all 16-character codes in `XXXX XXXX XXXX XXXX` format
4. **Parsing** — the response is matched against a strict regex `[A-Z0-9]{4} [A-Z0-9]{4} [A-Z0-9]{4} [A-Z0-9]{4}` to validate and extract codes
5. **Deduplication** — codes already in the list are silently ignored
6. **Export** — the list is written to a plain text file, one code per line

### Why Gemini instead of traditional OCR?

Traditional OCR engines (e.g. Tesseract) require carefully preprocessed images and are brittle when lighting, angle, or resolution vary. Gemini's vision model understands the full context of the image and reliably reads codes even in challenging conditions — and the free tier is more than sufficient for personal use.

---

## Changing the Gemini Model

The model is set in [src/gemini_client.py](src/gemini_client.py):

```python
_MODEL = "gemini-2.0-flash"
```

Other options (check [Google AI Studio](https://aistudio.google.com) for current free-tier availability):

| Model | Speed | Accuracy | Free tier |
|---|---|---|---|
| `gemini-2.0-flash` | Fast | High | Yes (default) |
| `gemini-2.0-flash-lite` | Fastest | Good | Yes |
| `gemini-2.5-pro` | Slower | Very High | Limited |

---

## Troubleshooting

**"No camera found"**
- Check that your webcam is connected and not in use by another app
- On Windows, try closing other apps that use the camera (Teams, Zoom, etc.)
- If you have multiple cameras, the app uses device index `0` by default

**"Invalid API key"**
- Double-check you copied the full key from Google AI Studio
- The key starts with `AIza...`
- You can update it any time via **Change API Key** in the sidebar

**API rate limit errors (429)**
- If you see this during setup, your key is valid — the app will save it and let you through
- The free tier allows 15 requests per minute; the app enforces a 5-second cooldown automatically
- For large batch uploads, the app adds a 1.5-second delay between images
- Check the **View Logs** panel for the full error detail

**"No code detected" on a valid card**
- Ensure the full 4×4-group code is visible and not obscured
- The app applies glare reduction automatically, but extreme glare can still cause issues
- Try the Image Upload mode with a higher-quality photo taken in better lighting

**PyInstaller build fails**
- Make sure you are running the build script from inside `code_scanner/` with the venv activated
- On macOS, if you see `tkinter` errors: `brew install python-tk`
- Re-run `pip install -r requirements.txt` to ensure all packages are present

---

## License

This project is for personal use. Dragon Ball Fusion World is a trademark of Bandai.
