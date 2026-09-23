from pathlib import Path
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from .config import load_settings
from .db import create_db, init_db, User, Campaign, Completion, Transaction
from .keyboards import main_menu, back_menu, campaign_buttons, admin_menu

settings = load_settings()
engine, Session = create_db(settings)
dp = Dispatcher()
maintenance = False

async def get_user(session, tg_user, referred_by=None):
    result = await session.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.username = tg_user.username
        return user
    user = User(telegram_id=tg_user.id, username=tg_user.username, referred_by=referred_by)
    session.add(user)
    await session.flush()
    return user

def is_owner(user_id: int) -> bool:
    return user_id == settings.owner_id

@dp.message(CommandStart())
async def start(message: Message):
    ref = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        raw = parts[1][4:]
        if raw.isdigit() and int(raw) != message.from_user.id:
            ref = int(raw)
    async with Session() as session:
        user = await get_user(session, message.from_user, ref)
        if ref and user.referred_by == ref:
            # referral reward is intentionally awarded only once, to avoid farming.
            ref_user = (await session.execute(select(User).where(User.telegram_id == ref))).scalar_one_or_none()
            if ref_user:
                ref_user.points += 10
                session.add(Transaction(user_id=ref_user.id, amount=10, kind="referral", note="Referral reward"))
                user.referred_by = None
        await session.commit()
    text = "👋 أهلاً بك في بوت التمويل والمهام\n\nأكمل المهام الطوعية واحصل على نقاط."
    await message.answer(text, reply_markup=main_menu(is_owner(message.from_user.id)))

@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("🏠 الرئيسية\nاختر الخدمة:", reply_markup=main_menu(is_owner(call.from_user.id)))

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    await call.answer()
    async with Session() as session:
        u = (await session.execute(select(User).where(User.telegram_id == call.from_user.id))).scalar_one_or_none()
        points = u.points if u else 0
    await call.message.edit_text(f"💰 رصيدك الحالي: **{points} نقطة**", parse_mode="Markdown", reply_markup=back_menu())

@dp.callback_query(F.data == "ref")
async def referral(call: CallbackQuery, bot: Bot):
    await call.answer()
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    await call.message.edit_text(
        f"👥 رابط الإحالة الخاص بك:\n\n`{link}`\n\nكل إحالة صالحة تمنح 10 نقاط.",
        parse_mode="Markdown", reply_markup=back_menu()
    )

@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    await call.answer()
    async with Session() as session:
        u = (await session.execute(select(User).where(User.telegram_id == call.from_user.id))).scalar_one_or_none()
        if not u:
            await call.message.edit_text("لا يوجد سجل.", reply_markup=back_menu()); return
        rows = (await session.execute(
            select(Transaction).where(Transaction.user_id == u.id).order_by(Transaction.id.desc()).limit(10)
        )).scalars().all()
    if not rows:
        text = "📜 لا توجد معاملات بعد."
    else:
        text = "📜 آخر المعاملات:\n\n" + "\n".join(
            f"• {('+' if r.amount >= 0 else '')}{r.amount} — {r.note}" for r in rows
        )
    await call.message.edit_text(text, reply_markup=back_menu())

@dp.callback_query(F.data == "tasks")
async def tasks(call: CallbackQuery):
    await call.answer()
    async with Session() as session:
        campaigns = (await session.execute(
            select(Campaign).where(Campaign.active == True).order_by(Campaign.id.desc()).limit(20)
        )).scalars().all()
    if not campaigns:
        await call.message.edit_text("📋 لا توجد مهام متاحة حاليًا.", reply_markup=back_menu()); return
    await call.message.edit_text("📋 اختر مهمة:", reply_markup=back_menu())
    for c in campaigns:
        await call.message.answer(
            f"📢 {c.chat_title}\n🎁 المكافأة: {c.reward} نقطة\n📦 المتبقي: {max(0,c.budget-c.completed*c.reward)} نقطة",
            reply_markup=campaign_buttons(c.id, c.invite_link)
        )

@dp.callback_query(F.data.startswith("verify:"))
async def verify(call: CallbackQuery, bot: Bot):
    await call.answer()
    campaign_id = int(call.data.split(":")[1])
    async with Session() as session:
        c = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
        if not c or not c.active:
            await call.message.answer("❌ المهمة غير متاحة."); return
        u = (await session.execute(select(User).where(User.telegram_id == call.from_user.id))).scalar_one_or_none()
        if not u:
            u = await get_user(session, call.from_user)
        existing = (await session.execute(select(Completion).where(
            Completion.campaign_id == c.id, Completion.user_id == u.id
        ))).scalar_one_or_none()
        if existing:
            await call.message.answer("ℹ️ تم احتساب هذه المهمة لك سابقًا."); return
        try:
            member = await bot.get_chat_member(c.chat_id, call.from_user.id)
            if member.status in {"member", "administrator", "creator"}:
                if c.completed * c.reward >= c.budget:
                    c.active = False
                    await session.commit()
                    await call.message.answer("⛔ اكتمل تمويل هذه الحملة.")
                    return
                session.add(Completion(campaign_id=c.id, user_id=u.id))
                u.points += c.reward
                c.completed += 1
                session.add(Transaction(user_id=u.id, amount=c.reward, kind="task", note=f"Task #{c.id}"))
                await session.commit()
                await call.message.answer(f"✅ تم التحقق! أضيفت {c.reward} نقطة.")
            else:
                await call.message.answer("❌ لم يتم العثور على اشتراكك في القناة. اشترك أولًا ثم اضغط تحقق.")
        except Exception as e:
            await session.rollback()
            await call.message.answer("⚠️ تعذر التحقق. تأكد أن البوت مشرف في القناة وأن القناة قابلة للوصول.")
            print("verify error:", repr(e))

