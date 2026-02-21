# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher — hentaimama.io downloader (497)

"""
HentaiMama Downloader — JS Render Edition for Telegram Bot
Adapted 1:1 from original CLI (234) Playwright version.
Full browser rendering + network interception + tab clicking + regex deep scan.
Pre-merged MP4 only (no FFmpeg). Max speed. Telegram-ready progress.

Bot usage:
    servers = await fetcher.get_servers(episode_url)   # show buttons
    chosen_player = user_picked_url
    qualities = await fetcher.get_qualities(chosen_player)
    await fetcher.download(chosen_player, chosen_format_id, progress_callback)
"""

import os
import re
import asyncio
import time
import yt_dlp
from playwright.async_api import async_playwright

from downloader.base import BaseFetcher
from utils.logger import get_logger
from utils.helpers import sanitize_filename
from secret import DOWNLOAD_PATH

log = get_logger("hentaimama")

SITE_DOMAIN = "hentaimama.io"

SITE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": f"https://{SITE_DOMAIN}/",
}

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

def guess_host(url: str) -> str:
    for h in ["doodstream", "ds2play", "streamtape", "filemoon",
              "streamwish", "vidhide", "voe", "mp4upload", "mixdrop",
              "kwik", "sendvid", "vidoza", "upstream", "vidmoly", "streamlare"]:
        if h in url.lower():
            return h.capitalize()
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "Unknown"


