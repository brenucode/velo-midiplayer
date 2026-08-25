<p align="center">
  <img src="assets/velo-banner.svg" alt="Velo" width="100%" />
</p>

<p align="center">
  <strong>A clean MIDI player — and now a full music studio.</strong><br/>
  Play MIDI as keystrokes (for virtual pianos in games) or MIDI output, practice it, and <strong>compose your own</strong>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-1c1c23?style=flat-square" />
  <img src="https://img.shields.io/badge/version-v2.7.0-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/license-Proprietary-c8ff4d?style=flat-square&labelColor=1c1c23" />
  <img src="https://img.shields.io/badge/made%20by-brenu-1c1c23?style=flat-square" />
</p>

<p align="center">
  <a href="https://github.com/brenucode/velo-midiplayer/releases/latest"><img src="https://img.shields.io/badge/⬇%20Download%20Velo-c8ff4d?style=for-the-badge&labelColor=1c1c23" /></a>
</p>

---

**Velo** started from a simple itch: play MIDI in an interface that doesn't look like 2009 software. A clean player, a **built-in music editor**, an online song library, a practice mode that feels like a little game, and a stage mode to look good on stream. No bloat, no annoying install — open it and it works.

> ## ⚠️ "My antivirus says it's a virus / keylogger!" — It isn't. Please read this.
>
> Windows SmartScreen and some antivirus tools flag Velo — sometimes literally as a **"keylogger"** or "HackTool". **This is a false positive.** Here's the honest reason, so you can decide for yourself:
>
> - **Velo reads your keyboard on purpose — that's the whole feature.** It turns your typing into piano notes, and can "play" a song into on-screen game pianos (Roblox, Virtual Piano, etc.). To do that, it has to listen to the keyboard system-wide — which is *technically* the same low-level trick a real keylogger uses. Antivirus heuristics can't tell "makes music" apart from "steals passwords", so they raise the alarm. **Velo never records, stores, or sends your keystrokes anywhere.** You can verify that yourself: watch Velo's network activity — it only ever reaches out to **check for updates**, never to send your input.
> - **Velo is unsigned.** Removing the warning requires a **code-signing certificate (~US$300 per year)**. Velo is **free**, made in spare time — paying a yearly fee for a free app isn't worth it, so you get the scary "unknown publisher" warning instead of a signed, pre-trusted one.
>
> **What to do:**
> - **"Windows protected your PC"** → click **More info → Run anyway**.
> - **Antivirus deleted a file and Velo won't open?** → restore it from quarantine (commonly `Velo\_internal\pythonnet\runtime\Python.Runtime.dll`) and add the Velo folder as an exception.
> - **Still blocked?** → right-click the `.zip` → **Properties** → tick **Unblock** → extract again.

## Velo 2.7.0 — Two hands, one of them yours

Velo could always play a song for you. Now it can play *half* of one.

- 🖐️ **Hands — play one, let Velo play the other.** Click one side of the keyboard strip and Velo stops typing that hand into the game: it's yours now. Turn on **Guide** and Velo keeps playing the other hand on its own piano, so you're playing *with* it instead of watching it. **Practice one hand at a time** with the same split the Player uses, **each hand in its own colour**, and the falling notes now show only what is actually being played — the muted half fades to glass, or disappears when nothing is sounding it. Velo also worked out something it could never say before: **how many people a piece needs.** One hand, two, four, or an arrangement no pair of hands can play — a symphony exported to MIDI is no longer described as "left or right".
- 🎛️ **Configs — your whole setup, in one preset.** Sound, background, visualizer, keyboard, playing options: save the lot under a name. Sign in and it follows you to another PC, which is the whole point of having a second one. Publish yours and other people can **Try** it — applied for real, not a preview, with one click back to your own.
- ⌨️ **Your keyboard, not an American one.** If your layout isn't US, Velo was pressing the *letter* your keyboard prints instead of the *position* the game reads — so the wrong note played and nothing said why. It presses the position now, every letter on screen shows the key on **your** keyboard, and Velo tells you which layout it recognised. Auto or US, and nothing in between pretending to be one.
- 🔌 **MIDI out from Practice.** The Practice piano can play through a MIDI port — pick it in the sound picker and a DAW or a VST plays what you play. Your velocity travels, and so does the sustain pedal on a real MIDI keyboard.
- ⚡ **It stopped eating your CPU.** Velo was burning **a whole processor core doing nothing** — open on any tab, idle. It was a background animation repainting two full-screen layers sixty times a second, forever, and one of those layers was invisible. It's about **1%** now, and nothing looks different. A big song also opens roughly twice as fast and holds a third of the memory it used to, because it was being read off your disk three times just to open it once.
- 🎼 **Transcribe is a tab in the app now** — the same queue as the bot and the site. **Settings** was rebuilt into five tabs instead of walls of paragraphs, and you can **save the letter sheet** straight out of Practice.

