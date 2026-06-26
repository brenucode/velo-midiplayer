# Velo on Linux

Velo runs on Linux. Most of it — the player, in-app piano sound, **Practice**,
**Stage / Free-play**, the MIDI **Hub** (downloads), queue, speed, humanizer —
works the same as on Windows, because the whole UI is a web app rendered by
**WebKitGTK** with Web Audio for sound.

Two honest caveats up front:

1. **"Type the song into another app" (Roblox / Virtual Piano) needs X11.**
   Sending keystrokes into *another* window is blocked by **Wayland** on
   purpose. On an **X11 / Xorg** session it works with no root. On Wayland that
   one feature won't reach the other app — everything else still works. (At the
   login screen, pick "Xorg" / "X11" via the gear icon to switch.)
2. **MIDI-output mode needs a synth.** Unlike Windows, Linux has no built-in
   MIDI synthesizer. If you want to drive a real synth via "MIDI output" mode,
   install **FluidSynth** (below). For just hearing Velo, the in-app sound needs
   nothing extra.

There are two ways to run Velo on Linux: **the AppImage** (easiest) or **from
source** (what you'll use while we polish it).

---

## Option A — AppImage (recommended once released)

Download `Velo-x86_64.AppImage` from the
[Releases page](https://github.com/brenucode/velo-midiplayer/releases), then:

```bash
chmod +x Velo-x86_64.AppImage
./Velo-x86_64.AppImage
```

That's it — the AppImage bundles Python and all deps. (You still need WebKitGTK
from your distro; see the package list below — most desktops already have it.)

---

## Option B — Run from source

### 1) Install the system packages (GTK + WebKit + PyGObject)

**Fedora**
```bash
sudo dnf install python3 python3-gobject gtk3 webkit2gtk4.1 alsa-lib
```

**Ubuntu / Debian**
```bash
sudo apt install python3 python3-venv python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libasound2
```
> Older releases ship WebKit **4.0** instead of 4.1 — install
> `gir1.2-webkit2-4.0` if 4.1 isn't found. Velo handles either.

**Arch**
```bash
sudo pacman -S python python-gobject gtk3 webkit2gtk-4.1 alsa-lib
```

### 2) Run it

```bash
./run-linux.sh
```

The script makes a `venv-lnx` virtualenv (with `--system-site-packages` so it
can see the GTK/WebKit bindings you just installed), installs the Python deps
from `requirements-linux.txt`, and launches Velo. Re-running is cheap.

If you prefer to do it by hand:
```bash
python3 -m venv --system-site-packages venv-lnx
source venv-lnx/bin/activate
pip install -r requirements-linux.txt
python velo_app.py
```

---

## Optional — real MIDI output with FluidSynth

Only needed if you turn on **"MIDI output"** mode (to play through a software
synth instead of typing keys). Install FluidSynth + a soundfont and start it as
an ALSA synth; Velo will list it as an output device:

```bash
# Fedora:        sudo dnf install fluidsynth fluid-soundfont-gm
# Ubuntu/Debian: sudo apt install fluidsynth fluid-soundfont-gm
# Arch:          sudo pacman -S fluidsynth soundfont-fluid

fluidsynth -a alsa -m alsa_seq -g 1.0 /usr/share/soundfonts/default.sf2 &
```
Then in Velo: enable **MIDI output**, pick the FluidSynth device, press play.

---

## Where Velo stores your data

- Config + downloaded MIDIs: `~/.local/share/Velo/` (the XDG location).
  *(On Windows it's `~/Documents/Velo` — Linux follows the XDG convention.)*

---

## Troubleshooting

- **Window doesn't open / `Namespace WebKit2 not available`** → WebKit2GTK isn't
  installed (or it's 4.0 and you only have the 4.1 dev binding, or vice-versa).
  Install the matching `webkit2gtk` package from the list above.
- **No sound in MIDI-output mode** → that mode needs a running synth; see the
  FluidSynth section. The in-app piano sound doesn't.
- **"Typing into the game does nothing"** → you're on Wayland. Log in with an
  X11/Xorg session for that feature (the title-bar tells you the session, and
  Velo logs a reminder when you start playback).
- **`python-rtmidi` fails to install** → install your distro's ALSA dev headers
  (`alsa-lib-devel` on Fedora, `libasound2-dev` on Debian/Ubuntu) and retry.

Found a bug? Tell us in the [Discord](https://discord.gg/velomidi) — Linux
support is new and your report genuinely helps. 🎹
