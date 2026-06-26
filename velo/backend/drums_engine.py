"""Drums playback engine (forked from drumsWindows.py).

Plays a MIDI drum track by mapping General-MIDI drum notes to QWERTY keys.
Decoupled from Tkinter: ``log`` and ``onFinished`` are injectable.
"""

import mido
import time
import random
import threading

# `keyboard` is imported for parity with the other engines but drums always use
# pynput; guard it so a Linux box without the (root-only) backend still loads.
try:
    import keyboard  # noqa: F401
except Exception:
    keyboard = None

from pynput import keyboard as pynputKeyboard
from velo.backend import config as configuration

selectedModule = "pynput"
pressedKeys = set()
heldKeys = set()


def log(*args, **kwargs):
    """No-op by default; the player replaces this to stream to the UI."""


onFinished = None


def logKeys(action, key):
    if isinstance(key, pynputKeyboard.Key):
        keyName = key.name if key.name else str(key)
    else:
        keyName = str(key)
    if action == "press":
        pressedKeys.add(keyName)
    elif action == "release" and keyName in pressedKeys:
        pressedKeys.remove(keyName)
    if pressedKeys:
        log(f"{action}: {'+'.join(sorted(pressedKeys))}")
    else:
        log(f"{action}: {keyName}")


pynputController = pynputKeyboard.Controller()
blockedKeys = {f"f{i}" for i in range(1, 13)} | {"tab", "backspace", "esc"}


def translateKey(key):
    keyLower = key.lower() if isinstance(key, str) else key
    if isinstance(keyLower, str) and len(keyLower) == 1:
        return keyLower
    elif isinstance(key, pynputKeyboard.Key):
        return key
    else:
        raise ValueError(f"Unsupported key: {key}")


def isBlockedKey(keyObj):
    if isinstance(keyObj, str):
        return keyObj.lower() in blockedKeys
    if isinstance(keyObj, pynputKeyboard.Key):
        name = getattr(keyObj, "name", None)
        if isinstance(name, str) and name.lower() in blockedKeys:
            return True
        s = str(keyObj).lower()
        if s.startswith("key.f") and any(s.startswith(f"key.f{i}") for i in range(1, 13)):
            return True
        return False
    return False


def press(key):
    keyObj = translateKey(key)
    if isBlockedKey(keyObj):
        return
    pynputController.press(keyObj)
    logKeys("press", keyObj)
    heldKeys.add(keyObj)


def release(key):
    keyObj = translateKey(key)
    if isBlockedKey(keyObj):
        return
    pynputController.release(keyObj)
    logKeys("release", keyObj)
    if keyObj in heldKeys:
        heldKeys.remove(keyObj)


def _drumsMap():
    m = configuration.configData["drumsMacro"]["drumsMap"]
    return {
        42: m["closed_Hi-Hat"], 44: m["closed_Hi-Hat2"], 46: m["open_Hi-Hat"],
        48: m["tom1"], 50: m["tom1_2"], 60: m["tom"], 62: m["tom2_2"],
        49: m["rightCrash"], 55: m["leftCrash"], 38: m["snare"], 40: m["snare2"],
        37: m["snareSide"], 35: m["kick"], 36: m["kick2"], 51: m["ride"],
        53: m["rideBell"], 39: m["cowbell"], 52: m["crashChina"], 57: m["splashCrash"],
        45: m["lowTom"], 47: m["lowMidTom"],
    }


stopEvent = threading.Event()
clockThreadRef = None
playThread = None
timerList = []
paused = False
closeThread = False
playbackSpeed = 1.0


def pressAndMaybeRelease(key):
    press(key)
    if configuration.configData["drumsMacro"]["customHoldLength"]["enabled"]:
        t = threading.Timer(configuration.configData["drumsMacro"]["customHoldLength"]["noteLength"], lambda: release(key))
        timerList.append(t)
        t.start()


def parseMidi(message, drumsMap):
    if message.type == "note_on" and message.velocity > 0:
        key = drumsMap.get(message.note)
        if key is not None:
            pressAndMaybeRelease(key)
    elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
        key = drumsMap.get(message.note)
        if key is not None:
            release(key)


