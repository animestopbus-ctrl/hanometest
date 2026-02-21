# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import os
import asyncio
import uuid
from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery
from pyrogram import enums
from aiohttp import web

from secret import (
    BOT_TOKEN, API_ID, API_HASH, STRING_SESSION,
    OWNER_ID, LOG_CHANNEL_ID, DOWNLOAD_PATH
)
from database.db import db
from downloader.manager import get_fetcher, list_supported_sites
from downloader.hentaimama import HentaimimaFetcher
from uploader.telegram_uploader import upload_video, upload_to_log_channel
from uploader.progress import UploadProgressTracker
from auth.session import (
    login_start, logout, cancel_login, login_handler, finalize_login
)
from auth.fsub import enforce_fsub, check_fsub_callback
from auth.access import check_access, can_start_download, register_download, release_download
from utils.branding import START_TEXT, HELP_TEXT, HEADER, FOOTER, BOT_NAME
from utils.helpers import is_supported_url, detect_site, sanitize_filename, format_size, clean_download_dir
from utils.progress_bar import build_download_progress
from utils.ui import (
    start_keyboard, help_keyboard, quality_keyboard,
    server_keyboard, settings_keyboard, cancel_download_keyboard
)
from utils.logger import get_logger
from admin import commands, panel  # register handlers by importing

log = get_logger("bot")

# ─── Active download sessions ─────────────────────────────────────────────────
# session_id → { "fetcher", "resolved_url", "servers", "user_id", "status_msg" }
DOWNLOAD_SESSIONS: dict[str, dict] = {}

# ─── Build client ─────────────────────────────────────────────────────────────
client_kwargs = dict(
    name      = "HanimeFetcher",
    api_id    = API_ID,
    api_hash  = API_HASH,
    bot_token = BOT_TOKEN,
)
if STRING_SESSION:
    # Optional string session for uploading as user account
    client_kwargs["session_string"] = STRING_SESSION