**Known limits, stated on purpose:** from this version on the **Linux and macOS builds are paused** — see the sections below. And three controls in here were quietly doing nothing before this release: the hand strip never listened to a click, Guide made no sound at all, and the Practice hand buttons died in Free play. If something in Velo looks like it should work and doesn't, saying so on the Discord is what gets it found.

## Velo 2.6.0 - Sheet music, straight into your library

The biggest release Velo has had, and one feature carries it.

- 🎼 **MuseScore now lands in your library.** Open the MIDI Hub, pick **MuseScore**, search a song or paste a score link - and it's yours, ready to play. No browser, no downloader site, no account. You can **browse** it too, by instrument and difficulty, with the difficulty and the length on the card before you commit to anything. And every score somebody brings in is **shared**, so the next person to want it gets it instantly rather than fetching it again.
- 🎚️ **Tracks stopped hiding.** Choosing which tracks play is a feature Velo has had for months, and people kept asking for it - because the control only appeared *after* you pressed Play, and the song Velo restores on startup never got one at all. Whoever opened the app looking for it met the one case where it was reliably absent. It's there from the moment a song loads now, and when there is nothing to split it says so instead of vanishing.
- 🎥 **Recording-friendly mode.** Some recorders and capture cards cannot see a GPU-drawn window and record a black box where Velo should be. This draws on the CPU instead. Settings -> Appearance. *(Windows only.)*
- ✨ **The visualizer runs smooth.** Five separate causes of stutter, all fixed - the worst being that the clock ran while the file was still being parsed, which is the *"the first song after opening always freezes"* people reported. Colours are one per track now, read from the file itself.
- 🍎 **macOS got its hotkeys back.** The one that matters isn't play/pause - it's **Panic**, your way out when a key sticks in a game you can't type in. And ⌘Q no longer walks away with your keys still held down.
- 🔧 **Two arrangements of the same song no longer overwrite each other.** They shared a filename, so the first one silently disappeared. Files are named by arranger now.

**Known limits, stated on purpose:** macOS is still a public beta - drag Velo to Applications *before* you open it the first time, because permissions are tied to where it lives. And on macOS and Linux a non-US keyboard layout can play the wrong note: Velo types by character there, where the Windows path types by key position. The app now tells you so in Settings -> Playing.

## Velo 2.5.2 — Velo runs on Mac, and four bugs members found

**🍎 macOS is here.** Native builds for Apple Silicon and Intel, with the permission setup macOS demands handled for you instead of left as homework. It's an **open beta** and we say so plainly: every other platform got years of people finding things, and this one has had none. See the [macOS section](#-macos--paused-after-262) below — and if something's off, please open a **ticket on the Discord server**.

The four fixes, all reported by members:

- 🎹 **A MIDI keyboard was sending a burst of extra keystrokes on every note.** Velo changes the game's velocity level with a key combination, and with a MIDI keyboard it was sending that combination on *every* note instead of only when the dynamic actually changed — 160 keystrokes where 4 were needed. Without the gaps between them the game reads the level key as an ordinary note: the setting did nothing **and** a wrong note played. That's the noise, and the two notes at once. QWERTY was never affected, which is exactly why it looked like a hardware problem.
- 🔇 **MIDI → Keys could type the piano into whatever window was focused.** The guard that keeps notes inside the game was only wired to the autoplayer. Live MIDI input runs in the background all the time, so alt-tabbing to Discord mid-song sent the notes there.
- 👻 **Half the Player could vanish when you came back to Velo.** The file card and the transport row were only visible because an entrance animation finished. An animation that never ran meant an element gone for good, and the only cure was switching tabs and back. Nothing in Velo depends on an animation finishing to be visible any more.
- ⏸️ **The Queue could show a song playing when nothing was.** If the playback thread hit an error it died silently, and Velo went on believing the song was still going. Worse: the same routine is what releases held keys, so a crash mid-chord could leave a key pressed down inside the game. Now it reports what happened, recovers, and lets go of the keys.

