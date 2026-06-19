"""High-level player: orchestrates the QWERTY / MIDI-out engines, forwards
log + timeline events to the UI, and manages global hotkeys. This is the clean
replacement for the old Tkinter-coupled midiPlayerFunctions.py.
"""

import os
import time
import datetime
import threading
import logging

import mido
import keyboard

from velo.backend import config as configuration
from velo.backend import qwerty_engine
from velo.backend import output_engine
from velo.backend.logbus import LogBus, NoteBus

logger = logging.getLogger("velo.player")


class Player:
    def __init__(self, emit):
        # emit(eventName: str, payload: dict) -> pushes an event to the web UI
        self.emit = emit
        self.currentFile = ""    # the selected/cued file
        self.playingFile = ""    # the file actually playing right now
        self.isRunning = False
        self.paused = False
        self.speed = 100
        self._hotkeyHandlers = []
        self._bus = LogBus(emit, "player")
        self._noteBus = NoteBus(emit)
        self.log = self._bus.log

        for engine in (qwerty_engine, output_engine):
            engine.log = self._bus.log
            engine.onFinished = self._onFinished

        self._restoreSavedFile()
        configuration.configData.setdefault("sound", {"enabled": False, "mode": "piano", "volume": 70, "pack": "brown-local", "piano": "grand"})
        self._applySoundHook()
        # Hotkeys are bound later (after the window loads) to avoid installing a
        # global low-level keyboard hook during WebView2's heavy first-run init,
        # which could freeze input on slower machines.

    # ----- engine selection -------------------------------------------------
    @property
    def _useMIDI(self):
        return bool(configuration.configData["midiPlayer"].get("useMIDIOutput", False))

    @property
    def _engine(self):
        return output_engine if self._useMIDI else qwerty_engine

    # ----- file handling ----------------------------------------------------
    def _midiLength(self, path):
        try:
            return mido.MidiFile(path, clip=True).length
        except Exception:
            return 0

    def _fmt(self, seconds):
        return str(datetime.timedelta(seconds=int(seconds)))

    def _restoreSavedFile(self):
        try:
            ml = configuration.configData["midiPlayer"].setdefault("midiList", [])
            # make sure MIDIs in the Velo/Midis folder (downloads, drag-drops) are queued
            midisDir = os.path.join(configuration.baseDirectory, "Midis")
            if os.path.isdir(midisDir):
                for fn in sorted(os.listdir(midisDir)):
                    if fn.lower().endswith((".mid", ".midi")):
                        p = os.path.join(midisDir, fn)
                        if p not in ml:
                            ml.append(p)
            # drop entries that no longer exist on disk (heals stale paths)
            ml[:] = [p for p in ml if os.path.exists(p)]
            configuration.save()

            current = configuration.configData["midiPlayer"].get("currentFile", "")
            if current and os.path.exists(current):
                self.currentFile = current
            elif ml:
                self.currentFile = ml[0]
                configuration.configData["midiPlayer"]["currentFile"] = self.currentFile
                configuration.save()
        except Exception:
            pass

    def setFile(self, path):
        if not path or not os.path.exists(path):
            return self.getState()
        self.currentFile = path
        mp = configuration.configData["midiPlayer"]
        mp["currentFile"] = path
        midiList = mp.setdefault("midiList", [])
        if path not in midiList:
            midiList.append(path)
        configuration.save()
        self.log(f"Loaded: {os.path.basename(path)}")
        return self.getState()

    def recentFiles(self):
        files = configuration.configData["midiPlayer"].get("midiList", [])
        return [f for f in files if os.path.exists(f)]

    # ----- playback ---------------------------------------------------------
    def _timelineCallback(self, text, shown, total):
        self.emit("timeline", {"text": text, "current": shown, "total": total})

    def _startFile(self, path, offset=0):
        """Start (or switch/seek to) a specific file, stopping any current playback."""
        if not path or not os.path.exists(path):
            self.log("No MIDI file selected.")
            return
        if self.isRunning:
            try:
                self._engine.stopPlayback()
            except Exception:
                pass
        self.isRunning = True
        self.paused = False
        self.playingFile = path
        total = self._midiLength(path)
        self.emit("timeline", {"text": f"{self._fmt(offset)} / {self._fmt(total)}", "current": offset, "total": total})
        try:
            if self._useMIDI:
                device = configuration.configData["midiPlayer"].get("outputDevice", "")
                if not device:
                    devices = self.listOutputDevices()
                    if not devices:
                        self.isRunning = False
                        self.playingFile = ""
                        self.log("No MIDI output device available.")
                        self._emitState()
                        return
                    device = devices[0]
                output_engine.playbackSpeed = self.speed / 100.0
                output_engine.startPlayback(path, device, updateCallback=self._timelineCallback, startOffset=offset)
            else:
                qwerty_engine.playbackSpeed = self.speed / 100.0
                qwerty_engine.startPlayback(path, updateCallback=self._timelineCallback, startOffset=offset)
        except Exception as e:
            logger.exception("play error")
            self.isRunning = False
            self.playingFile = ""
            self.log(f"Error starting playback: {e}")
        self._emitState()

    def seek(self, seconds):
        if not self.isRunning or not self.playingFile:
            return self.getState()
        total = int(self._midiLength(self.playingFile))
        try:
            seconds = max(0, min(int(seconds), max(0, total - 1)))
        except Exception:
            return self.getState()
        self._startFile(self.playingFile, offset=seconds)
        return self.getState()

    def addToQueue(self, path):
        if not path or not os.path.exists(path):
            return self.getState()
        ml = configuration.configData["midiPlayer"].setdefault("midiList", [])
        if path not in ml:
            ml.append(path)
        if not self.currentFile:
            self.currentFile = path
            configuration.configData["midiPlayer"]["currentFile"] = path
        configuration.save()
        self.log(f"Added to queue: {os.path.basename(path)}")
        self._emitState()
        return self.getState()

    def play(self):
        if not self.isRunning:
            self._startFile(self.currentFile)          # nothing playing -> play selected
        elif self.playingFile != self.currentFile:
            self._startFile(self.currentFile)          # switch to the newly selected song
        elif self._engine.paused:
            self.pause()                               # resume
        return self.getState()

    def _refIndex(self, playlist):
        ref = self.playingFile if (self.isRunning and self.playingFile) else self.currentFile
        if ref in playlist:
            return playlist.index(ref)
        if self.currentFile in playlist:
            return playlist.index(self.currentFile)
        return -1

    def _selectAndPlay(self, path):
        self.currentFile = path
        configuration.configData["midiPlayer"]["currentFile"] = path
        configuration.save()
        self._startFile(path)

    def nextTrack(self):
        pl = self.recentFiles()
        if not pl:
            return self.getState()
        i = self._refIndex(pl)
        self._selectAndPlay(pl[(i + 1) % len(pl)])
        return self.getState()

    def prevTrack(self):
        pl = self.recentFiles()
        if not pl:
            return self.getState()
        i = self._refIndex(pl)
        self._selectAndPlay(pl[(i - 1) % len(pl)])
        return self.getState()

    def playPath(self, path):
        if path and os.path.exists(path):
            self._selectAndPlay(path)
        return self.getState()

    def removeFile(self, path):
        ml = configuration.configData["midiPlayer"].setdefault("midiList", [])
        if path in ml:
            ml.remove(path)
        if self.currentFile == path:
            remaining = self.recentFiles()
            self.currentFile = remaining[0] if remaining else ""
            configuration.configData["midiPlayer"]["currentFile"] = self.currentFile
        configuration.save()
        self._emitState()
        return self.getState()

    def reorderQueue(self, paths):
        ml = configuration.configData["midiPlayer"].setdefault("midiList", [])
        known = set(ml)
        newOrder = [p for p in (paths or []) if p in known]
        for p in ml:
            if p not in newOrder:
                newOrder.append(p)
        configuration.configData["midiPlayer"]["midiList"] = newOrder
        configuration.save()
        self._emitState()
        return self.getState()

    def clearQueue(self):
        configuration.configData["midiPlayer"]["midiList"] = []
        # keep the song that's actually playing; just clear the selection list
        if not self.isRunning:
            self.currentFile = ""
            configuration.configData["midiPlayer"]["currentFile"] = ""
        configuration.save()
        self._emitState()
        return self.getState()

    def pause(self):
        if not self.isRunning:
            return self.getState()
        self.paused = self._engine.pausePlayback()
        self._emitState()
        return self.getState()

    def stop(self):
        if not self.isRunning:
            return self.getState()
        self._engine.stopPlayback()
        self.isRunning = False
        self.paused = False
        self.playingFile = ""
        total = self._midiLength(self.currentFile)
        self.emit("timeline", {"text": f"0:00:00 / {self._fmt(total)}", "current": 0, "total": total})
        self._emitState()
        return self.getState()

    def _onFinished(self):
        # called from the engine thread when a non-looping song ends naturally
        self._engine.stopPlayback()
        self.isRunning = False
        self.paused = False
        self.playingFile = ""
        self._emitState()

    def toggle(self):
        if self.isRunning and self.playingFile == self.currentFile:
            return self.pause()      # same song -> pause / resume
        return self.play()           # not playing, or switch to the selected song

    # ----- speed ------------------------------------------------------------
    # ----- sound (mic illusion) ---------------------------------------------
    def _emitNote(self, note, velocity, isOn):
        # non-blocking: queued + flushed on a separate thread (see NoteBus)
        self._noteBus.note(note, velocity, isOn)

    def _applySoundHook(self):
        on = bool(configuration.configData.get("sound", {}).get("enabled", False))
        hook = self._emitNote if on else None
        qwerty_engine.onNote = hook
        output_engine.onNote = hook

    def setSound(self, key, value):
        s = configuration.configData.setdefault("sound", {"enabled": False, "mode": "piano", "volume": 70, "pack": "brown-local", "piano": "grand"})
        if key == "enabled":
            s["enabled"] = bool(value)
        elif key == "mode":
            s["mode"] = "keyboard" if value == "keyboard" else "piano"
        elif key == "volume":
            try:
                s["volume"] = max(0, min(100, int(value)))
            except Exception:
                pass
        elif key == "pack":
            s["pack"] = str(value)
        elif key == "piano":
            s["piano"] = str(value)
        configuration.save()
        if key == "enabled":
            self._applySoundHook()
        self._emitState()
        return self.getState()

    def setSpeed(self, value):
        try:
            value = max(1, min(500, int(value)))
        except Exception:
            return self.getState()
        self.speed = value
        qwerty_engine.playbackSpeed = value / 100.0
        output_engine.playbackSpeed = value / 100.0
        self._emitState()
        return self.getState()

    def changeSpeed(self, delta):
        return self.setSpeed(self.speed + delta)

    # ----- options ----------------------------------------------------------
    def setOption(self, key, value):
        configuration.configData["midiPlayer"][key] = bool(value)
        configuration.save()
        if key == "useMIDIOutput" and self.isRunning:
            self.stop()
        self._emitState()
        return self.getState()

    # ----- devices ----------------------------------------------------------
    def listOutputDevices(self):
        try:
            return list(dict.fromkeys(mido.get_output_names()))
        except Exception:
            return []

    def setOutputDevice(self, name):
        configuration.configData["midiPlayer"]["outputDevice"] = name
        configuration.save()
        return self.getState()

    # ----- hotkeys ----------------------------------------------------------
    def bindHotkeys(self):
        self.unbindHotkeys()
        hk = configuration.configData.get("hotkeys", {})
        mapping = {
            hk.get("play", "f1"): self.toggle,
            hk.get("pause", "f2"): self.pause,
            hk.get("stop", "f3"): self.stop,
            hk.get("speedup", "f4"): lambda: self.changeSpeed(5),
            hk.get("slowdown", "f5"): lambda: self.changeSpeed(-5),
            hk.get("prevtrack", "f6"): self.prevTrack,
            hk.get("nexttrack", "f7"): self.nextTrack,
        }
        try:
            for key, fn in mapping.items():
                handler = keyboard.on_press_key(str(key).lower(), lambda e, fn=fn: fn())
                self._hotkeyHandlers.append(handler)
        except Exception as e:
            logger.warning(f"hotkey bind failed: {e}")

    def unbindHotkeys(self):
        for h in list(self._hotkeyHandlers):
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self._hotkeyHandlers.clear()

    # ----- state ------------------------------------------------------------
    def getState(self):
        mp = configuration.configData["midiPlayer"]
        total = self._midiLength(self.currentFile) if self.currentFile else 0
        return {
            "currentFile": self.currentFile,
            "fileName": os.path.basename(self.currentFile) if self.currentFile else "",
            "playingFile": self.playingFile,
            "playingName": os.path.basename(self.playingFile) if self.playingFile else "",
            "selectedIsPlaying": bool(self.isRunning and self.playingFile == self.currentFile),
            "recentFiles": [{"path": p, "name": os.path.basename(p)} for p in self.recentFiles()],
            "isRunning": self.isRunning,
            "paused": self.paused,
            "speed": self.speed,
            "totalSeconds": total,
            "totalText": self._fmt(total),
            "options": {
                "useMIDIOutput": bool(mp.get("useMIDIOutput", False)),
                "sustain": bool(mp.get("sustain", False)),
                "noDoubles": bool(mp.get("noDoubles", False)),
                "velocity": bool(mp.get("velocity", False)),
                "88Keys": bool(mp.get("88Keys", True)),
                "loopSong": bool(mp.get("loopSong", False)),
            },
            "outputDevices": self.listOutputDevices(),
            "outputDevice": mp.get("outputDevice", ""),
            "hotkeys": configuration.configData.get("hotkeys", {}),
            "lastView": configuration.configData.get("appUI", {}).get("lastView", "player"),
            "onTop": bool(configuration.configData.get("appUI", {}).get("onTop", False)),
            "sound": configuration.configData.get("sound", {"enabled": False, "mode": "piano", "volume": 70, "pack": "brown-local", "piano": "grand"}),
        }

    def _emitState(self):
        try:
            self.emit("state", self.getState())
        except Exception:
            pass
