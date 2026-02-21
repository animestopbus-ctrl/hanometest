# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from abc import ABC, abstractmethod


class BaseFetcher(ABC):
    """
    Every site downloader must extend this class and implement all
    abstract methods. This enforces a consistent interface so the
    download manager can call any fetcher identically.
    """

    SITE_NAME: str = "Unknown"
    SITE_DOMAIN: str = ""

    def __init__(self, download_path: str = "./downloads"):
        self.download_path = download_path
        self._cancelled    = False

    def cancel(self):
        """Signal the fetcher to stop mid-download."""
        self._cancelled = True

    # ─── Must implement ────────────────────────────────────────────────────
    @abstractmethod
    async def resolve_url(self, episode_url: str) -> str:
        """
        Resolve the episode page URL to the actual player/stream URL.
        Returns the resolved URL (may be same as input if no resolution needed).
        """

    @abstractmethod
    async def get_qualities(self, resolved_url: str) -> list[tuple[str, str]]:
        """
        Returns list of (label, format_id) tuples.
        e.g. [("1080p", "137+140"), ("720p", "136+140")]
        Empty list means only 'best' is available.
        """

    @abstractmethod
    async def download(
        self,
        resolved_url: str,
        format_id: str,
        progress_callback=None,
    ) -> str:
        """
        Download the video. Returns the local file path of the downloaded file.
        progress_callback(downloaded, total, speed, eta) is called periodically.
        """

    # ─── Optional override ─────────────────────────────────────────────────
    async def get_auth_headers(self, resolved_url: str) -> dict:
        """
        Returns extra headers needed for downloading this stream.
        Override in fetchers that need X-Video-Token etc.
        """
        return {}

    def get_site_name(self) -> str:
        return self.SITE_NAME
