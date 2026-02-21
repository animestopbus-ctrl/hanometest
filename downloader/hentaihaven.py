# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher — hentaihaven.xxx downloader

"""
HentaiHaven Downloader — Smart Escalation Edition
Sources: hentaihaven_downloader.py (player.php intercept) + hentaiplay.py (escalation pattern)
Integrated into Hanime Fetcher bot structure.

4-Stage escalation pipeline (stops as soon as any stage succeeds):
  Stage 1 — yt-dlp direct with impersonation (fastest, no browser)
  Stage 2 — Requests + BS4 (fast, no browser needed)
  Stage 3 — Playwright: intercept player.php REQUEST → replay with requests
             → parse response body for m3u8 URL + X-Video-Token auth headers
  Stage 4 — Playwright: intercept outgoing m3u8 REQUEST directly on the wire
             → capture full auth headers from the browser's own request

Auth headers (X-Video-Token, X-Video-Expiration, X-Video-Ip) are passed
to yt-dlp so every TS segment request is authenticated.
"""

import os
import re
import asyncio
import time
import json
import requests as req_lib
import yt_dlp
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from downloader.base import BaseFetcher
from utils.logger import get_logger
from utils.helpers import sanitize_filename
from secret import DOWNLOAD_PATH

log = get_logger("hentaihaven")

SITE_DOMAIN = "hentaihaven.xxx"
M3U8_HOST   = "master-lengs.org"
PLAYER_PHP  = "player.php"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Ad/junk domain filter (from hentaiplay.py)
AD_DOMAINS = [
    "magsrv", "realsrv", "exoclick", "doubleclick",
    "google", "recaptcha", "adgate", "popads",
]

# Robust session with retries (from hentaiplay.py pattern)
def _make_session() -> req_lib.Session:
    s = req_lib.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

_session = _make_session()

# Playwright anti-detection init script
_PLAYWRIGHT_INIT = """
    Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
    Object.defineProperty(navigator, 'plugins',    { get: () => [1,2,3,4,5] });
    Object.defineProperty(navigator, 'languages',  { get: () => ['en-US','en'] });
    Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
    Object.defineProperty(document, 'hidden',          { get: () => false });
"""


# ── Regex extractor for m3u8 URL + auth tokens from any text blob ─────────────
def _find_m3u8(text: str) -> tuple[str | None, dict]:
    """
    Searches for:
      - https://*.master.m3u8* URL
      - X-Video-Token, X-Video-Expiration, X-Video-Ip headers
    Returns (m3u8_url, extra_headers_dict).
    """
    m3u8  = None
    extra = {}

    m = re.search(r'(https?://[^\s\'"\\<>]*master\.m3u8[^\s\'"\\<>]*)', text, re.I)
    if m:
        m3u8 = m.group(1).rstrip('",}]\\ ')

    for key in ["X-Video-Token", "X-Video-Expiration", "X-Video-Ip"]:
        p = re.search(
            rf'["\']?{re.escape(key)}["\']?\s*[=:]\s*["\']?([^\s\'"\\,}}\]]+)["\']?',
            text, re.I
        )
        if p:
            extra[key] = p.group(1).strip('"\' ')

    return m3u8, extra


def _is_ad_url(url: str) -> bool:
    return any(ad in url.lower() for ad in AD_DOMAINS)


