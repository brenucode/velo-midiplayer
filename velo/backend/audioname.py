"""Make the Windows volume mixer show "Velo" + the app icon.

Velo's audio is the Web Audio API running *inside* the WebView2 child
processes (``msedgewebview2.exe``), so by default the Windows volume mixer
labels the session with that process's name and the Edge icon. There is no way
to rename it from the HTML/JS side.

The fix is the documented Core Audio per-session override: from our own
process we walk our process tree, find the audio sessions whose owning PID is
one of our WebView2 children, and set their ``DisplayName`` + ``IconPath``
(``IAudioSessionControl::SetDisplayName`` / ``SetIconPath``). No registry
writes, no AppUserModelID hacks on the children — just the session API.

A session only exists once audio actually plays and is recreated when playback
stops/starts, so a lightweight daemon thread re-applies the branding every few
seconds. All COM work stays on that one thread.
"""

import os
import threading
import time
import logging

logger = logging.getLogger("velo.audioname")

# session states for which a name is even visible in the mixer
_DONE = False  # set True once we've branded at least one live session


def setAppId(appId="brenu.Velo.MidiPlayer"):
    """Give our own process an explicit AppUserModelID (taskbar grouping +
    a few Win11 surfaces). Cheap, best-effort, no-op off Windows."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appId)
    except Exception:
        pass


def _ourPids():
    """Our PID plus every transitive child (the WebView2 helpers)."""
    import psutil
    me = psutil.Process(os.getpid())
    pids = {me.pid}
    try:
        for child in me.children(recursive=True):
            pids.add(child.pid)
    except Exception:
        pass
    return pids


def _apply(name, icon, pids):
    """Brand every audio session owned by one of our PIDs. Returns how many
    sessions we touched (so the poller can quiet down once it's working)."""
    from pycaw.pycaw import AudioUtilities

    touched = 0
    for session in AudioUtilities.GetAllSessions():
        try:
            if session.ProcessId not in pids:
                continue
            if session.DisplayName != name:
                session.DisplayName = name
            if icon and session.IconPath != icon:
                session.IconPath = icon
            touched += 1
        except Exception:
            # a session can vanish mid-iteration; just skip it
            continue
    return touched


def brand(name="Velo", icon=None, interval=2.0):
    """Start the background brander. Safe to call once at startup; returns
    immediately. Silently does nothing if pycaw/COM isn't available."""

    def worker():
        global _DONE
        # confirm the stack is importable before looping
        try:
            import pycaw.pycaw  # noqa: F401
            import comtypes      # noqa: F401
        except Exception as exc:
            logger.info("audio session branding unavailable: %s", exc)
            return

        # comtypes initialises COM lazily on first use, per-thread; keeping all
        # calls on this single daemon thread keeps that contained.
        misses = 0
        while True:
            try:
                n = _apply(name, icon, _ourPids())
                if n:
                    _DONE = True
                    misses = 0
                else:
                    misses += 1
            except Exception:
                misses += 1
            # poll briskly until it sticks, then relax to keep re-stamping
            # sessions that get recreated when playback restarts
            time.sleep(interval if not _DONE else max(interval, 4.0))

    t = threading.Thread(target=worker, name="velo-audioname", daemon=True)
    t.start()
    return t
