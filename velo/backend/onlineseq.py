"""Online Sequencer source for the MIDI Hub.

onlinesequencer.net sits behind a Cloudflare *managed challenge* — the whole
domain (listing, sequence pages, even the MIDI export) returns 403 to anything
that can't run the challenge JS, so a plain ``requests`` scrape (the trick we
use for BitMidi) is impossible.

Velo already embeds a real Chromium (WebView2), so we let a genuine browser
clear the challenge the normal way: a hidden helper window loads the site once,
Cloudflare's non-interactive challenge resolves on its own in ~10s (if it ever
asks for a click, we surface the window so the user solves it), and from that
point the page is a normal, cleared session.

With the session cleared we drive it entirely from Python via ``evaluate_js``:
 * search  → ``fetch('/sequences?search=…')`` in the page context, parse the
   ``.preview`` cards (id from the link, title from the ``title`` attribute).
 * download→ navigate to ``/<id>`` (loads the sequence into their editor) and
   call the site's own ``exportMidi()``. That builds the MIDI client-side and
   hands it to a Blob; we hook ``URL.createObjectURL`` to grab those bytes (and
   stub the anchor click so nothing hits the user's Downloads folder).

So: real browser, real human-passable challenge, the site's own public export
button — no fingerprint spoofing or challenge-bypass. The Velo UI never shows
their site; it only renders the parsed results in our own Hub.
"""

import base64
import json
import os
import re
import threading
import time
import logging

import webview

from velo.backend import config as configuration

logger = logging.getLogger("velo.onlineseq")

BASE = "https://onlinesequencer.net"
downloadFolder = os.path.join(configuration.baseDirectory, "Midis")
os.makedirs(downloadFolder, exist_ok=True)

_WIN = None
_LOCK = threading.RLock()
_BAD_FS = re.compile(r'[^\w\-. ()]+')
_CHALLENGE = ("just a moment", "um momento", "moment", "verify you are human",
              "attention required", "checking your browser", "verificando")


def _challenged(title):
    t = str(title or "").lower()
    return (not t) or any(s in t for s in _CHALLENGE)


def _poll(expr, timeout=20.0, interval=0.5):
    """Evaluate ``expr`` in the helper until it returns something truthy."""
    deadline = int(timeout / interval)
    for _ in range(deadline):
        time.sleep(interval)
        try:
            v = _WIN.evaluate_js(expr)
        except Exception:
            v = None
        if v:
            return v
    return None


def _ensure_window():
    global _WIN
    if _WIN is not None:
        return _WIN
    # hidden so it never flashes in the user's face; shown only if the
    # challenge stalls and needs a manual click
    _WIN = webview.create_window(
        "Velo · Online Sequencer", url=f"{BASE}/sequences",
        width=980, height=720, hidden=True,
    )
    return _WIN


def _await_clear(hard_timeout=90, reveal_after=45):
    """Return True once Cloudflare is cleared, staying invisible.

    With Chromium's background throttling disabled (see the WebView2 flags set
    in velo_app), a *hidden* window keeps running the challenge JS and clears
    on its own in ~20s — so the helper never has to appear. As a last resort,
    if a rare *interactive* challenge stalls past ``reveal_after`` seconds, we
    surface the window so the user can solve it, then hide it again."""
    try:
        if not _challenged(_WIN.evaluate_js("document.title")):
            return True   # already cleared
    except Exception:
        pass

    shown = False
    cleared = False
    for i in range(hard_timeout):
        try:
            title = _WIN.evaluate_js("document.title")
        except Exception:
            title = None
        if not _challenged(title):
            cleared = True
            break
        if i >= reveal_after and not shown:   # stuck → likely needs a human click
            try:
                _WIN.show()
            except Exception:
                pass
            shown = True
        time.sleep(1)
    if shown:
        try:
            _WIN.hide()
        except Exception:
            pass
    return cleared


# ---- search ---------------------------------------------------------------
_SEARCH_JS = r"""
window.__os_s = null;
(async () => {
  try {
    const r = await fetch(%s, { credentials: 'include' });
    if (!r.ok) { window.__os_s = JSON.stringify({ ok: false, status: r.status }); return; }
    const t = await r.text();
    const doc = new DOMParser().parseFromString(t, 'text/html');
    const items = [...doc.querySelectorAll('.preview')].map(c => {
      const a = c.querySelector('a[href]');
      const id = a ? (a.getAttribute('href') || '').replace(/[^0-9]/g, '') : '';
      return { id,
               title: (c.getAttribute('title') || '').trim(),
               notes: ((c.querySelector('.info') || {}).textContent || '').trim() };
    }).filter(x => x.id);
    window.__os_s = JSON.stringify({ ok: true, items });
  } catch (e) { window.__os_s = JSON.stringify({ ok: false, error: String(e) }); }
})();
"""


