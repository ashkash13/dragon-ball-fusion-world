# Dragon Ball Fusion World Tools

A desktop application that scans Dragon Ball Fusion World card redemption codes from photos and automatically enters them into the game — end to end, with no manual typing.

---

## Overview

**DBFW Tools** is a two-tab application:

| Tab | What it does |
|-----|-------------|
| **Scanner** | Extracts 16-character codes from card photos using Google Gemini AI. Supports file upload, drag & drop, and fetching images directly from a private Discord channel. |
| **Redeemer** | Takes the exported codes file and automatically types each code into the game, detects the result (Success / Already Used / Invalid), and logs everything. |

The Scanner exports directly to the Redeemer — after scanning your cards, one click loads them into the Redeemer tab ready to go.

---

## Requirements

- Windows or macOS
- Python 3.11+
- A free [Google Gemini API key](https://aistudio.google.com) (for the Scanner)
- Dragon Ball Fusion World installed and running (for the Redeemer)
- *(Optional)* A Discord bot and private channel (for the Discord fetch feature)

---

## Installation

```bash
# Clone the repo
git clone https://github.com/your-username/dragon-ball-fusion-world.git
cd dragon-ball-fusion-world/dbfw_tools

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the App

```bash
# From the dbfw_tools/ directory, with the venv active
python main.py
```

---

## Setup

### Gemini API Key

The Scanner uses Google Gemini to read codes from card photos. A free API key gives you 250 scans per day (125 if AI proofreading is enabled, since verification uses a second pass).

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with a Google account
2. Click **Get API Key** → **Create API key**
3. Copy the key
4. On first launch, the Scanner tab will prompt you to paste it — click **Save & Continue**

To change the key later, click **Change API Key** in the sidebar.

---

### Discord Channel *(optional)*

Instead of transferring card photos to your computer manually, you can send them to a private Discord channel from your phone and fetch them directly in the app.

#### 1. Create a Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name → **Create**
3. Go to **Bot** in the left sidebar
4. Click **Reset Token** → confirm → copy the token (you'll need this later)
5. Under **Privileged Gateway Intents**, enable **Message Content Intent** → **Save Changes**
6. Go to **Installation** → set **Install Link** to **None** → **Save Changes**

#### 2. Invite the bot to your server

Open this URL in your browser, replacing `YOUR_APP_ID` with your **Application ID** (found on the General Information page):

```
https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&permissions=76800&scope=bot
```

Select your server → **Authorize**.

The permissions value `76800` grants:
- View Channel
- Read Message History
- Manage Messages *(used to delete messages after scanning)*

#### 3. Grant access to your private channel

1. In Discord, right-click the channel → **Edit Channel** → **Permissions**
2. Click **+** next to Members → search for your bot → select it
3. Set these to green (Allow): **View Channel**, **Read Message History**, **Manage Messages**
4. **Save Changes**

#### 4. Get the Channel ID

1. In Discord, go to **Settings → Advanced** → enable **Developer Mode**
2. Right-click the target channel → **Copy Channel ID**

#### 5. Configure in the app

1. In the Scanner tab, find the **Discord Channel** section
2. Click **Set up Discord →**
3. Paste your bot token and channel ID
4. Click **Validate & Save** — the app confirms the bot can reach the channel

Once configured, send card photos to the channel from your phone and click **Fetch from Discord** to scan them automatically. Each message is deleted after a successful scan so it won't be processed again.

---

## Using the Scanner

1. **Add images** — click **Browse Images**, drag and drop files onto the window, or click **Fetch from Discord** to pull from your Discord channel
2. **Scan** — click **Scan All Images**. Each image is scanned by Gemini, then verified with a second AI pass to catch misread characters
3. **Review codes** — extracted codes appear in the **Collected Codes** sidebar. Use Ctrl+Click / Shift+Click to select multiple codes for removal
4. **Export** — click **Export codes.txt**. The app automatically switches to the Redeemer tab with the file pre-loaded

**Tips:**
- Multiple cards per photo are supported
- Keep the cards centered in the frame — avoid unnecessary background (keyboards, etc.) as it adds visual noise
- Supported formats: JPG, PNG, WEBP, BMP, TIFF

---

## Using the Redeemer

> The game must be open on the **Serial Code** entry screen before proceeding.

1. The codes file is pre-filled if you came from the Scanner export. Otherwise click **Browse…** to load a `codes.txt` file manually
2. Click **Proceed →** — the app locates the game window automatically
3. A **5-second countdown** gives you time to switch to the game and click inside the first code input box
4. The Redeemer types each code, clicks Confirm, reads the result dialog, and moves to the next code
5. When finished, a summary shows Success / Already Used / Invalid counts, and a results file is saved next to the codes file

**Safety features:**
- Move the mouse to the **top-left corner** of the screen at any time to immediately stop automation (PyAutoGUI failsafe)
- Click **Stop** in the app to finish the current code and halt
- Stops automatically after 3 consecutive INVALID results (indicates a bad codes file or expired codes)
- Warns when approaching the game's 10-error lockout limit

---

## Building a Standalone Executable

To produce a single distributable binary that doesn't require Python:

**Windows:**
```bat
cd dbfw_tools
build_windows.bat
```
Output: `dbfw_tools/dist/DBFWTools.exe`

**macOS:**
```bash
cd dbfw_tools
bash build_mac.sh
```
Output: `dbfw_tools/dist/DBFWTools`

On macOS, grant Accessibility permission on first launch: **System Settings → Privacy & Security → Accessibility → add the app**.

---

## Configuration Files

The app stores its configuration in your home directory:

```
~/.dbfw_tools/
├── config.json      # API key and Discord settings
├── scanner.log      # Scanner activity log (rotating, 1 MB max)
└── redeemer.log     # Redeemer activity log (rotating, 1 MB max)
```

---

## Troubleshooting

**Scanner says "No new images found" from Discord**
- Confirm the bot has **Read Message History** permission on the channel (check the channel's Permission Overrides, not just the server role)
- Ensure **Message Content Intent** is enabled in the Discord Developer Portal under Bot → Privileged Gateway Intents
- Verify the Channel ID matches the channel where you sent the photos

**Redeemer can't find the game window**
- Make sure Dragon Ball Fusion World is open and visible (not minimized)
- Navigate to the **Serial Code** entry screen before clicking Proceed

**Codes are being marked INVALID when they should be ALREADY_USED (or vice versa)**
- This is a screen detection threshold issue. Check the redeemer log for lines containing `detect_result: full_ratio=` and share them — the threshold can be adjusted in `src/redeemer/detector.py` (`ALREADY_USED_PIXEL_RATIO_THRESHOLD`)
