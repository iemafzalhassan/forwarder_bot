"""
Session Manager — The Heart of the Bot.
Manages user login flow (phone → OTP → 2FA) and background forwarding clients.
v1.0: Media group (album) support + message counting.
"""
import asyncio
import logging
from pyrogram import Client, filters, enums, errors
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio

from core.database import (
    get_all_active_users, get_destinations_for_source,
    increment_forwarded, increment_rule_count, get_active_rules
)

logger = logging.getLogger(__name__)

# How long to wait for more messages in a media group (seconds)
MEDIA_GROUP_WAIT = 1.0


class SessionManager:
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.active_clients: dict[int, Client] = {}
        self.login_temps: dict[int, dict] = {}
        self.user_states: dict[int, dict] = {}

    # ───── State Management (Lightweight FSM) ─────

    def get_state(self, user_id: int) -> dict:
        return self.user_states.get(user_id, {})

    def set_state(self, user_id: int, state: str, **data):
        current = self.user_states.get(user_id, {})
        current.update(data)
        current['state'] = state
        self.user_states[user_id] = current

    def clear_state(self, user_id: int):
        self.user_states.pop(user_id, None)

    # ───── Login Flow ─────

    async def begin_login(self, user_id: int):
        client = Client(
            name=f"login_{user_id}",
            api_id=self.api_id, api_hash=self.api_hash,
            in_memory=True
        )
        await client.connect()
        self.login_temps[user_id] = {'client': client}
        self.set_state(user_id, 'waiting_phone')

    async def send_otp(self, user_id: int, phone: str):
        temp = self.login_temps.get(user_id)
        if not temp:
            raise ValueError("No login session. Start login first.")
        sent_code = await temp['client'].send_code(phone)
        temp['phone'] = phone
        temp['phone_code_hash'] = sent_code.phone_code_hash
        self.set_state(user_id, 'waiting_otp')

    async def verify_otp(self, user_id: int, code: str) -> str:
        temp = self.login_temps.get(user_id)
        if not temp:
            raise ValueError("No login session.")
        try:
            await temp['client'].sign_in(temp['phone'], temp['phone_code_hash'], code)
        except errors.SessionPasswordNeeded:
            self.set_state(user_id, 'waiting_2fa')
            raise
        return await self._finish_login(user_id)

    async def verify_2fa(self, user_id: int, password: str) -> str:
        temp = self.login_temps.get(user_id)
        if not temp:
            raise ValueError("No login session.")
        await temp['client'].check_password(password)
        return await self._finish_login(user_id)

    async def _finish_login(self, user_id: int) -> str:
        temp = self.login_temps.pop(user_id)
        session_string = await temp['client'].export_session_string()
        await temp['client'].disconnect()
        self.clear_state(user_id)
        return session_string

    async def cancel_login(self, user_id: int):
        temp = self.login_temps.pop(user_id, None)
        if temp and temp.get('client'):
            try:
                await temp['client'].disconnect()
            except Exception:
                pass
        self.clear_state(user_id)

    # ───── Forwarding Sessions ─────

    async def start_all_sessions(self):
        users = await get_all_active_users()
        for user in users:
            try:
                await self.start_forwarding(user['user_id'], user['session_string'])
                logger.info(f"✅ Session started: user {user['user_id']}")
            except Exception as e:
                logger.error(f"❌ Session failed: user {user['user_id']}: {e}")

    async def start_forwarding(self, user_id: int, session_string: str):
        await self.stop_forwarding(user_id)

        client = Client(
            name=f"user_{user_id}",
            api_id=self.api_id, api_hash=self.api_hash,
            session_string=session_string, in_memory=True
        )

        # Buffer for collecting media group messages (albums)
        media_groups: dict[str, list] = {}
        media_group_tasks: dict[str, asyncio.Task] = {}

        async def _flush_media_group(group_id: str, chat_id: int):
            """Wait, then send the collected album as a single media group."""
            await asyncio.sleep(MEDIA_GROUP_WAIT)

            messages = media_groups.pop(group_id, [])
            media_group_tasks.pop(group_id, None)

            if not messages:
                return

            # Sort by message_id to keep original order
            messages.sort(key=lambda m: m.id)

            dests = await get_destinations_for_source(user_id, chat_id)
            for d in dests:
                try:
                    # Build InputMedia list from the collected messages
                    media_list = []
                    for msg in messages:
                        caption = msg.caption or ""
                        if msg.photo:
                            media_list.append(InputMediaPhoto(
                                msg.photo.file_id, caption=caption
                            ))
                        elif msg.video:
                            media_list.append(InputMediaVideo(
                                msg.video.file_id, caption=caption
                            ))
                        elif msg.document:
                            media_list.append(InputMediaDocument(
                                msg.document.file_id, caption=caption
                            ))
                        elif msg.audio:
                            media_list.append(InputMediaAudio(
                                msg.audio.file_id, caption=caption
                            ))

                    if media_list:
                        await client.send_media_group(d['dest_chat_id'], media_list)
                        await increment_forwarded(user_id, len(media_list))
                    else:
                        # Fallback: copy individually if media type is unknown
                        for msg in messages:
                            await msg.copy(d['dest_chat_id'])
                            await increment_forwarded(user_id)

                except errors.FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    logger.error(f"[User {user_id}] Album forward fail -> {d['dest_chat_id']}: {e}")

        @client.on_message(filters.group | filters.channel)
        async def _forwarder(c, message):
            # ── Media Group (Album) handling ──
            if message.media_group_id:
                group_id = message.media_group_id

                if group_id not in media_groups:
                    media_groups[group_id] = []

                media_groups[group_id].append(message)

                # Cancel previous flush timer, start new one
                old_task = media_group_tasks.get(group_id)
                if old_task:
                    old_task.cancel()

                media_group_tasks[group_id] = asyncio.create_task(
                    _flush_media_group(group_id, message.chat.id)
                )
                return

            # ── Single message (text, photo, video, etc.) ──
            dests = await get_destinations_for_source(user_id, message.chat.id)
            for d in dests:
                try:
                    await message.copy(d['dest_chat_id'])
                    await increment_forwarded(user_id)
                except errors.FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        await message.copy(d['dest_chat_id'])
                        await increment_forwarded(user_id)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"[User {user_id}] Forward fail -> {d['dest_chat_id']}: {e}")

        await client.start()

        # CRITICAL: Load all dialogs to populate Pyrogram's internal peer cache.
        logger.info(f"[User {user_id}] Loading peer cache (dialogs)...")
        peer_count = 0
        async for dialog in client.get_dialogs():
            peer_count += 1
        logger.info(f"[User {user_id}] Peer cache loaded: {peer_count} chats resolved.")

        self.active_clients[user_id] = client
        logger.info(f"🔁 Forwarding active for user {user_id}")

    async def stop_forwarding(self, user_id: int):
        client = self.active_clients.pop(user_id, None)
        if client:
            try:
                await client.stop()
            except Exception:
                pass

    async def get_user_groups(self, user_id: int) -> list[dict]:
        client = self.active_clients.get(user_id)
        if not client:
            return []
        groups = []
        async for dialog in client.get_dialogs():
            if dialog.chat.type in (
                enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL
            ):
                groups.append({
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or "Untitled",
                    'type': str(dialog.chat.type).split('.')[-1]
                })
        return groups

    async def shutdown(self):
        for uid in list(self.active_clients):
            await self.stop_forwarding(uid)
        for uid in list(self.login_temps):
            await self.cancel_login(uid)
