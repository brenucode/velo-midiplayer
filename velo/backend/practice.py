"""Practice mode — turns a MIDI file into an ordered sequence of "steps".

A step is one chord: the set of notes whose ``note_on`` events land at (nearly)
the same instant. The UI walks these steps one by one, waiting for the player to
press the right QWERTY keys before advancing — like a Synthesia practice mode,
but training the computer-keyboard mapping the app actually uses to play.

The note -> key mapping mirrors qwerty_engine.simulateKey's key selection, so the
characters shown here are exactly the keys the engine would press for real.
"""

import mido

from velo.backend import config as configuration

# Notes that fall within ~30ms of the chord's first note are treated as played
# together (a real chord), anything later starts a new step.
CHORD_WINDOW = 0.03
MAX_STEPS = 6000


def _maps():
    mp = configuration.configData["midiPlayer"]["pianoMap"]
    allow88 = bool(configuration.configData["midiPlayer"].get("88Keys", True))
    return mp, allow88


def noteToChar(note, mp, allow88):
    """The QWERTY character the engine presses for this MIDI note, or None if the
    note is out of the active mapping's range."""
    s = str(note)
    k61 = mp["61keyMap"]
    if s in k61:
        return k61[s]
    if allow88:
        low = mp["88keyMap"]["lowNotes"]
        high = mp["88keyMap"]["highNotes"]
        if s in low:
            return low[s]
        if s in high:
            return high[s]
    return None


def fullMap():
    """note number -> QWERTY char for every note in the active mapping (used to
    label the on-screen piano)."""
    mp, allow88 = _maps()
    out = {}
    for s, ch in mp["61keyMap"].items():
        out[int(s)] = ch
    if allow88:
        for s, ch in mp["88keyMap"]["lowNotes"].items():
            out.setdefault(int(s), ch)
        for s, ch in mp["88keyMap"]["highNotes"].items():
            out.setdefault(int(s), ch)
    return out


def songDuration(path):
    try:
        return round(mido.MidiFile(path, clip=True).length, 3)
    except Exception:
        return 0


def buildSteps(path):
    """Returns an ordered list of chord steps:
        [{"t": onsetSeconds, "notes": [{"note", "char"}, ...]}, ...]
    ``t`` lets the time-based modes (rhythm, live visualizer) place notes on a
    real timeline; the step trainer just walks the list and ignores ``t``."""
    mp, allow88 = _maps()
    mid = mido.MidiFile(path, clip=True)

    t = 0.0
    steps = []
    curNotes = None
    curStart = 0.0

    def flush():
        if curNotes:
            steps.append({"t": round(curStart, 4), "notes": curNotes})

    for msg in mid:
        t += msg.time
        if msg.is_meta:
            continue
        if msg.type != "note_on" or msg.velocity <= 0:
            continue
        ch = noteToChar(msg.note, mp, allow88)
        if ch is None:
            continue  # out of range for the current key map — skip, like the engine

        if curNotes is not None and (t - curStart) <= CHORD_WINDOW:
            if not any(n["note"] == msg.note for n in curNotes):
                curNotes.append({"note": msg.note, "char": ch})
        else:
            flush()
            curNotes = [{"note": msg.note, "char": ch}]
            curStart = t

        if len(steps) >= MAX_STEPS:
            curNotes = None
            break

    flush()
    return steps