# ═════════════════════════════════════════════════════════════════════════════
# Stage 1 — yt-dlp direct with impersonation (from hentaiplay.py)
# ═════════════════════════════════════════════════════════════════════════════
def _try_ytdlp_direct(episode_url: str) -> tuple[str | None, dict]:
    log.info("[HentaiHaven] Stage 1: yt-dlp direct...")
    opts = {
        "quiet":       True,
        "no_warnings": True,
        "impersonate": "chrome",
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(episode_url, download=False)
            if info and (info.get("url") or info.get("formats")):
                log.info("[HentaiHaven] Stage 1: yt-dlp direct succeeded.")
                return episode_url, {
                    "User-Agent": BROWSER_UA,
                    "Referer":    f"https://{SITE_DOMAIN}/",
                }
    except Exception:
        pass
    return None, {}


# ═════════════════════════════════════════════════════════════════════════════
# Stage 2 — Requests + BS4 (from hentaiplay.py URLResolver.extract_normal)
# ═════════════════════════════════════════════════════════════════════════════
def _try_requests_bs4(episode_url: str) -> tuple[str | None, dict]:
    log.info("[HentaiHaven] Stage 2: requests + BS4...")
    headers = {"User-Agent": BROWSER_UA, "Referer": f"https://{SITE_DOMAIN}/"}
    try:
        resp = _session.get(episode_url, headers=headers, timeout=15)
        if resp.status_code in [403, 503]:
            log.warning(f"[HentaiHaven] Stage 2: blocked ({resp.status_code})")
            return None, {}
        resp.raise_for_status()

        # Look for m3u8 directly in page source
        m3u8, extra = _find_m3u8(resp.text)
        if m3u8:
            log.info("[HentaiHaven] Stage 2: m3u8 found in page HTML.")
            h = {**headers, **extra}
            return m3u8, h

        # Look for player.php URL to replay
        php_match = re.search(r'(https?://[^\s\'"<>]*player\.php[^\s\'"<>]*)', resp.text)
        if php_match:
            php_url = php_match.group(1)
            log.info(f"[HentaiHaven] Stage 2: found player.php, replaying...")
            try:
                php_resp = _session.get(php_url, headers=headers, timeout=15)
                m3u8, extra = _find_m3u8(php_resp.text)
                if not m3u8:
                    try:
                        m3u8, extra = _find_m3u8(json.dumps(json.loads(php_resp.text)))
                    except Exception:
                        pass
                if m3u8:
                    log.info("[HentaiHaven] Stage 2: m3u8 found via player.php replay.")
                    h = {**headers, **extra}
                    return m3u8, h
            except Exception as e:
                log.warning(f"[HentaiHaven] Stage 2: player.php replay error: {e}")

    except Exception as e:
        log.warning(f"[HentaiHaven] Stage 2 failed: {e}")
    return None, {}


# ═════════════════════════════════════════════════════════════════════════════
# Stage 3 — Playwright: intercept player.php request → replay to get m3u8
# ═════════════════════════════════════════════════════════════════════════════
async def _try_playwright_player_php(episode_url: str) -> tuple[str | None, dict]:
    log.info("[HentaiHaven] Stage 3: Playwright player.php intercept + replay...")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error("Playwright not installed.")
        return None, {}

    player_php_url     = None
    player_php_headers = {}
    got_it             = asyncio.Event()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--autoplay-policy=no-user-gesture-required",
            ]
        )
        context = await browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script(_PLAYWRIGHT_INIT)
        page = await browser.new_page()

        async def on_request(request):
            nonlocal player_php_url, player_php_headers
            url = request.url
            if _is_ad_url(url):
                return
            if PLAYER_PHP in url and not got_it.is_set():
                player_php_url     = url
                player_php_headers = {
                    k: v for k, v in request.headers.items()
                    if not k.startswith(":")
                }
                log.info("[HentaiHaven] Stage 3: player.php request captured.")
                got_it.set()

        page.on("request", on_request)

        try:
            await page.goto(episode_url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            log.error(f"[HentaiHaven] Stage 3: page load error: {e}")
            await browser.close()
            return None, {}

        try:
            await asyncio.wait_for(got_it.wait(), timeout=12)
        except asyncio.TimeoutError:
            log.warning("[HentaiHaven] Stage 3: player.php not seen within timeout.")

        await browser.close()

    if not player_php_url:
        return None, {}

    # Replay the player.php request with Python requests
    log.info("[HentaiHaven] Stage 3: Replaying player.php request...")
    try:
        resp = req_lib.get(player_php_url, headers=player_php_headers, timeout=20)
        body = resp.text
        log.debug(f"[HentaiHaven] Stage 3: player.php response ({len(body)} chars): {body[:200]}")

        m3u8, extra = _find_m3u8(body)
        if not m3u8:
            try:
                m3u8, extra = _find_m3u8(json.dumps(json.loads(body)))
            except Exception:
                pass
        if m3u8:
            log.info("[HentaiHaven] Stage 3: m3u8 extracted from player.php response.")
            h = {**player_php_headers, **extra}
            h.setdefault("Origin",  f"https://{SITE_DOMAIN}")
            h.setdefault("Referer", f"https://{SITE_DOMAIN}/")
            return m3u8, h
    except Exception as e:
        log.error(f"[HentaiHaven] Stage 3: replay error: {e}")

    return None, {}


# ═════════════════════════════════════════════════════════════════════════════
# Stage 4 — Playwright: intercept outgoing m3u8 request directly
# ═════════════════════════════════════════════════════════════════════════════
async def _try_playwright_m3u8_direct(episode_url: str) -> tuple[str | None, dict]:
    log.info("[HentaiHaven] Stage 4: Playwright direct m3u8 request intercept...")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, {}

    m3u8_url     = None
    m3u8_headers = {}
    got_it       = asyncio.Event()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--autoplay-policy=no-user-gesture-required",
            ]
        )
        context = await browser.new_context(
            user_agent=BROWSER_UA,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script(_PLAYWRIGHT_INIT)
        page = await browser.new_page()

        async def on_request(request):
            nonlocal m3u8_url, m3u8_headers
            url = request.url
            if _is_ad_url(url):
                return
            if M3U8_HOST in url and "master.m3u8" in url and not got_it.is_set():
                m3u8_url     = url
                m3u8_headers = {
                    k: v for k, v in request.headers.items()
                    if not k.startswith(":")
                }
                log.info("[HentaiHaven] Stage 4: m3u8 request intercepted on wire!")
                got_it.set()

        page.on("request", on_request)

        try:
            await page.goto(episode_url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            log.error(f"[HentaiHaven] Stage 4: page load error: {e}")
            await browser.close()
            return None, {}

        # Wait — then try clicking play if m3u8 hasn't fired yet
        try:
            await asyncio.wait_for(got_it.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        if not got_it.is_set():
            log.info("[HentaiHaven] Stage 4: m3u8 not fired, trying to click play...")
            play_selectors = [
                ".plyr__control--overlaid", "[data-plyr='play']",
                "div[class*='play']", "button[class*='play']",
                "div[class*='Play']", "button[class*='Play']",
                "video", ".player-container", "#player",
            ]
            for sel in play_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=500):
                        await el.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await el.click(force=True, timeout=2000)
                        try:
                            await asyncio.wait_for(got_it.wait(), timeout=8)
                        except asyncio.TimeoutError:
                            pass
                        if got_it.is_set():
                            break
                except Exception:
                    pass

        if not got_it.is_set():
            # JS force-play all videos
            try:
                await page.evaluate("""
                    () => {
                        document.querySelectorAll('video').forEach(v => {
                            v.muted = true; v.currentTime = 0;
                            v.play().catch(() => {});
                        });
                        const evt = new MouseEvent('click', {bubbles:true, cancelable:true});
                        document.querySelectorAll('[class*="play"],[class*="Play"]').forEach(
                            el => el.dispatchEvent(evt)
                        );
                    }
                """)
                await asyncio.wait_for(got_it.wait(), timeout=10)
            except Exception:
                pass

        await browser.close()

    if got_it.is_set():
        m3u8_headers.setdefault("Origin",  f"https://{SITE_DOMAIN}")
        m3u8_headers.setdefault("Referer", f"https://{SITE_DOMAIN}/")
        return m3u8_url, m3u8_headers

    return None, {}


# ── Main fetcher ───────────────────────────────────────────────────────────────
class HentaiHavenFetcher(BaseFetcher):
    SITE_NAME   = "HentaiHaven"
    SITE_DOMAIN = SITE_DOMAIN

    def __init__(self, download_path: str = DOWNLOAD_PATH):
        super().__init__(download_path)
        self._auth_headers: dict = {}
        self._last_cb_time = 0.0

    async def get_auth_headers(self, resolved_url: str) -> dict:
        return self._auth_headers

    # ── resolve_url: 4-stage escalation ──────────────────────────────────
    async def resolve_url(self, episode_url: str) -> str:
        """
        Tries each stage in order, stops at first success:
          1. yt-dlp direct (impersonation)
          2. requests + BS4 + player.php regex
          3. Playwright: player.php intercept → replay
          4. Playwright: direct m3u8 wire intercept + play click
        """
        stages = [
            lambda: asyncio.to_thread(_try_ytdlp_direct, episode_url),
            lambda: asyncio.to_thread(_try_requests_bs4, episode_url),
            lambda: _try_playwright_player_php(episode_url),
            lambda: _try_playwright_m3u8_direct(episode_url),
        ]

        for i, stage_fn in enumerate(stages, 1):
            try:
                m3u8_url, headers = await stage_fn()
                if m3u8_url:
                    self._auth_headers = headers
                    log.info(f"[HentaiHaven] Stage {i} succeeded. URL: {m3u8_url[:60]}")
                    return m3u8_url
            except Exception as e:
                log.warning(f"[HentaiHaven] Stage {i} exception: {e}")

        log.error(f"[HentaiHaven] All 4 stages failed for {episode_url}")
        return episode_url  # return original so bot can show error gracefully

    # ── get_qualities ─────────────────────────────────────────────────────
    async def get_qualities(self, resolved_url: str) -> list[tuple[str, str]]:
        clean = {k: v for k, v in self._auth_headers.items() if not k.startswith(":")}
        clean.setdefault("User-Agent", BROWSER_UA)
        clean.setdefault("Origin",     f"https://{SITE_DOMAIN}")
        clean.setdefault("Referer",    f"https://{SITE_DOMAIN}/")

        opts = {"quiet": True, "no_warnings": True, "http_headers": clean}
        try:
            info    = await asyncio.to_thread(self._extract_info, resolved_url, opts)
            formats = info.get("formats", [])

            # HLS streams: sort by height/bitrate
            video_fmts = [f for f in formats if f.get("height") or f.get("tbr")]
            video_fmts.sort(
                key=lambda x: (x.get("height") or 0, x.get("tbr") or 0),
                reverse=True
            )

            result = []
            for f in video_fmts:
                height = f.get("height") or "?"
                fid    = f["format_id"]
                tbr    = f.get("tbr")
                tbr_s  = f"{tbr:.0f}kbps" if tbr else "?"
                label  = f"{height}p {tbr_s}"
                result.append((label, fid))

            return result

        except Exception as e:
            log.warning(f"[HentaiHaven] get_qualities error: {e}")
            return []

    # ── download ──────────────────────────────────────────────────────────
    async def download(
        self,
        resolved_url: str,
        format_id: str,
        progress_callback=None,
    ) -> str:
        os.makedirs(self.download_path, exist_ok=True)
        self._last_cb_time = 0.0

        clean = {k: v for k, v in self._auth_headers.items() if not k.startswith(":")}
        clean.setdefault("User-Agent", BROWSER_UA)
        clean.setdefault("Origin",     f"https://{SITE_DOMAIN}")
        clean.setdefault("Referer",    f"https://{SITE_DOMAIN}/")

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
            "format":              format_id or "best",
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
            "retries":             10,
            "fragment_retries":    20,
            "hls_prefer_native":   True,
            # ─────────────────────────────────────────────────────────────
            "progress_hooks":      [hook],
            "http_headers":        clean,
        }

        info = await asyncio.to_thread(self._extract_and_download, resolved_url, ydl_opts)
        title = info.get("title") or "hentaihaven_video"
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
        raise FileNotFoundError(f"[HentaiHaven] Downloaded file not found in {directory}")