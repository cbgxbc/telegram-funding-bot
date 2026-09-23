from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(admin=False):
    rows = [
        [InlineKeyboardButton(text="📋 المهام", callback_data="tasks"),
         InlineKeyboardButton(text="💰 رصيدي", callback_data="balance")],
        [InlineKeyboardButton(text="👥 الإحالات", callback_data="ref"),
         InlineKeyboardButton(text="📜 السجل", callback_data="history")],
        [InlineKeyboardButton(text="📢 حملتي", callback_data="campaign_help")],
    ]
    if admin:
        rows.append([InlineKeyboardButton(text="🛠 لوحة المالك", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="home")]
    ])

def campaign_buttons(campaign_id, invite_link=None):
    rows = []
    if invite_link:
        rows.append([InlineKeyboardButton(text="📢 فتح القناة", url=invite_link)])
    rows.append([InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data=f"verify:{campaign_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="a:stats"),
         InlineKeyboardButton(text="📋 الحملات", callback_data="a:campaigns")],
        [InlineKeyboardButton(text="👤 المستخدمون", callback_data="a:users"),
         InlineKeyboardButton(text="⏯ حالة البوت", callback_data="a:status")],
        [InlineKeyboardButton(text="🔙 الرئيسية", callback_data="home")]
    ])
