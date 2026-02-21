# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ─── Start keyboard ───────────────────────────────────────────────────────────
def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ],
        [
            InlineKeyboardButton("👤 My Account", callback_data="myaccount"),
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("📢 Channel", url="https://t.me/THEUPDATEDGUYS"),
        ],
    ])


# ─── Help keyboard ────────────────────────────────────────────────────────────
def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="start")],
    ])


# ─── Quality picker keyboard ──────────────────────────────────────────────────
def quality_keyboard(qualities: list[tuple[str, str]], session_id: str) -> InlineKeyboardMarkup:
    """
    qualities: list of (label, format_id)  e.g. [("1080p", "137"), ("720p", "136")]
    session_id: unique download session to tie the callback to
    """
    rows = []
    for label, fid in qualities:
        rows.append([
            InlineKeyboardButton(
                f"🎞 {label}",
                callback_data=f"quality:{session_id}:{fid}"
            )
        ])
    rows.append([
        InlineKeyboardButton("✨ Best (Auto)", callback_data=f"quality:{session_id}:best"),
        InlineKeyboardButton("❌ Cancel",     callback_data=f"quality:{session_id}:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


# ─── Server picker keyboard ───────────────────────────────────────────────────
def server_keyboard(servers: list[tuple[str, str]], session_id: str) -> InlineKeyboardMarkup:
    """
    servers: list of (server_name, url)
    """
    rows = []
    for i, (name, _) in enumerate(servers):
        rows.append([
            InlineKeyboardButton(
                f"🖥 {name}",
                callback_data=f"server:{session_id}:{i}"
            )
        ])
    rows.append([
        InlineKeyboardButton("❌ Cancel", callback_data=f"server:{session_id}:cancel")
    ])
    return InlineKeyboardMarkup(rows)


# ─── Admin panel keyboard ─────────────────────────────────────────────────────
def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats",       callback_data="admin:stats"),
            InlineKeyboardButton("📢 Broadcast",   callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton("🚫 Ban User",    callback_data="admin:ban"),
            InlineKeyboardButton("✅ Unban User",  callback_data="admin:unban"),
        ],
        [
            InlineKeyboardButton("⭐ Add Premium", callback_data="admin:premium_add"),
            InlineKeyboardButton("🗑 Rem Premium", callback_data="admin:premium_remove"),
        ],
        [
            InlineKeyboardButton("⚙️ Upload Mode", callback_data="admin:upload_mode"),
            InlineKeyboardButton("🔄 Restart",     callback_data="admin:restart"),
        ],
    ])


# ─── Upload mode keyboard (admin) ─────────────────────────────────────────────
def upload_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 DM Only",         callback_data="set_upload:dm")],
        [InlineKeyboardButton("📢 Channel Only",    callback_data="set_upload:channel")],
        [InlineKeyboardButton("👥 Group Only",      callback_data="set_upload:group")],
        [InlineKeyboardButton("📩+📢 DM + Channel", callback_data="set_upload:both")],
        [InlineKeyboardButton("🔙 Back",            callback_data="admin:panel")],
    ])


# ─── Settings keyboard (user) ─────────────────────────────────────────────────
def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎞 Default Quality", callback_data="setting:quality")],
        [InlineKeyboardButton("🔔 Notifications",   callback_data="setting:notifications")],
        [InlineKeyboardButton("🔙 Back",             callback_data="start")],
    ])


# ─── Force-subscribe keyboard ─────────────────────────────────────────────────
def fsub_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Join Channel", url=channel_link)],
        [InlineKeyboardButton("🔄 Check Again", callback_data="fsub:check")],
    ])


# ─── Confirm cancel download ──────────────────────────────────────────────────
def cancel_download_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel Download", callback_data=f"cancel_dl:{session_id}"),
        ]
    ])
