<p align="center">
  <img src="assets/velo-banner.svg" alt="Velo" width="100%" />
</p>

<p align="center">
  <strong>A clean MIDI player — with a practice studio and stage mode.</strong><br/>
  Plays MIDI by converting it to keystrokes (for virtual pianos in games) or to MIDI output.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-1c1c23?style=flat-square" />
  <img src="https://img.shields.io/badge/version-v1.1-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/license-GPL%20v3-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/made%20by-brenu-1c1c23?style=flat-square" />
</p>

---

**Velo** started from a simple itch: play MIDI in an interface that doesn't look like 2009 software. A clean player, an online song library, a practice mode that feels like a little game, and a stage mode to look good on stream. No bloat, no annoying install — open it and it works.

## 🆕 What's new in v1.1

- 🎭 **Humanizer** — playback no longer sounds like a robot. A profile (Subtle / Moderate / Loose) plus fine sliders add human imperfection: chords roll instead of hitting in unison, the timing of each note and release wanders, the tempo gently breathes (rubato), and the force varies — re-randomised every chord so it never repeats. Your settings are saved.
- 🌐 **Online Sequencer in the MIDI Hub** — search and download from [onlinesequencer.net](https://onlinesequencer.net) right inside Velo, alongside nanoMIDI and BitMidi.
- ▦ **Stage now plays the piano** — the visualizer voices the song as the notes cross, not just light up.
- 🔊 **Shows up as "Velo"** (with its icon) in the Windows volume mixer, instead of "Microsoft Edge WebView2".
- ✅ **Runs straight from a download** — Velo clears the Windows "downloaded file" block itself, so a freshly unzipped copy just opens.

## 📸 Screenshots

<p align="center">
  <img src="docs/player.png" alt="Velo — MIDI Player" width="100%" />
</p>

<table>
  <tr>
    <td width="50%" valign="top"><img src="docs/practice.png" alt="Practice — Rhythm mode" /><br/><sub><b>Practice (Rhythm)</b> — notes fall onto the keys; hit them in time.</sub></td>
    <td width="50%" valign="top"><img src="docs/stage.png" alt="Stage mode" /><br/><sub><b>Stage</b> — fullscreen visualizer, great for streaming.</sub></td>
  </tr>
</table>

## ✨ What it does

- 🎹 **Player** — plays MIDI via **keyboard (QWERTY)** or **MIDI output**. Song queue, speed control, previous/next, and **global hotkeys** that work even with the app in the background.
- 🎯 **Practice** — three modes on a 61-key piano that lights up which key to press:
  - **Step** — learn note by note, at your own pace. Miss it? It waits until you get it right.
  - **Rhythm** — turns into a rhythm game: notes fall in time, with **Perfect / Good / Miss**, combo, multiplier and a life bar.
  - **Free play** — a free piano (keyboard or mouse), with **rising trails** on every note and a **preview** that plays the song for you.
  - **Section trainer** — pick the hard part and drill it in **slow motion that speeds up** as you nail it.
- 🌐 **MIDI Hub** — search and download songs from three libraries without leaving Velo: the **nanoMIDI** library, **Online Sequencer**, and **BitMidi**. Pick the source from the dropdown; results show up in Velo's own UI.
- ▦ **Stage mode** — notes fall onto a **fullscreen** piano and the song **plays as they cross**, synced to what's playing. Perfect to leave on screen for Discord/streaming.
- 🎭 **Humanizer** — optional human feel: chord roll, timing/release wander, rubato and velocity variation, with profiles + sliders. Off by default (exact, mechanical original).
- 🥁 **Drums** and ⌨️ **MIDI → Keys** — turn a MIDI controller into a keyboard in real time.
- 🔊 **Real sound** — several **piano** models (Grand, Bright, Electric…) plus a **Cherry MX** mechanical-keyboard sound.
- 🏆 **Records** per song · 🖥️ **responsive** layout + **fullscreen (F11)**.

## ⬇️ Download (ready to use)

> No Python, nothing to install.

1. Go to **[Releases](../../releases)** and download `Velo-win.zip`.
2. Extract the folder anywhere.
3. Open **`Velo.exe`**.

Requires **Windows 10/11** with the **WebView2 Runtime** (already bundled in up-to-date Windows; if missing, Windows Update installs it, or grab it free from Microsoft).

<details>
<summary><b>It won't start? (rare)</b></summary>

Velo automatically removes the "downloaded from the internet" mark from its own files on first launch, so it should just work. If it still won't open:

- **Antivirus quarantined a file** — Velo is an unsigned app, so some antivirus tools remove a file by mistake. Check that `Velo\_internal\pythonnet\runtime\Python.Runtime.dll` still exists; if it's gone, restore it from quarantine and add the Velo folder as an exception.
- **Still blocked** — right-click `Velo-win.zip` → **Properties** → tick **Unblock** → **OK**, then extract again.
- **Missing .NET Framework** — on stripped Windows editions (N / LTSC), install the free **.NET Framework 4.8** from Microsoft.

</details>

## ⌨️ Global hotkeys

| Key  | Action |
|:----:|--------|
| `F1` | Play / Pause |
| `F2` | Pause |
| `F3` | Stop |
| `F4` | Speed up |
| `F5` | Slow down |
| `F6` | Previous track |
| `F7` | Next track |

You can remap any of them in **Settings**. They work even when Velo is minimized — handy for controlling it while you're in a game.

## 🧭 How to use

### 1. Play a song
1. **Player** tab → **Open** (or drag a `.mid` onto the window).
2. **Play** (or `F1`). Velo "types" the song into your virtual piano keys.
3. Want to play in a game (Roblox, etc.)? Keep the game focused and use the hotkeys — the keystrokes go to it.

> **QWERTY vs MIDI Output:** choose at the top of the Player. *QWERTY* simulates the keyboard (for in-game pianos). *MIDI Output* sends to an instrument/DAW via a MIDI port.

### 2. Download songs (MIDI Hub)
1. **MIDI Hub** tab → pick a source (**nanoMIDI**, **Online Sequencer** or **BitMidi**) and search by name.
2. Click the ↓ on a song — it downloads and drops straight into your queue.

> **Online Sequencer:** the first search opens a one-time check in a small window (it usually clears itself in a few seconds); after that, searching and downloading happen entirely inside Velo.

### 3. Practice
1. **Practice** tab → pick a mode (**Step / Rhythm / Free play**) and a song.
2. The on-screen keyboard lights up the right keys (sharps = **Shift**).
   - **Step:** press in sequence, no rush.
   - **Rhythm:** hit each note as it reaches the line.
   - **Free play:** play freely; pick a song and hit **Play (preview)** to watch it play itself.
3. **Section trainer:** toggle it on and drag the handles to drill just one part, slowly.

### 4. Stage mode (visualizer)
On the **Player**, click **Stage** (or `F11` for fullscreen). Hit play on a song and the notes fall onto the piano and play as they cross, in sync — great for streaming.

> Tip: turn on **Humanize** (Settings) for a less robotic, more played feel.

### 5. 🎙️ Sound like you're playing live (Discord / stream)
The idea: route Velo's piano sound into your virtual "microphone".

1. Install **[VB-CABLE](https://vb-audio.com/Cable/)** (a free virtual audio cable).
2. In Windows, under **Settings → System → Sound → Volume mixer**, send **Velo**'s output to **`CABLE Input`**.
3. In **Discord / OBS**, pick the microphone **`CABLE Output`**.
4. In Velo, under **Settings → Sound**, turn the sound on (piano or keyboard) and hit play.
5. Done — whoever's listening hears the piano as if it were you playing.

> Want to **talk and play at the same time**? Use **VoiceMeeter** to mix your real mic + Velo's audio into one channel.

### 6. Drums and MIDI → Keys
- **Drums:** same idea as the Player, with a drum map.
- **MIDI → Keys:** plug in a MIDI controller and play — Velo converts it to keystrokes in real time.

## 🛠️ Run from source

Requirements: **Python 3.12** (Windows) and the **WebView2 Runtime**.

```bash
python -m venv venv-win
venv-win\Scripts\activate
pip install -r requirements.txt
python velo_app.py
```

To build the `.exe` (PyInstaller, anti-false-positive setup):

```bash
scripts\build-velo-win.bat
```

The app lands in `dist\Velo\Velo.exe`.

## 🙏 Credits & License

**Velo** — created by **brenu** · [github.com/brenucode](https://github.com/brenucode)
Copyright © 2026 brenu.

Released under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)).

Built upon the playback engine of **[nanoMIDIPlayer](https://github.com/NotHammer043/nanoMIDIPlayer)** (NotHammer043), also licensed under GPLv3 — thanks for the base.

Sounds: **MusyngKite** pianos ([midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts)) and the **Cherry MX** keyboard ([Mechvibes](https://github.com/hainguyents13/mechvibes)).

Song libraries in the MIDI Hub belong to their respective services — **nanoMIDI** ([nanomidi.net](https://nanomidi.net)), **[Online Sequencer](https://onlinesequencer.net)** and **[BitMidi](https://bitmidi.com)**. Velo just gives you a tidy way to search them; all rights stay with them and their uploaders.

<p align="center"><sub>built in my spare time — because not every project needs a reason.</sub></p>
