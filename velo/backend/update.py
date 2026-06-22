"""Update check — detect a newer GitHub release and help fetch it.

On launch Velo asks GitHub for the latest release of the repo and compares its
tag to the running version. If a newer one exists the UI shows a small banner.
Nothing is installed automatically — the user clicks Download (which fetches the
zip into their Downloads folder and opens it) or opens the release page. We
never overwrite the running app from inside it: a program that rewrites its own
binaries is exactly the pattern antivirus flags, so the swap stays a manual,
visible step.
"""

import os
import re
import subprocess
import webbrowser
import logging

import requests

from velo.backend import config as configuration

logger = logging.getLogger("velo.update")

REPO = "brenucode/velo-midiplayer"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_HEADERS = {
    "User-Agent": "Velo-Updater",
    "Accept": "application/vnd.github+json",
}


def _parseVer(s):
    nums = re.findall(r"\d+", str(s or ""))
    return tuple(int(n) for n in nums[:3]) or (0,)


def checkLatest():
    """Return info about the latest release vs. the running version."""
    try:
        r = requests.get(LATEST_URL, headers=_HEADERS, timeout=8)
        r.raise_for_status()
        d = r.json()
        tag = d.get("tag_name", "") or ""
        asset = ""
        for a in d.get("assets", []) or []:
            if str(a.get("name", "")).lower().endswith(".zip"):
                asset = a.get("browser_download_url", "") or ""
                break
        newer = _parseVer(tag) > _parseVer(configuration.APP_VERSION)
        return {
            "ok": True,
            "current": configuration.APP_VERSION,
            "latest": tag.lstrip("vV") or tag,
            "tag": tag,
            "newer": bool(newer),
            "url": d.get("html_url", "") or "",
            "notes": (d.get("body", "") or "")[:1500],
            "asset": asset,
        }
    except Exception as e:
        logger.info("update check failed: %s", e)
        return {"ok": False}


def openReleasePage(url):
    try:
        if url:
            webbrowser.open(url)
            return True
    except Exception:
        pass
    return False


def downloadZip(assetUrl, tag=""):
    """Download the release zip into the user's Downloads folder and reveal it.
    Only github-hosted URLs are accepted."""
    try:
        from urllib.parse import urlparse
        host = (urlparse(assetUrl).hostname or "").lower()
        if not (host == "github.com" or host.endswith(".github.com")
                or host.endswith("githubusercontent.com")):
            return {"ok": False, "error": "refusing non-github URL"}

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(downloads, exist_ok=True)
        name = re.sub(r"[^\w\-.]+", "_", f"Velo-win-{tag}.zip" if tag else "Velo-win.zip")
        path = os.path.join(downloads, name)

        r = requests.get(assetUrl, headers={"User-Agent": "Velo-Updater"},
                         timeout=120, stream=True)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(65536):
                if chunk:
                    f.write(chunk)

        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        except Exception:
            try:
                os.startfile(downloads)  # noqa: P204 (Windows-only)
            except Exception:
                pass
        return {"ok": True, "path": path}
    except Exception as e:
        logger.warning("update download failed: %s", e)
        return {"ok": False, "error": type(e).__name__}