Plus: Stream mode works on macOS, and `velo --doctor` now prints what your copy of Velo can actually do on your machine.

## Velo 2.5.1 — Put back what a scan moved

Velo Scan finds the MIDIs already on your PC and adds them to your library. Adding **moves** the files — deliberately, so a song doesn't end up sitting on your disk twice. The problem was what came after: Velo only remembered where each file came from until you closed the app. Reopen it the next day, find the folders you'd spent years organising empty, hit Undo, and there was nothing left to undo with.

Nothing was ever deleted. But "it's all still there, somewhere in one flat folder" is not much comfort when you had it sorted by composer.

- 📦 **Put back** *(Settings › Library)* — a list of every song a scan moved and the folder each one goes back to. Tick what you want; not the whole import, just what you pick. It works months later, and it survives restarts and updates.
- 🗑️ **The Trash could delete the wrong song.** Removing two songs within a moment of each other gave them the same internal id, so **Delete forever** — the one button in Velo that really deletes a file — could take the song you hadn't selected. If your Trash already holds a pair like that, Velo repairs it on startup.

> ⚠️ Velo's library is **one flat folder**, and your own subfolders aren't recreated inside it. If you've sorted your MIDIs into folders you care about, keep a copy before you scan. Put back will rebuild them, but a copy costs you nothing.

## Velo 2.5 — The engine, rebuilt

The biggest change to how Velo *plays* since it existed — and almost none of it is a new button. Velo looks the same, and then it plays, and you can hear the difference.

**Four things were quietly broken the whole time.** Not features that were missing: features that were **there, switched on, and doing nothing.**

- 🎹 **Chords land together.** A five-note chord was five separate trips into the operating system, one key at a time, and anything that happened in between — the browser waking up, a frame being painted — spread it out. You heard a rolled chord you never asked for. The whole chord now leaves in **one call**.
- ⏱️ **The clock was rounding every note onto a 15 ms grid**, before anything else had a chance to go wrong. To put that in scale: a sixteenth note at 120 BPM is 125 ms. Measured wait error went from **11 ms to 0.004 ms**.
- 🔑 **Extended notes jammed keys in the game.** Notes past the main 61 keys are played with **Ctrl** held, and their release was being sent without it — so the game never ended the note and **the key stayed down**. Any song with a bass line below C2 could do it.
- 🎚️ **Velocity never reached the game.** It reads Alt through a *delayed* callback; Velo sent Alt and the level key with no gap, so the flag wasn't set yet and the key was read as an ordinary note. Your dynamics did nothing — and spent four extra key events on **every note** doing it.

**And new things to use:**

- 🆘 **Panic — release all keys** (`Ctrl + Alt + P`, rebindable). Everything held — notes, Shift, Ctrl, Alt, the sustain pedal — lets go, **without leaving the game**. Before this, a stuck key meant finding Velo's window.
- 🎭 **Expression** (`Off · Natural · Dramatic`) — dynamics taken from the music itself. Most MIDI has none at all, which is why playback can sound like a machine reading a list. Velo reads how busy the music is, where each note sits in its phrase and how the line rises and falls. *Only works on pianos that support velocity keybinds, so it ships off.*
- 🔄 **Fold range** *(on)* — notes above or below the keyboard used to be **dropped in silence**. They're moved into reach instead: one octave at most, and never on top of a note already sounding.
- 🎼 **Auto-fit key** *(off)* — the other answer to the same problem: move the **whole song** into a key that fits. Every interval survives, so it still sounds like the piece. Off by default, because transposing does change the key of something you know.
- 🪟 **Stay in window** *(on)* — Velo learns where you played the first note and holds if you tab away, so a song can never get typed into your Discord chat. The song clock holds with it, so you come back where you left off — and Velo's own windows don't trigger it.
- 📚 **Playlists** — named sets of your songs, each in its own order (a full FNAF list in chronological order, a practice set), without disturbing anything else. Drag a song onto a tab, or use **Add songs**. Next, previous, shuffle, the end-of-song advance and the floating **Select Music** window all follow the open playlist.
- 🗑️ **A Trash** — removing a song used to un-happen at the next launch, because Velo re-reads its Midis folder on startup and nothing recorded that you meant it. Removed songs now move to **Velo/Trash**, a real folder you can open, and the Trash button puts them back. Adding a song that's already in the trash restores it instead of leaving you a working copy and a twin in the bin.
- 🎹 **Octaves ×1–×5**, 🎚️ **per-track mute**, and ✨ **Flourish** — a run across the whole keyboard on demand, for when someone in chat says you're autoplaying. Three of them, and bindable to a key.
- 🎛️ **A MIDI keyboard that gets unplugged** is waited for and reopened instead of going deaf in silence — and whatever it was holding is released, not left down in the game.

