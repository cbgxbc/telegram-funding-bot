import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from config import load_settings
from db import Database, User, Campaign
from keyboards import main_kb, task_kb, admin_kb

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
settings = load_settings()
db = Database(settings.database_url)
bot = Bot(settings.bot_token)
dp = Dispatcher()


def admin(uid: int) -> bool:
    return uid in settings.admin_ids


async def allowed(uid: int) -> bool:
    if admin(uid):
        return True
    u = await db.get_user(uid)
    if u and u.banned:
        return False
    return not await db.maintenance()


async def ensure(message: Message):
    ref = None
    if message.text and message.text.startswith('/start '):
        arg = message.text.split(maxsplit=1)[1].strip()
        if arg.isdigit():
            ref = int(arg)
    return await db.ensure_user(message.from_user, ref)


@dp.message(CommandStart())
async def start(message: Message):
    user, created = await ensure(message)
    if user.banned:
        await message.answer('🚫 حسابك موقوف.')
        return
    if await db.maintenance() and not admin(message.from_user.id):
        await message.answer('🔧 البوت تحت الصيانة مؤقتًا. حاول لاحقًا.')
        return
    text = ('🎉 أهلاً بك في بوت تمويل القنوات!\n\n'
            'أنجز المهام، اشترك بالقنوات المطلوبة، ثم تحقّق لتحصل على النقاط.\n\n'
            '💡 يمكنك استخدام نقاطك لإنشاء حملات ترويجية لقناتك.')
    if created:
        text += '\n\n🎁 تم إنشاء حسابك. رابط الإحالة الخاص بك موجود في قسم الإحالات.'
    await message.answer(text, reply_markup=main_kb(admin(message.from_user.id)))


@dp.message(Command('help'))
async def help_cmd(message: Message):
    await ensure(message)
    await message.answer(
        '📚 الأوامر الأساسية:\n'
        '/start — الرئيسية\n'
        '/help — المساعدة\n\n'
        'إنشاء حملة:\n'
        '/newcampaign chat_id | title | reward | budget | invite_link\n\n'
        'مثال:\n'
        '/newcampaign -100123456789 | قناتي | 5 | 100 | https://t.me/example\n\n'
        'يجب أن يكون البوت مشرفًا في القناة المستهدفة.'
    )


@dp.message(Command('newcampaign'))
async def new_campaign(message: Message):
    await ensure(message)
    if not await allowed(message.from_user.id):
        await message.answer('🔧 البوت غير متاح حاليًا.')
        return
    raw = message.text.partition(' ')[2].strip()
    parts = [p.strip() for p in raw.split('|')]
    if len(parts) != 5:
        await message.answer('❌ الصيغة غير صحيحة.\n\n/newcampaign chat_id | title | reward | budget | invite_link')
        return
    try:
        chat_id = int(parts[0]); title = parts[1]; reward = int(parts[2]); budget = int(parts[3]); link = parts[4]
    except ValueError:
        await message.answer('❌ chat_id و reward و budget يجب أن تكون أرقامًا.')
        return
    if reward <= 0 or budget <= 0 or budget < reward or budget % reward != 0:
        await message.answer('❌ يجب أن يكون reward و budget موجبين، وأن يكون budget من مضاعفات reward.')
        return
    if not (link.startswith('https://t.me/') or link.startswith('http://t.me/')):
        await message.answer('❌ رابط الدعوة يجب أن يكون رابط Telegram مثل https://t.me/example')
        return
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        if member.status not in {'administrator', 'creator'}:
            await message.answer('❌ يجب أن يكون البوت مشرفًا في القناة/المجموعة.')
            return
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        logging.exception(e)
        await message.answer('❌ لم أستطع الوصول إلى القناة. تأكد من chat_id وأن البوت مشرف.')
        return
    campaign, err = await db.create_campaign(message.from_user.id, chat_id, title or chat.title or 'Channel', link, reward, budget)
    if err == 'insufficient':
        u = await db.get_user(message.from_user.id)
        await message.answer(f'❌ رصيدك غير كافٍ. رصيدك: {u.points if u else 0} نقطة، المطلوب: {budget}.')
        return
    await message.answer(f'✅ تم إنشاء الحملة #{campaign.id}\n📢 {campaign.chat_title}\n💰 المكافأة: {reward}\n🎯 الميزانية: {budget}\n👥 عدد الاشتراكات المطلوبة: {budget // reward}')


