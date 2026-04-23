"""
Cross-platform game window finder for DBSCGFW.

Returns the window's bounding rect so all click targets can be computed
as proportional offsets — works regardless of monitor resolution or
whether the game is windowed or fullscreen.
"""
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

GAME_TITLE = "DBSCGFW"


@dataclass
class WindowRect:
    x: int
    y: int
    width: int
    height: int

    def abs_pos(self, rel_x: float, rel_y: float) -> tuple[int, int]:
        """Convert a (rel_x, rel_y) fraction to absolute screen coordinates."""
        return (
            self.x + int(self.width * rel_x),
            self.y + int(self.height * rel_y),
        )

    def abs_region(
        self, rel_x: float, rel_y: float, rel_w: float, rel_h: float
    ) -> tuple[int, int, int, int]:
        """Convert a relative region to an absolute (x, y, w, h) screen region."""
        return (
            self.x + int(self.width * rel_x),
            self.y + int(self.height * rel_y),
            int(self.width * rel_w),
            int(self.height * rel_h),
        )

    def __str__(self) -> str:
        return f"WindowRect(x={self.x}, y={self.y}, w={self.width}, h={self.height})"


def find_game_window() -> Optional[WindowRect]:
    """
    Locate the DBSCGFW game window and return its bounding rect.
    Returns None if the window cannot be found.
    """
    system = platform.system()
    if system == "Windows":
        return _find_window_windows()
    elif system == "Darwin":
        return _find_window_macos()
    return None


def _find_window_windows() -> Optional[WindowRect]:
    try:
        import pygetwindow as gw  # type: ignore

        wins = gw.getWindowsWithTitle(GAME_TITLE)
        if not wins:
            return None
        w = wins[0]
        return WindowRect(w.left, w.top, w.width, w.height)
    except Exception:
        return None


def _find_window_macos() -> Optional[WindowRect]:
    """
    Use AppleScript to find the game window position and size.
    Requires Accessibility permission to be granted to the terminal / app.
    """
    script = f"""
tell application "System Events"
    repeat with proc in every process
        if name of proc contains "{GAME_TITLE}" then
            if (count of windows of proc) > 0 then
                set win to first window of proc
                set pos to position of win
                set sz to size of win
                return ((item 1 of pos) as string) & "," & \\
                       ((item 2 of pos) as string) & "," & \\
                       ((item 1 of sz) as string) & "," & \\
                       ((item 2 of sz) as string)
            end if
        end if
    end repeat
end tell
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) == 4:
                x, y, w, h = (int(p.strip()) for p in parts)
                return WindowRect(x, y, w, h)
    except Exception:
        pass
    return None