@dp.callback_query(F.data == "campaign_help")
async def campaign_help(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "📢 تمويل حملة\n\nلإضافة حملة جديدة استخدم الأمر:\n"
        "`/campaign CHAT_ID | اسم القناة | المكافأة | الميزانية | رابط الدعوة`\n\n"
        "مثال: /campaign -1001234567890 | قناتي | 5 | 500 | https://t.me/example\n\n"
        "يجب أن يكون البوت مشرفًا في القناة.",
        parse_mode="Markdown", reply_markup=back_menu()
    )

@dp.message(Command("campaign"))
async def create_campaign(message: Message, bot: Bot):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ هذا الأمر للمالك حاليًا.")
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("الصيغة: /campaign CHAT_ID | اسم القناة | المكافأة | الميزانية | رابط الدعوة")
        return
    parts = [x.strip() for x in raw[1].split("|")]
    if len(parts) != 5:
        await message.answer("❌ عدد الحقول غير صحيح.")
        return
    try:
        chat_id = int(parts[0]); reward = int(parts[2]); budget = int(parts[3])
        if reward <= 0 or budget < reward: raise ValueError
    except ValueError:
        await message.answer("❌ CHAT_ID/reward/budget غير صحيحة.")
        return
    try:
        await bot.get_chat_member(chat_id, message.from_user.id)
    except Exception:
        await message.answer("⚠️ تعذر الوصول إلى القناة. أضف البوت مشرفًا وتأكد من CHAT_ID.")
        return
    async with Session() as session:
        session.add(Campaign(owner_id=message.from_user.id, chat_id=chat_id, chat_title=parts[1],
                             reward=reward, budget=budget, invite_link=parts[4] or None))
        await session.commit()
    await message.answer("✅ تم إنشاء الحملة.")

@dp.callback_query(F.data == "admin")
async def admin(call: CallbackQuery):
    await call.answer()
    if not is_owner(call.from_user.id):
        await call.message.edit_text("⛔ غير مصرح.", reply_markup=back_menu()); return
    await call.message.edit_text("🛠 لوحة المالك", reply_markup=admin_menu())

@dp.callback_query(F.data == "a:stats")
async def a_stats(call: CallbackQuery):
    await call.answer()
    if not is_owner(call.from_user.id): return
    async with Session() as session:
        users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        campaigns = (await session.execute(select(func.count(Campaign.id)))).scalar() or 0
        active = (await session.execute(select(func.count(Campaign.id)).where(Campaign.active == True))).scalar() or 0
        completions = (await session.execute(select(func.count(Completion.id)))).scalar() or 0
    await call.message.edit_text(
        f"📊 الإحصائيات\n\n👤 المستخدمون: {users}\n📢 الحملات: {campaigns}\n🟢 النشطة: {active}\n✅ المهام المكتملة: {completions}",
        reply_markup=admin_menu()
    )

@dp.callback_query(F.data == "a:campaigns")
async def a_campaigns(call: CallbackQuery):
    await call.answer()
    if not is_owner(call.from_user.id): return
    async with Session() as session:
        rows = (await session.execute(select(Campaign).order_by(Campaign.id.desc()).limit(20))).scalars().all()
    text = "📋 الحملات\n\n" + ("لا توجد حملات." if not rows else "\n".join(
        f"#{c.id} {c.chat_title} — {'🟢' if c.active else '🔴'} — {c.completed} مكتمل" for c in rows
    ))
    await call.message.edit_text(text, reply_markup=admin_menu())

@dp.callback_query(F.data == "a:users")
async def a_users(call: CallbackQuery):
    await call.answer()
    if not is_owner(call.from_user.id): return
    async with Session() as session:
        rows = (await session.execute(select(User).order_by(User.id.desc()).limit(15))).scalars().all()
    text = "👤 آخر المستخدمين\n\n" + ("لا يوجد." if not rows else "\n".join(
        f"• {u.telegram_id} — {u.username or 'بدون اسم'} — {u.points} نقطة" for u in rows
    ))
    await call.message.edit_text(text, reply_markup=admin_menu())

@dp.callback_query(F.data == "a:status")
async def a_status(call: CallbackQuery):
    await call.answer()
    if not is_owner(call.from_user.id): return
    await call.message.edit_text("🟢 البوت يعمل.\n\nوضع الصيانة غير مفعل في هذا الإصدار.", reply_markup=admin_menu())

async def run():
    await init_db(engine)
    bot = Bot(settings.bot_token)
    print("Bot started.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()
