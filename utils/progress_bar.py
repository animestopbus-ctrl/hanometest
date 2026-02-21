# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from utils.helpers import format_size, format_duration


def make_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Returns a unicode progress bar string."""
    if total <= 0:
        return "▓" * length
    pct     = min(current / total, 1.0)
    filled  = int(pct * length)
    empty   = length - filled
    bar     = "█" * filled + "░" * empty
    return f"[{bar}] {pct*100:.1f}%"


def build_download_progress(
    title: str,
    current: int,
    total: int,
    speed: float,
    eta: float,
    site: str,
    quality: str,
) -> str:
    bar      = make_progress_bar(current, total)
    cur_s    = format_size(current)
    tot_s    = format_size(total) if total else "?"
    spd_s    = f"{format_size(int(speed))}/s" if speed else "?"
    eta_s    = format_duration(eta) if eta else "?"

    return (
        f"<b>📥 Downloading...</b>\n\n"
        f"🎬 <b>{title[:40]}</b>\n"
        f"🌐 <b>Site:</b> {site}\n"
        f"🎞 <b>Quality:</b> {quality}\n\n"
        f"<code>{bar}</code>\n\n"
        f"📦 <b>Size:</b> {cur_s} / {tot_s}\n"
        f"⚡ <b>Speed:</b> {spd_s}\n"
        f"⏳ <b>ETA:</b> {eta_s}"
    )


def build_upload_progress(
    title: str,
    current: int,
    total: int,
    speed: float,
) -> str:
    bar   = make_progress_bar(current, total)
    cur_s = format_size(current)
    tot_s = format_size(total) if total else "?"
    spd_s = f"{format_size(int(speed))}/s" if speed else "?"

    return (
        f"<b>📤 Uploading...</b>\n\n"
        f"🎬 <b>{title[:40]}</b>\n\n"
        f"<code>{bar}</code>\n\n"
        f"📦 <b>Sent:</b> {cur_s} / {tot_s}\n"
        f"⚡ <b>Speed:</b> {spd_s}"
    )
