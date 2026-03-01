"""Handlers: Admin dashboard — only for bot owner."""
from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMIN_ID
from core.database import get_global_stats, get_all_active_users


def register(bot: Client, session_mgr):

    @bot.on_message(filters.command("admin") & filters.private)
    async def cmd_admin(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            await message.reply("🚫 Admin access only.")
            return

        stats = await get_global_stats()
        session_count = len(session_mgr.active_clients)

        await message.reply(
            "👑 **Admin Dashboard**\n\n"
            f"👥 Total users: **{stats['total_users']}**\n"
            f"🟢 Active (logged in): **{stats['active_users']}**\n"
            f"📋 Active rules: **{stats['active_rules']}**\n"
            f"📨 Total messages forwarded: **{stats['total_messages']}**\n"
            f"🔌 Live sessions: **{session_count}**\n\n"
            f"_Bot is running on v1.0_"
        )
