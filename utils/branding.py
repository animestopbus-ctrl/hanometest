# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

# ─── Identity ─────────────────────────────────────────────────────────────────
BOT_NAME       = "Hanime Fetcher"
DEVELOPER      = "LastPerson07"
DEV_CHANNEL    = "@THEUPDATEDGUYS"
DEV_TELEGRAM   = "@RexBots_Official"
VERSION        = "1.0.0"

# ─── Header / Footer ──────────────────────────────────────────────────────────
HEADER = f"<b>🎌 {BOT_NAME}</b>"
FOOTER = f"\n\n<i>— Powered by {DEVELOPER} | {DEV_CHANNEL}</i>"

# ─── Start Message ────────────────────────────────────────────────────────────
START_TEXT = (
    f"{HEADER}\n\n"
    "👋 <b>Welcome!</b> I can download hentai videos from multiple sites "
    "and send them straight to your Telegram.\n\n"
    "<b>📌 Supported Sites:</b>\n"
    "  • hentaicity.com\n"
    "  • hentaimama.io\n"
    "  • hentaihaven.xxx\n\n"
    "<b>⚡ How to use:</b>\n"
    "  Just send me a valid episode link and I'll handle the rest!\n\n"
    "<b>🔐 Login:</b> Use /login to connect your Telegram account for "
    "uploading to channels/groups.\n\n"
    f"<b>📌 Commands:</b> /help\n"
    f"{FOOTER}"
)

# ─── Help Text ────────────────────────────────────────────────────────────────
HELP_TEXT = (
    f"{HEADER} — Help\n\n"
    "<b>📥 Downloading:</b>\n"
    "  Send any supported episode URL\n\n"
    "<b>👤 Account:</b>\n"
    "  /login — Connect your Telegram account\n"
    "  /logout — Disconnect your account\n"
    "  /mysettings — View your preferences\n\n"
    "<b>⚙️ Settings:</b>\n"
    "  /quality — Set default quality\n\n"
    "<b>ℹ️ Other:</b>\n"
    "  /status — Check bot status\n"
    "  /history — Your last 10 downloads\n"
    f"{FOOTER}"
)

# ─── Watermark appended to filenames ─────────────────────────────────────────
FILE_CAPTION = (
    f"<b>🎌 {{title}}</b>\n\n"
    f"📥 <b>Quality:</b> {{quality}}\n"
    f"📦 <b>Size:</b> {{size}}\n"
    f"🌐 <b>Source:</b> {{site}}\n"
    f"{FOOTER}"
)
