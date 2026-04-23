#!/bin/bash
# ============================================================
#  Uninstall Dragon Ball Fusion World Tools — macOS
#
#  All user interaction is via AppleScript dialogs.
#  No terminal output is shown to the user.
#
#  What this removes:
#    - DBFWTools.app (moved to Trash — recoverable)
#    - ~/.dbfw_tools/ (Gemini API key, Discord settings, logs)
#      ONLY if the user explicitly chooses to delete it.
#
#  What this does NOT remove:
#    - Python (never installed by this app's DMG distribution)
#    - Homebrew or any other system tools
# ============================================================

TITLE="DBFWTools Uninstaller"
CONFIG_DIR="$HOME/.dbfw_tools"

# ── AppleScript helpers ───────────────────────────────────────────────────────

# Display a dialog and return the button label clicked.
# Usage: btn=$(ask "message" '"Btn1","Btn2"' "DefaultBtn")
ask() {
  osascript -e "button returned of (display dialog \"$1\" \
    buttons {$2} default button \"$3\" \
    with title \"$TITLE\")" 2>/dev/null
}

# Display an information dialog (OK only).
info() {
  osascript -e "display dialog \"$1\" \
    buttons {\"OK\"} default button \"OK\" \
    with title \"$TITLE\"" 2>/dev/null
}

# Move a path to the Trash via Finder (recoverable; returns 0 on success).
trash() {
  osascript -e "tell application \"Finder\" to delete POSIX file \"$1\"" \
    >/dev/null 2>&1
}

# ── Locate the app bundle ─────────────────────────────────────────────────────

find_app() {
  local candidates=(
    "/Applications/DBFWTools.app"
    "$HOME/Applications/DBFWTools.app"
    "$(dirname "$0")/DBFWTools.app"
  )
  for p in "${candidates[@]}"; do
    if [ -d "$p" ]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

APP_PATH=$(find_app)

if [ -z "$APP_PATH" ]; then
  # App not found in standard locations — ask user to locate it
  located=$(osascript -e "POSIX path of (choose file \
    with prompt \"DBFWTools.app was not found in /Applications or ~/Applications. Please locate it:\" \
    of type {\"com.apple.application-bundle\"} \
    with title \"$TITLE\")" 2>/dev/null)

  if [ -z "$located" ]; then
    info "Uninstall cancelled."
    exit 0
  fi
  APP_PATH="${located%/}"  # strip trailing slash if present
fi

# ── Check if app is currently running ─────────────────────────────────────────

if pgrep -f "DBFWTools" >/dev/null 2>&1 || pgrep -f "main.py" >/dev/null 2>&1; then
  info "Dragon Ball Fusion World Tools is currently running.\n\nPlease quit the app and then run this uninstaller again."
  exit 1
fi

# ── Build the summary of what will be removed ────────────────────────────────

APP_SIZE=""
if [ -d "$APP_PATH" ]; then
  APP_SIZE=$(du -sh "$APP_PATH" 2>/dev/null | cut -f1)
  APP_SIZE=" (~${APP_SIZE})"
fi

CFG_SECTION=""
if [ -d "$CONFIG_DIR" ]; then
  CFG_SIZE=$(du -sh "$CONFIG_DIR" 2>/dev/null | cut -f1)
  CFG_SECTION="\n\nConfiguration folder (~${CFG_SIZE}):\n  $CONFIG_DIR\n  (Gemini API key, Discord settings, log files)"
fi

SUMMARY="The following will be removed:\n\nApp bundle${APP_SIZE}:\n  $APP_PATH\n  (moved to Trash — recoverable)${CFG_SECTION}\n\nPython is NOT affected."

btn=$(ask "$SUMMARY" '"Cancel","Uninstall"' "Cancel")
if [ "$btn" != "Uninstall" ]; then
  info "Uninstall cancelled. Nothing was changed."
  exit 0
fi

# ── Ask about config folder separately (default = Keep) ──────────────────────

KEEP_CFG=true

if [ -d "$CONFIG_DIR" ]; then
  btn=$(ask "Your saved settings are stored at:\n  $CONFIG_DIR\n\nThis includes your Gemini API key and Discord settings.\n\nDelete these settings?\n  Keep = preserve your API key (useful if reinstalling)\n  Delete = remove everything" \
    '"Delete","Keep"' "Keep")
  if [ "$btn" = "Delete" ]; then
    KEEP_CFG=false
  fi
fi

# ── Final confirmation ────────────────────────────────────────────────────────

if $KEEP_CFG; then
  CONFIRM_MSG="Ready to uninstall.\n\nWill remove: $APP_PATH\nWill keep:   $CONFIG_DIR\n\nProceed?"
else
  CONFIRM_MSG="Ready to uninstall.\n\nWill remove: $APP_PATH\nWill also delete: $CONFIG_DIR\n\nProceed?"
fi

btn=$(ask "$CONFIRM_MSG" '"Cancel","Uninstall"' "Cancel")
if [ "$btn" != "Uninstall" ]; then
  info "Uninstall cancelled. Nothing was changed."
  exit 0
fi

# ── Remove app bundle (move to Trash) ─────────────────────────────────────────

APP_REMOVED=false
if [ -d "$APP_PATH" ]; then
  trash "$APP_PATH"
  if [ ! -d "$APP_PATH" ]; then
    APP_REMOVED=true
  fi
fi

# ── Remove config folder if user chose Delete ─────────────────────────────────

CFG_REMOVED=false
CFG_MSG=""

if [ -d "$CONFIG_DIR" ]; then
  if $KEEP_CFG; then
    CFG_MSG="\nConfiguration kept at:\n  $CONFIG_DIR"
  else
    rm -rf "$CONFIG_DIR"
    if [ ! -d "$CONFIG_DIR" ]; then
      CFG_REMOVED=true
      CFG_MSG="\nConfiguration deleted."
    else
      CFG_MSG="\nCould not delete $CONFIG_DIR\nYou can delete it manually."
    fi
  fi
fi

# ── Show completion summary ───────────────────────────────────────────────────

if $APP_REMOVED; then
  APP_MSG="App moved to Trash:\n  $APP_PATH"
else
  APP_MSG="App could not be moved to Trash.\nYou may need to drag it to the Trash manually:\n  $APP_PATH"
fi

info "Uninstall complete.\n\n${APP_MSG}${CFG_MSG}\n\nThank you for using Dragon Ball Fusion World Tools."
