#!/usr/bin/env bash
# Velo — one-shot Linux installer.   Run:  ./install-linux.sh
#
# What it does:
#   1. installs the system libraries Velo needs (GTK 3 + WebKit2GTK + PyGObject
#      + ALSA) using your distro's package manager,
#   2. creates a Python virtualenv (that can see the system PyGObject),
#   3. adds "Velo" to your applications menu with an icon — so afterwards you
#      launch it like any normal app.
#
# Why this is the reliable path: it uses YOUR system's WebKit (not a bundled
# copy). Bundling WebKit into a single binary is the fragile part on Linux;
# using the system's makes it Just Work across Fedora / Ubuntu / Arch / openSUSE.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$SCRIPT_DIR"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }

# --------------------------------------------------------------- system deps
say "Installing system libraries (you'll be asked for your sudo password)…"
if command -v dnf >/dev/null 2>&1; then                       # Fedora / RHEL
    sudo dnf install -y git python3 python3-pip python3-gobject gtk3 \
        alsa-lib alsa-lib-devel gcc gcc-c++ python3-devel
    sudo dnf install -y webkit2gtk4.1 || sudo dnf install -y webkit2gtk4.0 \
        || warn "Install webkit2gtk manually if the window fails to open."
elif command -v apt-get >/dev/null 2>&1; then                 # Debian / Ubuntu
    sudo apt-get update
    sudo apt-get install -y git python3 python3-venv python3-pip python3-gi \
        python3-gi-cairo gir1.2-gtk-3.0 libasound2 libasound2-dev \
        build-essential python3-dev
    sudo apt-get install -y gir1.2-webkit2-4.1 \
        || sudo apt-get install -y gir1.2-webkit2-4.0 \
        || warn "Install gir1.2-webkit2-4.x manually if the window fails to open."
elif command -v pacman >/dev/null 2>&1; then                  # Arch
    sudo pacman -S --needed --noconfirm git python python-gobject gtk3 \
        webkit2gtk-4.1 alsa-lib base-devel
elif command -v zypper >/dev/null 2>&1; then                  # openSUSE
    sudo zypper install -y git python3 python3-pip python3-gobject gtk3 \
        webkit2gtk3 alsa-lib alsa-devel gcc gcc-c++ python3-devel
else
    warn "Couldn't detect dnf/apt/pacman/zypper. Install these by hand, then re-run:"
    warn "  git, python3 (+venv/pip), PyGObject, gtk3, webkit2gtk (4.1 or 4.0), alsa."
    exit 1
fi

# --------------------------------------------------------------- python venv
VENV="$SCRIPT_DIR/venv-lnx"
say "Setting up the Python environment…"
if [ ! -d "$VENV" ]; then
    python3 -m venv --system-site-packages "$VENV"
fi
# Call the venv's python directly instead of `source activate` — activating
# under `set -u` can abort on an unbound variable inside the activate script.
VPY="$VENV/bin/python"
"$VPY" -m pip install --upgrade pip wheel >/dev/null

say "Installing Velo's Python dependencies…"
"$VPY" -m pip install pywebview==6.2.1 mido==1.3.3 pynput==1.8.2 requests==2.34.2 psutil==7.2.2
# python-rtmidi powers the optional "MIDI output" mode and may need to compile.
# If it can't, Velo still runs fine (default playback + in-app sound + practice).
"$VPY" -m pip install python-rtmidi==1.5.8 \
    || warn "python-rtmidi skipped — 'MIDI output' mode off; everything else works."

# sanity check: can we actually reach GTK + WebKit before we claim success?
if "$VPY" - <<'PY'
import gi
ok = False
for v in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", v); ok = True; break
    except ValueError:
        pass
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, WebKit2  # noqa: F401
raise SystemExit(0 if ok else 1)
PY
then
    say "GTK + WebKit are ready."
else
    warn "GTK/WebKit not importable yet — make sure webkit2gtk is installed."
fi

# ----------------------------------------------------------- desktop launcher
say "Adding Velo to your applications menu…"
ICON_PATH="$SCRIPT_DIR/assets/icons/velo_logo.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
if mkdir -p "$ICON_DIR" && cp -f "$ICON_PATH" "$ICON_DIR/velo.png" 2>/dev/null; then
    ICON_PATH="$ICON_DIR/velo.png"
fi

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/velo.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Velo
Comment=A clean MIDI player with practice studio and stage mode
Exec=$VENV/bin/python $SCRIPT_DIR/velo_app.py
Path=$SCRIPT_DIR
Icon=$ICON_PATH
Categories=Audio;AudioVideo;Music;
Terminal=false
StartupWMClass=Velo
DESK
update-desktop-database "$APPS" 2>/dev/null || true

# a handy `velo` terminal command too (works if ~/.local/bin is on PATH)
BINDIR="$HOME/.local/bin"
mkdir -p "$BINDIR"
cat > "$BINDIR/velo" <<RUN
#!/usr/bin/env bash
exec "$VENV/bin/python" "$SCRIPT_DIR/velo_app.py" "\$@"
RUN
chmod +x "$BINDIR/velo"

echo
say "Done! 🎹  Launch Velo from your applications menu (search \"Velo\")"
say "or run  velo  in a terminal."
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    echo
    warn "You're on a Wayland session: everything works EXCEPT 'type the song into"
    warn "another app' (Roblox / Virtual Piano), which needs an X11/Xorg session."
fi
