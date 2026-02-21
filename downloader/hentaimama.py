# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher — hentaimama.io downloader

"""
HentaiMama Downloader — JS Render Edition
Source: hentaimama.py (Playwright + yt-dlp multi-server)
Integrated into Hanime Fetcher bot structure.

Pipeline (exact from original):
  1. yt-dlp direct attempt first (fastest if supported)
  2. Playwright headless Chromium:
       - Network response interception (catches CDN URLs live)
       - DOM iframe scan (src + data-src)
       - data-* attribute scan (data-embed, data-url, data-video, data-stream)
       - Server tab click-through (server picker buttons)
       - Deep regex scan of full page HTML
  3. Returns list of (server_name, url) tuples → bot shows server picker
  4. Quality scan: pre-merged streams only (no FFmpeg)
  5. Download with max speed settings
"""

import os
import re
import asyncio
import time
import yt_dlp
from urllib.parse import urlparse

from downloader.base import BaseFetcher
from utils.logger import get_logger
from utils.helpers import sanitize_filename
from secret import DOWNLOAD_PATH

log = get_logger("hentaimama")

SITE_DOMAIN = "hentaimama.io"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SITE_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Referer":    f"https://{SITE_DOMAIN}/",
}

# All CDN players yt-dlp can handle — exact list from hentaimama.py
KNOWN_HOSTS = [
    "doodstream", "dood.", "ds2play", "d0000d",
    "streamtape", "filemoon", "moon",
    "streamwish", "wishembed", "alions",
    "vidhide", "voe.sx", "voe.",
    "mp4upload", "mixdrop", "upstream",
    "vidmoly", "streamlare", "kwik",
    "sendvid", "vidoza", "streamhub",
    "embed", "player", "stream", "video",
]

# Regex patterns for deep HTML scan — exact from hentaimama.py
HTML_PATTERNS = [
    r'(https?://(?:[a-z0-9\-]+\.)?(?:'
    r'doodstream|ds2play|d0000d|streamtape|filemoon|streamwish|'
    r'vidhide|voe\.sx|mp4upload|mixdrop|kwik|sendvid|vidoza'
    r')[^\s\'"<>\\]+)',
    r'["\']?(https?://[^\s\'"<>\\]+\.(?:m3u8|mp4|webm)(?:\?[^\s\'"<>\\]*)?)["\']?',
]

# Server tab selectors — exact from hentaimama.py
TAB_SELECTORS = [
    ".server-item", ".ep-server", ".server-tab",
    "[data-server]", ".source-item", ".btn-server",
    "li[data-index]", ".link-video",
]

# data-* attributes to scan for embed URLs
DATA_ATTRS = ["data-src", "data-embed", "data-url", "data-video", "data-stream"]


def _guess_host(url: str) -> str:
    """Map URL to a human-readable CDN name."""
    for h in [
        "doodstream", "ds2play", "streamtape", "filemoon",
        "streamwish", "vidhide", "voe", "mp4upload", "mixdrop",
        "kwik", "sendvid", "vidoza", "upstream", "vidmoly", "streamlare",
    ]:
        if h in url.lower():
            return h.capitalize()
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "Unknown"


# ── Stage 1: yt-dlp direct (fastest, no browser needed) ──────────────────────
def _try_ytdlp_direct(episode_url: str) -> list[tuple[str, str]]:
    """
    Attempt yt-dlp extraction directly from the episode page.
    If yt-dlp has a native extractor for the embedded player, use it immediately.
    """
    opts = {"quiet": True, "no_warnings": True, "http_headers": SITE_HEADERS}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(episode_url, download=False)
            if info and info.get("formats"):
                log.info("[HentaiMama] yt-dlp direct extraction succeeded.")
                return [("Direct (yt-dlp)", episode_url)]
    except Exception:
        pass
    return []