def playMidiOnce(filePath, drumsMap):
    mid = mido.MidiFile(filePath, clip=True)
    startTime = time.monotonic()
    currentTime = 0
    for msg in mid:
        if stopEvent.is_set() or closeThread:
            return False
        adjustedDelay = msg.time / playbackSpeed
        if configuration.configData["drumsMacro"]["randomFail"]["enabled"] and not msg.is_meta:
            if random.random() < configuration.configData["drumsMacro"]["randomFail"]["speed"] / 100:
                adjustedDelay *= random.uniform(0.5, 1.5)
        currentTime += adjustedDelay
        targetTime = startTime + currentTime
        while time.monotonic() < targetTime:
            if stopEvent.is_set() or closeThread:
                return False
            while paused and not (stopEvent.is_set() or closeThread):
                pauseStart = time.monotonic()
                time.sleep(0.05)
                pauseDuration = time.monotonic() - pauseStart
                startTime += pauseDuration
                targetTime += pauseDuration
            remaining = targetTime - time.monotonic()
            if remaining > 0:
                time.sleep(min(remaining, 0.005))
        if msg.is_meta:
            continue
        parseMidi(msg, drumsMap)
    return True


def playMidiFile(filePath):
    log("Velo Drums Macro")
    log(f"Playing MIDI file: {filePath}")
    drumsMap = _drumsMap()
    while not (stopEvent.is_set() or closeThread):
        finished = playMidiOnce(filePath, drumsMap)
        if not configuration.configData["drumsMacro"]["loopSong"] or not finished or stopEvent.is_set() or closeThread:
            break
        for key in list(heldKeys):
            release(key)

    if not configuration.configData["drumsMacro"]["loopSong"] and not (stopEvent.is_set() or closeThread):
        if onFinished:
            onFinished()


def formatTime(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:0}:{minutes:02}:{secs:02}"


def clockThread(totalSeconds, updateCallback=None):
    global closeThread, playbackSpeed, paused
    currentSeconds = 0
    while not (stopEvent.is_set() or closeThread):
        if not paused:
            shown = currentSeconds % max(1, int(totalSeconds))
            formattedTime = f"{formatTime(shown)} / {formatTime(totalSeconds)}"
            if updateCallback:
                updateCallback(formattedTime, shown, totalSeconds)
            currentSeconds += 1
            for _ in range(10):
                if stopEvent.is_set() or closeThread:
                    break
                time.sleep(0.1 / playbackSpeed)
        else:
            time.sleep(0.1)


def startPlayback(filePath, updateCallback=None):
    global playThread, stopEvent, clockThreadRef, closeThread, paused
    stopEvent.clear()
    closeThread = False
    paused = False
    if playThread is not None and isinstance(playThread, threading.Thread) and playThread.is_alive():
        return
    totalSeconds = mido.MidiFile(filePath, clip=True).length
    playThread = threading.Thread(target=playMidiFile, args=(filePath,), daemon=True)
    clockThreadRef = threading.Thread(target=clockThread, args=(totalSeconds, updateCallback), daemon=True)
    clockThreadRef.start()
    playThread.start()


def pausePlayback():
    global paused
    paused = not paused
    if paused and configuration.configData["drumsMacro"]["releaseOnPause"]:
        for key in list(heldKeys):
            release(key)
    log("Playback paused." if paused else "Playback resumed.")
    return paused


def changeSpeed(amount):
    global playbackSpeed
    playbackSpeed = max(0.1, min(5.0, playbackSpeed + amount))
    log(f"Speed: {playbackSpeed * 100:.0f}%")


def stopPlayback():
    global closeThread, stopEvent, playThread, clockThreadRef, timerList
    if stopEvent.is_set():
        return
    stopEvent.set()
    closeThread = True
    for key in list(heldKeys):
        try:
            release(key)
        except Exception:
            pass
    for t in list(timerList):
        try:
            t.cancel()
        except Exception:
            pass
    timerList.clear()
    if playThread is not None and isinstance(playThread, threading.Thread):
        try:
            if threading.current_thread() is not playThread:
                playThread.join(timeout=1.0)
        except Exception:
            pass
    if clockThreadRef is not None and isinstance(clockThreadRef, threading.Thread):
        try:
            if threading.current_thread() is not clockThreadRef:
                clockThreadRef.join(timeout=1.0)
        except Exception:
            pass
    log("Playback fully stopped.")
