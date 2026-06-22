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

# All magnitudes in milliseconds. Each profile is a *character*, not a single
# value — the bands below are sampled fresh per chord, so intensity wanders.
PROFILES = {
    "moderate": {"timing": 32, "gapMin": 28, "gapMax": 62, "tightProb": 0.25,
                 "rollCap": 240, "driftStep": 9, "driftMax": 22, "vel": 22},
    "loose":    {"timing": 55, "gapMin": 48, "gapMax": 98, "tightProb": 0.20,
                 "rollCap": 430, "driftStep": 16, "driftMax": 45, "vel": 30},
    "extreme":  {"timing": 80, "gapMin": 72, "gapMax": 145, "tightProb": 0.16,
                 "rollCap": 640, "driftStep": 26, "driftMax": 75, "vel": 40},
}
DEFAULT_PROFILE = "off"
_ORDER = ("off", "moderate", "loose", "extreme")


def profileName():
    h = configuration.configData.get("midiPlayer", {}).get("humanize")
    if not isinstance(h, dict):
        return "off"
    p = h.get("profile", "off")
    return p if p in _ORDER else "off"


def _profile():
    return PROFILES.get(profileName())   # None when off


def jitterVelocity(velocity):
    """Return ``velocity`` nudged within the active profile's range (1..127)."""
    if velocity <= 0:
        return velocity
    p = _profile()
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
        p = _profile()
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
