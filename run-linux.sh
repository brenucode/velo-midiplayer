#!/usr/bin/env bash
# Velo — run from source on Linux.
#
# Creates a Python virtualenv that can SEE the system GTK/WebKit bindings
# (--system-site-packages), installs the pure-Python deps, then launches Velo.
# Re-running is cheap: the venv is reused and pip only installs what's missing.
#
# First make sure the system packages are installed (see README-LINUX.md):
#   Fedora:        sudo dnf install python3-gobject gtk3 webkit2gtk4.1
#   Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
#   Arch:          sudo pacman -S python-gobject gtk3 webkit2gtk-4.1
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
VENV="venv-lnx"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: '$PY' not found. Install Python 3 first." >&2
  exit 1
fi

if [ ! -d "$VENV" ]; then
  echo "Creating virtualenv '$VENV' (with access to system GTK/WebKit)…"
  "$PY" -m venv --system-site-packages "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip >/dev/null
echo "Installing/refreshing Python dependencies…"
pip install -r requirements-linux.txt

# Sanity check: can we reach the WebKitGTK binding? (the #1 thing people miss)
if ! python -c "import gi; gi.require_version('WebKit2','4.1'); from gi.repository import WebKit2" 2>/dev/null \
   && ! python -c "import gi; gi.require_version('WebKit2','4.0'); from gi.repository import WebKit2" 2>/dev/null; then
  echo
  echo "WARNING: WebKit2GTK (gir1.2-webkit2 / webkit2gtk) doesn't seem installed." >&2
  echo "         The window won't open without it — see README-LINUX.md." >&2
  echo
fi

# Heads-up: the 'type the song into another app' feature needs an X11 session.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
  echo
  echo "NOTE: You're on a Wayland session. The player, in-app sound, Practice and"
  echo "Stage all work — but 'type the song into another app' (Roblox / Virtual"
  echo "Piano) only works under X11. Log in choosing 'Xorg'/'X11' to use that,"
  echo "or use 'MIDI output' mode (e.g. with FluidSynth)."
  echo
fi

echo "Starting Velo…"
exec python velo_app.py
