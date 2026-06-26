# Velo on Linux

Velo runs great on Linux. The whole UI, the in-app piano **sound**, **Practice**,
**Stage / Free-play**, the MIDI **Hub** (downloads), the queue, speed and the
humanizer all work — because the interface is a web app rendered by your
system's **WebKitGTK** with Web Audio for sound.

## Install (one command)

Open a terminal and run:

```bash
git clone https://github.com/brenucode/velo-midiplayer.git
cd velo-midiplayer
./install-linux.sh
```

That's it. The installer:

- installs the system libraries Velo needs (GTK 3, WebKit2GTK, PyGObject, ALSA)
  using your distro's package manager — **Fedora, Ubuntu/Debian, Arch and
  openSUSE** are all handled (it asks for your sudo password),
- sets up a private Python environment,
- adds **Velo** to your applications menu with an icon.

When it finishes, just **search "Velo" in your apps menu** and launch it like any
other app. (You can also type `velo` in a terminal.)

> Why an installer instead of a single-file download? Velo uses **your system's
> WebKit**. Bundling WebKit into one binary is the fragile part of Linux
> packaging — using the system's is what makes it reliable across distros.

## Two things worth knowing

1. **"Type the song into another app" needs X11.** Sending keystrokes into
   *another* window (Roblox / Virtual Piano) is blocked by **Wayland** on
   purpose. On an **X11 / Xorg** session it works with no root. On Wayland that
   one feature won't reach the other app — everything else still works. (At the
   login screen, click the gear icon and pick "Xorg" / "X11" to switch.)
2. **MIDI-output mode wants a synth.** To drive a real software synth via the
   "MIDI output" toggle, install **FluidSynth** (optional — the in-app sound
   needs nothing extra):
   ```bash
   # Fedora:        sudo dnf install fluidsynth fluid-soundfont-gm
   # Ubuntu/Debian: sudo apt install fluidsynth fluid-soundfont-gm
   # Arch:          sudo pacman -S fluidsynth soundfont-fluid
   fluidsynth -a alsa -m alsa_seq -g 1.0 /usr/share/soundfonts/default.sf2 &
   ```
   Then enable **MIDI output** in Velo and pick the FluidSynth device.

## Where Velo stores your data

- Config + downloaded MIDIs: `~/.local/share/Velo/` (the XDG location).
  *(On Windows it's `~/Documents/Velo`; Linux follows the XDG convention.)*

## Updating

```bash
cd velo-midiplayer
git pull
./install-linux.sh    # safe to re-run; reuses the existing environment
```

## Troubleshooting

- **Window doesn't open / `Namespace WebKit2 not available`** → WebKitGTK isn't
  installed. Fedora: `sudo dnf install webkit2gtk4.1` · Ubuntu/Debian:
  `sudo apt install gir1.2-webkit2-4.1` (or `-4.0`) · Arch:
  `sudo pacman -S webkit2gtk-4.1`. Then re-run `./install-linux.sh`.
- **No sound in "MIDI output" mode** → that mode needs a running synth; see
  FluidSynth above. The in-app piano sound doesn't.
- **"Typing into the game does nothing"** → you're on Wayland. Log in with an
  X11/Xorg session for that feature.
- **`python-rtmidi` failed to install** → only affects "MIDI output" mode; the
  app still runs. To fix it, make sure your distro's ALSA dev headers and a C
  compiler are installed (the installer already tries), then re-run.

Found a bug? Tell us in the [Discord](https://discord.gg/velomidi) — Linux
support is new and your report genuinely helps. 🎹
