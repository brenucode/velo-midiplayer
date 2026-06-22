"""Humanizer — makes playback feel less robotic.

A real player never hits or releases the notes of a chord at the exact same
millisecond, and never plays two notes with identical force. MIDI playback,
being mathematically perfect, sounds mechanical. This module adds three small,
controllable imperfections — all gated by a single ``enabled`` toggle:

* **timing**   — random jitter (± ms) on every note's onset *and* release, so
  nothing lands dead on the grid.
* **chord**    — a tiny progressive offset across notes that fall on the same
  beat (onsets *and* releases), so chords "roll" like real fingers instead of
  snapping together.
* **velocity** — random ± % on each note's force (affects MIDI-out volume and
  the in-app piano sound; QWERTY keystrokes have no force, so there only the
  timing/chord parts apply).

Offsets are applied per note and never accumulated into the song clock, so the
overall tempo never drifts — each note just breathes a little around its true
position.
"""

import random

from velo.backend import config as configuration

_DEFAULT = {"enabled": False, "timing": 18, "velocity": 12, "chord": 14}


def getConfig():
    h = configuration.configData.get("midiPlayer", {}).get("humanize")
    if not isinstance(h, dict):
        return dict(_DEFAULT)
    return h


def _num(h, key):
    try:
        return max(0.0, float(h.get(key, 0)))
    except Exception:
        return 0.0


def jitterVelocity(velocity):
    """Return ``velocity`` nudged by a random ± percentage (clamped 1..127)."""
    h = getConfig()
    if not h.get("enabled") or velocity <= 0:
        return velocity
    pct = _num(h, "velocity")
    if pct <= 0:
        return velocity
    factor = 1.0 + random.uniform(-pct / 100.0, pct / 100.0)
    return max(1, min(127, int(round(velocity * factor))))


class Humanizer:
    """Per-playback state for timing/chord offsets. One instance per run."""

    def __init__(self):
        self._onIdx = 0      # position within a simultaneous cluster of onsets
        self._offIdx = 0     # ... and of releases

    def offset(self, msg):
        """Seconds to add to this message's scheduled time (never subtracted
        from the song clock — purely a local nudge). 0 for non-notes."""
        h = getConfig()
        if not h.get("enabled") or getattr(msg, "is_meta", False):
            return 0.0
        if not hasattr(msg, "note"):
            return 0.0

        timing = _num(h, "timing") / 1000.0
        chord = _num(h, "chord") / 1000.0

        isOn = msg.type == "note_on" and getattr(msg, "velocity", 0) > 0
        isOff = msg.type == "note_off" or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0)
        if not (isOn or isOff):
            return 0.0

        # a message with time > 0 starts a new beat cluster -> reset roll counters
        if getattr(msg, "time", 0) > 0:
            self._onIdx = 0
            self._offIdx = 0

        off = 0.0
        if timing > 0:
            off += random.uniform(-timing, timing)
        if isOn:
            if chord > 0:
                off += self._onIdx * chord
            self._onIdx += 1
        else:
            if chord > 0:
                off += self._offIdx * chord
            self._offIdx += 1
        return off
