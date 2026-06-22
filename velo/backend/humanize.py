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
_MAX_TIMING_MS = 30.0     # ± jitter on when a beat/chord lands
_MAX_CHORD_MS = 45.0      # average gap between successive notes of one chord
_MAX_VELOCITY_PCT = 22.0
_MAX_ROLL_MS = 140.0      # cap on a chord's total spread, so big chords stay sane


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
    """Per-playback timing state.

    The key to a believable chord is that its notes must *never* land (or lift)
    on the same instant. So we split the humanization in two:

    * a **shared beat jitter** — the whole cluster of simultaneous notes is
      nudged together by one random ± offset, humanizing *when* the chord hits
      without smearing it apart randomly;
    * a **monotonic roll** — within the cluster each successive note is pushed
      a little further than the previous one by an always-positive random gap,
      so the chord rolls low→high like real fingers and the random jitter can
      never cancel the spread back to unison.

    Onsets and releases roll independently, so chords don't release as a block
    either. Nothing is fed back into the song clock, so tempo never drifts."""

    def __init__(self):
        self._onJitter = 0.0    # shared beat jitter for the current onset cluster
        self._offJitter = 0.0   # ... and for the current release cluster
        self._onRoll = 0.0      # cumulative spread among this cluster's onsets
        self._offRoll = 0.0     # ... and among its releases

    def offset(self, msg):
        """Seconds to add to this message's scheduled time (never subtracted
        from the song clock). 0 for non-notes / when off."""
        timing, chord, _ = _params()
        if timing <= 0 and chord <= 0:
            return 0.0

        # any real time advance opens a new cluster: re-roll the shared beat
        # jitter and reset the spread. Done even for control/meta messages so
        # the notes that share their beat stay anchored to the same jitter.
        if getattr(msg, "time", 0) > 0:
            self._onJitter = random.uniform(-timing, timing) if timing > 0 else 0.0
            self._offJitter = random.uniform(-timing, timing) if timing > 0 else 0.0
            self._onRoll = 0.0
            self._offRoll = 0.0

        if getattr(msg, "is_meta", False) or not hasattr(msg, "note"):
            return 0.0

        isOn = msg.type == "note_on" and getattr(msg, "velocity", 0) > 0
        isOff = msg.type == "note_off" or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0)
        if not (isOn or isOff):
            return 0.0

        cap = _MAX_ROLL_MS / 1000.0
        if isOn:
            off = self._onJitter + self._onRoll
            if chord > 0:
                self._onRoll = min(cap, self._onRoll + random.uniform(0.6 * chord, 1.4 * chord))
            return off
        else:
            # releases breathe even more than presses — lift a touch looser
            off = self._offJitter + self._offRoll
            if chord > 0:
                self._offRoll = min(cap, self._offRoll + random.uniform(0.7 * chord, 1.6 * chord))
            return off
