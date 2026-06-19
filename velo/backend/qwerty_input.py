"""Live MIDI -> QWERTY controller — manages the input engine + events."""

import logging

from velo.backend import config as configuration
from velo.backend import qwerty_input_engine as engine
from velo.backend.logbus import LogBus

logger = logging.getLogger("velo.input")


class InputController:
    def __init__(self, emit):
        self.emit = emit
        self._bus = LogBus(emit, "input")
        self.log = self._bus.log
        engine.log = self._bus.log
        engine.onNote = self._onNote
        self.running = False

    def _onNote(self, note, velocity, isOn):
        self.emit("inputNote", {"note": note, "on": isOn})

    def listDevices(self):
        return engine.listInputDevices()

    def setDevice(self, name):
        configuration.configData["midiToQwerty"]["inputDevice"] = name
        configuration.save()
        return self.getState()

    def setOption(self, key, value):
        configuration.configData["midiToQwerty"][key] = bool(value)
        configuration.save()
        self._emit()
        return self.getState()

    def start(self):
        if self.running:
            return self.getState()
        device = configuration.configData["midiToQwerty"].get("inputDevice", "")
        devices = self.listDevices()
        if not device or device not in devices:
            device = devices[0] if devices else None
        if not device:
            self.log("No MIDI input device available.")
            return self.getState()
        configuration.configData["midiToQwerty"]["inputDevice"] = device
        configuration.save()
        thread = engine.startMidiInput(device)
        self.running = thread is not None
        self._emit()
        return self.getState()

    def stop(self):
        if not self.running:
            return self.getState()
        engine.stopMidiInput()
        self.running = False
        self._emit()
        return self.getState()

    def toggle(self):
        return self.stop() if self.running else self.start()

    def getState(self):
        mq = configuration.configData["midiToQwerty"]
        return {
            "running": self.running,
            "devices": self.listDevices(),
            "device": mq.get("inputDevice", ""),
            "options": {
                "velocity": bool(mq.get("velocity", False)),
                "sustain": bool(mq.get("sustain", False)),
                "noDoubles": bool(mq.get("noDoubles", False)),
            },
        }

    def _emit(self):
        try:
            self.emit("inputState", self.getState())
        except Exception:
            pass
