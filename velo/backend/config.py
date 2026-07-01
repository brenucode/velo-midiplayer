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

from velo.backend import platcompat

APP_NAME = "Velo"
# Single source of truth for the running version (keep in sync with version.txt).
# The updater compares this against the latest GitHub release tag.
APP_VERSION = "1.4"


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