app = Client(**client_kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# START / HELP
# ═══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_id   = message.from_user.id
    username  = message.from_user.username
    full_name = message.from_user.first_name

    is_new = await db.add_user(user_id, username, full_name)

    if is_new and LOG_CHANNEL_ID:
        try:
            await client.send_message(
                LOG_CHANNEL_ID,
                f"👤 <b>New User!</b>\n"
                f"Name: <a href='tg://user?id={user_id}'>{full_name}</a>\n"
                f"ID: <code>{user_id}</code>\n"
                f"Username: @{username or 'N/A'}",
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

    await message.reply(START_TEXT, reply_markup=start_keyboard(), parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.private & filters.command("help"))
async def help_handler(client: Client, message: Message):
    await message.reply(HELP_TEXT, reply_markup=help_keyboard(), parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.private & filters.command("status"))
async def status_handler(client: Client, message: Message):
    stats = await db.get_stats()
    me    = await client.get_me()
    await message.reply(
        f"{HEADER} — <b>Status</b>\n\n"
        f"🟢 <b>Bot is online</b>\n"
        f"👥 <b>Users:</b> {stats.get('total_users', 0):,}\n"
        f"📥 <b>Downloads:</b> {stats.get('total_downloads', 0):,}\n"
        f"🤖 <b>Version:</b> 1.0.0\n"
        f"{FOOTER}",
        parse_mode=enums.ParseMode.HTML
    )


@app.on_message(filters.private & filters.command("history"))
async def history_handler(client: Client, message: Message):
    user_id   = message.from_user.id
    downloads = await db.get_user_downloads(user_id, limit=10)
    if not downloads:
        return await message.reply(
            "<b>📭 No download history yet.</b>\n\nSend a supported URL to get started!",
            parse_mode=enums.ParseMode.HTML
        )
    lines = [f"{HEADER} — <b>Your Last Downloads</b>\n"]
    for i, d in enumerate(downloads, 1):
        status_icon = "✅" if d["status"] == "success" else "❌"
        lines.append(
            f"{i}. {status_icon} <b>{d['site']}</b> — {d['quality']}\n"
            f"   <code>{d['url'][:50]}...</code>"
        )
    lines.append(FOOTER)
    await message.reply("\n".join(lines), parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.private & filters.command("mysettings"))
async def mysettings_handler(client: Client, message: Message):
    user_id  = message.from_user.id
    settings = await db.get_settings(user_id)
    await message.reply(
        f"{HEADER} — <b>Your Settings</b>\n\n"
        f"🎞 <b>Default Quality:</b> {settings.get('default_quality', 'best')}\n"
        f"📩 <b>Upload Mode:</b> {settings.get('upload_mode', 'dm')}\n"
        f"🔔 <b>Notifications:</b> {'On' if settings.get('notifications', True) else 'Off'}\n"
        f"{FOOTER}",
        reply_markup=settings_keyboard(),
        parse_mode=enums.ParseMode.HTML
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DOWNLOAD PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
@app.on_message(filters.private & filters.text & ~filters.command([
    "start", "help", "login", "logout", "cancel", "cancellogin",
    "admin", "ban", "unban", "broadcast", "premium", "stats",
    "users", "status", "history", "mysettings", "quality"
]))
async def url_handler(client: Client, message: Message):
    user_id = message.from_user.id
    url     = message.text.strip()

    if not await check_access(message):
        return
    if not await enforce_fsub(client, message):
        return

    if not is_supported_url(url):
        sites = "\n".join(f"  • {s}" for s in list_supported_sites())
        return await message.reply(
            f"<b>❌ Unsupported URL.</b>\n\n"
            f"<b>Supported sites:</b>\n{sites}\n\n"
            f"Please send a valid episode link.",
            parse_mode=enums.ParseMode.HTML
        )

    if not can_start_download(user_id):
        from secret import MAX_CONCURRENT_DOWNLOADS
        return await message.reply(
            f"<b>⏳ You already have {MAX_CONCURRENT_DOWNLOADS} active download(s).</b>\n"
            f"Please wait for them to finish.",
            parse_mode=enums.ParseMode.HTML
        )

    site_key   = detect_site(url)
    session_id = str(uuid.uuid4())[:8]
    fetcher    = get_fetcher(url)

    if not fetcher:
        return await message.reply("<b>❌ Could not initialize downloader.</b>", parse_mode=enums.ParseMode.HTML)

    status_msg = await message.reply(
        f"<b>🔍 Resolving stream URL...</b>\n\n"
        f"🌐 <b>Site:</b> {fetcher.get_site_name()}\n"
        f"⏳ Please wait...",
        parse_mode=enums.ParseMode.HTML
    )

    register_download(user_id)

    try:
        resolved_url = await fetcher.resolve_url(url)

        if not resolved_url or resolved_url == url and "m3u8" not in url:
            release_download(user_id)
            return await status_msg.edit_text(
                "<b>❌ Could not resolve video stream.</b>\n\n"
                "The site may be temporarily unavailable.",
                parse_mode=enums.ParseMode.HTML
            )

        if isinstance(fetcher, HentaimimaFetcher):
            servers = fetcher.get_servers()
            if len(servers) > 1:
                DOWNLOAD_SESSIONS[session_id] = {
                    "fetcher":      fetcher,
                    "servers":      servers,
                    "url":          url,
                    "user_id":      user_id,
                    "status_msg":   status_msg,
                }
                await status_msg.edit_text(
                    f"<b>🖥 Multiple servers found!</b>\n\n"
                    f"<b>Site:</b> {fetcher.get_site_name()}\n"
                    f"Choose a server to continue:",
                    reply_markup=server_keyboard(servers, session_id),
                    parse_mode=enums.ParseMode.HTML
                )
                return

        await status_msg.edit_text(
            f"<b>🎞 Fetching quality options...</b>\n\n"
            f"🌐 <b>Site:</b> {fetcher.get_site_name()}",
            parse_mode=enums.ParseMode.HTML
        )

        qualities = await fetcher.get_qualities(resolved_url)

        DOWNLOAD_SESSIONS[session_id] = {
            "fetcher":      fetcher,
            "resolved_url": resolved_url,
            "url":          url,
            "user_id":      user_id,
            "status_msg":   status_msg,
            "site_key":     site_key,
        }

        if not qualities:
            await _start_download(client, session_id, "best")
            return

        await status_msg.edit_text(
            f"<b>🎞 Select Quality</b>\n\n"
            f"🌐 <b>Site:</b> {fetcher.get_site_name()}\n"
            f"Choose your preferred quality:",
            reply_markup=quality_keyboard(qualities, session_id),
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        release_download(user_id)
        log.error(f"URL handler error for {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"<b>❌ Error:</b> {str(e)[:200]}\n\nPlease try again.",
            parse_mode=enums.ParseMode.HTML
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════
@app.on_callback_query(lambda _, q: q.data.startswith("server:"))
async def server_callback(client: Client, query: CallbackQuery):
    _, session_id, choice = query.data.split(":", 2)
    session = DOWNLOAD_SESSIONS.get(session_id)

    if not session or session["user_id"] != query.from_user.id:
        return await query.answer("Session expired.", show_alert=True)

    if choice == "cancel":
        release_download(query.from_user.id)
        DOWNLOAD_SESSIONS.pop(session_id, None)
        await query.message.edit_text("<b>❌ Download cancelled.</b>", parse_mode=enums.ParseMode.HTML)
        return

    await query.answer()
    servers      = session["servers"]
    server_index = int(choice)
    _, server_url = servers[server_index]

    fetcher = session["fetcher"]
    session["resolved_url"] = server_url
    status_msg = session["status_msg"]

    await status_msg.edit_text(
        f"<b>🎞 Fetching quality options...</b>\n\n"
        f"🖥 <b>Server:</b> {servers[server_index][0]}",
        parse_mode=enums.ParseMode.HTML
    )

    qualities = await fetcher.get_qualities(server_url)
    if not qualities:
        await _start_download(client, session_id, "best")
        return

    await status_msg.edit_text(
        f"<b>🎞 Select Quality</b>\n\n"
        f"🖥 <b>Server:</b> {servers[server_index][0]}\n"
        f"Choose your preferred quality:",
        reply_markup=quality_keyboard(qualities, session_id),
        parse_mode=enums.ParseMode.HTML
    )


@app.on_callback_query(lambda _, q: q.data.startswith("quality:"))
async def quality_callback(client: Client, query: CallbackQuery):
    _, session_id, format_id = query.data.split(":", 2)
    session = DOWNLOAD_SESSIONS.get(session_id)

    if not session or session["user_id"] != query.from_user.id:
        return await query.answer("Session expired.", show_alert=True)

    if format_id == "cancel":
        release_download(query.from_user.id)
        DOWNLOAD_SESSIONS.pop(session_id, None)
        await query.message.edit_text("<b>❌ Download cancelled.</b>", parse_mode=enums.ParseMode.HTML)
        return

    await query.answer()
    await _start_download(client, session_id, format_id)


@app.on_callback_query(lambda _, q: q.data.startswith("cancel_dl:"))
async def cancel_download_callback(client: Client, query: CallbackQuery):
    session_id = query.data.split(":")[1]
    session    = DOWNLOAD_SESSIONS.get(session_id)

    if not session or session["user_id"] != query.from_user.id:
        return await query.answer("Session expired.", show_alert=True)

    fetcher = session.get("fetcher")
    if fetcher:
        fetcher.cancel()

    release_download(query.from_user.id)
    DOWNLOAD_SESSIONS.pop(session_id, None)
    await query.answer("❌ Cancelling...", show_alert=True)
    await query.message.edit_text("<b>❌ Download cancelled.</b>", parse_mode=enums.ParseMode.HTML)


@app.on_callback_query(lambda _, q: q.data in ("start", "help", "settings", "myaccount", "stats"))
async def nav_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data    = query.data

    if data == "start":
        await query.message.edit_text(START_TEXT, reply_markup=start_keyboard(), parse_mode=enums.ParseMode.HTML)
    elif data == "help":
        await query.message.edit_text(HELP_TEXT, reply_markup=help_keyboard(), parse_mode=enums.ParseMode.HTML)
    elif data == "settings":
        await query.message.edit_text(
            f"{HEADER} — <b>Settings</b>\n\nCustomize your experience:",
            reply_markup=settings_keyboard(), parse_mode=enums.ParseMode.HTML
        )
    elif data == "myaccount":
        user     = await db.get_user(user_id)
        session  = await db.get_session(user_id)
        premium  = "⭐ Yes" if user and user.get("is_premium") else "No"
        logged   = "✅ Logged in" if session else "❌ Not logged in"
        dl_count = user.get("downloads", 0) if user else 0
        await query.message.edit_text(
            f"{HEADER} — <b>My Account</b>\n\n"
            f"👤 <b>ID:</b> <code>{user_id}</code>\n"
            f"📥 <b>Downloads:</b> {dl_count}\n"
            f"⭐ <b>Premium:</b> {premium}\n"
            f"🔐 <b>Session:</b> {logged}\n"
            f"{FOOTER}",
            reply_markup=start_keyboard(), parse_mode=enums.ParseMode.HTML
        )
    elif data == "stats":
        stats = await db.get_stats()
        await query.message.edit_text(
            f"{HEADER} — <b>Statistics</b>\n\n"
            f"👥 <b>Users:</b> {stats.get('total_users', 0):,}\n"
            f"📥 <b>Downloads:</b> {stats.get('total_downloads', 0):,}\n"
            f"{FOOTER}",
            reply_markup=start_keyboard(), parse_mode=enums.ParseMode.HTML
        )
    await query.answer()


@app.on_callback_query(lambda _, q: q.data == "fsub:check")
async def fsub_check_callback(client: Client, query: CallbackQuery):
    await check_fsub_callback(client, query)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE DOWNLOADER
# ═══════════════════════════════════════════════════════════════════════════════
async def _start_download(client: Client, session_id: str, format_id: str):
    session    = DOWNLOAD_SESSIONS.get(session_id)
    if not session:
        return

    fetcher      = session["fetcher"]
    resolved_url = session["resolved_url"]
    user_id      = session["user_id"]
    status_msg   = session["status_msg"]
    url          = session["url"]

    quality_label = format_id if format_id != "best" else "Best"
    title         = fetcher.SITE_NAME + " Video"

    await status_msg.edit_text(
        f"<b>⬇️ Starting download...</b>\n\n"
        f"🌐 <b>Site:</b> {fetcher.get_site_name()}\n"
        f"🎞 <b>Quality:</b> {quality_label}",
        reply_markup=cancel_download_keyboard(session_id),
        parse_mode=enums.ParseMode.HTML
    )

    file_path = None
    try:
        last_update = [0.0]
        import time

        async def progress_cb(downloaded, total, speed, eta):
            now = time.time()
            from secret import PROGRESS_UPDATE_INTERVAL
            if now - last_update[0] < PROGRESS_UPDATE_INTERVAL:
                return
            last_update[0] = now
            text = build_download_progress(
                title   = title,
                current = downloaded,
                total   = total,
                speed   = speed,
                eta     = eta,
                site    = fetcher.get_site_name(),
                quality = quality_label,
            )
            try:
                await status_msg.edit_text(
                    text,
                    reply_markup=cancel_download_keyboard(session_id),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass

        file_path = await fetcher.download(resolved_url, format_id, progress_callback=progress_cb)

        if fetcher._cancelled:
            await db.log_download(user_id, url, fetcher.SITE_NAME, quality_label, "failed")
            return

        file_size     = os.path.getsize(file_path)
        title_clean   = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])
        quality_final = quality_label
        size_str      = format_size(file_size)

        await status_msg.edit_text(
            f"<b>📤 Uploading...</b>\n\n"
            f"🎬 <b>{title_clean[:40]}</b>\n"
            f"📦 <b>Size:</b> {size_str}",
            parse_mode=enums.ParseMode.HTML
        )

        user_settings = await db.get_settings(user_id)
        sent_msgs = await upload_video(
            client          = client,
            status_message  = status_msg,
            file_path       = file_path,
            title           = title_clean,
            quality         = quality_final,
            site            = fetcher.SITE_NAME,
            user_id         = user_id,
            user_upload_mode= user_settings.get("upload_mode"),
        )

        if LOG_CHANNEL_ID and sent_msgs:
            await upload_to_log_channel(
                client,
                file_path,
                caption=f"📥 New download\nUser: <code>{user_id}</code>\nSite: {fetcher.SITE_NAME}\nQuality: {quality_final}",
                log_channel_id=LOG_CHANNEL_ID,
            )

        await db.log_download(user_id, url, fetcher.SITE_NAME, quality_final, "success", file_size)

        await status_msg.edit_text(
            f"<b>✅ Done!</b>\n\n"
            f"🎬 <b>{title_clean[:40]}</b>\n"
            f"🎞 <b>Quality:</b> {quality_final}\n"
            f"📦 <b>Size:</b> {size_str}\n"
            f"{FOOTER}",
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        log.error(f"Download/upload failed for user {user_id}: {e}", exc_info=True)
        await db.log_download(user_id, url, fetcher.SITE_NAME, quality_label, "failed")
        await status_msg.edit_text(
            f"<b>❌ Failed!</b>\n\n{str(e)[:300]}\n\nPlease try again.",
            parse_mode=enums.ParseMode.HTML
        )
    finally:
        release_download(user_id)
        DOWNLOAD_SESSIONS.pop(session_id, None)
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# DUMMY WEB SERVER (FOR RENDER DEPLOYMENTS)
# ═══════════════════════════════════════════════════════════════════════════════
async def keep_alive():
    async def handle_request(request):
        return web.Response(text="Bot is running smoothly!")
    
    server = web.Application()
    server.router.add_get('/', handle_request)
    runner = web.AppRunner(server)
    await runner.setup()
    
    # Render binds the port to the PORT environment variable dynamically
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Dummy web server started on port {port}")


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════
async def main():
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    clean_download_dir(DOWNLOAD_PATH)
    await db.setup_indexes()
    
    # Start the dummy web server so Render doesn't kill the bot
    await keep_alive()
    
    async with app:
        log.info(f"🚀 {BOT_NAME} started successfully!")
        me = await app.get_me()
        log.info(f"Bot: @{me.username} | ID: {me.id}")
        
        if OWNER_ID:
            try:
                await app.send_message(
                    OWNER_ID,
                    f"<b>🚀 {BOT_NAME} is online!</b>\n\nVersion: 1.0.0",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass
                
        await idle()

if __name__ == "__main__":
    log.info(f"Starting {BOT_NAME}...")
    app.run(main())
