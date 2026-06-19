"""Buffered log forwarder: batches engine log lines and pushes them to a
specific console in the UI (~12 Hz) so high-rate note logging stays smooth.
"""

import time
import threading


class NoteBus:
    """Batches note on/off events off the playback thread (~12ms) so the tight
    timing loop is never blocked by the (synchronous) evaluate_js bridge call."""

    def __init__(self, emit):
        self.emit = emit
        self._buf = []
        self._lock = threading.Lock()
        threading.Thread(target=self._flush, daemon=True).start()

    def note(self, n, v, on):
        with self._lock:
            self._buf.append({"n": int(n), "v": int(v), "on": bool(on)})
            if len(self._buf) > 600:
                self._buf = self._buf[-600:]

    def _flush(self):
        while True:
            time.sleep(0.012)
            batch = None
            with self._lock:
                if self._buf:
                    batch = self._buf
                    self._buf = []
            if batch:
                try:
                    self.emit("notes", {"events": batch})
                except Exception:
                    pass


class LogBus:
    def __init__(self, emit, target):
        self.emit = emit
        self.target = target
        self._buf = []
        self._lock = threading.Lock()
        threading.Thread(target=self._flush, daemon=True).start()

    def log(self, *args):
        msg = " ".join(str(a) for a in args)
        with self._lock:
            self._buf.append(msg)
            if len(self._buf) > 400:
                self._buf = self._buf[-400:]

    def _flush(self):
        while True:
            time.sleep(0.08)
            lines = None
            with self._lock:
                if self._buf:
                    lines = self._buf
                    self._buf = []
            if lines:
                try:
                    self.emit("log", {"lines": lines, "target": self.target})
                except Exception:
                    pass
