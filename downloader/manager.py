# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from downloader.base import BaseFetcher
from downloader.hentaicity import HentaicityFetcher
from downloader.hentaimama import HentaimimaFetcher
from downloader.hentaihaven import HentaiHavenFetcher
from utils.helpers import detect_site
from utils.logger import get_logger
from secret import DOWNLOAD_PATH

log = get_logger("manager")

# Registry: site_key → fetcher class
# To add a new site: create downloader/newsite.py, add entry here. Done.
FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
    "hentaicity":  HentaicityFetcher,
    "hentaimama":  HentaimimaFetcher,
    "hentaihaven": HentaiHavenFetcher,
}


def get_fetcher(url: str) -> BaseFetcher | None:
    """
    Detects the site from the URL and returns an initialized fetcher instance.
    Returns None if the site is not supported.
    """
    site_key = detect_site(url)
    if not site_key:
        log.warning(f"No fetcher found for URL: {url}")
        return None

    fetcher_class = FETCHER_REGISTRY.get(site_key)
    if not fetcher_class:
        log.warning(f"Site key '{site_key}' has no registered fetcher.")
        return None

    log.info(f"Routing {url} → {fetcher_class.__name__}")
    return fetcher_class(download_path=DOWNLOAD_PATH)


def list_supported_sites() -> list[str]:
    """Returns list of supported domain strings for display."""
    from utils.helpers import SITE_MAP
    return list(SITE_MAP.keys())