# ── Stage 2: Playwright full JS render ───────────────────────────────────────
async def _get_servers_playwright(episode_url: str) -> list[tuple[str, str]]:
    """
    Exact Playwright logic from hentaimama.py:
      - Network response interception
      - DOM iframe scan (src + data-src)
      - data-* attribute scan
      - Server tab click-through
      - Deep regex HTML scan
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
        return []

    servers: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        # Mask automation flags — exact from hentaimama.py
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        # ── Network response interception ─────────────────────────────────
        async def on_response(response):
            url = response.url
            if any(h in url.lower() for h in KNOWN_HOSTS):
                host = _guess_host(url)
                if url not in seen_urls:
                    seen_urls.add(url)
                    servers.append((f"{host} [network]", url))

        page.on("response", on_response)

        # ── Load page ─────────────────────────────────────────────────────
        try:
            await page.goto(episode_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log.error(f"[HentaiMama] Page load failed: {e}")
            await browser.close()
            return []

        # Wait for JS player to initialize — exact timing from hentaimama.py
        await page.wait_for_timeout(4000)

        # ── DOM iframe scan ───────────────────────────────────────────────
        iframes = await page.query_selector_all("iframe")
        for iframe in iframes:
            src      = await iframe.get_attribute("src") or ""
            data_src = await iframe.get_attribute("data-src") or ""
            actual   = src or data_src
            if not actual:
                continue
            if actual.startswith("//"):
                actual = "https:" + actual
            if (any(h in actual.lower() for h in KNOWN_HOSTS) or actual.startswith("http")) \
                    and actual not in seen_urls:
                seen_urls.add(actual)
                servers.append((_guess_host(actual), actual))

        # ── data-* attribute scan ─────────────────────────────────────────
        for attr in DATA_ATTRS:
            els = await page.query_selector_all(f"[{attr}]")
            for el in els:
                val = await el.get_attribute(attr) or ""
                if val.startswith("//"):
                    val = "https:" + val
                if val.startswith("http") and val not in seen_urls:
                    seen_urls.add(val)
                    name = (
                        await el.get_attribute("title")
                        or await el.inner_text()
                        or _guess_host(val)
                    )
                    servers.append((name.strip()[:20] or _guess_host(val), val))

        # ── Server tab click-through ──────────────────────────────────────
        for sel in TAB_SELECTORS:
            tabs = await page.query_selector_all(sel)
            for tab in tabs:
                try:
                    await tab.click()
                    await page.wait_for_timeout(1500)
                    # Re-scan iframes after each click
                    for iframe in await page.query_selector_all("iframe"):
                        src = await iframe.get_attribute("src") or ""
                        if src.startswith("//"):
                            src = "https:" + src
                        if src.startswith("http") and src not in seen_urls:
                            seen_urls.add(src)
                            servers.append((_guess_host(src), src))
                except Exception:
                    pass

        # ── Deep regex HTML scan ──────────────────────────────────────────
        html = await page.content()
        for pat in HTML_PATTERNS:
            for m in re.finditer(pat, html, re.IGNORECASE):
                url_found = m.group(1)
                if url_found not in seen_urls:
                    seen_urls.add(url_found)
                    servers.append((_guess_host(url_found), url_found))

        await browser.close()

    log.info(f"[HentaiMama] Playwright found {len(servers)} server(s).")
    return servers


# ── Main fetcher ───────────────────────────────────────────────────────────────
class HentaimimaFetcher(BaseFetcher):
    SITE_NAME   = "HentaiMama"
    SITE_DOMAIN = SITE_DOMAIN

    def __init__(self, download_path: str = DOWNLOAD_PATH):
        super().__init__(download_path)
        self._servers: list[tuple[str, str]] = []
        self._last_cb_time = 0.0

    def get_servers(self) -> list[tuple[str, str]]:
        """Returns the discovered server list — used by bot.py server picker."""
        return self._servers

    # ── resolve_url ───────────────────────────────────────────────────────
    async def resolve_url(self, episode_url: str) -> str:
        """
        Pipeline:
          1. yt-dlp direct (fastest)
          2. Playwright full JS render
        Returns the first server URL found (default selection).
        The full server list is stored in self._servers for the bot's picker.
        """
        # Method 1: yt-dlp direct
        servers = await asyncio.to_thread(_try_ytdlp_direct, episode_url)

        # Method 2: Playwright
        if not servers:
            servers = await _get_servers_playwright(episode_url)

        self._servers = servers

        if not servers:
            log.warning(f"[HentaiMama] No servers found for {episode_url}")
            return episode_url

        return servers[0][1]  # default: first server (bot will show picker)

    # ── get_qualities ─────────────────────────────────────────────────────
    async def get_qualities(self, resolved_url: str) -> list[tuple[str, str]]:
        """
        Pre-merged only (vcodec + acodec both present = one file, no FFmpeg).
        Exact filter from hentaimama.py pick_quality().
        """
        opts = {"quiet": True, "no_warnings": True, "http_headers": SITE_HEADERS}
        try:
            info    = await asyncio.to_thread(self._extract_info, resolved_url, opts)
            formats = info.get("formats", [])

            # Only pre-merged streams
            merged = [
                f for f in formats
                if f.get("vcodec", "none") != "none"
                and f.get("acodec", "none") != "none"
            ]

            if not merged:
                log.warning("[HentaiMama] No pre-merged formats found.")
                return []

            merged.sort(key=lambda x: x.get("height") or 0, reverse=True)

            result = []
            for f in merged:
                height = f.get("height") or "?"
                fid    = f["format_id"]
                ext    = f.get("ext", "mp4")
                vc     = (f.get("vcodec") or "none").split(".")[0]
                ac     = (f.get("acodec") or "none").split(".")[0]
                size   = f.get("filesize") or f.get("filesize_approx")
                size_s = f"{size/1_048_576:.1f}MB" if size else "?"
                label  = f"{height}p {ext} [{vc}+{ac}] {size_s}"
                result.append((label, fid))

            return result

        except Exception as e:
            log.warning(f"[HentaiMama] get_qualities error: {e}")
            return []

    # ── download ──────────────────────────────────────────────────────────
    async def download(
        self,
        resolved_url: str,
        format_id: str,
        progress_callback=None,
    ) -> str:
        """
        Exact ydl_opts from HentaiMamaFetcher._sync_download() in hentaimama.py.
        No FFmpeg. Max speed. Async progress callback to Telegram.
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

        # Exact ydl_opts from hentaimama.py HentaiMamaFetcher
        ydl_opts = {
            "format":              format_id or "best[ext=mp4]/best",
            "outtmpl":             f"{self.download_path}/%(title)s.%(ext)s",
            # ── No FFmpeg ─────────────────────────────────────────────────
            "postprocessors":      [],
            "merge_output_format": None,
            "keepvideo":           False,
            # ─────────────────────────────────────────────────────────────
            "restrictfilenames":   True,
            "quiet":               True,
            "no_warnings":         True,
            "noprogress":          True,
            # ── Max speed ─────────────────────────────────────────────────
            "concurrent_fragment_downloads": 16,
            "buffersize":          1024 * 1024,
            "ratelimit":           None,
            "retries":             6,
            "fragment_retries":    12,
            "hls_prefer_native":   True,
            # ─────────────────────────────────────────────────────────────
            "progress_hooks":      [hook],
            "http_headers":        SITE_HEADERS,
        }

        info = await asyncio.to_thread(self._extract_and_download, resolved_url, ydl_opts)
        title = info.get("title") or "hentaimama_video"
        return self._find_output_file(self.download_path, title)

    # ── Sync helpers ──────────────────────────────────────────────────────
    def _extract_info(self, url: str, opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def _extract_and_download(self, url: str, opts: dict) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True) or {}

    def _find_output_file(self, directory: str, title: str) -> str:
        base = sanitize_filename(title)
        for fname in os.listdir(directory):
            if fname.endswith((".part", ".ytdl")):
                continue
            if base.lower() in fname.lower():
                return os.path.join(directory, fname)
        files = [
            os.path.join(directory, f) for f in os.listdir(directory)
            if not f.endswith((".part", ".ytdl"))
            and os.path.isfile(os.path.join(directory, f))
        ]
        if files:
            return max(files, key=os.path.getmtime)
        raise FileNotFoundError(f"[HentaiMama] Downloaded file not found in {directory}")