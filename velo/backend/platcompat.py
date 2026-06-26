"""Cross-platform helpers.

Velo was born on Windows (WebView2 + a few Win32/.NET niceties). This module
centralises the OS branching needed to also run on Linux (X11/Wayland) and
macOS WITHOUT changing any Windows behaviour: on Windows every helper returns
exactly what the old hard-coded code did.

What lives here:
 * platform flags (IS_WINDOWS / IS_LINUX / IS_MAC)
 * session_type() — on Linux, X11 vs Wayland. This is what decides whether the
   "type the song into another app" feature can work at all: X11 lets us send
   synthetic keystrokes to other windows; Wayland deliberately blocks that, so
   the feature simply cannot work there (a real OS limitation, not a Velo bug).
 * data_dir() — where config.json + downloaded MIDIs live.
 * reveal() — open a file/folder in the OS file manager.

Nothing here imports a heavy or platform-locked dependency at module load, so it
is always safe to import.
"""

import os
import sys
import subprocess

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def session_type():
    """Return 'windows' | 'mac' | 'x11' | 'wayland' | 'unknown'.

    On Linux the QWERTY output engine can only inject keystrokes into other
    apps under X11. Under Wayland the compositor isolates apps from each other,
    so pynput cannot type into a game/website — we use this to warn the user
    (and tell them how to switch to an X11 session) instead of silently failing.
    """
    if IS_WINDOWS:
        return "windows"
    if IS_MAC:
        return "mac"
    xdg = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if xdg in ("wayland", "x11"):
        return xdg
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


# True only when we're confident we're on a Wayland session (the one place the
# "type into another app" feature can't work). Computed once at import.
IS_WAYLAND = session_type() == "wayland"


def can_synthesize_input():
    """True when sending synthetic keystrokes to OTHER apps is expected to work.
    Windows/macOS: yes. Linux: only under X11 (never under Wayland)."""
    if IS_WINDOWS or IS_MAC:
        return True
    return session_type() != "wayland"


def data_dir(app_name="Velo"):
    """Folder for Velo's config + downloaded MIDIs.

    Windows/macOS keep the historical ``~/Documents/<app>`` (so existing users
    are untouched). Linux uses the XDG convention (``$XDG_DATA_HOME`` or
    ``~/.local/share/<app>``) because a fresh Linux box may have no ~/Documents
    and apps are expected to store data under XDG, not in the home root.
    """
    if IS_LINUX:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, app_name)
    return os.path.join(os.path.expanduser("~"), "Documents", app_name)


def downloads_dir():
    """The user's Downloads folder (best-effort; falls back to home)."""
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    return d if os.path.isdir(os.path.dirname(d)) else os.path.expanduser("~")


def reveal(path):
    """Open a file (selected) or a folder in the OS file manager. Best-effort —
    never raises. Returns True if a launcher was spawned."""
    try:
        if not path:
            return False
        if IS_WINDOWS:
            if os.path.isfile(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(path)  # noqa: P204 — Windows only
        elif IS_MAC:
            subprocess.Popen(["open", "-R", path] if os.path.isfile(path)
                             else ["open", path])
        else:  # Linux / other unix
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["xdg-open", target])
        return True
    except Exception:
        return False
