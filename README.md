<p align="center">
  <img src="assets/velo-banner.svg" alt="Velo" width="100%" />
</p>

<p align="center">
  <strong>A MIDI player that types.</strong><br/>
  It plays a song into the piano in your game — or out to a real MIDI port — and it can teach you to play it yourself.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-1c1c23?style=flat-square" />
  <img src="https://img.shields.io/badge/version-v2.7.3-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/license-Proprietary-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/made%20by-brenu-1c1c23?style=flat-square" />
</p>

<p align="center">
  <a href="https://github.com/brenucode/velo-midiplayer/releases/latest"><img src="https://img.shields.io/badge/⬇%20Download%20Velo-c8ff4d?style=for-the-badge&labelColor=1c1c23" /></a>
</p>

---

Velo started because playing MIDI meant using software that looked like it was written in 2009. It's grown a fair bit since — a practice studio, a piano-roll editor, an online library, a stage visualizer — but the centre of it hasn't moved: open it, pick a song, press play.

> ## ⚠️ Your antivirus may call this a keylogger. Here's why, honestly.
>
> Windows SmartScreen and some antivirus tools flag Velo, occasionally with the word **"keylogger"** on the screen. It's a false positive, and the reason is worth understanding rather than just clicking through:
>
> **Velo reads your keyboard on purpose — that is the feature.** It turns typing into piano notes, and it types songs into on-screen pianos. Doing that means listening to the keyboard system-wide, which is the same low-level trick a real keylogger uses. Heuristics can't tell "makes music" from "steals passwords", so they raise the alarm. Velo never records, stores or sends your keystrokes anywhere, and you don't have to take my word for it: watch its network activity. The only thing it ever reaches out for is the update check.
>
> **And Velo is unsigned.** Making that warning go away costs a code-signing certificate at roughly US$300 a year. Velo is free and made in spare time, so I'd rather you got the scary dialog than that I paid a yearly fee to remove it.
>
> **If it's blocked:**
> - *"Windows protected your PC"* → **More info** → **Run anyway**
> - Antivirus deleted a file → restore it from quarantine (usually `Velo\_internal\pythonnet\runtime\Python.Runtime.dll`) and add the Velo folder as an exception
> - Still blocked → right-click the `.zip` → **Properties** → tick **Unblock** → extract again

## Velo 2.7.3

One fix, and it came from Henrique noticing something I had measured wrong.

- **The animated background stopped juddering.** The drift is deliberately not
  redrawn sixty times a second — doing that used to burn an entire CPU core with
  the app sitting idle. The problem was the replacement: it stepped on a fixed
  clock, five times a second, and each step jumped up to 2.4 px on a 1080p
  screen and more on a bigger one. The comment in the code claimed those steps
  were a fifth of that size, and the test that was supposed to catch it repeated
  the same wrong arithmetic. It now paces itself by how far the layer actually
  moved, so no step crosses a single pixel, and it costs a fraction of what
  redrawing everything would.

## Velo 2.7.2

All Practice this time.

- **Arrange came back when you play with a MIDI keyboard.** It used to disappear the moment you switched Input to MIDI, which left you stuck on Faithful — the hardest one — with no way out. Faithful, Balanced and Easy are all there now, whatever you're playing with.
- **Finishing a sheet actually finishes it.** The bar used to fill up one note before the end, and after the last note the sheet just sat there. Now the last note takes it to 100%, and a moment later the sheet comes back ready from the top.
- **The MIDI output was findable only if you already knew where it was.** It lives in the Sound picker, but nothing on the bar said "output", so the ports sat in the list looking like more instruments. There's a heading over them now, and the Sound label reads "Sound / Output" while you're on MIDI input.
- **Practice sharps: Shift or No Shift** (*Settings → Controls → Keyboard*). Shift is how the game really works, so it stays the default. No Shift writes the sheet in lowercase and lets the plain key count, which makes the awkward stretches much easier. Same note either way, and copied or saved sheets don't change.

