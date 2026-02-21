# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from secret import MONGODB_URI, DB_NAME


class Database:
    def __init__(self):
        self.client   = AsyncIOMotorClient(MONGODB_URI)
        self.db       = self.client[DB_NAME]

        # Collections
        self.users     = self.db["users"]
        self.sessions  = self.db["sessions"]
        self.downloads = self.db["downloads"]
        self.settings  = self.db["settings"]
        self.stats     = self.db["stats"]

    # ─── Indexes (call once on startup) ──────────────────────────────────────
    async def setup_indexes(self):
        await self.users.create_index("user_id", unique=True)
        await self.sessions.create_index("user_id", unique=True)
        await self.downloads.create_index("user_id")
        await self.downloads.create_index("timestamp")
        await self.settings.create_index("user_id", unique=True)

    # ═══════════════════════════════════════════════════════════════════════
    # USERS
    # ═══════════════════════════════════════════════════════════════════════
    async def add_user(self, user_id: int, username: str = None, full_name: str = None):
        existing = await self.users.find_one({"user_id": user_id})
        if not existing:
            await self.users.insert_one({
                "user_id":    user_id,
                "username":   username,
                "full_name":  full_name,
                "joined_at":  datetime.utcnow(),
                "is_banned":  False,
                "is_premium": False,
                "downloads":  0,
            })
            await self.increment_stat("total_users")
            return True   # new user
        else:
            # Update username/name if changed
            await self.users.update_one(
                {"user_id": user_id},
                {"$set": {"username": username, "full_name": full_name}}
            )
            return False  # existing user

    async def get_user(self, user_id: int):
        return await self.users.find_one({"user_id": user_id})

    async def get_all_users(self):
        return await self.users.find({}, {"user_id": 1}).to_list(length=None)

    async def get_total_users(self) -> int:
        return await self.users.count_documents({})

    async def ban_user(self, user_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_banned": True}}
        )

    async def unban_user(self, user_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_banned": False}}
        )

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user.get("is_banned", False) if user else False

    async def set_premium(self, user_id: int, status: bool):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_premium": status}}
        )

    async def is_premium(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user.get("is_premium", False) if user else False

    async def increment_user_downloads(self, user_id: int):
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"downloads": 1}}
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SESSIONS
    # ═══════════════════════════════════════════════════════════════════════
    async def set_session(self, user_id: int, session: str | None):
        if session is None:
            await self.sessions.delete_one({"user_id": user_id})
        else:
            await self.sessions.update_one(
                {"user_id": user_id},
                {"$set": {"session": session, "updated_at": datetime.utcnow()}},
                upsert=True
            )

    async def get_session(self, user_id: int) -> str | None:
        doc = await self.sessions.find_one({"user_id": user_id})
        return doc["session"] if doc else None

    # ═══════════════════════════════════════════════════════════════════════
    # DOWNLOADS (history / logging)
    # ═══════════════════════════════════════════════════════════════════════
    async def log_download(self, user_id: int, url: str, site: str,
                           quality: str, status: str, file_size: int = 0):
        await self.downloads.insert_one({
            "user_id":   user_id,
            "url":       url,
            "site":      site,
            "quality":   quality,
            "status":    status,          # "success" | "failed"
            "file_size": file_size,
            "timestamp": datetime.utcnow(),
        })
        if status == "success":
            await self.increment_user_downloads(user_id)
            await self.increment_stat("total_downloads")

    async def get_user_downloads(self, user_id: int, limit: int = 10):
        cursor = self.downloads.find(
            {"user_id": user_id},
            sort=[("timestamp", -1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_total_downloads(self) -> int:
        return await self.downloads.count_documents({"status": "success"})

    # ═══════════════════════════════════════════════════════════════════════
    # SETTINGS (per-user preferences)
    # ═══════════════════════════════════════════════════════════════════════
    async def get_settings(self, user_id: int) -> dict:
        doc = await self.settings.find_one({"user_id": user_id})
        if not doc:
            return {
                "default_quality":  "best",
                "upload_mode":      "dm",      # overrides global if set
                "notifications":    True,
            }
        return doc

    async def update_settings(self, user_id: int, **kwargs):
        await self.settings.update_one(
            {"user_id": user_id},
            {"$set": kwargs},
            upsert=True
        )

    # ═══════════════════════════════════════════════════════════════════════
    # STATS (global counters)
    # ═══════════════════════════════════════════════════════════════════════
    async def increment_stat(self, key: str, amount: int = 1):
        await self.stats.update_one(
            {"_id": "global"},
            {"$inc": {key: amount}},
            upsert=True
        )

    async def get_stats(self) -> dict:
        doc = await self.stats.find_one({"_id": "global"})
        total_users     = await self.get_total_users()
        total_downloads = await self.get_total_downloads()
        return {
            "total_users":     total_users,
            "total_downloads": total_downloads,
            **(doc or {}),
        }


# Singleton instance used across the entire project
db = Database()