🐧 **Linux got fixed properly** — see the [Linux section](#-linux) below.

## Earlier releases

<details>
<summary><b>What landed in v2.4 → v1.8</b></summary>

- **v2.4 — Your setup, your rules:** **song key-binds** (bind a queued song to one key and trigger it from anywhere), **stream mode** (hide Velo from OBS, screen-share and screenshots while it stays visible to you), **bring your own soundfont** (`.sf2` / `.sf3`, without bloating the app), and friendlier guidance for sending MIDI to a DAW or plugin through loopMIDI. **v2.4.1** then went over Practice: a **Sustain** toggle for Free play, **Sheet** coloured by how you actually played each note and openable **fullscreen**, **Step** rebuilt on the same canvas as the other modes, and the piano filling the screen properly.

- **v2.3 — 24 sounds:** grand, bright and electric pianos, Rhodes/FM, harpsichord, clavinet, celesta, music box, vibraphone, marimba, organs and more, all in **Settings → Playing → Sound** (core pianos offline; the rest stream and cache on first use).
- **v2.2 — Play with feeling:** **QWERTY velocity** (computer-keyboard notes respond to *how* you play, and it drives the visualizer's brightness) and an optional **sustain pedal (Space)** so keyboard Free play feels like a real piano. Both in **Settings → Playing**, off by default.
- **v2.1 — the Visualizer:** the falling-notes view became a tunable light show — 10 scene wallpapers, real effects (glow, particles, shockwaves, streaklets, chord-reactive bloom), a **rainbow** mode, your own note & saber colors, darken/blur/vignette, and an **auto-hiding gear** with one-click presets. Measured to stay at 60fps, and it drives **Practice → Free play and Rhythm** too, not just Stage.
- **v2.0 — Compose:** a full built-in **piano-roll editor** (record, paste a sheet, import a MIDI or draw notes; save a `.mid`, export a sheet, or publish to the library — also at **[velomidi.com/compose](https://velomidi.com/compose)**), a **unified MIDI-input layer** so your keyboard works the same in Practice / MIDI → Keys / Compose, an **expandable mini-player**, and **update-safe data** so your songs, backgrounds and settings survive an update.
- **v1.9 — Velo Scan:** find the MIDIs already on your PC and import them, grouped by folder, no duplicates, undoable.
- **v1.8.2:** 9 keyboard-sound models, searchable dropdowns and a tabbed Settings redesign.

</details>


## 📸 Screenshots

<p align="center">
  <img src="docs/player.png" alt="Velo — MIDI Player with the live mini-stage" width="100%" /><br/>
  <sub><b>Player</b> — now with the live mini-stage: watch the notes fall while a song plays.</sub>
</p>

<table>
  <tr>
    <td width="50%" valign="top"><img src="docs/appearance.png" alt="Custom accent colors + rebindable hotkeys" /><br/><sub><b>Appearance</b> — recolor the whole app to any accent, and rebind hotkeys (incl. mouse M4/M5).</sub></td>
    <td width="50%" valign="top"><img src="docs/sheet.png" alt="Practice — Sheet mode" /><br/><sub><b>Practice (Sheet)</b> — any MIDI written out as Virtual-Piano letters you can play.</sub></td>
  </tr>
  <tr>
    <td width="50%" valign="top"><img src="docs/practice.png" alt="Practice — Rhythm mode" /><br/><sub><b>Practice (Rhythm)</b> — notes fall onto the keys; hit them in time.</sub></td>
    <td width="50%" valign="top"><img src="docs/stage.png" alt="Stage mode" /><br/><sub><b>Stage</b> — fullscreen visualizer, great for streaming.</sub></td>
  </tr>
</table>

## ✨ What it does

- 🎹 **Player** — plays MIDI via **keyboard (QWERTY)** or **MIDI output**. Song queue, **playlists** (named sets in their own order), speed control, previous/next, and **global hotkeys** that work even with the app in the background. A **floating mini-player** stays on top of your game, with a **Select Music** window to jump to any queued song (search, favorites, shuffle, loop). Bind a **song to a key** to trigger it from anywhere, and a **Trash** so removing one is never final.
- ✨ **Compose** — a built-in **piano-roll editor** to make your own music: record on your keyboard (3·2·1 count-in), paste a Virtual-Piano sheet, import a MIDI or draw notes, with a clean studio visualizer (ghost-note preview, live pitch/position readout, zoom-to-cursor, scrub-to-hear, loop shading). Save a `.mid`, export a sheet, or **publish to the library**. Also runs in the browser at **[velomidi.com/compose](https://velomidi.com/compose)**.
- 🖐️ **Hands** — Velo plays one hand while you play the other, live. Click a half of the keyboard strip to take it over, turn on **Guide** and Velo keeps the other one singing. Works in Practice too, one hand at a time, with each hand in its own colour on the falling notes.
- 🎛️ **Configs** — save your whole setup (sound, background, visualizer, keyboard, playing options) as a named preset, sync it to another PC by signing in, and publish it or try someone else's.
- 🎯 **Practice** — four modes on a 61-key piano that lights up which key to press:
  - **Step** — learn note by note, at your own pace. Miss it? It waits until you get it right.
  - **Rhythm** — turns into a rhythm game: notes fall in time, with **Perfect / Good / Miss**, combo, multiplier and a life bar.
  - **Sheet** — the song written out as Virtual-Piano letters, each one **coloured by how you actually played it** (on time / early / late / missed), readable fullscreen.
  - **Free play** — a free piano (keyboard or mouse), with **rising trails** on every note, an optional **sustain** pedal, and a **preview** that plays the song for you.
  - **Section trainer** — pick the hard part and drill it in **slow motion that speeds up** as you nail it.
- 🌐 **MIDI Hub** — search and download songs from three libraries without leaving Velo: the **nanoMIDI** library, **Online Sequencer**, and **BitMidi**. Pick the source from the dropdown; results show up in Velo's own UI.
- 🔎 **Velo Scan** — find the MIDI files already sitting on your computer and add them to your library. Tap the sonar, choose where to look, review the results grouped by folder, and import only what you want — no duplicates, and undoable.
- ▦ **Stage mode** — notes fall onto a **fullscreen** piano and the song **plays as they cross**, synced to what's playing, and they **follow your play style** (Faithful/Balanced/Easy). Perfect to leave on screen for Discord/streaming.
- 🎥 **Stream mode** — hide Velo from OBS, screen-share and screenshots (and optionally from the taskbar) while it stays visible on your own screen — for a clean capture.
- 🎭 **Humanizer** — optional human feel: chord roll, timing/release wander, rubato and velocity variation, with profiles + sliders. Off by default (exact, mechanical original).
- 🥁 **Drums** and ⌨️ **MIDI → Keys** — turn a MIDI controller into a keyboard in real time.
- 🔊 **Real sound** — **24 instruments** (grand/bright/electric pianos, Rhodes, harpsichord, organs, mallets and more) plus a **Cherry MX** mechanical-keyboard sound — or **load your own `.sf2` / `.sf3` soundfont**.
- 🏆 **Records** per song · 🖥️ **responsive** layout + **fullscreen (F11)**.

## 🎼 Companion app — VeloScribe

Got a song with no MIDI? **[VeloScribe](https://github.com/brenucode/veloscribe)** is Velo's companion tool: drop an audio file (or paste a link) and it transcribes it into a clean piano `.mid` — saved straight into Velo's queue. Same look, same family, made by the same person.

## ⬇️ Download (ready to use)

> No Python, nothing to install.
> **On a Mac or on Linux?** Those builds are **paused from 2.7.0** — **v2.6.2** is the last one for them and it stays up. See [🍎 macOS](#-macos--paused-after-262) and [🐧 Linux](#-linux).

### Windows

1. Go to **[Releases](../../releases)** and download `Velo-win.zip`.
2. Extract the folder somewhere normal — **Documents** or your Desktop.
3. Open **`Velo.exe`**.

> **Don't run it from inside the zip, from OneDrive, or from Program Files.** Velo needs to write its own data folder next to itself, and in those three places Windows won't let it — you get a black window and nothing else. Extracting it properly is the fix.

Requires **Windows 10/11** with the **WebView2 Runtime** (already bundled in up-to-date Windows; if missing, Windows Update installs it, or grab it free from Microsoft).

<details>
<summary><b>It won't start? (rare)</b></summary>

Velo automatically removes the "downloaded from the internet" mark from its own files on first launch, so it should just work. If it still won't open:

- **Antivirus quarantined a file** — Velo is an unsigned app, so some antivirus tools remove a file by mistake. Check that `Velo\_internal\pythonnet\runtime\Python.Runtime.dll` still exists; if it's gone, restore it from quarantine and add the Velo folder as an exception.
- **Still blocked** — right-click `Velo-win.zip` → **Properties** → tick **Unblock** → **OK**, then extract again.
- **Missing .NET Framework** — on stripped Windows editions (N / LTSC), install the free **.NET Framework 4.8** from Microsoft.

</details>

## 🐧 Linux

> **Paused from 2.7.0.** Nearly everyone using Velo is on Windows, and keeping three builds properly tested costs time that's better spent on the app itself. **v2.6.2 is the last Linux release** and it stays up — everything below still applies to it. If Linux ever gets a real crowd here, the builds come back.

Velo runs on Linux too — **Fedora, Ubuntu/Debian, Arch, openSUSE**. It uses your system's WebKit (the reliable way — no fragile bundled browser), so it's a quick one-time setup in a terminal:

1. Download **`velo-linux.tar.gz`** from **[Releases](../../releases)**.
2. Extract it and run the installer:

```bash
tar xzf velo-linux.tar.gz
cd velo-linux
./install-linux.sh
```

The installer pulls the libraries it needs (GTK + WebKit + PyGObject via your distro's package manager), sets everything up, and adds **Velo** to your applications menu — then just search **"Velo"** and launch it like any app (or run `velo`). Full guide + troubleshooting: **[README-LINUX.md](README-LINUX.md)**.

**New in 2.5 — Wayland works now.** Velo used to run as a native Wayland client, where the compositor forbids the two things Velo is *for*: putting its own window on top of your game, and typing into another application. That's why the mini-player and the autoplayer both looked dead on a Wayland desktop. Velo now runs itself through **XWayland**, where both come back — no session switching, nothing to configure.

Two more things that release fixed: the bug that **heated laptops** (Velo was disabling GPU compositing for every Linux user, so the CPU was drawing every frame of the visualizer), and a new **`velo --doctor`** that reports *measured* facts about your machine rather than guesses — it really types a character, really moves a window, and tells you what to do about what it finds. It runs even when the app won't start.

> Two honest limits. A game written as a **native Wayland client** still can't receive synthetic keys from anything — ask it to run on X11 instead (SDL games take `SDL_VIDEODRIVER=x11`; for Sober: `flatpak run --env=SDL_VIDEODRIVER=x11 org.vinegarhq.Sober`). And **velocity / Expression don't reach the game on Linux** — that path can't send the modifier timing the game needs.

## 🍎 macOS — **paused after 2.6.2**

> **Paused from 2.7.0.** The Mac build never got confirmed doing the one thing Velo is actually for — playing into a game — and shipping something nobody can stand behind is worse than not shipping it. **v2.6.2 is the last macOS release** and stays up; everything below still applies to it. If the Mac ever gets a real crowd here, it comes back properly tested.

Velo runs on macOS from 2.5.2. **This is the first public build for the Mac and it is openly a test:** every other platform got years of members finding things; this one has had none. It is here so that can start.

> ### 🐞 Found something? Open a ticket on the Discord server.
> Not a message in chat, where it scrolls away — a **ticket**, so it doesn't get lost and we can ask you follow-up questions. Say which Mac you have (Apple menu → About This Mac), your macOS version, and what you were doing.

**Which file?** Apple menu → **About This Mac**. *Chip: Apple M1/M2/M3/M4* → **`Velo-mac-AppleSilicon.dmg`**. *Processor: Intel* → **`Velo-mac-Intel.dmg`**. The Intel build runs on Apple Silicon through Rosetta; the Apple Silicon build does **not** run on an Intel Mac at all.

1. Download your `.dmg` from **[Releases](../../releases)**.
2. Open it and **drag Velo into the Applications folder — before you open it.**
3. Open **Applications** and double-click **Velo**. macOS will refuse, because Velo isn't signed with an Apple certificate.
4. **System Settings → Privacy & Security**, scroll to the bottom, click **Open Anyway**, confirm.
5. Velo will ask for **Accessibility**. Say yes — that's the permission that lets it press keys in the game. Without it the autoplayer runs and nothing happens.
6. macOS only applies that permission **when an app launches**, so Velo notices when you grant it and offers to reopen itself. Let it.

> ⚠️ **Step 2 is not housekeeping.** For an unsigned app, macOS ties the permission to **where the app is**. Open it from Downloads and move it to Applications later, and Velo silently loses that permission — the autoplayer stops working and nothing tells you why.

Full guide, including the second permission (**Input Monitoring**, for the global hotkeys): **[README-MAC.md](README-MAC.md)**.

> **Two limits that belong to macOS, not to Velo.** A game in **native fullscreen** gets a Space of its own and *nothing* can appear over it — keep the game in a window if you want the mini-player. And **non-US keyboard layouts can play the wrong note**: the Mac key path resolves keys by character rather than by physical position. Known, on the list, and exactly what this beta exists to hear about.

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
| `F8` | Cycle play style (Faithful / Balanced / Easy) |
| `F9` | Show / hide the floating mini-player |
| `Ctrl` + `Alt` + `P` | **Panic — release every held key** |
| — | Show / hide Velo itself *(unbound by default)* |
| — | Toggle sustain *(unbound by default)* |
| — | Flourish — a run across the keyboard *(unbound by default)* |

All of them are remappable in **Settings › Appearance**, including **mouse buttons M4/M5**, and modifier combos like `Alt + Shift + F`. They work while Velo is minimised — which is the point, since you'll be inside a game.

**Panic is the one to remember.** The autoplayer holds keys down; if a song is interrupted at the wrong moment you can be left with keys stuck in a game you can no longer type in. Panic lets go of everything — notes, Shift, Ctrl, Alt, the sustain pedal — **without leaving the game**. It's the only optional action that ships already bound.

You can also bind **a song to a key** (Player › the key icon on a queued song) and start it from anywhere.

## 🧭 How to use

### 1. Play a song
1. **Player** tab → **Open** (or drag a `.mid` onto the window).
2. **Play** (or `F1`). Velo "types" the song into your virtual piano keys.
3. Want to play in a game (Roblox, etc.)? Keep the game focused and use the hotkeys — the keystrokes go to it.

> **QWERTY vs MIDI Output:** choose at the top of the Player. *QWERTY* simulates the keyboard (for in-game pianos). *MIDI Output* sends real MIDI notes — with velocity and sustain — to a MIDI port.

**Sending MIDI to another program on the same PC.** A MIDI port normally goes to hardware, so to reach a program running beside Velo you need a **virtual MIDI cable** — the same idea as VB-CABLE for audio (§5). Install **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)** (free), create a port, then pick it under *Output device*. Anything that reads MIDI input — a DAW, an instrument plugin, or a helper app — will see Velo as if it were a MIDI keyboard plugged into the PC.

> ⚠️ Windows' built-in *Microsoft GS Wavetable Synth* is a dead end: it makes sound, but can't pass the notes on to another program.

> **About game "MIDI mode":** some virtual-piano games advertise MIDI support, but that support usually comes from a **separate helper app** that reads a MIDI keyboard and turns it into keystrokes — the game itself doesn't read MIDI ports. If your game works that way, pointing that helper at a loopMIDI port fed by Velo is worth a try. If it doesn't, **QWERTY mode already sends the keystrokes directly**, which is where that chain ends up anyway.

### 2. Download songs (MIDI Hub)
1. **MIDI Hub** tab → pick a source (**nanoMIDI**, **Online Sequencer** or **BitMidi**) and search by name.
2. Click the ↓ on a song — it downloads and drops straight into your queue.

> **Online Sequencer:** the first search opens a one-time check in a small window (it usually clears itself in a few seconds); after that, searching and downloading happen entirely inside Velo.

### 3. Practice
1. **Practice** tab → pick a mode (**Step / Rhythm / Sheet / Free play**) and a song.
2. The on-screen keyboard lights up the right keys (sharps = **Shift**).
   - **Step:** press in sequence, no rush. It waits until you get it right.
   - **Rhythm:** hit each note as it reaches the line — **Perfect / Good / Miss**, combo, multiplier and a life bar.
   - **Sheet:** the whole song written out as Virtual-Piano letters. Each letter is **coloured by how you actually played it** — green on time, orange early or late, red missed — so you can see where you drift rather than guess. Opens **fullscreen** for reading from across the desk.
   - **Free play:** play freely on the keyboard or with the mouse, with **rising trails** on every note. Pick a song and hit **Play (preview)** to watch it play itself. **Sustain** is one toggle here, shared with the Settings switch and a rebindable hotkey.
3. **Section trainer:** toggle it on and drag the handles to drill just one part, in **slow motion that speeds up** as you nail it.

> All four modes share the same visualizer and the same lit keys, and the gear that tunes the Stage tunes these too.

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

> **Pick your sound.** Under **Settings → Playing → Sound**, choose from **24 instruments** — grand, bright and electric pianos, Rhodes/FM, harpsichord, clavinet, celesta, music box, vibraphone, marimba, organs and more. The core pianos ship offline; the rest stream and cache on first use. Want a specific piano? **Load your own `.sf2` / `.sf3` soundfont** under **Your soundfont** and it becomes the live instrument everywhere (prefer SF3 — same sound, lighter on RAM).

### 6. Drums and MIDI → Keys
- **Drums:** same idea as the Player, with a drum map.
- **MIDI → Keys:** plug in a MIDI controller and play — Velo converts it to keystrokes in real time.

### 7. Compose (make your own music)
1. **Compose** tab → start from a blank roll, or bring notes in: **Record** (play your keyboard after the 3·2·1 count-in), **Paste a sheet**, **Import MIDI**, or **draw** with the mouse (a ghost note shows exactly where it'll land).
2. Shape it: drag to move/resize, edit velocity in the bottom lane, snap to the grid, and set a key so you stay in tune. Zoom with `Ctrl`+scroll (toward the cursor), scrub the timeline to hear it.
3. **Save** to your library, **Copy sheet** / **export a `.mid`**, or **Publish** it to [velomidi.com](https://velomidi.com) — link your account once and it goes through the same library as the site.

> Prefer the browser? The exact same editor lives at **[velomidi.com/compose](https://velomidi.com/compose)**.

## 🛠️ Running Velo

**Windows** — download `Velo-win.zip` from [Releases](../../releases), extract it anywhere, run `Velo.exe`. Nothing to install.

**macOS** *(beta)* — download `Velo-mac-AppleSilicon.dmg` or `Velo-mac-Intel.dmg`, **drag Velo into Applications before opening it**, then follow the permission steps in the [🍎 macOS](#-macos--paused-after-262) section.

**Linux** — download `velo-linux.tar.gz`, extract, run `./install-linux.sh` (see the [🐧 Linux](#-linux) section). To run it in place without installing, `./run-linux.sh`.

> **There is no source to build here.** This repository is the download page and the documentation — Velo's code is private (see below), so there's no `requirements.txt` to install and no build script to run. Earlier versions up to **v2.0** were GPL v3 and their source is still in the history of the tags that shipped them.

## 📄 License & why Velo is no longer open-source

Velo **used to be open-source (GPL v3)**. It isn't anymore — from **v2.1** on, Velo is **closed-source**, and this repository no longer publishes the app's code.

**Why the change?** Velo grew from a small MIDI player into something much bigger — a full **Compose** studio, a custom visualizer, an online library and website, and a lot of original work poured in over many months. Keeping all of that open meant anyone could take the whole thing and ship their own copy of it. To keep building Velo sustainably and protect that work, newer versions are now closed-source.

**What this means for you, the user: nothing changes.** Velo is still **free**, still just download-and-run. You simply can't read or fork the source of the new versions anymore.

Older versions that were released under **GPL v3 stay under GPL v3** for the copies already out there — that can't be (and isn't being) undone.

**Velo** — created by **brenu** · [github.com/brenucode](https://github.com/brenucode)
Copyright © 2026 brenu. **All rights reserved.** See [LICENSE](LICENSE).

Sounds: **MusyngKite** pianos ([midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts)) and the **Cherry MX** keyboard ([Mechvibes](https://github.com/hainguyents13/mechvibes)).

Song libraries in the MIDI Hub belong to their respective services — **nanoMIDI** ([nanomidi.net](https://nanomidi.net)), **[Online Sequencer](https://onlinesequencer.net)** and **[BitMidi](https://bitmidi.com)**. Velo just gives you a tidy way to search them; all rights stay with them and their uploaders.

<p align="center"><sub>built in my spare time — because not every project needs a reason.</sub></p>
