"""
Premium Inline Keyboard Builders — v2.1 Flagship
Every screen has consistent navigation. Migration accessible from main menu.
"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_logged_in: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if is_logged_in:
        buttons.append([InlineKeyboardButton("＋  New Rule", callback_data="add_rule")])
        buttons.append([InlineKeyboardButton("☰  My Rules", callback_data="my_rules")])
        buttons.append([InlineKeyboardButton("⟳  Migrate Old Messages", callback_data="migrate_menu")])
        buttons.append([
            InlineKeyboardButton("⊡  Stats", callback_data="my_stats"),
            InlineKeyboardButton("⊗  Disconnect", callback_data="logout")
        ])
    else:
        buttons.append([InlineKeyboardButton("▸  Connect Telegram Account", callback_data="login")])
    buttons.append([InlineKeyboardButton("◇  Guide", callback_data="guide")])
    return InlineKeyboardMarkup(buttons)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("‹  Back", callback_data="main_menu")]
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✕  Cancel", callback_data="cancel")]
    ])


def groups_keyboard(groups: list[dict], page: int = 0, per_page: int = 6,
                     prefix: str = "src") -> InlineKeyboardMarkup:
    start = page * per_page
    page_groups = groups[start:start + per_page]

    buttons = []
    for g in page_groups:
        icon = "◈" if "CHANNEL" in g['type'] else "◆"
        label = f"{icon}  {g['title'][:28]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{g['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("‹ Prev", callback_data=f"{prefix}page_{page - 1}"))
    if start + per_page < len(groups):
        nav.append(InlineKeyboardButton("Next ›", callback_data=f"{prefix}page_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("⌨  Enter ID Manually", callback_data=f"{prefix}_manual")])
    buttons.append([InlineKeyboardButton("✕  Cancel", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)


def rule_detail_kb(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❚❚  Pause" if is_active else "▸  Resume"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(toggle_text, callback_data=f"toggle_{rule_id}"),
            InlineKeyboardButton("✕  Delete", callback_data=f"delrule_{rule_id}")
        ],
        [InlineKeyboardButton("⟳  Migrate Old Messages", callback_data=f"migrate_{rule_id}")],
        [InlineKeyboardButton("‹  Back to Rules", callback_data="my_rules")],
        [InlineKeyboardButton("‹‹  Main Menu", callback_data="main_menu")]
    ])


def confirm_delete_kb(rule_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◉  Yes, Delete", callback_data=f"confirmdel_{rule_id}"),
            InlineKeyboardButton("○  No, Keep", callback_data=f"viewrule_{rule_id}")
        ]
    ])


def confirm_migration_kb(rule_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⟳  Yes, Migrate Again", callback_data=f"startmig_{rule_id}")],
        [InlineKeyboardButton("✕  No, Cancel", callback_data=f"viewrule_{rule_id}")]
    ])


def rules_list_kb(rules: list) -> InlineKeyboardMarkup:
    buttons = []
    for r in rules:
        status = "◉" if r['is_active'] else "○"
        src = r['source_title'][:14] if r['source_title'] else str(r['source_chat_id'])[:14]
        dst = r['dest_title'][:14] if r['dest_title'] else str(r['dest_chat_id'])[:14]
        label = f"{status}  {src}  →  {dst}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"viewrule_{r['id']}")])

    buttons.append([InlineKeyboardButton("＋  New Rule", callback_data="add_rule")])
    buttons.append([InlineKeyboardButton("‹  Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def migrate_menu_kb(rules: list) -> InlineKeyboardMarkup:
    """Migration menu — shows all rules with migrate option."""
    buttons = []
    for r in rules:
        src = r['source_title'][:16] if r['source_title'] else str(r['source_chat_id'])[:16]
        dst = r['dest_title'][:16] if r['dest_title'] else str(r['dest_chat_id'])[:16]
        label = f"⟳  {src}  →  {dst}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"migrate_{r['id']}")])

    buttons.append([InlineKeyboardButton("‹  Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)
