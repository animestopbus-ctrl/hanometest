# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

# ─── Telegram Bot Credentials ────────────────────────────────────────────────
BOT_TOKEN   = "7940504106:AAFpnrTJe6AtQzDEri-rrJgOZ2j59Z3Kwgc"           # @BotFather
API_ID      = 27322718                         # my.telegram.org
API_HASH    = "4f6d1b67cf101aea5cf0536885aa1b82"            # my.telegram.org

# ─── Optional: String Session ────────────────────────────────────────────────
# If filled, bot uses this session directly (no /login needed for the bot account)
# Leave as empty string "" to use /login method instead
STRING_SESSION = ""

# ─── Owner & Admin ───────────────────────────────────────────────────────────
OWNER_ID    = 1633472140                          # Your Telegram user ID (integer)
ADMIN_IDS   = [OWNER_ID]                 # List of admin IDs

# ─── MongoDB ─────────────────────────────────────────────────────────────────
MONGODB_URI = "mongodb+srv://TestBot1:IrsPgBoXwFeLE5dH@testbot.mo3ecqh.mongodb.net/?appName=Testbot" # or Atlas URI
DB_NAME     = "hanime_fetcher"

# ─── Force Subscribe ─────────────────────────────────────────────────────────
# Set to None to disable force-subscribe
FSUB_CHANNEL_ID    = -1001557378145                # e.g. 
FSUB_CHANNEL_LINK  = "https://t.me/THEUPDATEDGUYS"                # e.g. "https://t.me/yourchannel"

# ─── Logging Channel ─────────────────────────────────────────────────────────
LOG_CHANNEL_ID = -1003144372708                    # Bot logs new users/downloads here

# ─── Upload Destination ──────────────────────────────────────────────────────
# "dm"      → send to user's DM
# "channel" → send to UPLOAD_TARGET_ID
# "group"   → send to UPLOAD_TARGET_ID
# "both"    → send to user's DM + UPLOAD_TARGET_ID
UPLOAD_MODE      = "dm"
UPLOAD_TARGET_ID = None                  # channel or group chat_id

# ─── Download Settings ───────────────────────────────────────────────────────
DOWNLOAD_PATH           = "./downloads"
MAX_CONCURRENT_DOWNLOADS = 3             # per-user concurrency limit
DEFAULT_QUALITY         = "best"         # fallback if user skips quality pick

# ─── Bot Behaviour ───────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 2000                  # Telegram limit (2 GB for bots with local API)
PROGRESS_UPDATE_INTERVAL = 10            # seconds between progress bar edits
