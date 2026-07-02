"""Velo — entry point.

Velo — a clean MIDI player with a practice studio and stage mode.
Copyright (C) 2026 brenu  <https://github.com/brenucode>

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License v3 as published by the Free Software
Foundation. Built upon nanoMIDIPlayer (NotHammer043), also licensed under GPLv3.
See the LICENSE file for details.

Launches a frameless WebView2 window that renders the HTML/CSS/JS UI and bridges
to the Python MIDI engine through a js_api object. No Tkinter, no remote servers.

IMPORTANT: the js_api object (Api) must NOT hold references to the pywebview
window or the managers as attributes. pywebview introspects the api object, and
walking into ``window.native`` (the .NET/WebView2 objects) triggers infinite
recursion + cross-thread access that freezes the packaged app. So the window and
managers live in module globals and the Api methods reach them from there.
"""

import os
import sys
import json
import time
import base64
import ctypes
import logging
import threading
import socket

# Keep WebView2 timers/rendering alive even when a window is hidden or occluded.
# This lets the Online Sequencer helper window clear its Cloudflare check while
# staying completely invisible (a throttled hidden window never solves it), and
# keeps the main window's playback loops smooth while running in the background.
# Must be set before any WebView2 starts. WebView2 is Windows-only; on Linux
# (WebKitGTK) / macOS the flag is irrelevant, so only set it there.
if os.name == "nt":
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--disable-background-timer-throttling "
        "--disable-backgrounding-occluded-windows "
        "--disable-renderer-backgrounding",
    )
elif sys.platform.startswith("linux"):
    # WebKitGTK can stop repainting and the page goes blank ("the UI vanishes")
    # on several GPU/driver combos — notably with the newer DMABUF renderer on
    # recent distros (Fedora). Disabling the DMABUF renderer and accelerated
    # compositing keeps the page reliably painted. Must be set before WebKitGTK
    # starts (i.e. before `import webview`).
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

import webview

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from velo.backend import config as configuration
from velo.backend import platcompat
from velo.backend import hub
from velo.backend import onlineseq
from velo.backend import audioname
from velo.backend.player import Player
from velo.backend.drums import DrumsPlayer
from velo.backend.qwerty_input import InputController


def resourcePath(relativePath):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relativePath)


def _unblockSelf():
    """Strip Windows' "mark of the web" from our own bundled files.

    Files extracted from a downloaded .zip inherit a ``Zone.Identifier``
    stream; the .NET Framework then refuses to load our pythonnet assemblies
    (``Python.Runtime.dll``) — which is what drives the WebView2 window — and
    the app dies at launch with "Failed to resolve Python.Runtime.Loader…".
    Deleting that stream at startup, *before* pywebview imports clr, lets a
    freshly downloaded copy run without the user having to right-click the zip
    and choose "Unblock". We sweep the whole bundle (not just pythonnet) so the
    WebView2 .NET assemblies are cleared too. No sentinel on disk — a stray one
    could ship inside the zip and silently disable the fix; the sweep is a few
    milliseconds, so we just run it every launch."""
    base = getattr(sys, "_MEIPASS", None)
    if not base or os.name != "nt":
        return
    try:
        import ctypes
        deleteFile = ctypes.windll.kernel32.DeleteFileW
        for root, _dirs, files in os.walk(base):
            for name in files:
                try:
                    deleteFile(os.path.join(root, name) + ":Zone.Identifier")
                except Exception:
                    pass
    except Exception:
        pass


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("velo")


# ---- module-level state (kept OUT of the js_api object on purpose) ----------
WINDOW = None
OVERLAY = None            # the floating mini-player window (2nd window)
OVERLAY_READY = False     # True once its DOM has loaded (safe to evaluate_js)
OVERLAY_VISIBLE = False   # True while it's shown on screen
OVERLAY_GEOM = {}         # last known {x,y} of the overlay (persisted on close)
_OVERLAY_WNDPROC = None    # keep the WM_MOUSEACTIVATE hook callback alive (GC guard)
_OVERLAY_OLDPROC = None    # original child WNDPROC (to chain via CallWindowProc)
PLAYER = None
DRUMS = None
INPUT = None
GEOM = {}
# Once teardown begins, no more evaluate_js calls may touch the window. The
# background buses (NoteBus ~12ms, LogBus ~80ms) and stop() all funnel through
# emit(); calling into a WebView2 that's mid-destroy is a hard native crash
# (access violation) that Python try/except can't catch. This gate stops that.
SHUTTING_DOWN = False
FULLSCREEN = False


def _validGeom(g):
    """Reject window geometry we should never persist: minimized windows report
    (-32000,-32000); fullscreen/garbage report off-screen or tiny sizes. Saving
    those makes the app reopen invisible."""
    try:
        x, y, w, h = g.get("x", 0), g.get("y", 0), g.get("w", 0), g.get("h", 0)
    except Exception:
        return False
    if w < 400 or h < 300 or w > 8000 or h > 8000:
        return False
    # -32000 is the minimize sentinel; allow modest negatives for multi-monitor
    if x <= -10000 or y <= -10000 or x > 15000 or y > 15000:
        return False
    return True


