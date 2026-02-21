# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from secret import UPLOAD_MODE, UPLOAD_TARGET_ID


def get_upload_targets(user_id: int, user_mode: str | None = None) -> list[int]:
    """
    Returns a list of chat_ids to upload the file to.
    user_mode overrides global UPLOAD_MODE if set (per-user setting).
    """
    mode = user_mode or UPLOAD_MODE

    targets = []
    if mode in ("dm", "both"):
        targets.append(user_id)
    if mode in ("channel", "group", "both") and UPLOAD_TARGET_ID:
        targets.append(int(UPLOAD_TARGET_ID))
    if not targets:
        targets.append(user_id)   # safe fallback: always send to user DM
    return targets
