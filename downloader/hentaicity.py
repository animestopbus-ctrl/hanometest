# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher — hentaicity.com downloader

"""
Hentaicity Downloader — No FFmpeg / Max Speed Edition
Source: hcitytestpassed.py (✅ tests passed)
Integrated into Hanime Fetcher bot structure.

Logic preserved 1:1 from original:
  - Requests + BS4 iframe resolver
  - Pre-merged MP4 only (vcodec + acodec both present = no FFmpeg needed)
  - 16 concurrent fragments, 1MB buffer, no rate limit
  - Async progress callback → Telegram message edit
"""

import os
import asyncio
import time
import requests
from bs4 import BeautifulSoup
import yt_dlp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from downloader.base import BaseFetcher
from utils.logger import get_logger
from utils.helpers import sanitize_filename
from secret import DOWNLOAD_PATH

log = get_logger("hentaicity")

SITE_DOMAIN = "hentaicity.com"

# Exact headers from hcitytestpassed.py
SITE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    f"https://{SITE_DOMAIN}/",
}

# Robust session with retry — from hentaiplay.py escalation pattern
def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

_session = _make_session()


# ── Stage 1: Iframe resolver (exact from hcitytestpassed.py) ──────────────────
class _URLResolver:
    @staticmethod
    def resolve_iframe(url: str) -> str:
        """
        Fetches the episode page with requests + BS4,
        finds the first player/embed/video iframe and returns its src.
        Falls back to original URL if nothing found.
        """
        try:
            r = _session.get(url, headers=SITE_HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src", "").strip()
                if not src:
                    continue
                if any(k in src for k in ("player", "embed", "video", "stream")):
                    return src
                if src.startswith("https://"):
                    return src
            return url
        except Exception as e:
            log.warning(f"Iframe resolve failed for {url}: {e}")
            return url


# ── Main fetcher ───────────────────────────────────────────────────────────────
class HentaicityFetcher(BaseFetcher):
    SITE_NAME   = "HentaiCity"
    SITE_DOMAIN = SITE_DOMAIN

    def __init__(self, download_path: str = DOWNLOAD_PATH):
        super().__init__(download_path)
        self._last_cb_time = 0.0

    # ── resolve_url ───────────────────────────────────────────────────────
    async def resolve_url(self, episode_url: str) -> str:
        """Scrape iframe embed URL from the episode page (thread-safe)."""
        resolved = await asyncio.to_thread(_URLResolver.resolve_iframe, episode_url)
        log.info(f"[HentaiCity] Resolved: {episode_url[:55]} → {resolved[:55]}")
        return resolved

    # ── get_qualities ─────────────────────────────────────────────────────
    async def get_qualities(self, resolved_url: str) -> list[tuple[str, str]]:
        """
        Scans yt-dlp format list and returns only pre-merged streams.
        Pre-merged = vcodec AND acodec both present → single download file, no FFmpeg.
        Exact filter logic from hcitytestpassed.py.
        """
        opts = {
            "quiet":       True,
            "no_warnings": True,
            "http_headers": SITE_HEADERS,
        }
        try:
            info    = await asyncio.to_thread(self._extract_info, resolved_url, opts)
            formats = info.get("formats", [])

            # Only pre-merged streams (video + audio in one file)
            merged = [
                f for f in formats
                if f.get("vcodec", "none") != "none"
                and f.get("acodec", "none") != "none"
            ]

            if not merged:
                log.warning("[HentaiCity] No pre-merged streams found.")
                return []

            # Sort highest resolution first
            merged.sort(key=lambda x: x.get("height") or 0, reverse=True)

            result = []
            for f in merged:
                height = f.get("height") or "?"
                fid    = f["format_id"]
                ext    = f.get("ext", "mp4")
                fps    = f.get("fps") or "?"
                vc     = (f.get("vcodec") or "none").split(".")[0]
                ac     = (f.get("acodec") or "none").split(".")[0]
                size   = f.get("filesize") or f.get("filesize_approx")
                size_s = f"{size/1_048_576:.1f}MB" if size else "?"
                # label shown in Telegram quality picker button
                label  = f"{height}p {ext} [{vc}+{ac}] {size_s} {fps}fps"
                result.append((label, fid))

            return result

        except Exception as e:
            log.warning(f"[HentaiCity] get_qualities error: {e}")
            return []

    # ── download ──────────────────────────────────────────────────────────
    async def download(
        self,
        resolved_url: str,
        format_id: str,
        progress_callback=None,
    ) -> str:
        """
        Downloads the video using exact ydl_opts from hcitytestpassed.py.
        Fires async progress_callback(downloaded, total, speed, eta) every 3s.
        Returns local file path of completed download.
        """
        os.makedirs(self.download_path, exist_ok=True)
        self._last_cb_time = 0.0

        def hook(d):
            if self._cancelled:
                raise yt_dlp.utils.DownloadError("Cancelled by user")

            if d["status"] == "downloading" and progress_callback:
                now = time.time()
                if now - self._last_cb_time >= 3:
                    self._last_cb_time = now
                    asyncio.get_event_loop().call_soon_threadsafe(
                        asyncio.ensure_future,
                        progress_callback(
                            d.get("downloaded_bytes", 0),
                            d.get("total_bytes") or d.get("total_bytes_estimate", 0),
                            d.get("speed") or 0,
                            d.get("eta") or 0,
                        )
                    )

        # Exact ydl_opts from hcitytestpassed.py — proven working
        ydl_opts = {
            "format":              format_id or "best[ext=mp4]/best",
            "outtmpl":             f"{self.download_path}/%(title)s.%(ext)s",
            # ── No FFmpeg at all ──────────────────────────────────────────
            "postprocessors":      [],
            "merge_output_format": None,
            "keepvideo":           False,
            # ─────────────────────────────────────────────────────────────
            "restrictfilenames":   True,
            "quiet":               True,
            "no_warnings":         True,
            "noprogress":          True,
            # ── Max speed knobs ───────────────────────────────────────────
            "concurrent_fragment_downloads": 16,
            "buffersize":          1024 * 1024,
            "ratelimit":           None,
            "retries":             5,
            "fragment_retries":    10,
            "hls_prefer_native":   True,
            # ─────────────────────────────────────────────────────────────
            "progress_hooks":      [hook],
            "http_headers":        SITE_HEADERS,
        }

        info = await asyncio.to_thread(self._extract_and_download, resolved_url, ydl_opts)
        title = info.get("title") or "hentaicity_video"
        return self._find_output_file(self.download_path, title)

    # ── Sync helpers (run in thread pool) ────────────────────────────────
    def _extract_info(self, url: str, opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def _extract_and_download(self, url: str, opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True) or {}

    def _find_output_file(self, directory: str, title: str) -> str:
        """
        yt-dlp writes files with unpredictable names (restrictfilenames mangling).
        Searches by sanitized title first, then falls back to most-recent file.
        """
        base = sanitize_filename(title)
        for fname in os.listdir(directory):
            if fname.endswith((".part", ".ytdl")):
                continue
            if base.lower() in fname.lower():
                return os.path.join(directory, fname)
        # Fallback — most recently modified non-partial file
        files = [
            os.path.join(directory, f) for f in os.listdir(directory)
            if not f.endswith((".part", ".ytdl"))
            and os.path.isfile(os.path.join(directory, f))
        ]
        if files:
            return max(files, key=os.path.getmtime)
        raise FileNotFoundError(f"[HentaiCity] Downloaded file not found in {directory}")