Almost all of this came from Yami, who kept picking at Practice until it made sense.

## Earlier releases

<details>
<summary><b>What landed in v2.7.1 → v1.8</b></summary>

- **v2.7.1 — fixes:** chords stopped rolling (sending the velocity level was splitting them apart), **Reset Velo** in Settings, sound off finally silent everywhere, the letter sheet keeping its colours through **Save**, Practice reaching a MIDI port, and the console no longer going quiet while Velo's own window is in front.
- **v2.7.0 — two hands, one of them yours.** Play one hand and let Velo play the other; save your whole setup as a **Config** and share it with a code; Velo learned to read **your keyboard's layout** instead of assuming a US one (on a German keyboard the autoplayer had been sending y and z swapped, in every build, for everyone); **Practice can play out through a MIDI port**; **Transcribe** became a tab; Settings was rebuilt into five tabs. It also stopped eating a whole CPU core while sitting idle. From this version on, **Windows is the only platform** — see the Linux and macOS sections.
- **v2.6.2** — the Practice play key sounds on Practice's own piano, three MuseScore import bugs fixed, and the floating helpers stop showing through on Linux.
- **v2.6.1** — searching the library bar stopped skipping playback: seeking asked for a note and got silence, because the engine read the jump forward as being late.
- **v2.6.0 — MuseScore, straight into your library.** Search a song or paste a score link and it's yours, no browser and no account. Track muting stopped hiding until after Play, a recording-friendly mode for capture cards that record a black window, five separate causes of visualizer stutter fixed, macOS hotkeys rebuilt.
- **v2.5.2 — Velo runs on Mac, and four bugs members found:** a MIDI keyboard sending 160 keystrokes where 4 were needed, MIDI → Keys typing into whatever window was focused, half the Player vanishing when you came back, and the Queue showing a song playing when the thread had died.
- **v2.5.1 — Put back what a scan moved.** Velo Scan *moves* files, and only remembered where they came from until you closed the app. There's a **Put back** list now that survives restarts — and the Trash stopped being able to delete the wrong song.
- **v2.5 — the engine, rebuilt.** Chords leave in one call instead of one key at a time, the clock's rounding error went from **11 ms to 0.004 ms**, extended notes stopped jamming keys in the game, and velocity finally reached it at all. Plus **Panic**, **Expression**, **Fold range**, **Auto-fit key**, **Stay in window**, **Playlists**, a real **Trash**, octaves ×1–×5, per-track mute and **Flourish**.
- **v2.4 — your setup, your rules:** song key-binds, stream mode (hidden from OBS and screenshots), bring your own soundfont, and friendlier guidance for sending MIDI to a DAW through loopMIDI. **v2.4.1** went over Practice: a Sustain toggle for Free play, Sheet coloured by how you actually played each note, and Step rebuilt on the same canvas as the other modes.
- **v2.3 — 24 sounds:** grand, bright and electric pianos, Rhodes/FM, harpsichord, clavinet, celesta, music box, vibraphone, marimba, organs and more.
- **v2.2 — play with feeling:** QWERTY velocity, and an optional sustain pedal on Space.
- **v2.1 — the Visualizer:** 10 scene wallpapers, glow, particles, shockwaves, rainbow mode, your own note and saber colours, and one-click presets — at 60fps, in Stage *and* Practice.
- **v2.0 — Compose:** a full built-in piano-roll editor (also at **[velomidi.com/compose](https://velomidi.com/compose)**), a unified MIDI-input layer, an expandable mini-player, and update-safe data.
- **v1.9 — Velo Scan:** find the MIDIs already on your PC and import them, grouped by folder, no duplicates, undoable.
- **v1.8.2:** 9 keyboard-sound models, searchable dropdowns and a tabbed Settings redesign.

</details>

## Screenshots

<p align="center">
  <img src="docs/player.png" alt="Velo — the Player, with the live mini-stage" width="100%" /><br/>
  <sub><b>Player</b> — the mini-stage runs while the song plays.</sub>
</p>

<table>
  <tr>
    <td width="50%" valign="top"><img src="docs/appearance.png" alt="Appearance settings" /><br/><sub><b>Appearance</b> — recolour the whole app, and rebind anything.</sub></td>
    <td width="50%" valign="top"><img src="docs/sheet.png" alt="Practice — Sheet mode" /><br/><sub><b>Practice · Sheet</b> — the song as letters you can play.</sub></td>
  </tr>
  <tr>
    <td width="50%" valign="top"><img src="docs/practice.png" alt="Practice — Rhythm mode" /><br/><sub><b>Practice · Rhythm</b> — notes fall onto the keys; hit them in time.</sub></td>
    <td width="50%" valign="top"><img src="docs/stage.png" alt="Stage mode" /><br/><sub><b>Stage</b> — fullscreen, for streaming.</sub></td>
  </tr>
</table>

## What Velo does

**It plays a MIDI file by typing it.** That's the whole trick, and it's why the game pianos in Roblox, Virtual Piano and the rest can play things nobody could physically type. Velo can also send the song out as real MIDI to a port instead, with velocity and sustain, if you'd rather feed a DAW or a plugin.

Everything below grew around that.

### Playing

The Player has a queue, playlists that keep their own order, speed control, and hotkeys that work with Velo minimized — because you're going to be inside a game, not looking at it. A **floating mini-player** stays on top of the game, and **Select Music** jumps to any queued song without leaving what you're doing. You can bind a single song to a key and trigger it from anywhere.

Three things exist because the song rarely fits the keyboard as written:

- **Arrange** (Faithful · Balanced · Easy) decides how much of a chord survives. Faithful is the real song, and some of it can't be pressed on a QWERTY keyboard at all.
- **Fold range** pulls notes that fall off the ends of the keyboard back into reach instead of dropping them silently, and **Auto-fit key** moves the whole song into a key that fits.
- **Expression** takes the dynamics out of the music itself, since most MIDI files have none — which is why playback can sound like a list being read out loud.

And two that exist because things go wrong:

- **Panic** (`Ctrl+Alt+P`) lets go of everything Velo is holding — notes, Shift, Ctrl, the pedal — without making you leave the game to find the window.
- **Stay in window** notices where you played the first note and holds the song if you tab away, so a piece never gets typed into your Discord chat.

### Practising

A 61-key piano lights up what to press, in four modes:

- **Step** waits for you. Miss a note and nothing moves until you get it right.
- **Rhythm** is a rhythm game — notes fall to a line, with Perfect / Good / Miss, combo and a life bar.
- **Sheet** writes the song out as Virtual-Piano letters, coloured by rhythm or by hand, and you play along by typing (or clicking a letter to hear it). **Save** writes it out as an HTML file you can keep or send to someone.
- **Free play** is just a piano — keyboard, mouse or a real MIDI keyboard — with a preview that plays a song for you to watch.

**Hands** is the one worth knowing about. Pick a side and Velo stops playing it: that half is yours, and turning on **Guide** has Velo keep playing the other hand so you're playing *with* it rather than watching. It works out which hand each note belongs to from how a hand actually moves — reach, thumb-unders, the cost of crossing — and when a piece genuinely needs more than two hands it says so instead of inventing a split.

There's a **section trainer** for the part that's beating you: pick the bars, and it drills them in slow motion that speeds up as you get them. And sharps can be set to need Shift or not, which is the difference between practising the way the game really works and practising comfortably.

### Getting songs

**MIDI Hub** searches four libraries from inside Velo — nanoMIDI, Online Sequencer, BitMidi, and **MuseScore**, where you can search or paste a score link and it lands in your library with no browser and no account. **Velo Scan** finds the MIDI files already sitting on your PC and imports them grouped by folder, without duplicates, and it can put them back where they came from months later.

**Transcribe** is a tab now: hand it audio or a link and it comes back as a MIDI. It shares a queue with the Discord bot and the website, so a job you start in one place shows up in the others.

### Making things

**Compose** is a piano-roll editor. Record on your keyboard after a 3·2·1 count-in, paste a Virtual-Piano sheet, import a MIDI, or draw notes with the mouse. Edit velocity in the bottom lane, snap to a grid, scrub the timeline to hear it, and save a `.mid`, export a sheet, or publish it to the library. The same editor runs in a browser at **[velomidi.com/compose](https://velomidi.com/compose)**.

### Looking good while you do it

**Stage** drops the notes onto a fullscreen piano that plays as they cross, with wallpapers, glow, particles and colours you pick. **Stream mode** hides Velo from OBS, screen-share and screenshots while you can still see it, so your capture stays clean. **Humanize** adds chord roll, timing wander and rubato when the exactness starts sounding mechanical.

### Sound

24 instruments — grand, bright and electric pianos, Rhodes, harpsichord, organs, mallets — plus a Cherry MX mechanical-keyboard sound, or **load your own `.sf2` / `.sf3` soundfont** and it becomes the instrument everywhere. Or pick a MIDI port instead and let a DAW make the sound.

### Making it yours

**Configs** save your whole setup — colours, wallpaper, effects, keybinds, playing options — under a name you choose. Sign in and they follow you to another PC; publish one and other people can try it with a click and get their own back just as fast.

Velo also reads **your keyboard's layout** rather than assuming an American one. Every letter on screen becomes the key on *your* keyboard, and the autoplayer presses the right physical position regardless — which matters more than it sounds, because for a long time it didn't.

Also here: drum playback, **MIDI → Keys** (a controller becomes a keyboard in real time), per-song records, a Trash that makes removing a song reversible, and **Reset Velo**, which puts everything back to how it arrives without you having to reinstall.

## Hotkeys

| Key | Action |
|:---:|--------|
| `F1` | Play / Pause |
| `F2` | Pause |
| `F3` | Stop |
| `F4` | Speed up |
| `F5` | Slow down |
| `F6` | Previous track |
| `F7` | Next track |
| `Ctrl+Alt+P` | Panic — let go of every key |

All of them are rebindable in Settings, and they work with Velo minimized. Mouse buttons M4/M5 count as keys.

## How to use it

### Play a song into a game

Open a `.mid` in the Player (or drag one onto the window), keep the game focused, and hit `F1`. The keystrokes go wherever you're typing — which is also why **Stay in window** exists.

At the top of the Player you choose between **QWERTY** and **MIDI Output**. QWERTY types the letters, which is what in-game pianos read. MIDI Output sends real notes with velocity and sustain to a port.

**Sending MIDI to another program on the same PC.** A MIDI port normally goes to hardware, so reaching a program running next to Velo needs a virtual cable — the same idea as VB-CABLE for audio. Install **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)**, create a port, and pick it under *Output device*. Anything that reads MIDI input sees Velo as a keyboard plugged into the PC.

> Windows' built-in *Microsoft GS Wavetable Synth* is a dead end. It makes sound, but it can't pass the notes on to anything else.

> Some games advertise MIDI support, but that support usually comes from a separate helper app that reads a MIDI keyboard and turns it into keystrokes — the game itself doesn't read MIDI ports. If yours works that way, pointing that helper at a loopMIDI port fed by Velo is worth trying. If it doesn't, QWERTY already sends the keystrokes directly, which is where that chain ends up anyway.

### Practise

Pick a mode and a song in the **Practice** tab, and the on-screen keyboard shows you what to press. If a piece is fighting you, three things help before you give up on it: drop **Arrange** to Balanced or Easy, turn on **Hands** and take one side at a time, or switch **Practice sharps** to *No Shift* so you're not holding a modifier through a fast passage.

### Sound like you're playing live (Discord, streams)

The idea is to route Velo's piano into a virtual microphone.

1. Install **[VB-CABLE](https://vb-audio.com/Cable/)**.
2. In Windows, under **Settings → System → Sound → Volume mixer**, send Velo's output to `CABLE Input`.
3. In Discord or OBS, pick `CABLE Output` as the microphone.
4. In Velo, turn the sound on and hit play.

To talk and play at the same time, **VoiceMeeter** mixes your real mic and Velo into one channel.

## Running Velo

Download `Velo-win.zip` from **[Releases](../../releases)**, extract it somewhere normal, and open `Velo.exe`. There's no installer and no Python to set up.

Extract it to Documents or your desktop — **not** Program Files, and not inside OneDrive. Velo's browser engine needs to write next to itself, and in those two places Windows won't let it, which shows up as an app whose windows are all black.

Needs **Windows 10/11** with the **WebView2 Runtime**, which up-to-date Windows already has.

<details>
<summary><b>It won't start</b></summary>

Velo clears the "downloaded from the internet" mark from its own files on first launch, so this is rare. If it still won't open:

- **Antivirus took a file.** Velo is unsigned, so this happens. Check that `Velo\_internal\pythonnet\runtime\Python.Runtime.dll` is still there; if it's gone, restore it from quarantine and add the Velo folder as an exception.
- **Still blocked.** Right-click `Velo-win.zip` → **Properties** → tick **Unblock** → extract again.
- **Missing .NET Framework.** On stripped Windows editions (N / LTSC), install the free **.NET Framework 4.8** from Microsoft.

</details>

## Linux and macOS

Both are **paused as of 2.7.0**, and the honest reason is that everything built since then was only ever verified on Windows — shipping builds nobody has tested isn't better than not shipping them. The last builds that exist are **2.6.2**, still on the [Releases](../../releases) page, and the guides are still here: **[README-LINUX.md](README-LINUX.md)** · **[README-MAC.md](README-MAC.md)**.

If you're on either and want them back, say so on the Discord. What decides it isn't the download numbers, it's whether anyone is there to report what breaks.

## A companion app

Got a song with no MIDI anywhere? **[VeloScribe](https://github.com/brenucode/veloscribe)** takes an audio file or a link and transcribes it into a piano `.mid`, straight into Velo's queue. Same person, same look, same family.

## Why Velo isn't open-source anymore

Velo **was** GPL v3, up to **v2.0**. From **v2.1** it's closed, and this repository stopped publishing the app's code.

It grew from a small MIDI player into a Compose studio, a visualizer, an online library and a website — a lot of work over a lot of months. Open, all of it could be taken whole and reshipped by anyone. Closing it is what makes continuing to build it sustainable.

For you, nothing changes: Velo is still free, still download-and-run. You just can't read or fork the newer source. The versions that shipped under GPL v3 **stay** under GPL v3 for the copies already out there — that isn't something I could undo, and I'm not trying to.

> **There's no source to build here.** This repository is the download page and the documentation. The tags up to v2.0 still carry the GPL code that shipped with them.

---

**Velo** — made by **brenu** · [github.com/brenucode](https://github.com/brenucode)
Copyright © 2026 brenu. All rights reserved. See [LICENSE](LICENSE).

Sounds: **MusyngKite** pianos ([midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts)) and the **Cherry MX** keyboard ([Mechvibes](https://github.com/hainguyents13/mechvibes)).

The libraries in the MIDI Hub belong to the services they come from — **nanoMIDI** ([nanomidi.net](https://nanomidi.net)), **[Online Sequencer](https://onlinesequencer.net)**, **[BitMidi](https://bitmidi.com)** and **[MuseScore](https://musescore.com)**. Velo only gives you a tidier way to search them; all rights stay with them and their uploaders.

<p align="center"><sub>built in my spare time — because not every project needs a reason.</sub></p>
