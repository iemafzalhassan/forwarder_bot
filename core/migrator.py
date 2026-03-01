"""
Message Migration Engine — Copies ALL old messages from source to destination.
Rate-limited to avoid Telegram flood. Runs in background.
"""
import asyncio
import logging
from pyrogram import Client, errors

from core.database import (
    create_migration, update_migration_progress,
    finish_migration, get_rule_by_id, increment_rule_count, increment_forwarded,
    mark_message_copied
)

logger = logging.getLogger(__name__)

# Active migrations tracker: {user_id: asyncio.Task}
active_migrations: dict[int, asyncio.Task] = {}


async def start_migration(bot: Client, user_id: int, rule_id: int,
                           user_client: Client, notify_chat_id: int):
    """Start migrating old messages for a rule. Runs as background task."""

    # Cancel if already migrating
    if user_id in active_migrations:
        existing = active_migrations[user_id]
        if not existing.done():
            return False, "You already have a migration running!"

    rule = await get_rule_by_id(rule_id, user_id)
    if not rule:
        return False, "Rule not found."

    source_id = rule['source_chat_id']
    dest_id = rule['dest_chat_id']

    # Start as background task
    task = asyncio.create_task(
        _run_migration(bot, user_id, rule_id, source_id, dest_id,
                       user_client, notify_chat_id)
    )
    active_migrations[user_id] = task
    return True, "Migration started!"


async def stop_migration(user_id: int):
    """Stop a running migration."""
    task = active_migrations.pop(user_id, None)
    if task and not task.done():
        task.cancel()
        return True
    return False


async def _run_migration(bot: Client, user_id: int, rule_id: int,
                          source_id: int, dest_id: int,
                          user_client: Client, notify_chat_id: int):
    """Core migration logic — runs in background."""
    try:
        # Count total messages first
        total = 0
        async for _ in user_client.get_chat_history(source_id, limit=0):
            pass
        # Pyrogram doesn't give count directly, so we estimate
        # We'll update as we go

        migration_id = await create_migration(user_id, rule_id, total_messages=0)

        await bot.send_message(
            notify_chat_id,
            "**Migration Started**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Copying messages from source\n"
            "to destination.\n\n"
            "Send `/stop_migration` to cancel.\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        copied = 0
        errors_count = 0
        last_msg_id = 0
        batch_size = 100
        update_interval = 50  # Notify every 50 messages

        # Get all already copied message IDs for this rule to prevent duplicates
        import aiosqlite
        from core.database import DB_PATH
        copied_ids = set()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT source_message_id FROM copied_messages WHERE rule_id = ?",
                (rule_id,)
            ) as cur:
                async for row in cur:
                    copied_ids.add(row[0])

        # Get messages in reverse (oldest first) skipping already copied ones
        all_ids = []
        async for msg in user_client.get_chat_history(source_id):
            if msg.id not in copied_ids:
                all_ids.append(msg.id)

        total = len(all_ids)
        if total == 0:
            await finish_migration(migration_id, 'completed')
            active_migrations.pop(user_id, None)
            await bot.send_message(
                notify_chat_id,
                "**Already Synced**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ No new messages found to copy.\n"
                "Duplicates have been prevented.\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            return

        await update_migration_progress(migration_id, 0, 0)

        await bot.send_message(
            notify_chat_id,
            f"**{total}** new messages found.\n"
            f"Estimated time: ~{total * 0.6 / 60:.1f} min"
        )

        # Process oldest first
        all_ids.reverse()

        for msg_id in all_ids:
            try:
                # Check if task was cancelled
                await asyncio.sleep(0)  # Yield to allow cancellation

                await user_client.copy_message(
                    chat_id=dest_id,
                    from_chat_id=source_id,
                    message_id=msg_id
                )
                copied += 1
                last_msg_id = msg_id
                await mark_message_copied(rule_id, msg_id)

                # Rate limit: 1 message per 0.5 seconds
                await asyncio.sleep(0.5)

                # Update DB periodically
                if copied % 10 == 0:
                    await update_migration_progress(migration_id, copied, last_msg_id)
                    await increment_rule_count(rule_id, 10)
                    await increment_forwarded(user_id, 10)

                # Notify user periodically
                if copied % update_interval == 0:
                    pct = (copied / total * 100) if total > 0 else 0
                    bar = '▓' * int(pct / 5) + '░' * (20 - int(pct / 5))
                    await bot.send_message(
                        notify_chat_id,
                        f"**Migration**  ·  {pct:.0f}%\n"
                        f"{bar}\n"
                        f"{copied} / {total}"
                    )

            except errors.FloodWait as e:
                logger.warning(f"[Migration] FloodWait {e.value}s for user {user_id}")
                await asyncio.sleep(e.value + 1)
            except errors.MessageEmpty:
                pass  # Skip empty/deleted messages
            except asyncio.CancelledError:
                await finish_migration(migration_id, 'cancelled')
                await bot.send_message(
                    notify_chat_id,
                    "**Migration Cancelled**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Copied: {copied} / {total}\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
                return
            except Exception as e:
                errors_count += 1
                if errors_count > 20:
                    logger.error(f"[Migration] Too many errors, stopping: {e}")
                    break

        # Final update
        await update_migration_progress(migration_id, copied, last_msg_id)
        remaining = 10 - (copied % 10) if copied % 10 != 0 else 0
        if remaining:
            await increment_rule_count(rule_id, copied % 10)
            await increment_forwarded(user_id, copied % 10)

        await finish_migration(migration_id, 'completed')
        await bot.send_message(
            notify_chat_id,
            "**Migration Complete**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  Copied:  **{copied}**\n"
            f"┊  Errors:  **{errors_count}**\n"
            f"┊  Total:  **{total}**\n\n"
            "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  100%\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    except asyncio.CancelledError:
        logger.info(f"[Migration] Cancelled for user {user_id}")
    except Exception as e:
        logger.error(f"[Migration] Fatal error for user {user_id}: {e}")
        try:
            await bot.send_message(
                notify_chat_id,
                "**Migration Failed**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{e}"
            )
        except Exception:
            pass
    finally:
        active_migrations.pop(user_id, None)