def _onScreen(x, y, w, h):
    """True only if the rect overlaps a CURRENTLY CONNECTED monitor. Catches a
    geometry saved on a monitor that's no longer plugged in / a phantom one —
    which is exactly what makes the window reopen invisible off-screen."""
    try:
        import ctypes

        class _R(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        r = _R(int(x), int(y), int(x) + int(w), int(y) + int(h))
        # MONITOR_DEFAULTTONULL = 0 → returns NULL if the rect hits no monitor
        return bool(ctypes.windll.user32.MonitorFromRect(ctypes.byref(r), 0))
    except Exception:
        return True  # if the check fails, don't block (fail open)


def emit(event, payload):
    if SHUTTING_DOWN:
        return
    code = ("window.veloEvent && window.veloEvent(%s, %s)"
            % (json.dumps(event), json.dumps(payload)))
    # main window
    if WINDOW is not None:
        try:
            WINDOW.evaluate_js(code)
        except Exception:
            pass
    # floating mini-player (only when it's loaded AND currently shown, so we
    # never evaluate_js into a mid-navigation / hidden overlay → native crash)
    if OVERLAY is not None and OVERLAY_READY and OVERLAY_VISIBLE:
        try:
            OVERLAY.evaluate_js(code)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Floating mini-player (overlay) — native window plumbing.
#
# Everything that pokes the native window runs on the WinForms UI thread via
# BeginInvoke (same pattern as Api.setOnTop / Api.startResize). We deliberately
# bypass pywebview's own show()/hide()/move()/resize() for the overlay: those
# activate the window (Show()+Activate()+webview.Focus()), which would yank the
# user out of their game. We drive Win32 directly with SWP_NOACTIVATE, so the
# pill can be shown/moved/resized/clicked while the game keeps input focus.
# ---------------------------------------------------------------------------
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_LAYERED = 0x00080000
_LWA_ALPHA = 0x02
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SW_HIDE = 0
_SW_SHOWNOACTIVATE = 4


def _overlayHwnd():
    try:
        return int(OVERLAY.native.Handle.ToInt64())
    except Exception:
        return None


def _overlayScale(hwnd):
    """Physical-per-CSS pixel ratio for this window (DPI aware)."""
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        if dpi:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def _overlayInvoke(fn):
    """Run fn() on the WinForms UI thread — native window ops must live there."""
    try:
        from System import Action
        OVERLAY.native.BeginInvoke(Action(fn))
        return
    except Exception:
        try:
            fn()
        except Exception:
            pass


def _overlayPinTopmost(hwnd):
    try:
        ctypes.windll.user32.SetWindowPos(
            hwnd, _HWND_TOPMOST, 0, 0, 0, 0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE)
    except Exception:
        pass


def _overlayApplyStyles():
    """UI thread: keep it off the taskbar/alt-tab (TOOLWINDOW), non-activating
    (NOACTIVATE — pywebview already set it via focus=False, we re-assert), and
    pinned above everything (incl. borderless Roblox)."""
    hwnd = _overlayHwnd()
    if not hwnd:
        return
    try:
        u = ctypes.windll.user32
        ex = u.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE | _WS_EX_LAYERED)
    except Exception:
        pass
    _overlayPinTopmost(hwnd)


def _overlayRound(hwnd):
    """Clip the (opaque) window to a rounded rect so it reads as a floating pill.
    Region is in window pixels, so it must be re-applied whenever the size
    changes. The window takes ownership of the region handle."""
    try:
        u = ctypes.windll.user32
        g = ctypes.windll.gdi32

        class _R(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        rc = _R()
        u.GetWindowRect(hwnd, ctypes.byref(rc))
        w, h = rc.r - rc.l, rc.b - rc.t
        if w <= 0 or h <= 0:
            return
        rad = int(round(19 * _overlayScale(hwnd)))
        rgn = g.CreateRoundRectRgn(0, 0, w + 1, h + 1, rad * 2, rad * 2)
        u.SetWindowRgn(hwnd, rgn, True)
    except Exception:
        pass


def _overlaySetAlpha(hwnd, a):
    try:
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, int(max(0, min(255, a))), _LWA_ALPHA)
    except Exception:
        pass


