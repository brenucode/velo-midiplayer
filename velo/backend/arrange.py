"""Play-style arranger for the autoplayer (shared by the QWERTY and MIDI-out
engines).

Mirrors Practice's Arrange control, but for the autoplayer that *performs* the
song. It never changes WHICH key a note maps to — it only decides which notes
of a simultaneous chord actually get played:

  * "faith" — every note, exactly as written (default; no change).
  * "bal"   — keep the bass + melody and thin dense chords down to a small cap,
              so the performance looks lighter and less like an autoplayer.
  * "easy"  — melody only: the top note of each chord.

Both engines call ``on_suppress_sets()`` once at the start of a play pass to
precompute, for EACH style, the note_on indices to drop. The play loop then
reads the live ``arrangeMode`` per note and pairs each note_off with its note_on
at runtime — so the user can switch styles mid-song (a hotkey) and it takes
effect on the very next note with no restart, no gap, and no stuck keys.
"""

from velo.backend import config as configuration

VALID_MODES = ("faith", "bal", "easy")

# note_ons whose onsets fall within this window (seconds) count as one chord
CHORD_WINDOW = 0.03
# Balanced: at most this many notes survive per chord (bass + melody + inner)
BAL_MAX_NOTES = 3


def current_mode():
    mode = configuration.configData["midiPlayer"].get("arrangeMode", "faith")
    return mode if mode in VALID_MODES else "faith"


def _note_playable(note):
    """True if this MIDI note maps to a key under the current keyboard settings
    (mirrors the range check both engines already do before playing a note)."""
    mp = configuration.configData["midiPlayer"]
    maps = mp["pianoMap"]
    s = str(note)
    if s in maps["61keyMap"]:
        return True
    if mp["88Keys"] and (s in maps["88keyMap"]["lowNotes"] or s in maps["88keyMap"]["highNotes"]):
        return True
    return False


def _keep_pitches(pitches, mode):
    """Given one chord's pitches (ascending), return the set of pitches to KEEP."""
    if mode == "easy":
        return {pitches[-1]}                       # melody = the top note
    # balanced: always keep bass + melody, then fill inner voices from the top
    # down until we hit the cap
    if len(pitches) <= BAL_MAX_NOTES:
        return set(pitches)
    keep = {pitches[0], pitches[-1]}
    for p in sorted(pitches[1:-1], reverse=True):
        if len(keep) >= BAL_MAX_NOTES:
            break
        keep.add(p)
    return keep


def on_suppress_sets(messages):
    """Precompute, for every play style, the set of note_on indices to drop.

    ``messages`` is the fully-expanded event list (``list(mido.MidiFile(...))``),
    where each message carries a real-time ``.time`` delta. Returns
    ``{"faith": frozenset(), "bal": frozenset(...), "easy": frozenset(...)}`` in
    a single chord-grouping pass, so the play loop can switch styles for free.

    Only note_ons are decided here; the loop pairs each note_off with its note_on
    at runtime (so a mid-song switch never leaves a key stuck).
    """
    bal, easy = set(), set()

    # absolute onset time of every message (cumulative delta)
    abs_t = []
    acc = 0.0
    for m in messages:
        acc += m.time
        abs_t.append(acc)

    # playable note-on events, in time order
    ons = [(i, m.note) for i, m in enumerate(messages)
           if m.type == "note_on" and m.velocity > 0 and _note_playable(m.note)]

    i = 0
    while i < len(ons):
        anchor = abs_t[ons[i][0]]
        j = i
        chord = []
        while j < len(ons) and abs_t[ons[j][0]] - anchor <= CHORD_WINDOW:
            chord.append(ons[j])
            j += 1
        if len(chord) > 1:
            pitches = sorted(p for _, p in chord)
            keep_bal = _keep_pitches(pitches, "bal")
            keep_easy = _keep_pitches(pitches, "easy")
            used_bal, used_easy = set(), set()
            for idx, p in chord:
                if p in keep_bal and p not in used_bal:
                    used_bal.add(p)                # keep the first note-on per kept pitch
                else:
                    bal.add(idx)
                if p in keep_easy and p not in used_easy:
                    used_easy.add(p)
                else:
                    easy.add(idx)
        i = j

    return {"faith": frozenset(), "bal": frozenset(bal), "easy": frozenset(easy)}
