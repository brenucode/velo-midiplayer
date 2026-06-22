"""Humanizer — makes playback feel played, not computed.

Perfect-grid MIDI is robotic because every note lands exactly on time, chords
hit and release in unison, and every note has identical force. Worse, a *fixed*
amount of "humanization" still sounds mechanical, because the deviation is
always the same shape. Real playing is **inconsistent**: one chord is tight,
the next is rolled wide, a note lags, and the whole tempo breathes.

So instead of one intensity knob this exposes **profiles**, and within a profile
everything is re-randomised constantly:

* **per-chord character** — each chord independently draws its own spread: some
  land nearly block-tight, others roll wide, so no two chords feel alike.
* **monotonic roll** — within a chord each successive note gets an always-
  positive gap (low->high), so the random jitter can never collapse it back to
  unison; onsets and releases roll independently.
* **beat jitter** — the chord as a whole is nudged early/late.
* **rubato** — a slow, bounded random-walk that makes the tempo drift ahead and
  behind over time (mean-reverting, so the song never runs away).
* **velocity** — each note's force varies within the profile's range.

Nothing is fed back into the song clock; offsets are local nudges, so the
overall duration stays put.
"""

import random

from velo.backend import config as configuration

# The user controls four 0-100 sliders; each maps onto a real magnitude here
# (full = slider at 100). Profiles are just presets that fill those sliders.
_MAX_GAP_MS = 145.0      # widest average per-note chord gap
_MAX_TIMING_MS = 80.0    # widest ± beat jitter
_MAX_DRIFT_MS = 75.0     # widest rubato wander
_MAX_VEL_PCT = 42.0      # widest ± velocity swing

# Presets in slider units (roll / timing / rubato / velocity, each 0-100).
PRESETS = {
    "moderate": {"roll": 43, "timing": 40, "rubato": 29, "velocity": 52},
    "loose":    {"roll": 68, "timing": 69, "rubato": 60, "velocity": 71},
    "extreme":  {"roll": 100, "timing": 100, "rubato": 100, "velocity": 95},
}
DEFAULTS = {"on": False, "profile": "moderate",
            "roll": 43, "timing": 40, "rubato": 29, "velocity": 52}


def _cfg():
    h = configuration.configData.get("midiPlayer", {}).get("humanize")
    return h if isinstance(h, dict) else {}


def _slider(h, key):
    try:
        return max(0.0, min(100.0, float(h.get(key, 0)))) / 100.0
    except Exception:
        return 0.0


def _active():
    """Resolve the four sliders into real magnitudes, or None when off."""
    h = _cfg()
    if not h.get("on"):
        return None
    gapMax = _MAX_GAP_MS * _slider(h, "roll")
    return {
        "timing": _MAX_TIMING_MS * _slider(h, "timing"),
        "gapMin": gapMax * 0.4,
        "gapMax": gapMax,
        "tightProb": 0.2,
        "rollCap": max(120.0, gapMax * 4.0),
        "driftMax": _MAX_DRIFT_MS * _slider(h, "rubato"),
        "driftStep": _MAX_DRIFT_MS * _slider(h, "rubato") * 0.35,
        "vel": _MAX_VEL_PCT * _slider(h, "velocity"),
    }


def jitterVelocity(velocity):
    """Return ``velocity`` nudged within the active range (1..127)."""
    if velocity <= 0:
        return velocity
    p = _active()
    if not p or p["vel"] <= 0:
        return velocity
    factor = 1.0 + random.uniform(-p["vel"] / 100.0, p["vel"] / 100.0)
    return max(1, min(127, int(round(velocity * factor))))


class Humanizer:
    """Per-playback timing state (one instance per run)."""

    def __init__(self):
        self._drift = 0.0       # rubato: slowly wandering tempo offset (s)
        self._onJitter = 0.0    # this onset-cluster's shared beat nudge (s)
        self._offJitter = 0.0   # this release-cluster's shared beat nudge (s)
        self._gap = 0.0         # this chord's per-note roll gap (s)
        self._onRoll = 0.0      # cumulative onset spread so far (s)
        self._offRoll = 0.0     # cumulative release spread so far (s)

    def _newCluster(self, p):
        # rubato: mean-reverting bounded random walk
        driftMax = p["driftMax"] / 1000.0
        self._drift += random.uniform(-p["driftStep"], p["driftStep"]) / 1000.0
        self._drift -= self._drift * 0.15          # pull back toward centre
        self._drift = max(-driftMax, min(driftMax, self._drift))

        timing = p["timing"] / 1000.0
        self._onJitter = random.uniform(-timing, timing)
        self._offJitter = random.uniform(-timing, timing)

        # per-chord character: sometimes tight/block, sometimes rolled wide
        if random.random() < p["tightProb"]:
            self._gap = random.uniform(2, 9) / 1000.0
        else:
            self._gap = random.uniform(p["gapMin"], p["gapMax"]) / 1000.0
        self._onRoll = 0.0
        self._offRoll = 0.0

    def offset(self, msg):
        """Seconds to add to this message's scheduled time. 0 when off."""
        p = _active()
        if p is None:
            return 0.0

        if getattr(msg, "time", 0) > 0:
            self._newCluster(p)

        if getattr(msg, "is_meta", False) or not hasattr(msg, "note"):
            return 0.0

        isOn = msg.type == "note_on" and getattr(msg, "velocity", 0) > 0
        isOff = msg.type == "note_off" or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0)
        if not (isOn or isOff):
            return 0.0

        cap = p["rollCap"] / 1000.0
        if isOn:
            off = self._drift + self._onJitter + self._onRoll
            self._onRoll = min(cap, self._onRoll + random.uniform(0.6, 1.4) * self._gap)
            return off
        # releases breathe a touch wider than presses
        off = self._drift + self._offJitter + self._offRoll
        self._offRoll = min(cap, self._offRoll + random.uniform(0.7, 1.7) * self._gap)
        return off
