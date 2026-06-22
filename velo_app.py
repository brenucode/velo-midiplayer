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
import base64
import logging
import threading

# Keep WebView2 timers/rendering alive even when a window is hidden or occluded.
# This lets the Online Sequencer helper window clear its Cloudflare check while
# staying completely invisible (a throttled hidden window never solves it), and
# keeps the main window's playback loops smooth while running in the background.
# Must be set before any WebView2 starts.
os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--disable-background-timer-throttling "
    "--disable-backgrounding-occluded-windows "
    "--disable-renderer-backgrounding",
)

import webview

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from velo.backend import config as configuration
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


def emit(event, payload):
    if SHUTTING_DOWN:
        return
    w = WINDOW
    if w is None:
        return
    try:
        w.evaluate_js("window.veloEvent && window.veloEvent(%s, %s)"
                      % (json.dumps(event), json.dumps(payload)))
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

    def setSound(self, key, value):
        return PLAYER.setSound(key, value)

    def setHumanize(self, key, value):
        return PLAYER.setHumanize(key, value)

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

    # ----- app state / drag-drop -------------------------------------------
    def setLastView(self, name):
        configuration.configData.setdefault("appUI", {})["lastView"] = str(name)
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

    # ----- window controls (frameless) -------------------------------------
    def minimize(self):
        try:
            WINDOW.minimize()
        except Exception:
            pass

    def maximize(self):
        # Toggle on the native WinForms window's REAL state, so it stays in sync
        # even if the user maximized/restored via a titlebar double-click. Set
        # MaximizedBounds to the work area so a frameless maximize doesn't cover
        # the taskbar.
        try:
            from System.Windows.Forms import FormWindowState, Screen
            from System import Action
            native = WINDOW.native

            def toggle():
                if native.WindowState == FormWindowState.Maximized:
                    native.WindowState = FormWindowState.Normal
                else:
                    try:
                        native.MaximizedBounds = Screen.FromControl(native).WorkingArea
                    except Exception:
                        pass
                    native.WindowState = FormWindowState.Maximized

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
        except Exception:
            pass
        return FULLSCREEN

    def close(self):
        global SHUTTING_DOWN
        SHUTTING_DOWN = True
        try:
            WINDOW.destroy()
        except Exception:
            pass


def main():
    global WINDOW, PLAYER, DRUMS, INPUT

    # remove the "downloaded from the internet" mark from our own files so the
    # .NET/pythonnet bridge loads on a fresh download (must run before start())
    _unblockSelf()

    # taskbar + volume-mixer identity (see audioname for why this is needed)
    audioname.setAppId("brenu.Velo.MidiPlayer")

    indexPath = resourcePath(os.path.join("velo", "web", "index.html"))

    ui = configuration.configData.get("appUI", {})
    saved = ui.get("window", {}) or {}
    w = int(saved.get("w", 1100)); h = int(saved.get("h", 720))
    if not (400 <= w <= 8000): w = 1100
    if not (300 <= h <= 8000): h = 720
    kwargs = dict(width=w, height=h)
    # only honour a saved position if it lands somewhere visible (never the
    # -32000 minimize sentinel) — otherwise let pywebview centre the window
    if "x" in saved and "y" in saved and _validGeom({"x": saved["x"], "y": saved["y"], "w": w, "h": h}):
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
            if _validGeom(GEOM):
                win = configuration.configData.setdefault("appUI", {}).setdefault("window", {})
                win.update(GEOM)
                configuration.save()
        except Exception:
            pass

    window.events.closing += onClosing
    # http_server=True serves the UI over http://127.0.0.1 so the page can
    # fetch()/decodeAudioData() local audio assets (blocked under file://).
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
