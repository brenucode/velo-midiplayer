"""Velo configuration — local only, no network, no nanomidi servers.

Loads sane defaults bundled in assets/defaultConfig.json, then overlays the
user's saved config from Documents/Velo/config.json. The MIDI engines read
values via ``configData[...]`` exactly like the original code, so they work
unchanged after we swap their import to point here.
"""

import os
import sys
import json
import copy
import random

from velo.backend import platcompat

APP_NAME = "Velo"
# Single source of truth for the running version (keep in sync with version.txt).
# The updater compares this against the latest GitHub release tag.
APP_VERSION = "1.5"

# Floor so a tap is always long enough for the game to register the key press.
SHORT_NOTES_FLOOR_MS = 30


def short_hold_seconds():
    """How long a simulated key should stay down when 'Short notes' is on.

    Returns None when the feature is off (the engine then holds the key for the
    note's real duration). When on, returns a SHORT hold in seconds — a random
    human-like dwell time (Random mode) or a fixed one — so long notes become
    quick taps and the in-game note-trail looks like a real player, not autoplay.
    """
    sn = configData.get("shortNotes")
    if not sn or not sn.get("enabled"):
        return None
    floor = SHORT_NOTES_FLOOR_MS
    if sn.get("random", True):
        lo = max(floor, int(sn.get("minMs", 55)))
        hi = max(lo, int(sn.get("maxMs", 130)))
        ms = random.uniform(lo, hi)
    else:
        ms = max(floor, int(sn.get("fixedMs", 100)))
    return ms / 1000.0


def resourcePath(relativePath):
    # Frozen: PyInstaller's bundle dir. From source: the repo root (three levels
    # up from velo/backend/config.py) — NOT the current working directory, so
    # bundled assets resolve no matter where Velo is launched from (e.g. a
    # desktop-menu launcher whose cwd is $HOME, not the app folder).
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relativePath)


# Windows/macOS: ~/Documents/Velo (unchanged). Linux: XDG (~/.local/share/Velo).
baseDirectory = platcompat.data_dir(APP_NAME)
os.makedirs(baseDirectory, exist_ok=True)

configPath = os.path.join(baseDirectory, "config.json")
defaultConfigPath = resourcePath("assets/defaultConfig.json")


def _loadDefaults():
    try:
        with open(defaultConfigPath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _deepMerge(target, source):
    """Recursively overlay ``source`` onto ``target`` (source wins on leaves)."""
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deepMerge(target[key], value)
        else:
            target[key] = value


# configData is a plain dict — nested access (configData["midiPlayer"]["..."])
# works just like the original SafeDict, but with zero remote calls.
configData = _loadDefaults()

if os.path.exists(configPath):
    try:
        with open(configPath, "r", encoding="utf-8") as f:
            _deepMerge(configData, json.load(f))
    except Exception:
        pass


def save():
    try:
        with open(configPath, "w", encoding="utf-8") as f:
            json.dump(configData, f, indent=2)
    except Exception:
        pass


def setValue(section, key, value):
    configData.setdefault(section, {})[key] = value
    save()


def defaults():
    return copy.deepcopy(_loadDefaults())


if not os.path.exists(configPath):
    save()