def _overlayShow(show):
    """UI thread: show without activating (keeps game focus) / hide. Also
    re-asserts topmost + rounded corners on show. On show it starts fully
    transparent (alpha 0) so the fade-in can raise it — nothing pops in."""
    global OVERLAY_VISIBLE
    hwnd = _overlayHwnd()
    if not hwnd:
        return
    if show:
        _overlayApplyStyles()            # adds WS_EX_LAYERED (needed for alpha)
        _overlaySetAlpha(hwnd, 0)        # invisible first; fade-in ramps it up
        try:
            ctypes.windll.user32.ShowWindow(hwnd, _SW_SHOWNOACTIVATE)
        except Exception:
            pass
        _overlayRound(hwnd)
        OVERLAY_VISIBLE = True
    else:
        try:
            ctypes.windll.user32.ShowWindow(hwnd, _SW_HIDE)
        except Exception:
            pass
        OVERLAY_VISIBLE = False


def _overlayAnim(fade_in):
    """Fade the WHOLE window (background + content) via layered-window alpha, so
    it never pops. On fade-out, hide the native window once fully faded."""
    hwnd = _overlayHwnd()
    if not hwnd:
        return
    steps, dur = 14, 0.17
    for i in range(steps + 1):
        frac = i / steps
        _overlaySetAlpha(hwnd, 255 * (frac if fade_in else (1 - frac)))
        time.sleep(dur / steps)
    if not fade_in:
        _overlayInvoke(lambda: _overlayShow(False))


def _overlayMoveTo(x_css, y_css):
    """UI thread: move top-left to a CSS-pixel screen coord (converted to
    physical), without activating."""
    hwnd = _overlayHwnd()
    if not hwnd:
        return
    s = _overlayScale(hwnd)
    try:
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, int(round(x_css * s)), int(round(y_css * s)), 0, 0,
            _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE)
    except Exception:
        pass


def _overlayResize(w_css, h_css):
    """UI thread: resize (CSS px → physical) without moving or activating."""
    hwnd = _overlayHwnd()
    if not hwnd:
        return
    s = _overlayScale(hwnd)
    try:
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, int(round(w_css * s)), int(round(h_css * s)),
            _SWP_NOMOVE | _SWP_NOZORDER | _SWP_NOACTIVATE)
        _overlayRound(hwnd)          # re-clip: region depends on the new size
    except Exception:
        pass


def _pickMidi():
    try:
        result = WINDOW.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("MIDI files (*.mid;*.midi)", "All files (*.*)"),
        )
    except Exception as e:
        logger.warning(f"file dialog error: {e}")
        return None
    if result:
        return result[0] if isinstance(result, (list, tuple)) else result
    return None


def _stopExcept(keep):
    try:
        if keep != "player" and PLAYER and PLAYER.isRunning:
            PLAYER.stop()
        if keep != "drums" and DRUMS and DRUMS.isRunning:
            DRUMS.stop()
        if keep != "input" and INPUT and INPUT.running:
            INPUT.stop()
    except Exception:
        pass


