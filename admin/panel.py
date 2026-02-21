# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from pyrogram import Client
from pyrogram.types import CallbackQuery
from admin.middleware import admin_only, owner_only
from database.db import db
from utils.branding import HEADER, FOOTER
from utils.ui import admin_panel_keyboard, upload_mode_keyboard
from utils.logger import get_logger

log = get_logger("admin.panel")


@Client.on_callback_query(lambda _, q: q.data.startswith("admin:"))
@admin_only
async def admin_panel_callback(client: Client, query: CallbackQuery):
    action = query.data.split(":")[1]

    if action == "panel":
        await query.message.edit_text(
            f"{HEADER} — <b>Admin Panel</b>\n\nSelect an action below:",
            reply_markup=admin_panel_keyboard(),
            parse_mode="html"
        )

    elif action == "stats":
        stats = await db.get_stats()
        await query.message.edit_text(
            f"{HEADER} — <b>Bot Statistics</b>\n\n"
            f"👥 <b>Total Users:</b> {stats.get('total_users', 0):,}\n"
            f"📥 <b>Total Downloads:</b> {stats.get('total_downloads', 0):,}\n"
            f"{FOOTER}",
            reply_markup=admin_panel_keyboard(),
            parse_mode="html"
        )

    elif action == "broadcast":
        await query.message.edit_text(
            f"{HEADER}\n\n"
            "<b>📢 Broadcast Mode</b>\n\n"
            "Reply to any message with /broadcast to send it to all users.",
            parse_mode="html"
        )
        await query.answer()

    elif action in ("ban", "unban"):
        verb = "ban" if action == "ban" else "unban"
        await query.message.edit_text(
            f"{HEADER}\n\n"
            f"<b>{'🚫 Ban' if action == 'ban' else '✅ Unban'} a User</b>\n\n"
            f"Use: <code>/{verb} user_id</code> in chat.",
            parse_mode="html"
        )
        await query.answer()

    elif action in ("premium_add", "premium_remove"):
        verb = "add" if action == "premium_add" else "remove"
        await query.message.edit_text(
            f"{HEADER}\n\n<b>⭐ Premium Management</b>\n\n"
            f"Use: <code>/premium {verb} user_id</code> in chat.",
            parse_mode="html"
        )
        await query.answer()

    elif action == "upload_mode":
        await query.message.edit_text(
            f"{HEADER} — <b>Upload Mode</b>\n\n"
            "Choose where files are sent after download:",
            reply_markup=upload_mode_keyboard(),
            parse_mode="html"
        )

    elif action == "restart":
        if query.from_user.id != __import__("secret").OWNER_ID:
            await query.answer("🚫 Owner only.", show_alert=True)
            return
        await query.answer("🔄 Restarting...", show_alert=True)
        await query.message.edit_text("<b>🔄 Bot is restarting...</b>", parse_mode="html")
        import os, sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    else:
        await query.answer("Unknown action.", show_alert=True)


@Client.on_callback_query(lambda _, q: q.data.startswith("set_upload:"))
@owner_only
async def set_upload_mode_callback(client: Client, query: CallbackQuery):
    mode = query.data.split(":")[1]
    valid = {"dm", "channel", "group", "both"}
    if mode not in valid:
        await query.answer("Invalid mode.", show_alert=True)
        return

    # Persist to DB as global setting
    await db.stats.update_one(
        {"_id": "global"},
        {"$set": {"upload_mode": mode}},
        upsert=True
    )

    # Update runtime config
    import secret
    secret.UPLOAD_MODE = mode

    await query.answer(f"✅ Upload mode set to: {mode}", show_alert=True)
    await query.message.edit_text(
        f"{HEADER} — <b>Upload Mode</b>\n\n"
        f"✅ Mode updated to: <b>{mode}</b>\n\n"
        "This takes effect immediately.",
        reply_markup=upload_mode_keyboard(),
        parse_mode="html"
    )
    log.info(f"Upload mode changed to '{mode}' by owner {query.from_user.id}")
