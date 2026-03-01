"""Handlers: /start, guide, main menu — v2.0 Premium UI."""
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
        status = "◉ Connected" if logged_in else "○ Not Connected"

        await message.reply(
            f"**Msg Forwarder**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Hey, {message.from_user.first_name}.\n\n"
            f"Silent message forwarding for Telegram.\n"
            f"No admin access needed. No forwarded tags.\n\n"
            f"**What it does:**\n"
            f"┊  Forward from any group or channel\n"
            f"┊  Copy all media, text, files — as-is\n"
            f"┊  Migrate entire chat history\n"
            f"┊  Runs 24/7 in background\n\n"
            f"**Status:**  {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )

    @bot.on_callback_query(filters.regex("^guide$"))
    async def cb_guide(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        logged_in = bool(user and user['status'] == 'active')
        await cb.answer()
        await safe_edit(
            cb.message,
            "**How to Use**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**① Connect**\n"
            "┊  Tap Connect → Enter phone number\n"
            "┊  Enter OTP with random letters mixed in\n"
            "┊  Example: code `68415` → send `6a8b4c1d5`\n\n"
            "**② Add Rule**\n"
            "┊  Tap Add Rule → Pick source group\n"
            "┊  Pick destination → Done\n"
            "┊  New messages auto-forward silently\n\n"
            "**③ Migrate History**\n"
            "┊  Go to My Rules → Tap a rule\n"
            "┊  Tap Migrate → All old messages copied\n\n"
            "**④ Manage**\n"
            "┊  Pause / Resume any rule\n"
            "┊  Delete rules you don't need\n"
            "┊  View forwarding stats\n\n"
            "**Privacy:**  We never store your messages.\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )

    @bot.on_callback_query(filters.regex("^main_menu$"))
    async def cb_main_menu(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        logged_in = bool(user and user['status'] == 'active')
        status = "◉ Connected" if logged_in else "○ Not Connected"
        await cb.answer()
        await safe_edit(
            cb.message,
            f"**Msg Forwarder**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"**Status:**  {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )
