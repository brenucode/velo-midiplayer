"""Passive MIDI input for Practice mode.

Reads note on/off from a MIDI device and forwards them to the UI as
``practiceMidiNote`` events. Unlike ``qwerty_input`` (the MIDI -> Keys feature),
this NEVER presses any keyboard keys — it only reports what was played, so the
practice trainer can match it. Fully self-contained so it can't affect the
MIDI -> Keys engine.
"""

import threading
import time

try:                      # a missing mido/backend must degrade, not crash import
    import mido
except Exception:
    mido = None

_port = None
_thread = None
_stop = threading.Event()
_emit = None
_lock = threading.Lock()


def list_devices():
    if mido is None:
        return []
    try:
        return list(dict.fromkeys(mido.get_input_names()))
    except Exception:
        return []


def start(device, emit):
    """Open ``device`` and stream note events via emit(). Returns True on success."""
    global _port, _thread, _emit
    if mido is None:
        return False
    stop()                      # make sure any previous listener is fully gone
    with _lock:
        _emit = emit
        _stop.clear()
        try:
            _port = mido.open_input(device) if device else mido.open_input()
        except Exception:
            _port = None
            return False
        port = _port

    def loop():
        # Poll instead of the blocking `for msg in port`: that way we re-check the
        # stop flag every couple ms and exit cleanly even on an idle device (a
        # blocking iterator would hang until the next message / port teardown).
        try:
            while not _stop.is_set():
                try:
                    msg = port.poll()
                except Exception:
                    break
                if msg is None:
                    time.sleep(0.002)
                    continue
                if msg.type in ("note_on", "note_off"):
                    on = (msg.type == "note_on" and msg.velocity > 0)
                    cb = _emit
                    if cb:
                        try:
                            cb("practiceMidiNote",
                               {"note": int(msg.note), "on": bool(on),
                                "vel": int(getattr(msg, "velocity", 0))})
                        except Exception:
                            pass
        except Exception:
            pass

    with _lock:
        _thread = threading.Thread(target=loop, daemon=True)
        _thread.start()
    return True


def stop():
    global _port, _thread, _emit
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=0.5)     # wait for the poll loop to exit before closing
    if _port is not None:
        try:
            _port.close()
        except Exception:
            pass
    _port = None
    _thread = None
    _emit = None