class Api:
    """Thin bridge — only methods, no window/manager attributes."""

    # ----- player -----------------------------------------------------------
    def getState(self):
        return PLAYER.getState()

    def chooseFile(self):
        path = _pickMidi()
        return PLAYER.setFile(path) if path else PLAYER.getState()

    def setFile(self, path):
        return PLAYER.setFile(path)

    def play(self):
        _stopExcept("player")
        return PLAYER.play()

    def pause(self):
        return PLAYER.pause()

    def stop(self):
        return PLAYER.stop()

    def toggle(self):
        if not PLAYER.isRunning:
            _stopExcept("player")
        return PLAYER.toggle()

    def setSpeed(self, value):
        return PLAYER.setSpeed(value)

    def changeSpeed(self, delta):
        return PLAYER.changeSpeed(delta)

    def nextTrack(self):
        _stopExcept("player")
        return PLAYER.nextTrack()

    def prevTrack(self):
        _stopExcept("player")
        return PLAYER.prevTrack()

    def playPath(self, path):
        _stopExcept("player")
        return PLAYER.playPath(path)

    def seek(self, seconds):
        return PLAYER.seek(seconds)

    def removeFromQueue(self, path):
        return PLAYER.removeFile(path)

    def reorderQueue(self, paths):
        return PLAYER.reorderQueue(paths)

    def clearQueue(self):
        return PLAYER.clearQueue()

    def queueAdd(self):
        path = _pickMidi()
        return PLAYER.addToQueue(path) if path else PLAYER.getState()

    def setOption(self, key, value):
        return PLAYER.setOption(key, value)

    def setShortNotes(self, patch):
        return PLAYER.setShortNotes(patch)

    def setArrangeMode(self, mode):
        return PLAYER.setArrangeMode(mode)

    def cyclePlayStyle(self):
        return PLAYER.cycleArrangeMode()

    # ----- floating mini-player (overlay) -----------------------------------
    def overlaySetEnabled(self, value):
        value = bool(value)
        configuration.configData.setdefault("overlay", {})["enabled"] = value
        configuration.save()

        # NOTE: evaluate_js MUST run off the WinForms UI thread (on it → WebView2
        # deadlock / "not responding"). So native show/hide goes through
        # _overlayInvoke (UI thread), and the fade + state push run on a Timer.
        if value:
            _overlayInvoke(lambda: _overlayShow(True))    # native show at alpha 0
            threading.Timer(0.04, lambda: threading.Thread(
                target=lambda: _overlayAnim(True), daemon=True).start()).start()  # fade in
            def _push():
                try:
                    if PLAYER:
                        PLAYER._emitState()
                        PLAYER.pushTimeline()
                except Exception:
                    pass
            threading.Timer(0.06, _push).start()
        else:
            threading.Thread(target=lambda: _overlayAnim(False), daemon=True).start()  # fade out, then hide
        if PLAYER:
            PLAYER._emitState()                  # reflect the toggle in the main window
            return PLAYER.getState()
        return {}

    def overlayClose(self):
        """The pill's ✕ — hide it and flip the Settings toggle off. NEVER closes
        the window (closing any window calls Application.Exit → kills the app)."""
        return self.overlaySetEnabled(False)

    def overlaySetScale(self, value):
        try:
            s = max(0.7, min(1.6, float(value)))
        except (TypeError, ValueError):
            return PLAYER.getState() if PLAYER else {}
        configuration.configData.setdefault("overlay", {})["scale"] = round(s, 3)
        configuration.save()
        if PLAYER:
            PLAYER._emitState()                  # overlay.js re-syncs its size from scale
            return PLAYER.getState()
        return {}

    def overlayMoveTo(self, x, y):
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            return
        _overlayInvoke(lambda: _overlayMoveTo(x, y))

    def overlayResize(self, w, h):
        try:
            w, h = int(float(w)), int(float(h))
        except (TypeError, ValueError):
            return
        _overlayInvoke(lambda: _overlayResize(w, h))

    def setSound(self, key, value):
        return PLAYER.setSound(key, value)

    def setHumanize(self, key, value):
        return PLAYER.setHumanize(key, value)

    def setRandomFail(self, key, value):
        return PLAYER.setRandomFail(key, value)

    # ----- self-update (check + assisted download, never silent overwrite) --
    def checkUpdate(self):
        from velo.backend import update
        return update.checkLatest()

    def openRelease(self, url):
        from velo.backend import update
        return {"ok": update.openReleasePage(url)}

    def downloadUpdate(self, assetUrl, tag=""):
        from velo.backend import update
        return update.downloadZip(assetUrl, tag)

    def setOutputDevice(self, name):
        return PLAYER.setOutputDevice(name)

    def refreshDevices(self):
        return PLAYER.getState()

    # ----- MIDI Hub ---------------------------------------------------------
    def hubList(self):
        try:
            return {"ok": True, "items": hub.listMidis()}
        except Exception as e:
            logger.warning(f"hubList error: {e}")
            return {"ok": False, "error": type(e).__name__}

    def hubDownload(self, midiFilename):
        try:
            path = hub.downloadMidi(midiFilename)
            return {"ok": True, "state": PLAYER.setFile(path)}
        except Exception as e:
            logger.warning(f"hubDownload error: {e}")
            return {"ok": False, "error": str(e)}

    def hubSearchBit(self, query, page=0):
        try:
            res = hub.bitmidiSearch(query, page)
            return {"ok": True, "items": res["items"], "total": res["total"],
                    "page": res["page"], "pageSize": res["pageSize"]}
        except Exception as e:
            logger.warning(f"hubSearchBit error: {e}")
            return {"ok": False, "error": type(e).__name__}

    def hubDownloadBit(self, downloadUrl, name=None):
        try:
            path = hub.bitmidiDownload(downloadUrl, name)
            return {"ok": True, "state": PLAYER.setFile(path)}
        except Exception as e:
            logger.warning(f"hubDownloadBit error: {e}")
            return {"ok": False, "error": str(e)}

    # ----- Online Sequencer (cleared via the embedded browser) -------------
    def osSearch(self, query):
        return onlineseq.search(query)

    def osDownload(self, seqId, name=None):
        try:
            res = onlineseq.download(seqId, name)
            if not res.get("ok"):
                return res
            return {"ok": True, "state": PLAYER.setFile(res["path"])}
        except Exception as e:
            logger.warning(f"osDownload error: {e}")
            return {"ok": False, "error": str(e)}

    # ----- practice (training mode) ----------------------------------------
    def practiceLoad(self, path):
        try:
            from velo.backend import practice
            if not path or not os.path.exists(path):
                return {"ok": False, "error": "missing"}
            steps = practice.buildSteps(path)
            if not steps:
                return {"ok": False, "error": "empty"}
            notes = [n["note"] for st in steps for n in st["notes"]]
            key = os.path.basename(path)
            return {"ok": True, "name": key, "path": path,
                    "steps": steps, "minNote": min(notes), "maxNote": max(notes),
                    "total": len(steps), "duration": practice.songDuration(path),
                    "keymap": practice.fullMap(),
                    "records": configuration.configData.get("practice", {}).get(key, {})}
        except Exception as e:
            logger.warning(f"practiceLoad error: {e}")
            return {"ok": False, "error": str(e)}

    def practiceChoose(self):
        path = _pickMidi()
        if not path:
            return {"ok": False, "error": "cancel"}
        return self.practiceLoad(path)

    def practiceSaveResult(self, key, mode, score, accuracy, maxCombo, seconds):
        """Persist a run and return the (possibly new) personal-best record for the
        song+mode. Records live in config under "practice"[songName][mode]."""
        try:
            store = configuration.configData.setdefault("practice", {})
            song = store.setdefault(str(key), {})
            prev = song.get(mode, {})
            isPB = (score or 0) > prev.get("score", -1) or (accuracy or 0) > prev.get("accuracy", -1)
            best = {
                "score": max(int(score or 0), prev.get("score", 0)),
                "accuracy": max(int(accuracy or 0), prev.get("accuracy", 0)),
                "maxCombo": max(int(maxCombo or 0), prev.get("maxCombo", 0)),
                "seconds": int(seconds or 0),
                "plays": prev.get("plays", 0) + 1,
            }
            song[mode] = best
            configuration.save()
            return {"ok": True, "record": best, "isPB": bool(isPB)}
        except Exception as e:
            logger.warning(f"practiceSaveResult error: {e}")
            return {"ok": False}

    def practiceRecords(self):
        return configuration.configData.get("practice", {})

    def practiceKeymap(self):
        from velo.backend import practice
        return practice.fullMap()

    def practiceActive(self, active):
        # Practice no longer suspends the global hotkeys: the user wants the
        # Player's play hotkey to work from the Practice tab too (it drives the
        # Player's own selected song via the real engine). Keep hotkeys bound.
        try:
            PLAYER.bindHotkeys()
        except Exception:
            pass
        return True

    # ----- practice MIDI input (passive — reads a keyboard, presses nothing) -
    def practiceMidiDevices(self):
        from velo.backend import practice_input
        return practice_input.list_devices()

    def practiceMidiStart(self, device):
        from velo.backend import practice_input
        # free the MIDI device from the "MIDI -> Keys" engine if it's holding it
        try:
            if INPUT is not None and INPUT.running:
                INPUT.stop()
        except Exception:
            pass
        ok = practice_input.start(device or "", emit)
        return {"ok": bool(ok), "device": device or "",
                "devices": practice_input.list_devices()}

    def practiceMidiStop(self):
        from velo.backend import practice_input
        practice_input.stop()
        return {"ok": True}

    # ----- app state / drag-drop -------------------------------------------
    def setLastView(self, name):
        configuration.configData.setdefault("appUI", {})["lastView"] = str(name)
        configuration.save()
        return True

    def getSkin(self):
        return configuration.configData.get("appUI", {}).get("skin", "lime")

    def setSkin(self, name):
        configuration.configData.setdefault("appUI", {})["skin"] = str(name)
        configuration.save()
        return True

    def loadMidiBytes(self, name, dataUrl, target="player"):
        try:
            data = base64.b64decode(dataUrl.split(",", 1)[-1])
            safe = os.path.basename(name) or "dropped.mid"
            folder = os.path.join(configuration.baseDirectory, "Midis")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, safe)
            with open(path, "wb") as f:
                f.write(data)
            if target == "drums":
                return {"ok": True, "target": "drums", "state": DRUMS.setFile(path)}
            return {"ok": True, "target": "player", "state": PLAYER.setFile(path)}
        except Exception as e:
            logger.warning(f"loadMidiBytes error: {e}")
            return {"ok": False, "error": str(e)}

    # ----- drums ------------------------------------------------------------
    def drumsState(self):
        return DRUMS.getState()

    def drumsChoose(self):
        path = _pickMidi()
        return DRUMS.setFile(path) if path else DRUMS.getState()

    def drumsSetFile(self, path):
        return DRUMS.setFile(path)

    def drumsToggle(self):
        if not DRUMS.isRunning:
            _stopExcept("drums")
        return DRUMS.toggle()

    def drumsStop(self):
        return DRUMS.stop()

    def drumsSetSpeed(self, value):
        return DRUMS.setSpeed(value)

    def drumsChangeSpeed(self, delta):
        return DRUMS.changeSpeed(delta)

    def drumsSetOption(self, key, value):
        return DRUMS.setOption(key, value)

    # ----- MIDI -> QWERTY (live input) --------------------------------------
    def inputState(self):
        return INPUT.getState()

    def inputToggle(self):
        if not INPUT.running:
            _stopExcept("input")
        return INPUT.toggle()

    def inputStop(self):
        return INPUT.stop()

    def inputSetDevice(self, name):
        return INPUT.setDevice(name)

    def inputSetOption(self, key, value):
        return INPUT.setOption(key, value)

    # ----- hotkeys ----------------------------------------------------------
    def setHotkey(self, action, key):
        hk = configuration.configData.setdefault("hotkeys", {})
        hk[action] = str(key).lower()
        configuration.save()
        PLAYER.bindHotkeys()
        return PLAYER.getState()

    def setOnTop(self, value):
        value = bool(value)
        configuration.configData.setdefault("appUI", {})["onTop"] = value
        configuration.save()
        try:
            native = WINDOW.native
            from System import Action  # pythonnet
            native.BeginInvoke(Action(lambda: setattr(native, "TopMost", value)))
        except Exception:
            try:
                WINDOW.on_top = value
            except Exception:
                pass
        return value

    # ----- platform ---------------------------------------------------------
    def platformInfo(self):
        """Tell the UI what OS/session we're on so it can warn (e.g. on Wayland
        the 'type into another app' feature can't work — see platcompat)."""
        return {
            "os": ("windows" if platcompat.IS_WINDOWS
                   else "mac" if platcompat.IS_MAC else "linux"),
            "session": platcompat.session_type(),
            "isWayland": platcompat.IS_WAYLAND,
            "canType": platcompat.can_synthesize_input(),
        }

    # ----- window controls (frameless) -------------------------------------
    def minimize(self):
        try:
            WINDOW.minimize()
        except Exception:
            pass

    def maximize(self):
        # Frameless maximize/restore by setting the window Bounds directly to the
        # monitor work area. We DON'T use WindowState.Maximized: on a borderless
        # WinForms form it misbehaves (with MaximizedBounds it could throw the
        # window off-screen — the "window disappears when I maximize" bug). Toggles.
        try:
            from System.Windows.Forms import FormWindowState, Screen
            from System.Drawing import Rectangle
            from System import Action
            native = WINDOW.native

            def toggle():
                try:
                    # never leave the form in a native Maximized state
                    if native.WindowState != FormWindowState.Normal:
                        native.WindowState = FormWindowState.Normal
                    saved = getattr(self, "_maxRestore", None)
                    if saved is not None:
                        # if the monitor layout changed and the saved rect is now
                        # off every screen, re-center it so the window can't vanish
                        try:
                            visible = any(scr.WorkingArea.IntersectsWith(saved) for scr in Screen.AllScreens)
                        except Exception:
                            visible = True
                        if not visible:
                            wa = Screen.PrimaryScreen.WorkingArea
                            w = min(saved.Width, wa.Width)
                            h = min(saved.Height, wa.Height)
                            saved = Rectangle(wa.X + (wa.Width - w) // 2,
                                              wa.Y + (wa.Height - h) // 2, w, h)
                        native.Bounds = saved            # restore the previous size/pos
                        self._maxRestore = None
                    else:
                        self._maxRestore = native.Bounds  # remember where we were
                        wa = Screen.FromControl(native).WorkingArea
                        native.Bounds = Rectangle(wa.X, wa.Y, wa.Width, wa.Height)
                except Exception:
                    pass

            native.BeginInvoke(Action(toggle))
            return
        except Exception:
            pass
        # fallback: pywebview's own API
        try:
            if getattr(self, "_maximized", False):
                WINDOW.restore()
                self._maximized = False
            else:
                WINDOW.maximize()
                self._maximized = True
        except Exception:
            pass

    def toggleFullscreen(self):
        global FULLSCREEN
        try:
            WINDOW.toggle_fullscreen()
            FULLSCREEN = not FULLSCREEN
            # fullscreen resizes the window, so any pending maximize-restore bounds
            # are now stale — drop them so the next Maximize press captures fresh.
            self._maxRestore = None
            if not FULLSCREEN:
                # pywebview re-adds the native title bar when LEAVING fullscreen on a
                # frameless window — which draws the OS min/max/close on top of our
                # own custom titlebar (the "duplicate buttons" bug). Force the window
                # back to borderless so only our custom controls remain.
                try:
                    from System.Windows.Forms import FormBorderStyle
                    from System import Action
                    native = WINDOW.native
                    borderless = getattr(FormBorderStyle, "None")
                    native.BeginInvoke(Action(lambda: setattr(native, "FormBorderStyle", borderless)))
                except Exception:
                    pass
        except Exception:
            pass
        return FULLSCREEN

    def startResize(self, edge):
        """Begin a NATIVE window resize from a frameless edge/corner grip — lets
        the user drag the borders to resize even though the window has no native
        frame. Hands off to Windows' own size loop (smooth, respects min_size)."""
        if FULLSCREEN:
            return
        # edge → Win32 hit-test code (HTLEFT..HTBOTTOMRIGHT)
        ht = {"left": 0xA, "right": 0xB, "top": 0xC, "topleft": 0xD,
              "topright": 0xE, "bottom": 0xF, "bottomleft": 0x10,
              "bottomright": 0x11}.get(edge)
        if ht is None:
            return
        try:
            import ctypes
            native = WINDOW.native
            hwnd = int(native.Handle.ToInt64())
            from System import Action

            def go():
                ctypes.windll.user32.ReleaseCapture()
                # WM_NCLBUTTONDOWN = 0x00A1 → starts the native resize tracking
                ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, ht, 0)

            native.BeginInvoke(Action(go))
        except Exception:
            pass

    def close(self):
        global SHUTTING_DOWN
        SHUTTING_DOWN = True
        try:
            WINDOW.destroy()
        except Exception:
            pass


