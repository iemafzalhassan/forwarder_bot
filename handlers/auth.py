"""Handlers: Login flow (Phone → OTP → 2FA) and Logout — v2.0 Premium UI."""
from pyrogram import Client, filters, errors
from pyrogram.types import CallbackQuery

from keyboards.buttons import cancel_kb, main_menu_kb
from core.database import save_user, get_user, logout_user


async def safe_edit(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except errors.MessageNotModified:
        pass


def register(bot: Client, session_mgr):

    @bot.on_callback_query(filters.regex("^login$"))
    async def cb_login(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        if user and user['status'] == 'active':
            await cb.answer("Already connected.", show_alert=True)
            return

        await cb.answer()
        try:
            await session_mgr.begin_login(cb.from_user.id)
        except Exception as e:
            await safe_edit(cb.message, f"Connection error: {e}", reply_markup=main_menu_kb())
            return

        await safe_edit(
            cb.message,
            "**Connect Account**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send your **phone number**\n"
            "with country code.\n\n"
            "┊  Example:  `+919876543210`\n\n"
            "Your number is only used to\n"
            "create a secure session.\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=cancel_kb()
        )

    @bot.on_callback_query(filters.regex("^logout$"))
    async def cb_logout(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        await session_mgr.stop_forwarding(uid)
        await logout_user(uid)
        await cb.answer("Disconnected.")
        await safe_edit(
            cb.message,
            "**Disconnected**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "All forwarding paused.\n"
            "Connect again to resume.\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=False)
        )

    @bot.on_callback_query(filters.regex("^cancel$"))
    async def cb_cancel(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        await session_mgr.cancel_login(uid)
        session_mgr.clear_state(uid)
        user = await get_user(uid)
        logged_in = bool(user and user['status'] == 'active')
        await cb.answer("Cancelled.")
        await safe_edit(
            cb.message,
            "**Cancelled**\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=logged_in)
        )


async def process_text(client: Client, message, session_mgr):
    """Called by main dispatcher for auth-related text input."""
    uid = message.from_user.id
    state = session_mgr.get_state(uid)
    current = state.get('state', '')

    if current == 'waiting_phone':
        phone = message.text.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        try:
            await session_mgr.send_otp(uid, phone)
            await message.reply(
                "**Verification Code Sent**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Check your Telegram app.\n\n"
                "**Important:**  Telegram blocks codes\n"
                "sent directly in chat. Mix random\n"
                "letters between the digits.\n\n"
                "┊  Code `68415` → send `6a8b4c1d5`\n"
                "┊  Code `97688` → send `9x7y6z8w8`\n\n"
                "I'll extract the numbers automatically.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=cancel_kb()
            )
        except errors.PhoneNumberInvalid:
            await message.reply(
                "**Invalid Number**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Include country code: `+91...`",
                reply_markup=cancel_kb()
            )
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"Error: {e}", reply_markup=main_menu_kb())

    elif current == 'waiting_otp':
        code = ''.join(c for c in message.text if c.isdigit())
        try:
            session_string = await session_mgr.verify_otp(uid, code)
            await save_user(uid, session_string)
            await session_mgr.start_forwarding(uid, session_string)
            await message.reply(
                "**Connected**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Account connected successfully.\n"
                "You can now create forwarding rules.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
        except errors.SessionPasswordNeeded:
            await message.reply(
                "**Two-Factor Auth**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Your account has 2FA enabled.\n"
                "Send your **cloud password**.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=cancel_kb()
            )
        except errors.PhoneCodeInvalid:
            await message.reply(
                "**Invalid Code**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Try again. Remember to\n"
                "mix letters with digits.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=cancel_kb()
            )
        except errors.PhoneCodeExpired:
            await session_mgr.cancel_login(uid)
            await message.reply(
                "**Code Expired**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Start login again.",
                reply_markup=main_menu_kb()
            )
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"Login failed: {e}", reply_markup=main_menu_kb())

    elif current == 'waiting_2fa':
        try:
            session_string = await session_mgr.verify_2fa(uid, message.text.strip())
            await save_user(uid, session_string)
            await session_mgr.start_forwarding(uid, session_string)
            await message.reply(
                "**Connected**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Account connected successfully.\n"
                "You can now create forwarding rules.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
        except errors.PasswordHashInvalid:
            await message.reply(
                "**Wrong Password**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Try again.",
                reply_markup=cancel_kb()
            )
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"2FA failed: {e}", reply_markup=main_menu_kb())
