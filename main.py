"""
Msg Forwarder Bot — v1.0 Production
Entry point: DB → Bot → Session Manager → Handlers → GO!
"""
import asyncio
import logging

from pyrogram import Client, filters, idle

from config import BOT_TOKEN, API_ID, API_HASH
from core.database import init_db
from core.session_manager import SessionManager
from handlers import start, auth, rules, admin


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger(__name__)

    # 1. Initialize Database
    await init_db()

    # 2. Create Bot Client
    bot = Client(
        name="msg_forwarder_bot",
        bot_token=BOT_TOKEN,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="data"
    )

    # 3. Create Session Manager
    session_mgr = SessionManager(api_id=API_ID, api_hash=API_HASH)

    # 4. Register handlers
    start.register(bot, session_mgr)
    auth.register(bot, session_mgr)
    rules.register(bot, session_mgr)
    admin.register(bot, session_mgr)

    # 5. Central text dispatcher
    @bot.on_message(filters.private & filters.text & ~filters.regex(r"^/"))
    async def on_text_input(client, message):
        uid = message.from_user.id
        state = session_mgr.get_state(uid)
        if not state:
            return

        s = state.get('state', '')
        if s in ('waiting_phone', 'waiting_otp', 'waiting_2fa'):
            await auth.process_text(client, message, session_mgr)
        elif s in ('rule_waiting_source_id', 'rule_waiting_dest_id'):
            await rules.process_text(client, message, session_mgr)

    # 6. Start Bot
    await bot.start()
    logger.info("🤖 Bot is online! (v1.0)")

    # 7. Resume saved sessions
    await session_mgr.start_all_sessions()
    logger.info("🔁 All saved sessions resumed.")

    # 8. Keep running
    print("🤖 Premium Forwarder Bot v1.0 is LIVE! Press Ctrl+C to stop.")
    await idle()

    # 9. Graceful shutdown
    await session_mgr.shutdown()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
