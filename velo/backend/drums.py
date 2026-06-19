"""Drums player manager — orchestrates drums_engine and forwards events."""

import os
import datetime
import logging

import mido

from velo.backend import config as configuration
from velo.backend import drums_engine
from velo.backend.logbus import LogBus

logger = logging.getLogger("velo.drums")


class DrumsPlayer:
    def __init__(self, emit):
        self.emit = emit
        self._bus = LogBus(emit, "drums")
        self.log = self._bus.log
        drums_engine.log = self._bus.log
        drums_engine.onFinished = self._onFinished

        self.currentFile = ""
        self.isRunning = False
        self.paused = False
        self.speed = 100

        cur = configuration.configData["drumsMacro"].get("currentFile", "")
        if cur and os.path.exists(cur):
            self.currentFile = cur

    def _len(self, path):
        try:
            return mido.MidiFile(path, clip=True).length
        except Exception:
            return 0

    def _fmt(self, s):
        return str(datetime.timedelta(seconds=int(s)))

    def setFile(self, path):
        if not path or not os.path.exists(path):
            return self.getState()
        self.currentFile = path
        dm = configuration.configData["drumsMacro"]
        dm["currentFile"] = path
        lst = dm.setdefault("midiList", [])
        if path not in lst:
            lst.append(path)
        configuration.save()
        self.log(f"Loaded: {os.path.basename(path)}")
        return self.getState()

    def recentFiles(self):
        return [f for f in configuration.configData["drumsMacro"].get("midiList", []) if os.path.exists(f)]

    def _timeline(self, text, shown, total):
        self.emit("drumsTimeline", {"text": text, "current": shown, "total": total})

    def play(self):
        if self.isRunning and not drums_engine.paused:
            return self.getState()
        if self.isRunning and drums_engine.paused:
            return self.pause()
        if not self.currentFile or not os.path.exists(self.currentFile):
            self.log("No MIDI file selected.")
            return self.getState()
        total = self._len(self.currentFile)
        self.emit("drumsTimeline", {"text": f"0:00:00 / {self._fmt(total)}", "current": 0, "total": total})
        self.isRunning = True
        self.paused = False
        try:
            drums_engine.playbackSpeed = self.speed / 100.0
            drums_engine.startPlayback(self.currentFile, updateCallback=self._timeline)
        except Exception as e:
            logger.exception("drums play error")
            self.isRunning = False
            self.log(f"Error: {e}")
        self._emit()
        return self.getState()

    def pause(self):
        if not self.isRunning:
            return self.getState()
        self.paused = drums_engine.pausePlayback()
        self._emit()
        return self.getState()

    def stop(self):
        if not self.isRunning:
            return self.getState()
        drums_engine.stopPlayback()
        self.isRunning = False
        self.paused = False
        total = self._len(self.currentFile)
        self.emit("drumsTimeline", {"text": f"0:00:00 / {self._fmt(total)}", "current": 0, "total": total})
        self._emit()
        return self.getState()

    def _onFinished(self):
        drums_engine.stopPlayback()
        self.isRunning = False
        self.paused = False
        self._emit()

    def toggle(self):
        return self.pause() if self.isRunning else self.play()

    def setSpeed(self, value):
        try:
            value = max(1, min(500, int(value)))
        except Exception:
            return self.getState()
        self.speed = value
        drums_engine.playbackSpeed = value / 100.0
        self._emit()
        return self.getState()

    def changeSpeed(self, delta):
        return self.setSpeed(self.speed + delta)

    def setOption(self, key, value):
        configuration.configData["drumsMacro"][key] = bool(value)
        configuration.save()
        self._emit()
        return self.getState()

    def getState(self):
        dm = configuration.configData["drumsMacro"]
        total = self._len(self.currentFile) if self.currentFile else 0
        return {
            "currentFile": self.currentFile,
            "fileName": os.path.basename(self.currentFile) if self.currentFile else "",
            "recentFiles": [{"path": p, "name": os.path.basename(p)} for p in self.recentFiles()],
            "isRunning": self.isRunning,
            "paused": self.paused,
            "speed": self.speed,
            "totalText": self._fmt(total),
            "options": {
                "loopSong": bool(dm.get("loopSong", False)),
                "releaseOnPause": bool(dm.get("releaseOnPause", True)),
            },
        }

    def _emit(self):
        try:
            self.emit("drumsState", self.getState())
        except Exception:
            pass