class HentaiMamaFetcher(BaseFetcher):
    SITE_NAME   = "HentaiMama"
    SITE_DOMAIN = SITE_DOMAIN

    def __init__(self, download_path: str = DOWNLOAD_PATH):
        super().__init__(download_path)
        self._last_cb_time = 0.0

    # ── get_servers (FULL Playwright logic from original 234) ─────────────────
    async def get_servers(self, episode_url: str) -> list[tuple[str, str]]:
        """Returns all available video servers (for Telegram buttons)."""
        log.info(f"[HentaiMama] Launching browser for {episode_url}")
        servers = []
        seen_urls = set()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ]
                )

                context = await browser.new_context(
                    user_agent=SITE_HEADERS["User-Agent"],
                    viewport={"width": 1280, "height": 720},
                    locale="en-US",
                )

                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                """)

                page = await context.new_page()

                # Network interception
                async def on_response(response):
                    url = response.url
                    if any(h in url.lower() for h in KNOWN_HOSTS):
                        if url not in seen_urls:
                            seen_urls.add(url)
                            servers.append((f"{guess_host(url)} [network]", url))

                page.on("response", on_response)

                await page.goto(episode_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)

                # Iframes
                for iframe in await page.query_selector_all("iframe"):
                    src = await iframe.get_attribute("src") or await iframe.get_attribute("data-src") or ""
                    if src.startswith("//"):
                        src = "https:" + src
                    if src and (any(h in src.lower() for h in KNOWN_HOSTS) or src.startswith("http")):
                        if src not in seen_urls:
                            seen_urls.add(src)
                            servers.append((guess_host(src), src))

                # Server-picker buttons / data-*
                for attr in ["data-src", "data-embed", "data-url", "data-video", "data-stream"]:
                    for el in await page.query_selector_all(f"[{attr}]"):
                        val = await el.get_attribute(attr) or ""
                        if val.startswith("//"):
                            val = "https:" + val
                        if val.startswith("http") and val not in seen_urls:
                            seen_urls.add(val)
                            name = await el.get_attribute("title") or await el.inner_text() or guess_host(val)
                            servers.append((name.strip()[:35] or guess_host(val), val))

                # Click server tabs (many sites hide servers behind tabs)
                tab_selectors = [
                    ".server-item", ".ep-server", ".server-tab",
                    "[data-server]", ".source-item", ".btn-server",
                    "li[data-index]", ".link-video",
                ]
                for sel in tab_selectors:
                    tabs = await page.query_selector_all(sel)
                    for tab in tabs:
                        try:
                            await tab.click()
                            await page.wait_for_timeout(1500)
                            # re-scan iframes after click
                            for iframe in await page.query_selector_all("iframe"):
                                src = await iframe.get_attribute("src") or ""
                                if src.startswith("//"):
                                    src = "https:" + src
                                if src.startswith("http") and src not in seen_urls:
                                    seen_urls.add(src)
                                    servers.append((guess_host(src), src))
                        except Exception:
                            pass

                # Deep regex scan on final HTML
                html = await page.content()
                patterns = [
                    r'(https?://(?:[a-z0-9\-]+\.)?(?:doodstream|ds2play|d0000d|streamtape|filemoon|streamwish|vidhide|voe\.sx|mp4upload|mixdrop|kwik|sendvid|vidoza)[^\s\'"<>\\]+)',
                    r'["\']?(https?://[^\s\'"<>\\]+\.(?:m3u8|mp4|webm)(?:\?[^\s\'"<>\\]*)?)["\']?',
                ]
                for pat in patterns:
                    for m in re.finditer(pat, html, re.IGNORECASE):
                        url_found = m.group(1) if m.lastindex is not None else m.group(0)
                        if url_found.startswith("http") and url_found not in seen_urls:
                            seen_urls.add(url_found)
                            servers.append((guess_host(url_found), url_found))

                await browser.close()

            log.info(f"[HentaiMama] ✅ Found {len(servers)} source(s)")
            return servers

        except Exception as e:
            log.error(f"[HentaiMama] Playwright failed: {e}", exc_info=True)
            return []

    # ── resolve_url (fallback for auto-mode or single-server flow) ─────────────
    async def resolve_url(self, episode_url: str) -> str:
        """Auto-picks first server (used if bot doesn't show server list)."""
        servers = await self.get_servers(episode_url)
        if servers:
            name, url = servers[0]
            log.info(f"[HentaiMama] Auto-resolved: {name}")
            return url
        log.warning(f"[HentaiMama] No servers found, returning original URL")
        return episode_url

    # ── get_qualities (1:1 from Hentaicity pattern) ───────────────────────────
    async def get_qualities(self, resolved_url: str) -> list[tuple[str, str]]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "http_headers": SITE_HEADERS,
        }
        try:
            info = await asyncio.to_thread(self._extract_info, resolved_url, opts)
            formats = info.get("formats", [])

            merged = [
                f for f in formats
                if f.get("vcodec", "none") != "none" and f.get("acodec", "none") != "none"
            ]

            if not merged:
                log.warning("[HentaiMama] No pre-merged formats found")
                return []

            merged.sort(key=lambda x: x.get("height") or 0, reverse=True)

            result = []
            for f in merged:
                height = f.get("height") or "?"
                fid = f["format_id"]
                ext = f.get("ext", "mp4")
                vc = (f.get("vcodec") or "none").split(".")[0]
                ac = (f.get("acodec") or "none").split(".")[0]
                size = f.get("filesize") or f.get("filesize_approx")
                size_s = f"{size/1_048_576:.1f}MB" if size else "?"
                label = f"{height}p {ext} [{vc}+{ac}] {size_s}"
                result.append((label, fid))

            return result

        except Exception as e:
            log.warning(f"[HentaiMama] get_qualities error: {e}")
            return []

    # ── download (1:1 from Hentaicity pattern) ────────────────────────────────
    async def download(
        self,
        resolved_url: str,
        format_id: str,
        progress_callback=None,
    ) -> str:
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

        ydl_opts = {
            "format": format_id or "best[ext=mp4]/best",
            "outtmpl": f"{self.download_path}/%(title)s.%(ext)s",
            "postprocessors": [],
            "merge_output_format": None,
            "keepvideo": False,
            "restrictfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "concurrent_fragment_downloads": 16,
            "buffersize": 1024 * 1024,
            "ratelimit": None,
            "retries": 6,
            "fragment_retries": 12,
            "hls_prefer_native": True,
            "progress_hooks": [hook],
            "http_headers": SITE_HEADERS,
        }

        info = await asyncio.to_thread(self._extract_and_download, resolved_url, ydl_opts)
        title = info.get("title") or "hentaimama_video"
        return self._find_output_file(self.download_path, title)

    # ── Sync helpers ──────────────────────────────────────────────────────────
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
        # fallback: newest file
        files = [
            os.path.join(directory, f) for f in os.listdir(directory)
            if not f.endswith((".part", ".ytdl")) and os.path.isfile(os.path.join(directory, f))
        ]
        if files:
            return max(files, key=os.path.getmtime)
        raise FileNotFoundError(f"[HentaiMama] Downloaded file not found in {directory}")
