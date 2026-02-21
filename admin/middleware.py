# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from functools import wraps
from pyrogram.types import Message, CallbackQuery
from auth.access import is_owner, is_admin


def owner_only(func):
    """Decorator: restricts handler to OWNER_ID only."""
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        user_id = (
            update.from_user.id if isinstance(update, (Message, CallbackQuery))
            else 0
        )
        if not is_owner(user_id):
            if isinstance(update, CallbackQuery):
                await update.answer("🚫 Owner only.", show_alert=True)
            else:
                await update.reply("<b>🚫 This command is for the owner only.</b>", parse_mode="html")
            return
        return await func(client, update, *args, **kwargs)
    return wrapper


def admin_only(func):
    """Decorator: restricts handler to ADMIN_IDS."""
    @wraps(func)
    async def wrapper(client, update, *args, **kwargs):
        user_id = (
            update.from_user.id if isinstance(update, (Message, CallbackQuery))
            else 0
        )
        if not is_admin(user_id):
            if isinstance(update, CallbackQuery):
                await update.answer("🚫 Admins only.", show_alert=True)
            else:
                await update.reply("<b>🚫 This command is for admins only.</b>", parse_mode="html")
            return
        return await func(client, update, *args, **kwargs)
    return wrapper
