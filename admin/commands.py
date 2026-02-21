# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from admin.middleware import admin_only, owner_only
from database.db import db
from utils.branding import HEADER, FOOTER
from utils.logger import get_logger
from secret import OWNER_ID

log = get_logger("admin.commands")


# ─── /admin ───────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("admin"))
@admin_only
async def admin_panel_cmd(client: Client, message: Message):
    from utils.ui import admin_panel_keyboard
    await message.reply(
        f"{HEADER} — <b>Admin Panel</b>\n\n"
        "Select an action below:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="html"
    )


# ─── /stats ───────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("stats"))
@admin_only
async def stats_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    text  = (
        f"{HEADER} — <b>Bot Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> {stats.get('total_users', 0):,}\n"
        f"📥 <b>Total Downloads:</b> {stats.get('total_downloads', 0):,}\n"
        f"{FOOTER}"
    )
    await message.reply(text, parse_mode="html")


# ─── /ban ─────────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("ban"))
@admin_only
async def ban_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply(
            "<b>Usage:</b> <code>/ban user_id</code>", parse_mode="html"
        )
    target_id = int(args[1])
    if target_id == OWNER_ID:
        return await message.reply("<b>🚫 Cannot ban the owner.</b>", parse_mode="html")
    await db.ban_user(target_id)
    await message.reply(f"<b>✅ User <code>{target_id}</code> has been banned.</b>", parse_mode="html")
    try:
        await client.send_message(
            target_id,
            "<b>🚫 You have been banned from Hanime Fetcher.</b>",
            parse_mode="html"
        )
    except Exception:
        pass
    log.info(f"Admin {message.from_user.id} banned user {target_id}")


# ─── /unban ───────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("unban"))
@admin_only
async def unban_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.reply(
            "<b>Usage:</b> <code>/unban user_id</code>", parse_mode="html"
        )
    target_id = int(args[1])
    await db.unban_user(target_id)
    await message.reply(f"<b>✅ User <code>{target_id}</code> has been unbanned.</b>", parse_mode="html")
    try:
        await client.send_message(
            target_id,
            "<b>✅ You have been unbanned from Hanime Fetcher. Welcome back!</b>",
            parse_mode="html"
        )
    except Exception:
        pass
    log.info(f"Admin {message.from_user.id} unbanned user {target_id}")


# ─── /premium ─────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("premium"))
@owner_only
async def premium_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 3 or not args[2].isdigit():
        return await message.reply(
            "<b>Usage:</b> <code>/premium add|remove user_id</code>", parse_mode="html"
        )
    action    = args[1].lower()
    target_id = int(args[2])
    if action == "add":
        await db.set_premium(target_id, True)
        await message.reply(f"<b>⭐ User <code>{target_id}</code> is now Premium.</b>", parse_mode="html")
        try:
            await client.send_message(
                target_id,
                "<b>⭐ Congratulations! You've been granted Premium access to Hanime Fetcher!</b>",
                parse_mode="html"
            )
        except Exception:
            pass
    elif action == "remove":
        await db.set_premium(target_id, False)
        await message.reply(f"<b>✅ Premium removed for <code>{target_id}</code>.</b>", parse_mode="html")
    else:
        await message.reply("<b>Usage:</b> <code>/premium add|remove user_id</code>", parse_mode="html")


# ─── /broadcast ───────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("broadcast"))
@owner_only
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply(
            "<b>Reply to a message to broadcast it.</b>\n"
            "Usage: Reply to a message and send /broadcast",
            parse_mode="html"
        )

    all_users = await db.get_all_users()
    total     = len(all_users)
    success   = 0
    failed    = 0

    status = await message.reply(
        f"<b>📢 Broadcasting to {total} users...</b>", parse_mode="html"
    )

    for i, user_doc in enumerate(all_users):
        uid = user_doc["user_id"]
        try:
            await message.reply_to_message.copy(uid)
            success += 1
        except Exception:
            failed += 1
        # Update status every 50 users
        if (i + 1) % 50 == 0:
            try:
                await status.edit_text(
                    f"<b>📢 Broadcasting...</b>\n"
                    f"✅ Sent: {success} | ❌ Failed: {failed} | Total: {total}",
                    parse_mode="html"
                )
            except Exception:
                pass
        await asyncio.sleep(0.05)   # avoid flood

    await status.edit_text(
        f"<b>📢 Broadcast Complete!</b>\n\n"
        f"✅ <b>Sent:</b> {success}\n"
        f"❌ <b>Failed:</b> {failed}\n"
        f"👥 <b>Total:</b> {total}",
        parse_mode="html"
    )
    log.info(f"Broadcast complete: {success}/{total} delivered")


# ─── /users ───────────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("users"))
@admin_only
async def users_cmd(client: Client, message: Message):
    count = await db.get_total_users()
    await message.reply(
        f"<b>👥 Total registered users: {count:,}</b>", parse_mode="html"
    )
