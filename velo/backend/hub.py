"""MIDI Hub — online library.

Consumes the same public nanomidi.net API the original app used (the library
content is hosted there). The Velo UI re-skins it; the data source is unchanged.
"""

import os
import re
import requests

from velo.backend import config as configuration

API = "https://api.nanomidi.net"
MIDI_DATA_URL = f"{API}/api/midiData"

downloadFolder = os.path.join(configuration.baseDirectory, "Midis")
os.makedirs(downloadFolder, exist_ok=True)


def listMidis():
    r = requests.get(MIDI_DATA_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        data.reverse()
    items = []
    for m in data:
        imageFile = m.get("imageFilename")
        items.append({
            "id": m.get("id"),
            "name": m.get("name", ""),
            "artists": m.get("artists", ""),
            "arranger": m.get("arranger") or "",
            "uploader": m.get("uploader", ""),
            "downloads": m.get("downloads", 0),
            "views": m.get("views", 0),
            "image": f"{API}/api/v2/images/{imageFile}?size=100x100" if imageFile else "",
            "midiFilename": m.get("midiFilename") or "",
        })
    return items


def downloadMidi(midiFilename):
    url = f"{API}/api/midis/{midiFilename}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    safeName = os.path.basename(midiFilename)
    path = os.path.join(downloadFolder, safeName)
    with open(path, "wb") as f:
        f.write(r.content)
    return path


# ---- BitMidi (alternative source) -----------------------------------------
# BitMidi sits behind Cloudflare and only serves JSON to browser-like clients,
# so a real User-Agent is required.
BITMIDI = "https://bitmidi.com"
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_BAD_FS = re.compile(r'[^\w\-. ()]+')


def bitmidiSearch(query, page=0):
    q = (query or "").strip() or "piano"
    try:
        page = max(0, int(page))
    except Exception:
        page = 0
    r = requests.get(f"{BITMIDI}/api/midi/search",
                     params={"q": q, "page": page}, headers=_BROWSER_HEADERS, timeout=15)
    r.raise_for_status()
    result = (r.json() or {}).get("result", {})
    items = []
    for x in result.get("results", []):
        du = x.get("downloadUrl") or (f"/uploads/{x.get('id')}.mid" if x.get("id") else "")
        if not du:
            continue
        items.append({
            "name": x.get("name", ""),
            "artists": "BitMidi",
            "downloads": x.get("downloads") or x.get("plays") or 0,
            "views": x.get("views") or 0,
            "image": "",
            "downloadUrl": du,
        })
    pageSize = (result.get("query", {}) or {}).get("pageSize", 15) or 15
    return {"items": items, "total": result.get("total", len(items)), "page": page, "pageSize": pageSize}


def bitmidiDownload(downloadUrl, name=None):
    du = str(downloadUrl or "")
    if du.startswith("http"):
        # the downloadUrl comes from BitMidi's search JSON — only follow it if it
        # really points at bitmidi, so a tampered response can't make us fetch an
        # arbitrary host (e.g. a localhost/LAN address) and save it to disk.
        from urllib.parse import urlparse
        host = (urlparse(du).hostname or "").lower()
        if not (host == "bitmidi.com" or host.endswith(".bitmidi.com")):
            raise ValueError("refusing non-bitmidi download URL")
        url = du
    else:
        url = BITMIDI + du
    r = requests.get(url, headers=_BROWSER_HEADERS, timeout=25)
    r.raise_for_status()
    base = (name or os.path.basename(str(downloadUrl).split("?")[0]) or "bitmidi").strip()
    base = _BAD_FS.sub("_", base)
    if not base.lower().endswith((".mid", ".midi")):
        base += ".mid"
    path = os.path.join(downloadFolder, base[:90])
    with open(path, "wb") as f:
        f.write(r.content)
    return path