@dp.message(Command('addpoints'))
async def addpoints(message: Message):
    if not admin(message.from_user.id):
        return
    raw = message.text.partition(' ')[2].split()
    if len(raw) != 2 or not raw[0].isdigit() or not raw[1].lstrip('-').isdigit():
        await message.answer('/addpoints USER_ID AMOUNT')
        return
    uid, amount = int(raw[0]), int(raw[1])
    ok = await db.add_points(uid, amount, 'admin', 'Admin adjustment')
    await message.answer('✅ تم تعديل الرصيد.' if ok else '❌ المستخدم غير موجود.')


@dp.message(Command('ban'))
async def ban(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer('/ban USER_ID'); return
    await db.set_banned(int(parts[1]), True); await message.answer('🚫 تم الإيقاف.')


@dp.message(Command('unban'))
async def unban(message: Message):
    if not admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer('/unban USER_ID'); return
    await db.set_banned(int(parts[1]), False); await message.answer('✅ تم إلغاء الإيقاف.')


@dp.message(Command('maintenance'))
async def maintenance_cmd(message: Message):
    if not admin(message.from_user.id): return
    arg = message.text.partition(' ')[2].strip().lower()
    if arg not in {'on','off'}:
        await message.answer('/maintenance on أو /maintenance off'); return
    await db.set_maintenance(arg == 'on'); await message.answer('🔧 تم تحديث وضع الصيانة.')


@dp.message(Command('broadcast'))
async def broadcast(message: Message):
    if not admin(message.from_user.id): return
    text = message.text.partition(' ')[2].strip()
    if not text:
        await message.answer('/broadcast نص الرسالة'); return
    ids = await db.all_user_ids(); ok = fail = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await message.answer(f'📣 انتهى البث.\n✅ {ok}\n❌ {fail}')


@dp.callback_query(F.data == 'home')
async def home(c: CallbackQuery):
    await c.answer(); await c.message.edit_text('🏠 الرئيسية', reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'tasks')
async def tasks(c: CallbackQuery):
    await c.answer()
    if not await allowed(c.from_user.id):
        await c.message.answer('🔧 البوت غير متاح حاليًا.'); return
    campaigns = await db.list_active_campaigns()
    if not campaigns:
        await c.message.edit_text('📭 لا توجد مهام متاحة حاليًا.', reply_markup=main_kb(admin(c.from_user.id))); return
    await c.message.edit_text(f'📋 المهام المتاحة: {len(campaigns)}')
    for x in campaigns:
        slots = max(0, x.budget // x.reward - x.completed)
        await c.message.answer(f'📢 {x.chat_title}\n💰 المكافأة: {x.reward} نقطة\n👥 المتبقي: {slots}', reply_markup=task_kb(x.id, x.invite_link))


@dp.callback_query(F.data.startswith('verify:'))
async def verify(c: CallbackQuery):
    await c.answer()
    if not await allowed(c.from_user.id):
        await c.message.answer('🔧 البوت غير متاح حاليًا.'); return
    cid = int(c.data.split(':',1)[1])
    async with db.session() as s:
        campaign = await s.get(Campaign, cid)
    if not campaign:
        await c.message.answer('❌ المهمة غير موجودة.'); return
    try:
        member = await bot.get_chat_member(campaign.chat_id, c.from_user.id)
        joined = member.status in {'member','administrator','creator'} or (member.status == 'restricted' and getattr(member, 'is_member', False))
    except Exception:
        joined = False
    if not joined:
        await c.message.answer('❌ لم أجد اشتراكك بعد. اشترك أولًا ثم اضغط التحقق مرة أخرى.')
        return
    status, reward = await db.claim(cid, c.from_user.id)
    msgs = {'ok': f'🎉 تم التحقق! +{reward} نقطة.', 'duplicate':'ℹ️ حصلت على مكافأة هذه المهمة سابقًا.', 'owner':'❌ لا يمكنك تنفيذ حملتك الخاصة.', 'closed':'❌ انتهت الحملة.', 'missing':'❌ المهمة غير موجودة.'}
    await c.message.answer(msgs.get(status, '❌ تعذر إكمال المهمة.'))


@dp.callback_query(F.data == 'balance')
async def balance(c: CallbackQuery):
    await c.answer(); u = await db.get_user(c.from_user.id); await c.message.edit_text(f'💰 رصيدك الحالي: {u.points if u else 0} نقطة', reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'referrals')
async def referrals(c: CallbackQuery):
    await c.answer()
    link = f'https://t.me/{settings.bot_username}?start={c.from_user.id}' if settings.bot_username else f'/start {c.from_user.id}'
    await c.message.edit_text(f'👥 الإحالات\n\nارسل هذا الرابط لأصدقائك:\n{link}\n\n🎁 مكافأة الإحالة: 10 نقاط.', reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'history')
async def history(c: CallbackQuery):
    await c.answer(); rows = await db.transactions(c.from_user.id)
    if not rows: text='📜 لا يوجد سجل بعد.'
    else:
        text='📜 آخر العمليات:\n\n' + '\n'.join(f"{'+' if x.amount >= 0 else ''}{x.amount} — {x.note}" for x in rows)
    await c.message.edit_text(text, reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'my_campaigns')
async def my_campaigns(c: CallbackQuery):
    await c.answer(); rows = await db.my_campaigns(c.from_user.id)
    if not rows: text='📢 لا توجد حملات لك.'
    else:
        text='📢 حملاتك:\n\n' + '\n'.join(f'#{x.id} {x.chat_title} — {x.completed}/{x.budget//x.reward} — {"🟢" if x.active else "🔴"}' for x in rows)
    await c.message.edit_text(text, reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'new_campaign')
async def new_campaign_help(c: CallbackQuery):
    await c.answer(); await c.message.edit_text('➕ إنشاء حملة\n\nاستخدم الأمر:\n/newcampaign chat_id | title | reward | budget | invite_link\n\nمثال:\n/newcampaign -100123456789 | قناتي | 5 | 100 | https://t.me/example\n\nيتم خصم الميزانية من رصيدك عند إنشاء الحملة.', reply_markup=main_kb(admin(c.from_user.id)))


@dp.callback_query(F.data == 'admin')
async def admin_panel(c: CallbackQuery):
    await c.answer()
    if not admin(c.from_user.id): return
    await c.message.edit_text('🛠 لوحة المالك\n\nاختر العملية:', reply_markup=admin_kb())


@dp.callback_query(F.data == 'admin_stats')
async def admin_stats(c: CallbackQuery):
    await c.answer(); users, active, completions, points = await db.stats()
    await c.message.edit_text(f'📊 الإحصائيات\n\n👥 المستخدمون: {users}\n📢 الحملات النشطة: {active}\n✅ الإنجازات: {completions}\n💰 مجموع الأرصدة: {points}', reply_markup=admin_kb())


@dp.callback_query(F.data == 'admin_campaigns')
async def admin_campaigns(c: CallbackQuery):
    await c.answer(); rows = await db.list_active_campaigns(20)
    text = '📢 الحملات النشطة:\n\n' + ('\n'.join(f'#{x.id} {x.chat_title} — {x.completed}/{x.budget//x.reward}' for x in rows) if rows else 'لا توجد حملات.')
    await c.message.edit_text(text, reply_markup=admin_kb())


@dp.callback_query(F.data == 'admin_users')
async def admin_users(c: CallbackQuery):
    await c.answer(); users, _, _, _ = await db.stats()
    await c.message.edit_text(f'👥 عدد المستخدمين: {users}\n\nاستخدم /addpoints USER_ID AMOUNT لتعديل الرصيد.\nاستخدم /ban USER_ID أو /unban USER_ID.', reply_markup=admin_kb())


@dp.callback_query(F.data == 'admin_maintenance')
async def admin_maintenance(c: CallbackQuery):
    await c.answer(); state = await db.maintenance()
    await c.message.edit_text(f'🔧 وضع الصيانة الحالي: {"مفعل" if state else "متوقف"}\n\n/maintenance on\n/maintenance off', reply_markup=admin_kb())


@dp.callback_query(F.data == 'admin_broadcast_help')
async def admin_broadcast_help(c: CallbackQuery):
    await c.answer(); await c.message.edit_text('📣 البث\n\nاستخدم:\n/broadcast نص الرسالة\n\nسيتم الإرسال للمستخدمين غير الموقوفين.', reply_markup=admin_kb())


async def main():
    await db.init()
    me = await bot.get_me()
    logging.info('Bot started as @%s', me.username)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
