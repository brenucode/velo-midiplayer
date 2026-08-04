# Velo on macOS

Velo is a Windows app that also runs on Linux and macOS. The Mac build is new,
and macOS asks more of an app that types into another program than either of the
others does. Everything below is a macOS rule, not a Velo setting — this page
exists so you know which is which.

---

## 1. Pick the right download

macOS comes in two flavours of chip and the builds are not interchangeable:

| Your Mac | Download |
|---|---|
| **Apple silicon** (M1, M2, M3, M4…) | `Velo-mac-AppleSilicon.dmg` |
| **Intel** | `Velo-mac-Intel.dmg` |

Not sure?  Apple menu → **About This Mac**. It says either "Chip: Apple M…" or
"Processor: … Intel …".

After the first download you never have to think about it again: Velo checks for
updates and picks the right one for your machine. If a release ever ships without
a build for your chip, Velo says so instead of offering you one that cannot run.

## 2. Open it the first time

Open the `.dmg` and **drag Velo into Applications**. Do this before anything
else — see step 3 for why it matters more here than on Windows.

The first launch, macOS will refuse: *"Velo can't be opened because Apple cannot
check it for malicious software."* That is Gatekeeper, and it says that about
every app whose developer has not paid Apple's $99/year certificate.

**On macOS 15 (Sequoia) and newer** — including macOS 26:

1. Double-click Velo and let it be blocked. **This step is required**: the button
   below does not appear until macOS has something to allow.
2. **System Settings → Privacy & Security**, scroll to the Security section
3. Next to *"Velo was blocked…"*, click **Open Anyway**, and confirm

**On macOS 14 (Sonoma) and older**, the shortcut still works: **right-click** (or
Control-click) Velo in Applications → **Open** → **Open**. Apple removed that
path in Sequoia, which is why the longer route is listed first.

Once only, either way. Every launch after that is a normal double-click.

> Prefer to check for yourself first? Every release lists the SHA-256 of its
> files. Compare it with
> `shasum -a 256 ~/Downloads/Velo-mac-AppleSilicon.dmg`.

## 3. Let Velo press keys

To play a song into a game, Velo has to send keystrokes to another app, and macOS
requires your permission for that.

**Velo asks you on first launch.** Say yes, and it opens the right page in System
Settings for you. Then:

* tick **Velo** under Privacy & Security → **Accessibility**
* come back to Velo and press **Reopen Velo now** in the amber bar

That second step is not us being lazy. **macOS only applies this permission when
an app starts**, so ticking the box changes nothing for the copy of Velo that is
already running — which is why so many apps feel broken at this point. Velo
notices the moment you grant it and offers to restart itself.

**Move Velo to Applications BEFORE granting.** Velo is not signed with a paid
Apple certificate, so macOS ties this permission to *where the app is*. Grant it
in your Downloads folder, drag Velo to Applications afterwards, and the
permission silently stops applying, with nothing to tell you why.

For the same reason, **installing a new version may ask you to grant it again.**

### Two smaller ones

* **Input Monitoring** (Privacy & Security → Input Monitoring) powers the global
  hotkeys — the ones that work while the *game* has focus, including **Panic**,
  which releases keys the autoplayer left held down. Everything else works
  without it.
* **Documents folder** — macOS may ask the first time Velo starts. Velo keeps
  `config.json`, your library and your playlists in `~/Documents/Velo`. If you
  say no, Velo cannot save anything.

Not sure what state you are in? Run this in Terminal — it prints a page of
measured facts, and it is the useful thing to paste when asking for help:

```bash
/Applications/Velo.app/Contents/MacOS/Velo --doctor
```

⚠️ **Read the permission state in Velo's own window, not from Terminal.** macOS
grants these to whatever *launched* the app, so a Velo started from a terminal
reports the terminal's permissions. This cost us an evening once.

## 4. Play into a game

Two things are different from Windows.

**Run the game in a WINDOW, not fullscreen.** macOS gives a fullscreen app a
desktop of its own and lets no other app draw there — at any window level, by any
app. The mini-player is then working and invisible. Windowed or borderless, and
it sits on top as it should. Velo tells you when it detects this.

**The game also sees your hotkeys.** macOS offers no way to swallow a key on its
way to another application. Velo's defaults (F1–F8, Ctrl+Alt+P) are keys games
almost never use; if you rebind one to a letter, that letter will still reach the
game.

## What is not there yet

* **No auto-update.** Velo tells you a new version is out and downloads it; you
  drag it to Applications yourself. On Windows it can swap itself; here it would
  need Apple's certificate to be safe about it.
* **Non-US keyboard layouts** may play the wrong notes. On Windows Velo sends
  keys by physical position; on macOS it sends characters, which depend on your
  layout. Being fixed — if you use ABNT2, ISO or anything but US, please say so.

## When something is wrong

`--doctor` first, then bring the output. It reports the permissions, whether the
mini-player layer is alive, whether something fullscreen is covering the screen,
and which key backend is actually in use.

If Velo opens and vanishes after a second, that is a crash, and the crash report
is the only thing that identifies it: **Console.app → Crash Reports → Velo**.
Please send that rather than a description — we once spent a day chasing the
wrong cause because a shell message said "illegal hardware instruction", which
sounded like an old CPU and was in fact macOS deliberately stopping the app for
calling one API from the wrong thread.
