# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import time
from pyrogram.types import Message
from utils.progress_bar import build_upload_progress
from secret import PROGRESS_UPDATE_INTERVAL


class UploadProgressTracker:
    """
    Passed as the progress callback to pyrogram's send_video/send_document.
    Edits a Telegram message every PROGRESS_UPDATE_INTERVAL seconds.
    """

    def __init__(self, status_message: Message, title: str):
        self.status_message = status_message
        self.title          = title
        self._last_update   = 0.0
        self._start_time    = time.time()

    async def __call__(self, current: int, total: int):
        now = time.time()
        if now - self._last_update < PROGRESS_UPDATE_INTERVAL and current < total:
            return
        self._last_update = now

        elapsed = now - self._start_time
        speed   = current / elapsed if elapsed > 0 else 0

        text = build_upload_progress(
            title   = self.title,
            current = current,
            total   = total,
            speed   = speed,
        )
        try:
            await self.status_message.edit_text(text, parse_mode="html")
        except Exception:
            pass   # FloodWait or MessageNotModified — silently skip