# ---- single instance ------------------------------------------------------
# Two Velos running at once = every keystroke/sound fires twice ("extra notes").
# Guard with a loopback socket: the first instance binds it and holds it for its
# whole life; a second instance fails to bind, so it knows one is already up. The
# OS frees the socket automatically on exit/crash, so there are no stale locks.
_INSTANCE_LOCK = None
_INSTANCE_PORT = 49517   # fixed, Velo-private loopback port


def _acquireSingleInstance():
    """True if we're the only Velo; False if another instance holds the lock."""
    global _INSTANCE_LOCK
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", _INSTANCE_PORT))
        s.listen(1)
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return False
    _INSTANCE_LOCK = s   # keep the reference alive for the process lifetime
    return True


def _focusExistingVelo():
    """Best-effort: bring the already-running Velo window to the front (Windows)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Velo")
        if hwnd:
            user32.ShowWindow(hwnd, 9)        # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _notifyAlreadyRunning():
    """Tell the user (who just double-clicked) that Velo is already open."""
    if os.name == "nt":
        try:
            import ctypes
            # MB_ICONINFORMATION | MB_SETFOREGROUND
            ctypes.windll.user32.MessageBoxW(
                0, "Velo is already running.", "Velo", 0x40 | 0x10000)
        except Exception:
            pass
    else:
        try:
            sys.stderr.write("Velo is already running.\n")
        except Exception:
            pass


def main():
    global WINDOW, OVERLAY, OVERLAY_READY, PLAYER, DRUMS, INPUT

    # single-instance guard — a second Velo would double every note. If one is
    # already up, focus it and quit before doing any work.
    if not _acquireSingleInstance():
        _focusExistingVelo()
        _notifyAlreadyRunning()
        return

    # remove the "downloaded from the internet" mark from our own files so the
    # .NET/pythonnet bridge loads on a fresh download (must run before start())
    _unblockSelf()

    # taskbar + volume-mixer identity (see audioname for why this is needed)
    audioname.setAppId("brenu.Velo.MidiPlayer")

    indexPath = resourcePath(os.path.join("velo", "web", "index.html"))
    overlayPath = resourcePath(os.path.join("velo", "web", "overlay.html"))

    ui = configuration.configData.get("appUI", {})
    saved = ui.get("window", {}) or {}
    w = int(saved.get("w", 1100)); h = int(saved.get("h", 720))
    if not (400 <= w <= 8000): w = 1100
    if not (300 <= h <= 8000): h = 720
    kwargs = dict(width=w, height=h)
    # only honour a saved position if it lands somewhere visible (never the
    # -32000 minimize sentinel) — otherwise let pywebview centre the window
    if ("x" in saved and "y" in saved
            and _validGeom({"x": saved["x"], "y": saved["y"], "w": w, "h": h})
            and _onScreen(saved["x"], saved["y"], w, h)):
        kwargs["x"] = int(saved["x"])
        kwargs["y"] = int(saved["y"])

    api = Api()
    window = webview.create_window(
        "Velo",
        url=indexPath,
        js_api=api,
        min_size=(860, 580),
        frameless=True,
        easy_drag=False,
        on_top=bool(ui.get("onTop", False)),
        background_color="#0B0B0F",
        **kwargs,
    )

    WINDOW = window
    PLAYER = Player(emit=emit)
    DRUMS = DrumsPlayer(emit=emit)
    INPUT = InputController(emit=emit)

    # ----- floating mini-player (2nd window) --------------------------------
    # OPAQUE dark window (NOT transparent): WebView2 per-pixel transparency is
    # unreliable here — it rendered the pill as opaque grey AND corrupted the
    # main window's compositor (shared process). Instead we make it a solid dark
    # window and round its corners with a Win32 region (SetWindowRgn), so it
    # still reads as a floating pill. focus=False → pywebview adds
    # WS_EX_NOACTIVATE; we show/hide with Win32 SW_SHOWNOACTIVATE/SW_HIDE
    # (never pywebview show()/hide(), which steal focus from the game).
    ovCfg = configuration.configData.get("overlay", {}) or {}
    try:
        ovScale = float(ovCfg.get("scale", 1.0) or 1.0)
    except (TypeError, ValueError):
        ovScale = 1.0
    overlay = webview.create_window(
        "VeloOverlay",
        url=overlayPath,
        js_api=api,
        width=int(round(372 * ovScale)),
        height=int(round(118 * ovScale)),
        min_size=(160, 60),        # allow the small pill (pywebview defaults ~200x100)
        frameless=True,
        easy_drag=False,
        on_top=True,
        focus=False,
        resizable=False,
        background_color="#0d0d12",   # opaque dark; the native region rounds it
    )
    OVERLAY = overlay

    def onOverlayLoaded():
        global OVERLAY_READY
        OVERLAY_READY = True
        ovc = configuration.configData.get("overlay", {}) or {}
        enabled = bool(ovc.get("enabled", False))
        sx, sy = ovc.get("x"), ovc.get("y")

        def _init():
            _overlayApplyStyles()
            if isinstance(sx, (int, float)) and isinstance(sy, (int, float)):
                _overlayMoveTo(sx, sy)
            _overlayShow(enabled)
        _overlayInvoke(_init)
        if enabled:                          # fade the pill in, then hand it the
            threading.Timer(0.12, lambda: threading.Thread(   # current song/time
                target=lambda: _overlayAnim(True), daemon=True).start()).start()
            def _push():
                try:
                    if PLAYER:
                        PLAYER._emitState()
                        PLAYER.pushTimeline()
                except Exception:
                    pass
            threading.Timer(0.20, _push).start()

    def onOverlayMoved(x, y):
        try:
            x, y = int(x), int(y)
            if x > -10000 and y > -10000:   # ignore the minimize sentinel
                OVERLAY_GEOM["x"], OVERLAY_GEOM["y"] = x, y
        except Exception:
            pass

    overlay.events.loaded += onOverlayLoaded
    overlay.events.moved += onOverlayMoved

    # global hotkey (default F9) flips the mini-player on/off
    def _toggleOverlay():
        cur = bool(configuration.configData.get("overlay", {}).get("enabled", False))
        api.overlaySetEnabled(not cur)
    PLAYER.onOverlayToggle = _toggleOverlay

    def onResized(w, h):
        if FULLSCREEN:
            return
        w, h = int(w), int(h)
        if 400 <= w <= 8000 and 300 <= h <= 8000:
            GEOM["w"], GEOM["h"] = w, h

    def onMoved(x, y):
        if FULLSCREEN:
            return
        x, y = int(x), int(y)
        if x > -10000 and y > -10000:   # ignore the minimize sentinel
            GEOM["x"], GEOM["y"] = x, y

    window.events.resized += onResized
    window.events.moved += onMoved

    def onLoaded():
        logger.info("UI loaded OK (webview rendered, bridge alive)")
        # let the UI know the platform/session up front (Wayland banner, etc.)
        try:
            emit("platform", api.platformInfo())
        except Exception:
            pass
        try:
            PLAYER.bindHotkeys()
        except Exception:
            pass
        # relabel the WebView2 audio session as "Velo" in the volume mixer
        try:
            iconPath = resourcePath(os.path.join("assets", "icons", "velo.ico"))
            audioname.brand("Velo", icon=iconPath if os.path.exists(iconPath) else None)
        except Exception:
            pass
        # check GitHub for a newer release (non-blocking); the UI shows a banner
        def _checkUpdate():
            try:
                from velo.backend import update
                res = update.checkLatest()
                if res.get("ok") and res.get("newer"):
                    emit("update", res)
            except Exception:
                pass
        threading.Thread(target=_checkUpdate, name="velo-update", daemon=True).start()

    window.events.loaded += onLoaded

    def onClosing():
        global SHUTTING_DOWN
        SHUTTING_DOWN = True   # silence the buses before the WebView2 tears down
        try:
            onlineseq.shutdown()
            PLAYER.unbindHotkeys()
            if PLAYER.isRunning:
                PLAYER.stop()
            if DRUMS and DRUMS.isRunning:
                DRUMS.stop()
            if INPUT and INPUT.running:
                INPUT.stop()
            if _validGeom(GEOM) and _onScreen(GEOM.get("x", 0), GEOM.get("y", 0),
                                              GEOM.get("w", 0), GEOM.get("h", 0)):
                win = configuration.configData.setdefault("appUI", {}).setdefault("window", {})
                win.update(GEOM)
                configuration.save()
            # remember where the mini-player pill was left
            if isinstance(OVERLAY_GEOM.get("x"), int) and isinstance(OVERLAY_GEOM.get("y"), int):
                ov = configuration.configData.setdefault("overlay", {})
                ov["x"], ov["y"] = OVERLAY_GEOM["x"], OVERLAY_GEOM["y"]
                configuration.save()
        except Exception:
            pass

    window.events.closing += onClosing
    # http_server=True serves the UI over http://127.0.0.1 so the page can
    # fetch()/decodeAudioData() local audio assets (blocked under file://).
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
