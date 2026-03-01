"""Handlers: Admin dashboard — v2.0 Premium UI."""
from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMIN_ID
from core.database import get_global_stats


def register(bot: Client, session_mgr):

    @bot.on_message(filters.command("admin") & filters.private)
    async def cmd_admin(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return

        stats = await get_global_stats()
        session_count = len(session_mgr.active_clients)

        await message.reply(
            "**Admin Dashboard**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  Users:  **{stats['total_users']}**  total\n"
            f"┊  Active:  **{stats['active_users']}**  connected\n"
            f"┊  Rules:  **{stats['active_rules']}**  active\n"
            f"┊  Messages:  **{stats['total_messages']}**  forwarded\n"
            f"┊  Sessions:  **{session_count}**  live\n\n"
            f"**Version:**  v2.0\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
