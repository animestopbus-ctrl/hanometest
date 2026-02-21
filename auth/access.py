# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import time
from collections import defaultdict
from pyrogram.types import Message
from secret import OWNER_ID, ADMIN_IDS, MAX_CONCURRENT_DOWNLOADS
from database.db import db

# ─── Rate limiting: track active downloads per user ───────────────────────────
_active_downloads: dict[int, int] = defaultdict(int)

# ─── Flood control: track last command time ───────────────────────────────────
_last_command: dict[int, float] = {}
FLOOD_WAIT_SECONDS = 3


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id == OWNER_ID


async def is_banned_user(user_id: int) -> bool:
    return await db.is_banned(user_id)


async def check_access(message: Message) -> bool:
    """
    Full access check pipeline:
    1. Ban check
    2. Flood control
    Returns True if user may proceed.
    """
    user_id = message.from_user.id

    # Admins bypass all restrictions
    if is_admin(user_id):
        return True

    # Ban check
    if await is_banned_user(user_id):
        await message.reply(
            "<b>🚫 You are banned from using Hanime Fetcher.</b>\n\n"
            "Contact support if you think this is a mistake.",
            parse_mode="html"
        )
        return False

    # Flood control
    now = time.time()
    last = _last_command.get(user_id, 0)
    if now - last < FLOOD_WAIT_SECONDS:
        await message.reply(
            f"<b>⏳ Slow down!</b> Please wait {FLOOD_WAIT_SECONDS}s between commands.",
            parse_mode="html"
        )
        return False
    _last_command[user_id] = now
    return True


def can_start_download(user_id: int) -> bool:
    """Returns True if user hasn't hit their concurrent download limit."""
    if is_admin(user_id):
        return True
    return _active_downloads[user_id] < MAX_CONCURRENT_DOWNLOADS


def register_download(user_id: int):
    _active_downloads[user_id] += 1


def release_download(user_id: int):
    if _active_downloads[user_id] > 0:
        _active_downloads[user_id] -= 1


def get_active_downloads(user_id: int) -> int:
    return _active_downloads[user_id]
