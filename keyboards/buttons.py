"""Reusable Inline Keyboard Builders — v1.0."""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_logged_in: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if is_logged_in:
        buttons.append([InlineKeyboardButton("➕ Add Forwarding Rule", callback_data="add_rule")])
        buttons.append([InlineKeyboardButton("📋 My Rules", callback_data="my_rules")])
        buttons.append([InlineKeyboardButton("📊 My Stats", callback_data="my_stats")])
        buttons.append([InlineKeyboardButton("🔴 Logout", callback_data="logout")])
    else:
        buttons.append([InlineKeyboardButton("🔐 Login with Telegram", callback_data="login")])
    buttons.append([InlineKeyboardButton("📖 How to Use", callback_data="guide")])
    return InlineKeyboardMarkup(buttons)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])


def groups_keyboard(groups: list[dict], page: int = 0, per_page: int = 6,
                     prefix: str = "src") -> InlineKeyboardMarkup:
    start = page * per_page
    page_groups = groups[start:start + per_page]

    buttons = []
    for g in page_groups:
        icon = "📢" if "CHANNEL" in g['type'] else "👥"
        label = f"{icon} {g['title'][:28]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{g['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}page_{page - 1}"))
    if start + per_page < len(groups):
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}page_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("📝 Enter ID Manually", callback_data=f"{prefix}_manual")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)


def rule_detail_kb(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Pause" if is_active else "▶️ Resume"
    toggle_data = f"toggle_{rule_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(toggle_text, callback_data=toggle_data),
            InlineKeyboardButton("🗑 Delete", callback_data=f"delrule_{rule_id}")
        ],
        [InlineKeyboardButton("📦 Migrate Old Messages", callback_data=f"migrate_{rule_id}")],
        [InlineKeyboardButton("◀️ Back to Rules", callback_data="my_rules")]
    ])


def confirm_delete_kb(rule_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirmdel_{rule_id}"),
            InlineKeyboardButton("❌ No, Keep", callback_data="my_rules")
        ]
    ])


def rules_list_kb(rules: list) -> InlineKeyboardMarkup:
    buttons = []
    for r in rules:
        status = "🟢" if r['is_active'] else "🔴"
        src = r['source_title'][:15] if r['source_title'] else str(r['source_chat_id'])
        dst = r['dest_title'][:15] if r['dest_title'] else str(r['dest_chat_id'])
        label = f"{status} {src} → {dst}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"viewrule_{r['id']}")])

    buttons.append([InlineKeyboardButton("➕ Add New Rule", callback_data="add_rule")])
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)
