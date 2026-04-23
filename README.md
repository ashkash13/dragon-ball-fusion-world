# Dragon Ball Fusion World Tools

A desktop application that scans Dragon Ball Fusion World card redemption codes from photos and automatically enters them into the game — end to end, with no manual typing.

Send card photos from your phone to Discord, scan them with one click, and watch the codes get entered automatically. No typing, no copy-pasting.

---

## Table of Contents

- [What It Does](#what-it-does)
- [For Users — Download & Setup](#for-users--download--setup)
  - [Download the App](#1-download-the-app)
  - [First Launch](#2-first-launch)
  - [Get a Google Gemini API Key](#3-get-a-google-gemini-api-key)
  - [Set Up Discord (Optional)](#4-set-up-discord-optional)
  - [Using the Scanner](#5-using-the-scanner)
  - [Using the Redeemer](#6-using-the-redeemer)
  - [Output Folder & Logs](#7-output-folder--logs)
  - [Troubleshooting](#troubleshooting)
- [For Developers — Local Setup](#for-developers--local-setup)
  - [Prerequisites](#prerequisites)
  - [Clone & Install](#clone--install)
  - [Run the App](#run-the-app)
  - [Build a Distributable](#build-a-distributable)

---

## What It Does

DBFW Tools is a two-tab desktop app:

| Tab | What it does |
|-----|-------------|
| **Scanner** | Reads 16-character redemption codes from card photos using Google Gemini AI. Upload files, drag and drop, or pull images directly from a private Discord channel. |
| **Redeemer** | Takes the exported codes file and automatically types each code into the game, reads the result screen, and logs everything. |

The two tabs work together: after scanning your cards, one click loads all codes into the Redeemer, ready to go.

---

## For Users — Download & Setup

### 1. Download the App

Go to the [**Releases page**](https://github.com/ashkash13/dragon-ball-fusion-world/releases) and download the file for your platform:

| Platform | File to download |
|----------|-----------------|
| Windows | `DBFWTools.exe` |
| macOS | `DBFWTools-Mac.dmg` |

No Python installation required — the app is fully self-contained.

---

### 2. First Launch

**Windows**

1. Double-click `DBFWTools.exe` to run it
2. If Windows Defender shows a warning, click **More info → Run anyway** — this happens because the app is not from the Microsoft Store

**macOS**

1. Open `DBFWTools-Mac.dmg`
2. Drag **DBFWTools** into your **Applications** folder

   <!-- screenshot: macOS DMG drag-to-Applications window -->

3. Open **Finder → Applications** and find DBFWTools
4. **Right-click** the app → click **Open** → click **Open** again in the dialog

   > This one-time step is required because the app is not from the Mac App Store. After doing it once, the app opens normally from then on.

5. **Accessibility permission (Redeemer tab only):** The Redeemer controls your keyboard and mouse to type codes. macOS requires you to grant permission for this:
   - Go to **System Settings → Privacy & Security → Accessibility**
   - Click **+** and add **DBFWTools**

   <!-- screenshot: macOS Accessibility settings with DBFWTools added -->

---

### 3. Get a Google Gemini API Key

The Scanner uses Google Gemini AI to read codes from your card photos. A free API key gives you **250 image scans per day** (125 if AI Verification is enabled, since it uses a second pass per image).

**Steps:**

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with any Google account
2. Click **Get API Key** in the bottom left pane
3. Click **Create API key** → choose any Google Cloud project (or create a new one)
4. Copy the key that appears

   <!-- screenshot: Google AI Studio — Get API Key page -->

5. On first launch, the app will ask for your API key — paste it in and click **Save & Continue**

   <!-- screenshot: App first-launch API key dialog -->

**To change the key later:** Click **Change API Key** in the left sidebar of the Scanner tab.

> Your API key is stored only on your own computer at `~/.dbfw_tools/config.json`. It is never sent anywhere except directly to Google.

---

### 4. Set Up Discord *(Optional)*

Instead of transferring card photos to your computer by cable or email, you can send them from your phone to a private Discord channel and pull them directly into the app. This is the fastest workflow.

A shared bot is already set up — you do not need to create your own Discord application.

#### Step 1 — Invite the bot to your server

Open the Scanner tab and click **Set up Discord →**, then click **Open Invite Link in Browser →**. This opens:

```
https://discord.com/oauth2/authorize?client_id=1485769708367249528&permissions=76800&scope=bot
```

Select your Discord server and click **Authorize**.

<!-- screenshot: Discord bot authorization page -->

#### Step 2 — Create a private channel for card photos

In Discord, create a private text channel (or use an existing one). Give the bot access to it:

1. Right-click the channel → **Edit Channel → Permissions**
2. Click **+** next to **Members**, search for the bot, and select it
3. Enable **View Channel**, **Read Message History**, and **Manage Messages**
4. Click **Save Changes**

<!-- screenshot: Discord channel permissions with bot added -->

#### Step 3 — Get your Channel ID

1. In Discord, go to **Settings → Advanced** and turn on **Developer Mode**
2. Right-click your channel → **Copy Channel ID**

<!-- screenshot: Discord right-click Copy Channel ID -->

#### Step 4 — Configure in the app

1. In the Scanner tab, click **Set up Discord →**
2. Contact the developer to get the **bot token** and paste it in
3. Paste your **Channel ID**
4. Click **Validate & Save** — the app confirms the connection

<!-- screenshot: App Discord setup dialog -->

Once configured, send card photos to your Discord channel from your phone, then click **Fetch from Discord** in the app. Each image is deleted from the channel after a successful scan so it won't be processed twice.

---

### 5. Using the Scanner

<!-- screenshot: Scanner tab with images loaded and codes in the sidebar -->

1. **Add card photos** using any of these methods:
   - Click **Browse Images** and select files
   - Drag and drop image files directly onto the app window
   - Click **Fetch from Discord** to pull new photos from your Discord channel

2. **Click Scan All Images** — the app sends each photo to Gemini, extracts any codes it finds, and runs a second verification pass to catch misread characters

3. **Review the codes** in the **Collected Codes** panel on the right. Use Ctrl+Click (Cmd+Click on Mac) or Shift+Click to select multiple codes for removal if needed

4. **Click Export codes.txt** — the file is saved to your configured output folder and the app automatically switches to the Redeemer tab with the file pre-loaded

**Tips for best results:**
- Photograph the code area clearly — keep it well-lit and in focus
- Multiple cards per photo are supported
- Avoid cluttered backgrounds; center the card in the frame
- Supported formats: JPG, PNG, WEBP, BMP, TIFF

---

### 6. Using the Redeemer

> **Before starting:** Open Dragon Ball Fusion World and navigate to the **Serial Code** entry screen.

<!-- screenshot: Redeemer tab with codes file loaded, showing Proceed button -->

1. The codes file is automatically filled in if you came from the Scanner. Otherwise click **Browse…** to load a `codes.txt` file manually

2. Click **Proceed →** — the app finds the game window automatically

3. A **5-second countdown** gives you time to switch to the game and click inside the code input box

4. The Redeemer types each code, clicks Confirm, reads the result, and moves to the next one automatically

5. When finished, a summary shows Success / Already Used / Invalid counts, and a results file is saved to your output folder

**To stop at any time:**
- Move your mouse to the **top-left corner** of the screen — this immediately halts automation
- Or click **Stop** in the app — it finishes the current code then stops

**Automatic safety stops:**
- Stops after 3 consecutive INVALID results (indicates expired or bad codes)
- Warns when approaching the game's 10-error lockout limit

---

### 7. Output Folder & Logs

By default, output files are saved to:

| Platform | Default location |
|----------|-----------------|
| Windows | `Documents\DBFWTools\` |
| macOS | `~/Documents/DBFWTools/` |

**To change the output folder:** Click **Change…** next to the output folder path in the Scanner tab sidebar. All logs, exported codes, and results files will move to the new location.

<!-- screenshot: Scanner sidebar showing Output Folder section -->

**Files saved in the output folder:**

| File | Contents |
|------|----------|
| `codes.txt` | Codes exported from the Scanner |
| `redeemer_results_YYYY-MM-DD.txt` | Results log from each Redeemer session |
| `scanner.log` | Detailed Scanner activity (rotating, 1 MB max) |
| `redeemer.log` | Detailed Redeemer activity (rotating, 1 MB max) |

> The app's internal configuration (API key, Discord settings) is always stored at `~/.dbfw_tools/config.json` regardless of your output folder setting.

---

### Troubleshooting

**"No new images found" when fetching from Discord**
- Confirm the bot has **Read Message History** permission on the channel — check the channel's Permission Overrides specifically (not just the server-level role)
- In the Discord Developer Portal, go to **Bot → Privileged Gateway Intents** and make sure **Message Content Intent** is enabled
- Verify the Channel ID in the app matches the channel where you sent the photos

**Redeemer can't find the game window**
- Make sure the game is open and visible on screen — not minimized or behind other windows
- Navigate to the **Serial Code** entry screen before clicking Proceed

**Codes show as INVALID when they should be ALREADY_USED (or vice versa)**
- This is a pixel detection threshold issue specific to your display settings
- Open your redeemer log and look for lines containing `detect_result: full_ratio=` — share those values with the developer so the threshold can be adjusted

**macOS: "DBFWTools can't be opened because it's from an unidentified developer"**
- Right-click the app → **Open** → **Open** — this bypasses Gatekeeper for the app permanently

**macOS: Redeemer isn't typing anything**
- Grant Accessibility permission: **System Settings → Privacy & Security → Accessibility → add DBFWTools**

---

## For Developers — Local Setup

### Prerequisites

- Python 3.11 or newer ([python.org/downloads](https://www.python.org/downloads/))
  - **Windows:** During install, check **"Add Python to PATH"**
  - **macOS:** Use the python.org installer (not Homebrew) — it includes tkinter
- Git

### Clone & Install

```bash
git clone https://github.com/ashkash13/dragon-ball-fusion-world.git
cd dragon-ball-fusion-world/dbfw_tools
```

**Windows:**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the App

```bash
# From the dbfw_tools/ directory with the venv active
python main.py
```

### Build a Distributable

The build scripts produce self-contained binaries — no Python required on the end user's machine.

**Windows → `dist\DBFWTools.exe`**

```bat
cd dbfw_tools
.venv\Scripts\activate
build_windows.bat
```

**macOS → `DBFWTools-Mac.dmg`**

```bash
cd dbfw_tools
source .venv/bin/activate
brew install create-dmg   # one-time, skip if already installed
bash build_mac.sh
```

**Automated releases via GitHub Actions**

Pushing a version tag triggers the CI workflow, which builds both platforms in parallel and publishes a GitHub Release automatically:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The release appears at `https://github.com/ashkash13/dragon-ball-fusion-world/releases` with both files attached.

### Project Structure

```
dbfw_tools/
├── main.py                  # Entry point — configures log dir, launches GUI
├── requirements.txt         # Runtime + build dependencies
├── build_windows.bat        # Windows build script (PyInstaller)
├── build_mac.sh             # macOS build script (PyInstaller + create-dmg)
└── src/
    ├── gui.py               # Main window — Scanner tab + Redeemer tab
    ├── logger.py            # Rotating file logger with runtime dir-switching
    ├── scanner/
    │   ├── config.py        # Persistent config (API key, Discord, output dir)
    │   ├── gemini_client.py # Google Gemini image → codes extraction
    │   └── discord_client.py# Discord channel image fetcher
    └── redeemer/
        ├── redeemer.py      # Automation loop — type, confirm, detect result
        ├── window.py        # Game window detection
        └── detector.py      # Screen pixel analysis for result detection
```

### Configuration Reference

The app's config is stored at `~/.dbfw_tools/config.json`:

```json
{
  "api_key": "your-gemini-api-key",
  "discord_bot_token": "...",
  "discord_channel_id": "...",
  "discord_last_message_id": "",
  "output_dir": "/Users/you/Documents/DBFWTools"
}
```

`output_dir` controls where `scanner.log`, `redeemer.log`, `codes.txt`, and results files are written. It can be changed at runtime via the Output Folder section in the Scanner tab sidebar — no restart required.
