from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_kb(is_admin=False):
    rows = [
        [InlineKeyboardButton(text='📋 المهام', callback_data='tasks'), InlineKeyboardButton(text='💰 رصيدي', callback_data='balance')],
        [InlineKeyboardButton(text='👥 الإحالات', callback_data='referrals'), InlineKeyboardButton(text='📜 السجل', callback_data='history')],
        [InlineKeyboardButton(text='📢 حملاتي', callback_data='my_campaigns'), InlineKeyboardButton(text='➕ حملة جديدة', callback_data='new_campaign')],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text='🛠 لوحة المالك', callback_data='admin')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_kb(campaign_id, link):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📢 فتح القناة', url=link)],
        [InlineKeyboardButton(text='✅ تحقّق من الاشتراك', callback_data=f'verify:{campaign_id}')],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 الإحصائيات', callback_data='admin_stats'), InlineKeyboardButton(text='📢 الحملات', callback_data='admin_campaigns')],
        [InlineKeyboardButton(text='👥 المستخدمون', callback_data='admin_users'), InlineKeyboardButton(text='🔧 الصيانة', callback_data='admin_maintenance')],
        [InlineKeyboardButton(text='📣 البث', callback_data='admin_broadcast_help')],
        [InlineKeyboardButton(text='⬅️ الرئيسية', callback_data='home')],
    ])
