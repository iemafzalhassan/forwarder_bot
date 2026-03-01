"""Handlers: Add / List / Manage / Delete / Migrate forwarding rules — v2.0 Premium UI."""
from pyrogram import Client, filters, errors
from pyrogram.types import CallbackQuery

from keyboards.buttons import (
    main_menu_kb, groups_keyboard, cancel_kb,
    rules_list_kb, rule_detail_kb, confirm_delete_kb
)
from core.database import (
    get_user, add_rule, get_user_rules, get_active_rules,
    get_rule_by_id, delete_rule, toggle_rule
)
from core import migrator


async def safe_edit(message, text, reply_markup=None):
    """Edit message safely — ignores MessageNotModified error."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except errors.MessageNotModified:
        pass


def register(bot: Client, session_mgr):

    # ═══════════ ADD RULE FLOW ═══════════

    @bot.on_callback_query(filters.regex("^add_rule$"))
    async def cb_add_rule(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        user = await get_user(uid)
        if not user or user['status'] != 'active':
            await cb.answer("Connect your account first.", show_alert=True)
            return

        if uid not in session_mgr.active_clients:
            await session_mgr.start_forwarding(uid, user['session_string'])

        await cb.answer()
        await safe_edit(
            cb.message,
            "**Loading Groups**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Fetching your groups and channels..."
        )

        groups = await session_mgr.get_user_groups(uid)
        session_mgr.set_state(uid, 'rule_picking_source', groups=groups)

        if not groups:
            session_mgr.set_state(uid, 'rule_waiting_source_id')
            await safe_edit(
                cb.message,
                "**Add Rule  ·  Step 1**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "No groups found.\n"
                "Enter the **Source** chat ID manually:\n\n"
                "`-1001234567890`",
                reply_markup=cancel_kb()
            )
            return

        await safe_edit(
            cb.message,
            "**Add Rule  ·  Step 1**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select the group to **copy messages from:**",
            reply_markup=groups_keyboard(groups, page=0, prefix="src")
        )

    # ── Source selection ──

    @bot.on_callback_query(filters.regex(r"^src_-?\d+$"))
    async def pick_source(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        source_id = int(cb.data.split("_", 1)[1])
        state = session_mgr.get_state(uid)
        groups = state.get('groups', [])

        title = next((g['title'] for g in groups if g['id'] == source_id), str(source_id))
        session_mgr.set_state(uid, 'rule_picking_dest', groups=groups,
                              source_id=source_id, source_title=title)

        await cb.answer()
        await safe_edit(
            cb.message,
            "**Add Rule  ·  Step 2**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"**Source:**  {title}\n\n"
            "Now select the **destination:**",
            reply_markup=groups_keyboard(groups, page=0, prefix="dst")
        )

    @bot.on_callback_query(filters.regex(r"^dst_-?\d+$"))
    async def pick_dest(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        dest_id = int(cb.data.split("_", 1)[1])
        state = session_mgr.get_state(uid)
        source_id = state.get('source_id')
        source_title = state.get('source_title', '')
        groups = state.get('groups', [])

        if not source_id:
            await cb.answer("Session expired. Start over.", show_alert=True)
            session_mgr.clear_state(uid)
            await safe_edit(
                cb.message,
                "**Session Expired**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please try again.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
            return

        dest_title = next((g['title'] for g in groups if g['id'] == dest_id), str(dest_id))

        success = await add_rule(uid, source_id, dest_id, source_title, dest_title)
        session_mgr.clear_state(uid)

        if not success:
            await cb.answer("This rule already exists.", show_alert=True)
            await safe_edit(
                cb.message,
                "**Duplicate Rule**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "This source → destination pair\n"
                "already exists in your rules.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
            return

        # Restart forwarding to pick up new rule
        user = await get_user(uid)
        await session_mgr.start_forwarding(uid, user['session_string'])

        await cb.answer("Rule created!")
        await safe_edit(
            cb.message,
            "**Rule Created**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  **From:**  {source_title}\n"
            f"┊  **To:**      {dest_title}\n\n"
            "New messages will be copied silently.\n"
            "Want old messages too?\n"
            "Go to My Rules → Migrate.\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=True)
        )

    # ── Manual ID entry ──

    @bot.on_callback_query(filters.regex("^src_manual$"))
    async def src_manual(client: Client, cb: CallbackQuery):
        state = session_mgr.get_state(cb.from_user.id)
        session_mgr.set_state(cb.from_user.id, 'rule_waiting_source_id',
                              groups=state.get('groups', []))
        await cb.answer()
        await safe_edit(
            cb.message,
            "**Add Rule  ·  Manual Entry**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter the **Source** chat ID:\n\n"
            "`-1001234567890`",
            reply_markup=cancel_kb()
        )

    @bot.on_callback_query(filters.regex("^dst_manual$"))
    async def dst_manual(client: Client, cb: CallbackQuery):
        state = session_mgr.get_state(cb.from_user.id)
        session_mgr.set_state(cb.from_user.id, 'rule_waiting_dest_id',
                              groups=state.get('groups', []),
                              source_id=state.get('source_id'),
                              source_title=state.get('source_title', ''))
        await cb.answer()
        await safe_edit(
            cb.message,
            "**Add Rule  ·  Manual Entry**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter the **Destination** chat ID:\n\n"
            "`-1001234567890`",
            reply_markup=cancel_kb()
        )

    # ── Pagination ──

    @bot.on_callback_query(filters.regex(r"^(src|dst)page_\d+$"))
    async def paginate(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        parts = cb.data.split("_")
        prefix = parts[0].replace("page", "")
        page = int(parts[1])
        state = session_mgr.get_state(uid)
        groups = state.get('groups', [])

        step = "Step 1" if prefix == "src" else "Step 2"
        action = "copy messages from" if prefix == "src" else "forward messages to"

        await cb.answer()
        await safe_edit(
            cb.message,
            f"**Add Rule  ·  {step}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Select the group to **{action}:**",
            reply_markup=groups_keyboard(groups, page=page, prefix=prefix)
        )

    # ═══════════ RULE MANAGEMENT ═══════════

    @bot.on_callback_query(filters.regex("^my_rules$"))
    async def cb_my_rules(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rules = await get_user_rules(uid)
        if not rules:
            await cb.answer()
            await safe_edit(
                cb.message,
                "**My Rules**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "No rules yet.\n"
                "Create your first forwarding rule.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
            return

        active = sum(1 for r in rules if r['is_active'])
        await cb.answer()
        await safe_edit(
            cb.message,
            f"**My Rules**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Total: **{len(rules)}**  ·  Active: **{active}**\n\n"
            f"Tap a rule to manage it:",
            reply_markup=rules_list_kb(rules)
        )

    @bot.on_callback_query(filters.regex(r"^viewrule_\d+$"))
    async def view_rule(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rule_id = int(cb.data.split("_")[1])
        rule = await get_rule_by_id(rule_id, uid)

        if not rule:
            await cb.answer("Rule not found.", show_alert=True)
            return

        status = "◉ Active" if rule['is_active'] else "○ Paused"
        src = rule['source_title'] or str(rule['source_chat_id'])
        dst = rule['dest_title'] or str(rule['dest_chat_id'])

        await cb.answer()
        await safe_edit(
            cb.message,
            f"**Rule #{rule['id']}**  ·  {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  **Source:**  {src}\n"
            f"┊  `{rule['source_chat_id']}`\n\n"
            f"┊  **Dest:**  {dst}\n"
            f"┊  `{rule['dest_chat_id']}`\n\n"
            f"**Messages copied:**  {rule['messages_copied']}\n"
            f"**Created:**  {rule['created_at'][:10]}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=rule_detail_kb(rule_id, bool(rule['is_active']))
        )

    # ── Toggle (Pause/Resume) ──

    @bot.on_callback_query(filters.regex(r"^toggle_\d+$"))
    async def cb_toggle(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rule_id = int(cb.data.split("_")[1])
        await toggle_rule(rule_id, uid)

        user = await get_user(uid)
        if user and user['status'] == 'active':
            await session_mgr.start_forwarding(uid, user['session_string'])

        rule = await get_rule_by_id(rule_id, uid)
        action = "Resumed" if rule['is_active'] else "Paused"
        await cb.answer(f"Rule {action}.")

        status = "◉ Active" if rule['is_active'] else "○ Paused"
        src = rule['source_title'] or str(rule['source_chat_id'])
        dst = rule['dest_title'] or str(rule['dest_chat_id'])
        await safe_edit(
            cb.message,
            f"**Rule #{rule['id']}**  ·  {status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  **Source:**  {src}\n"
            f"┊  `{rule['source_chat_id']}`\n\n"
            f"┊  **Dest:**  {dst}\n"
            f"┊  `{rule['dest_chat_id']}`\n\n"
            f"**Messages copied:**  {rule['messages_copied']}\n"
            f"**Created:**  {rule['created_at'][:10]}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=rule_detail_kb(rule_id, bool(rule['is_active']))
        )

    # ── Delete with Confirmation ──

    @bot.on_callback_query(filters.regex(r"^delrule_\d+$"))
    async def cb_delrule(client: Client, cb: CallbackQuery):
        rule_id = int(cb.data.split("_")[1])
        await cb.answer()
        await safe_edit(
            cb.message,
            f"**Delete Rule #{rule_id}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"This action cannot be undone.\n"
            f"Are you sure?",
            reply_markup=confirm_delete_kb(rule_id)
        )

    @bot.on_callback_query(filters.regex(r"^confirmdel_\d+$"))
    async def cb_confirmdel(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rule_id = int(cb.data.split("_")[1])
        await delete_rule(rule_id, uid)

        user = await get_user(uid)
        if user and user['status'] == 'active':
            await session_mgr.start_forwarding(uid, user['session_string'])

        await cb.answer("Rule deleted.")
        rules = await get_user_rules(uid)
        if rules:
            active = sum(1 for r in rules if r['is_active'])
            await safe_edit(
                cb.message,
                f"**My Rules**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Rule #{rule_id} deleted.\n\n"
                f"Total: **{len(rules)}**  ·  Active: **{active}**",
                reply_markup=rules_list_kb(rules)
            )
        else:
            await safe_edit(
                cb.message,
                "**My Rules**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "All rules deleted.\n"
                "No active rules.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )

    # ── Migration ──

    @bot.on_callback_query(filters.regex(r"^migrate_\d+$"))
    async def cb_migrate(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rule_id = int(cb.data.split("_")[1])

        user_client = session_mgr.active_clients.get(uid)
        if not user_client:
            await cb.answer("Session not active. Connect again.", show_alert=True)
            return

        await cb.answer()
        await safe_edit(
            cb.message,
            "**Migration Starting**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Copying all old messages\n"
            "from source to destination.\n\n"
            "This may take several minutes.\n"
            "You'll receive progress updates.\n\n"
            "Send `/stop_migration` to cancel.\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        success, msg = await migrator.start_migration(
            bot=client, user_id=uid, rule_id=rule_id,
            user_client=user_client, notify_chat_id=cb.message.chat.id
        )

        if not success:
            await cb.message.reply(
                f"**Migration Error**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{msg}",
                reply_markup=main_menu_kb(is_logged_in=True)
            )

    # ── Stop Migration ──

    @bot.on_message(filters.command("stop_migration") & filters.private)
    async def cmd_stop_migration(client: Client, message):
        stopped = await migrator.stop_migration(message.from_user.id)
        if stopped:
            await message.reply("Migration stop requested.")
        else:
            await message.reply("No migration is running.")

    # ── Stats ──

    @bot.on_callback_query(filters.regex("^my_stats$"))
    async def cb_my_stats(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        user = await get_user(uid)
        rules = await get_user_rules(uid)
        active = sum(1 for r in rules if r['is_active'])
        total_copied = sum(r['messages_copied'] for r in rules) if rules else 0

        await cb.answer()
        await safe_edit(
            cb.message,
            "**Your Stats**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  Messages forwarded:  **{user['messages_forwarded'] if user else 0}**\n"
            f"┊  Total rules:  **{len(rules)}**  ({active} active)\n"
            f"┊  Migrated messages:  **{total_copied}**\n\n"
            f"**Account:**  {'◉ Active' if user and user['status'] == 'active' else '○ Inactive'}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=True)
        )

    # ── Del command (text) ──

    @bot.on_message(filters.command("del") & filters.private)
    async def cmd_del(client: Client, message):
        try:
            rule_id = int(message.text.split()[1])
            await delete_rule(rule_id, message.from_user.id)
            user = await get_user(message.from_user.id)
            if user and user['status'] == 'active':
                await session_mgr.start_forwarding(message.from_user.id, user['session_string'])
            await message.reply(f"Rule #{rule_id} deleted.")
        except (IndexError, ValueError):
            await message.reply("Usage: `/del <rule_id>`")


async def process_text(client: Client, message, session_mgr):
    """Called by main dispatcher for rule-related manual ID input."""
    uid = message.from_user.id
    state = session_mgr.get_state(uid)
    current = state.get('state', '')
    text = message.text.strip()

    try:
        chat_id = int(text)
    except ValueError:
        await message.reply(
            "**Invalid ID**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter a number like `-1001234567890`.",
            reply_markup=cancel_kb()
        )
        return

    if current == 'rule_waiting_source_id':
        groups = state.get('groups', [])
        session_mgr.set_state(uid, 'rule_picking_dest', groups=groups,
                              source_id=chat_id, source_title=str(chat_id))
        if groups:
            await message.reply(
                "**Add Rule  ·  Step 2**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Source:**  `{chat_id}`\n\n"
                "Now select the **destination:**",
                reply_markup=groups_keyboard(groups, page=0, prefix="dst")
            )
        else:
            session_mgr.set_state(uid, 'rule_waiting_dest_id',
                                  groups=[], source_id=chat_id, source_title=str(chat_id))
            await message.reply(
                "**Add Rule  ·  Step 2**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Source:**  `{chat_id}`\n\n"
                "Now enter **Destination** chat ID:",
                reply_markup=cancel_kb()
            )

    elif current == 'rule_waiting_dest_id':
        source_id = state.get('source_id')
        source_title = state.get('source_title', '')
        if not source_id:
            await message.reply(
                "**Session Expired**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please start over.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
            session_mgr.clear_state(uid)
            return

        success = await add_rule(uid, source_id, chat_id, source_title, str(chat_id))
        session_mgr.clear_state(uid)

        if not success:
            await message.reply(
                "**Duplicate Rule**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "This rule already exists.",
                reply_markup=main_menu_kb(is_logged_in=True)
            )
            return

        user = await get_user(uid)
        await session_mgr.start_forwarding(uid, user['session_string'])
        await message.reply(
            "**Rule Created**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"┊  **From:**  `{source_id}`\n"
            f"┊  **To:**      `{chat_id}`\n\n"
            "Messages will now be forwarded silently.\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=main_menu_kb(is_logged_in=True)
        )
