# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pyrogram.types import Message, CallbackQuery
from secret import FSUB_CHANNEL_ID, FSUB_CHANNEL_LINK, OWNER_ID, ADMIN_IDS
from utils.ui import fsub_keyboard


async def is_subscribed(client: Client, user_id: int) -> bool:
    """Returns True if user is a member of the fsub channel, or if fsub is disabled."""
    if not FSUB_CHANNEL_ID:
        return True
    if user_id in ADMIN_IDS or user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(FSUB_CHANNEL_ID, user_id)
        return member.status.value not in ("left", "banned", "kicked")
    except UserNotParticipant:
        return False
    except Exception:
        return True   # don't block on unexpected errors


async def enforce_fsub(client: Client, message: Message) -> bool:
    """
    Checks fsub and sends join prompt if not subscribed.
    Returns True if the user may proceed, False if blocked.
    """
    user_id = message.from_user.id
    if await is_subscribed(client, user_id):
        return True

    link = FSUB_CHANNEL_LINK or "https://t.me"
    await message.reply(
        "<b>🔒 Access Restricted!</b>\n\n"
        "You must join our channel to use <b>Hanime Fetcher</b>.\n\n"
        "👇 Click below to join, then press <b>Check Again</b>.",
        reply_markup=fsub_keyboard(link),
        parse_mode="html"
    )
    return False


async def check_fsub_callback(client: Client, query: CallbackQuery) -> bool:
    """Used in callback handler for the 'Check Again' button."""
    user_id = query.from_user.id
    if await is_subscribed(client, user_id):
        await query.answer("✅ Verified! You're good to go.", show_alert=True)
        await query.message.delete()
        return True
    else:
        link = FSUB_CHANNEL_LINK or "https://t.me"
        await query.answer("❌ Still not joined!", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=fsub_keyboard(link))
        return False
