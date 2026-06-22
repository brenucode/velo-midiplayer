"""Humanizer — makes playback feel less robotic.

A real player never hits or releases the notes of a chord at the exact same
millisecond, and never plays two notes with identical force. MIDI playback,
being mathematically perfect, sounds mechanical. This module adds three small
imperfections, all driven by a single **amount** knob (0-100):

* **timing**   — random jitter (± ms) on every note's onset *and* release.
* **chord**    — a tiny progressive offset across notes on the same beat
  (onsets *and* releases), so chords "roll" instead of snapping together.
* **velocity** — random ± % on each note's force (MIDI-out volume and the
  in-app piano sound; QWERTY keystrokes have no force, so there only the
  timing/chord parts apply).

One slider scales all three together along a calibrated curve — 0 is the exact
mechanical original, 100 is loose/expressive. Offsets are applied per note and
never accumulated into the song clock, so the overall tempo never drifts: each
note just breathes a little around its true position.
"""

import random

from velo.backend import config as configuration

DEFAULT_AMOUNT = 45

# the three effects at full strength (amount = 100); everything below scales
# linearly from these
_MAX_TIMING_MS = 35.0
_MAX_CHORD_MS = 30.0
_MAX_VELOCITY_PCT = 22.0


def amount():
    """The single 0-100 humanize knob (0 = off)."""
    h = configuration.configData.get("midiPlayer", {}).get("humanize")
    if not isinstance(h, dict):
        return 0.0
    try:
        return max(0.0, min(100.0, float(h.get("amount", 0))))
    except Exception:
        return 0.0


def _params():
    """(timing_seconds, chord_seconds, velocity_percent) for the current knob."""
    frac = amount() / 100.0
    return (_MAX_TIMING_MS * frac / 1000.0,
            _MAX_CHORD_MS * frac / 1000.0,
            _MAX_VELOCITY_PCT * frac)


def jitterVelocity(velocity):
    """Return ``velocity`` nudged by a random ± percentage (clamped 1..127)."""
    if velocity <= 0:
        return velocity
    pct = _params()[2]
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
        from the song clock — purely a local nudge). 0 for non-notes / off."""
        if getattr(msg, "is_meta", False) or not hasattr(msg, "note"):
            return 0.0
        timing, chord, _ = _params()
        if timing <= 0 and chord <= 0:
            return 0.0

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