def search(query, limit=120):
    """Return ``{ok, items:[{id,title,notes}], needWindow?}``."""
    with _LOCK:
        try:
            _ensure_window()
            if not _await_clear():
                return {"ok": False, "error": "cloudflare", "needWindow": True}
            q = (query or "").strip()
            from urllib.parse import quote
            url = "/sequences?search=" + quote(q)
            _WIN.evaluate_js(_SEARCH_JS % json.dumps(url))
            raw = _poll("window.__os_s", timeout=20)
            if not raw:
                return {"ok": False, "error": "timeout"}
            data = json.loads(raw)
            if not data.get("ok"):
                return {"ok": False, "error": data.get("error") or f"http {data.get('status')}"}
            items = data.get("items", [])[:limit]
            return {"ok": True, "items": items}
        except Exception as e:
            logger.warning(f"onlineseq.search error: {e}")
            return {"ok": False, "error": type(e).__name__}


# ---- download -------------------------------------------------------------
# Installed after each navigation (a page load wipes it): capture the Blob that
# exportMidi() generates and stop the anchor click from saving to disk.
_HOOK_JS = r"""
window.__os_midi = null; window.__os_err = null;
(function () {
  try {
    const oc = URL.createObjectURL.bind(URL);
    URL.createObjectURL = function (o) {
      try {
        if (o instanceof Blob) {
          const fr = new FileReader();
          fr.onload = function () { window.__os_midi = fr.result; };
          fr.readAsDataURL(o);
        }
      } catch (e) { window.__os_err = String(e); }
      return oc(o);
    };
    const ac = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
      if (this.download) return;            // swallow the file-save click
      return ac.apply(this, arguments);
    };
  } catch (e) { window.__os_err = String(e); }
})();
"""


def download(seqId, title=None):
    """Navigate to the sequence, run the site's exportMidi(), capture the MIDI
    bytes and save them. Returns ``{ok, path}``."""
    with _LOCK:
        try:
            sid = re.sub(r"[^0-9]", "", str(seqId or ""))
            if not sid:
                return {"ok": False, "error": "bad id"}
            _ensure_window()
            _WIN.load_url(f"{BASE}/{sid}")
            if not _await_clear():
                return {"ok": False, "error": "cloudflare", "needWindow": True}
            # wait for the editor to define exportMidi and load the sequence
            if not _poll("(typeof exportMidi==='function')?'1':''", timeout=30):
                return {"ok": False, "error": "editor"}
            time.sleep(2.5)  # let song.notes populate

            data = None
            for attempt in range(2):
                _WIN.evaluate_js(_HOOK_JS)
                _WIN.evaluate_js("try{exportMidi();}catch(e){window.__os_err='call:'+e;}")
                data = _poll("window.__os_midi", timeout=10)
                if data:
                    break
                time.sleep(2.5)
            if not data:
                err = None
                try:
                    err = _WIN.evaluate_js("window.__os_err")
                except Exception:
                    pass
                return {"ok": False, "error": err or "export"}

            # data is a "data:audio/midi;base64,…" URL
            b64 = data.split(",", 1)[1] if "," in data else data
            raw = base64.b64decode(b64)
            if raw[:4] != b"MThd":
                return {"ok": False, "error": "not midi"}

            base = (title or f"sequence-{sid}").strip()
            base = _BAD_FS.sub("_", base)[:90].rstrip(". ") or f"sequence-{sid}"
            if not base.lower().endswith((".mid", ".midi")):
                base += ".mid"
            path = os.path.join(downloadFolder, base)
            with open(path, "wb") as f:
                f.write(raw)
            return {"ok": True, "path": path}
        except Exception as e:
            logger.warning(f"onlineseq.download error: {e}")
            return {"ok": False, "error": type(e).__name__}


def shutdown():
    global _WIN
    try:
        if _WIN is not None:
            _WIN.destroy()
    except Exception:
        pass
    _WIN = None
