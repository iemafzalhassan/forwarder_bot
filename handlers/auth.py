"""Handlers: Login flow (Phone → OTP → 2FA) and Logout."""
from pyrogram import Client, filters, errors
from pyrogram.types import CallbackQuery

from keyboards.buttons import cancel_kb, main_menu_kb
from core.database import save_user, get_user, logout_user


def register(bot: Client, session_mgr):

    @bot.on_callback_query(filters.regex("^login$"))
    async def cb_login(client: Client, cb: CallbackQuery):
        user = await get_user(cb.from_user.id)
        if user and user['status'] == 'active':
            await cb.answer("You're already logged in!", show_alert=True)
            return

        await cb.answer()
        try:
            await session_mgr.begin_login(cb.from_user.id)
        except Exception as e:
            await cb.message.edit_text(f"❌ Login error: {e}", reply_markup=main_menu_kb())
            return

        await cb.message.edit_text(
            "🔐 **Login to Your Telegram Account**\n\n"
            "Please send your **phone number** with country code.\n"
            "Example: `+919876543210`\n\n"
            "🔒 _Your number is only used to create a session._",
            reply_markup=cancel_kb()
        )

    @bot.on_callback_query(filters.regex("^logout$"))
    async def cb_logout(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        await session_mgr.stop_forwarding(uid)
        await logout_user(uid)
        await cb.answer("Logged out!", show_alert=True)
        await cb.message.edit_text(
            "🔴 **Logged out.** All forwarding paused.",
            reply_markup=main_menu_kb(is_logged_in=False)
        )

    @bot.on_callback_query(filters.regex("^cancel$"))
    async def cb_cancel(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        await session_mgr.cancel_login(uid)
        session_mgr.clear_state(uid)
        user = await get_user(uid)
        logged_in = bool(user and user['status'] == 'active')
        await cb.answer("Cancelled")
        await cb.message.edit_text("❌ **Cancelled.**", reply_markup=main_menu_kb(is_logged_in=logged_in))


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
                "📲 **OTP Sent!**\n\n"
                "Check your Telegram app for the login code.\n\n"
                "⚠️ **IMPORTANT:** Telegram will BLOCK the code if you type it directly!\n"
                "You MUST add random letters between digits.\n\n"
                "Example: If code is `68415`, send it as:\n"
                "`6x8x4x1x5` or `6a8b4c1d5`\n\n"
                "_(I will extract only the numbers automatically)_",
                reply_markup=cancel_kb()
            )
        except errors.PhoneNumberInvalid:
            await message.reply("❌ Invalid number. Try with country code (+91...).", reply_markup=cancel_kb())
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"❌ Error: {e}", reply_markup=main_menu_kb())

    elif current == 'waiting_otp':
        # Strip ALL non-numeric characters (user adds letters to bypass Telegram detection)
        code = ''.join(c for c in message.text if c.isdigit())
        try:
            session_string = await session_mgr.verify_otp(uid, code)
            await save_user(uid, session_string)
            await session_mgr.start_forwarding(uid, session_string)
            await message.reply(
                "✅ **Login Successful!**\n\nYou can now create forwarding rules!",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
        except errors.SessionPasswordNeeded:
            await message.reply(
                "🔑 **Two-Factor Authentication**\n\n"
                "Your account has 2FA. Please send your **cloud password**.",
                reply_markup=cancel_kb()
            )
        except errors.PhoneCodeInvalid:
            await message.reply("❌ Invalid OTP. Try again.", reply_markup=cancel_kb())
        except errors.PhoneCodeExpired:
            await session_mgr.cancel_login(uid)
            await message.reply("❌ OTP expired. Start login again.", reply_markup=main_menu_kb())
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"❌ Login failed: {e}", reply_markup=main_menu_kb())

    elif current == 'waiting_2fa':
        try:
            session_string = await session_mgr.verify_2fa(uid, message.text.strip())
            await save_user(uid, session_string)
            await session_mgr.start_forwarding(uid, session_string)
            await message.reply(
                "✅ **Login Successful!**\n\nYou can now create forwarding rules!",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
        except errors.PasswordHashInvalid:
            await message.reply("❌ Wrong password. Try again.", reply_markup=cancel_kb())
        except Exception as e:
            await session_mgr.cancel_login(uid)
            await message.reply(f"❌ 2FA failed: {e}", reply_markup=main_menu_kb())
