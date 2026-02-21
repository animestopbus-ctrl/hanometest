# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import re
import os
from urllib.parse import urlparse

# ─── Supported sites registry ────────────────────────────────────────────────
SITE_MAP = {
    "hentaicity.com":   "hentaicity",
    "hentaimama.io":    "hentaimama",
    "hentaihaven.xxx":  "hentaihaven",
}

def detect_site(url: str) -> str | None:
    """Returns site key string or None if not supported."""
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        for domain, key in SITE_MAP.items():
            if domain in host:
                return key
    except Exception:
        pass
    return None

def is_supported_url(url: str) -> bool:
    return detect_site(url) is not None

def sanitize_filename(name: str) -> str:
    """Strip illegal filesystem characters from a filename."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', "_", name.strip())
    return name[:200] or "hanime_video"

def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes <= 0:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def format_duration(seconds: float) -> str:
    """Format seconds into mm:ss or hh:mm:ss."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def extract_episode_name(url: str) -> str:
    """Best-effort episode name from URL path."""
    try:
        path = urlparse(url).path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        return parts[-1].replace("-", " ").title() if parts else "Episode"
    except Exception:
        return "Episode"

def clean_download_dir(path: str):
    """Remove empty files/partial downloads from the download directory."""
    if not os.path.isdir(path):
        return
    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)
        if fname.endswith(".part") or fname.endswith(".ytdl"):
            try:
                os.remove(fpath)
            except Exception:
                pass
        elif os.path.isfile(fpath) and os.path.getsize(fpath) == 0:
            try:
                os.remove(fpath)
            except Exception:
                pass
