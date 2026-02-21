# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

import os
from pyrogram import Client
from pyrogram.types import Message
from uploader.destination import get_upload_targets
from uploader.progress import UploadProgressTracker
from utils.branding import FILE_CAPTION
from utils.helpers import format_size
from utils.logger import get_logger
from secret import MAX_FILE_SIZE_MB

log = get_logger("uploader")


async def upload_video(
    client: Client,
    status_message: Message,
    file_path: str,
    title: str,
    quality: str,
    site: str,
    user_id: int,
    user_upload_mode: str | None = None,
    thumb_path: str | None = None,
) -> list[Message]:
    """
    Uploads the video to all configured destinations.
    Returns list of sent Message objects.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    size_mb   = file_size / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File is {size_mb:.1f} MB, exceeds limit of {MAX_FILE_SIZE_MB} MB."
        )

    targets  = get_upload_targets(user_id, user_upload_mode)
    caption  = FILE_CAPTION.format(
        title   = title[:50],
        quality = quality,
        size    = format_size(file_size),
        site    = site,
    )

    tracker  = UploadProgressTracker(status_message, title)
    sent     = []

    for chat_id in targets:
        try:
            log.info(f"Uploading '{title}' to chat_id={chat_id}")
            msg = await client.send_video(
                chat_id         = chat_id,
                video           = file_path,
                caption         = caption,
                parse_mode      = "html",
                thumb           = thumb_path,
                supports_streaming = True,
                progress        = tracker,
            )
            sent.append(msg)
            log.info(f"Upload to {chat_id} complete.")
        except Exception as e:
            log.error(f"Failed to upload to {chat_id}: {e}")
            # Try as document fallback
            try:
                msg = await client.send_document(
                    chat_id    = chat_id,
                    document   = file_path,
                    caption    = caption,
                    parse_mode = "html",
                    thumb      = thumb_path,
                    progress   = tracker,
                )
                sent.append(msg)
                log.info(f"Uploaded as document to {chat_id}.")
            except Exception as e2:
                log.error(f"Document fallback also failed for {chat_id}: {e2}")

    return sent


async def upload_to_log_channel(
    client: Client,
    file_path: str,
    caption: str,
    log_channel_id: int,
):
    """Send a copy to the log channel silently."""
    try:
        await client.send_video(
            chat_id    = log_channel_id,
            video      = file_path,
            caption    = caption,
            parse_mode = "html",
        )
    except Exception:
        try:
            await client.send_document(
                chat_id    = log_channel_id,
                document   = file_path,
                caption    = caption,
                parse_mode = "html",
            )
        except Exception as e:
            log.warning(f"Log channel upload failed: {e}")
