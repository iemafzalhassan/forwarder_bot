"""
Database Abstraction Layer (DAL) — v1.0 Production
SQLite now, PostgreSQL later. Only stores mandatory data.
"""
import aiosqlite
import os
import logging

DB_PATH = "data/forwarder.db"
logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database and create tables with v1.0 schema."""
    os.makedirs("data", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                session_string TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                messages_forwarded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS forwarding_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_chat_id INTEGER NOT NULL,
                dest_chat_id INTEGER NOT NULL,
                source_title TEXT DEFAULT '',
                dest_title TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                messages_copied INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                rule_id INTEGER NOT NULL,
                total_messages INTEGER DEFAULT 0,
                copied_messages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                last_message_id INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rule_id) REFERENCES forwarding_rules(id)
            )
        ''')

        # ── Auto-migration: add new columns to existing tables ──
        migrations = [
            ("users", "messages_forwarded", "INTEGER DEFAULT 0"),
            ("forwarding_rules", "source_title", "TEXT DEFAULT ''"),
            ("forwarding_rules", "dest_title", "TEXT DEFAULT ''"),
            ("forwarding_rules", "messages_copied", "INTEGER DEFAULT 0"),
        ]
        for table, column, col_type in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                logger.info(f"Migration: added {column} to {table}")
            except Exception:
                pass  # Column already exists

        # Add UNIQUE constraint if not exists (recreate index)
        try:
            await db.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_rule
                ON forwarding_rules(user_id, source_chat_id, dest_chat_id)
            ''')
        except Exception:
            pass

        await db.commit()
    logger.info("Database initialized (v1.0 schema).")


# ===== User Operations =====

async def save_user(user_id: int, session_string: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT INTO users (user_id, session_string, status)
               VALUES (?, ?, 'active')
               ON CONFLICT(user_id) DO UPDATE SET
               session_string = excluded.session_string, status = 'active' ''',
            (user_id, session_string)
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def get_all_active_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE status = 'active'") as cur:
            return await cur.fetchall()


async def logout_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET status = 'logged_out', session_string = '' WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def increment_forwarded(user_id: int, count: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET messages_forwarded = messages_forwarded + ? WHERE user_id = ?",
            (count, user_id)
        )
        await db.commit()


# ===== Rule Operations =====

async def add_rule(user_id: int, source_chat_id: int, dest_chat_id: int,
                   source_title: str = "", dest_title: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO forwarding_rules
                   (user_id, source_chat_id, dest_chat_id, source_title, dest_title)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, source_chat_id, dest_chat_id, source_title, dest_title)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # Duplicate rule


async def get_user_rules(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM forwarding_rules WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchall()


async def get_active_rules(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM forwarding_rules WHERE user_id = ? AND is_active = 1", (user_id,)
        ) as cur:
            return await cur.fetchall()


async def get_destinations_for_source(user_id: int, source_chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT dest_chat_id FROM forwarding_rules WHERE user_id = ? AND source_chat_id = ? AND is_active = 1",
            (user_id, source_chat_id)
        ) as cur:
            return await cur.fetchall()


async def get_rule_by_id(rule_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM forwarding_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        ) as cur:
            return await cur.fetchone()


async def toggle_rule(rule_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE forwarding_rules SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )
        await db.commit()


async def delete_rule(rule_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM forwarding_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )
        await db.commit()


async def increment_rule_count(rule_id: int, count: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE forwarding_rules SET messages_copied = messages_copied + ? WHERE id = ?",
            (count, rule_id)
        )
        await db.commit()


# ===== Migration Operations =====

async def create_migration(user_id: int, rule_id: int, total_messages: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO migrations (user_id, rule_id, total_messages, status) VALUES (?, ?, ?, 'running')",
            (user_id, rule_id, total_messages)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            return row[0]


async def update_migration_progress(migration_id: int, copied: int, last_msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE migrations SET copied_messages = ?, last_message_id = ? WHERE id = ?",
            (copied, last_msg_id, migration_id)
        )
        await db.commit()


async def finish_migration(migration_id: int, status: str = 'completed'):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE migrations SET status = ? WHERE id = ?",
            (status, migration_id)
        )
        await db.commit()


async def get_active_migration(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM migrations WHERE user_id = ? AND status = 'running' LIMIT 1",
            (user_id,)
        ) as cur:
            return await cur.fetchone()


# ===== Stats =====

async def get_global_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            stats['total_users'] = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE status='active'") as cur:
            stats['active_users'] = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM forwarding_rules WHERE is_active=1") as cur:
            stats['active_rules'] = (await cur.fetchone())[0]
        async with db.execute("SELECT COALESCE(SUM(messages_forwarded),0) FROM users") as cur:
            stats['total_messages'] = (await cur.fetchone())[0]
        return stats
