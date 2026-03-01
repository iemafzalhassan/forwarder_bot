"""Handlers: /start, guide, main menu — v1.0."""
from pyrogram import Client, filters, errors
from pyrogram.types import Message, CallbackQuery

from keyboards.buttons import main_menu_kb
from core.database import get_user


async def safe_edit(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except errors.MessageNotModified:
        pass


def register(bot: Client, session_mgr):

    @bot.on_message(filters.command("start") & filters.private)
    async def cmd_start(client: Client, message: Message):
        user = await get_user(message.from_user.id)
        logged_in = bool(user and user['status'] == 'active')
        status = "🟢 Logged In" if logged_in else "🔴 Not Logged In"

        await message.reply(
            f"👋 **Welcome, {message.from_user.first_name}!**\n\n"
            f"I'm **Msg Forwarder Bot** — the ultimate silent message forwarder.\n\n"
            f"🔥 **Features:**\n"
            f"• Forward from ANY group (no admin needed!)\n"
            f"• Invisible — no 'Forwarded from' tag\n"
            f"• Migrate ALL old messages with one click\n"
            f"• Pause/Resume rules anytime\n"
            f"• Works 24/7 in background\n\n"
            f"**Status:** {status}\n\n"
            f"Choose an option below:",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )

    @bot.on_callback_query(filters.regex("^guide$"))
    async def cb_guide(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        logged_in = bool(user and user['status'] == 'active')
        await cb.answer()
        await safe_edit(
            cb.message,
            "📖 **How to Use Msg Forwarder Bot:**\n\n"
            "**Step 1: Login** 🔐\n"
            "Click Login → Send phone number → Enter OTP code\n"
            "_(Add random letters in OTP: `6x8x4x1x5`)_\n\n"
            "**Step 2: Add Rule** ➕\n"
            "Click Add Rule → Pick Source group → Pick Destination\n"
            "Bot shows ALL your groups — just tap to select!\n\n"
            "**Step 3: Migrate** 📦\n"
            "Want old messages too? Go to My Rules → tap a rule → Migrate\n\n"
            "**Step 4: Manage** 📋\n"
            "• Pause/Resume any rule\n"
            "• Delete rules you don't need\n"
            "• View your stats\n\n"
            "⚠️ **No admin access needed** in source group!\n"
            "🔒 **Privacy:** We never store your messages.",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )

    @bot.on_callback_query(filters.regex("^main_menu$"))
    async def cb_main_menu(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        logged_in = bool(user and user['status'] == 'active')
        status = "🟢 Logged In" if logged_in else "🔴 Not Logged In"
        await cb.answer()
        await safe_edit(cb.message, f"🏠 **Main Menu**\n\n**Status:** {status}",
                        reply_markup=main_menu_kb(is_logged_in=logged_in))
