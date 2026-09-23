from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, func
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default='')
    points: Mapped[int] = mapped_column(Integer, default=0)
    referred_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Campaign(Base):
    __tablename__ = 'campaigns'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    chat_id: Mapped[int] = mapped_column(Integer)
    chat_title: Mapped[str] = mapped_column(String(255), default='Channel')
    invite_link: Mapped[str] = mapped_column(String(500))
    reward: Mapped[int] = mapped_column(Integer)
    budget: Mapped[int] = mapped_column(Integer)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Completion(Base):
    __tablename__ = 'completions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey('campaigns.id'))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    reward: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('campaign_id', 'user_id', name='uq_campaign_user'),)


class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'))
    amount: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(String(500), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default='')


class Database:
    def __init__(self, url: str):
        if url.startswith('sqlite'):
            Path('data').mkdir(exist_ok=True)
        self.engine = create_async_engine(url, future=True)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()

    async def get_user(self, user_id: int):
        async with self.session() as s:
            return await s.get(User, user_id)

    async def ensure_user(self, tg_user, referrer_id: int | None = None):
        async with self.session() as s:
            user = await s.get(User, tg_user.id)
            if user:
                user.username = tg_user.username
                user.full_name = tg_user.full_name or ''
                await s.commit()
                return user, False
            valid_ref = referrer_id if referrer_id and referrer_id != tg_user.id else None
            if valid_ref and not await s.get(User, valid_ref):
                valid_ref = None
            user = User(id=tg_user.id, username=tg_user.username, full_name=tg_user.full_name or '', referred_by=valid_ref)
            s.add(user)
            if valid_ref:
                ref = await s.get(User, valid_ref)
                ref.points += 10
                s.add(Transaction(user_id=valid_ref, amount=10, kind='referral', note=f'New referral: {tg_user.id}'))
                user.referral_rewarded = True
            await s.commit()
            return user, True

    async def add_points(self, user_id: int, amount: int, kind: str, note: str):
        async with self.session() as s:
            user = await s.get(User, user_id)
            if not user:
                return False
            user.points += amount
            s.add(Transaction(user_id=user_id, amount=amount, kind=kind, note=note))
            await s.commit()
            return True

    async def list_active_campaigns(self, limit=20):
        async with self.session() as s:
            result = await s.execute(select(Campaign).where(Campaign.active.is_(True)).order_by(Campaign.id.desc()).limit(limit))
            return result.scalars().all()

    async def create_campaign(self, owner_id, chat_id, title, invite_link, reward, budget):
        async with self.session() as s:
            owner = await s.get(User, owner_id)
            if not owner or owner.points < budget:
                return None, 'insufficient'
            owner.points -= budget
            campaign = Campaign(owner_id=owner_id, chat_id=chat_id, chat_title=title, invite_link=invite_link, reward=reward, budget=budget)
            s.add(campaign)
            s.add(Transaction(user_id=owner_id, amount=-budget, kind='campaign_fund', note=f'Campaign: {title}'))
            await s.commit()
            await s.refresh(campaign)
            return campaign, None

    async def claim(self, campaign_id: int, user_id: int):
        from sqlalchemy.exc import IntegrityError
        async with self.session() as s:
            campaign = await s.get(Campaign, campaign_id)
            user = await s.get(User, user_id)
            if not campaign or not user:
                return 'missing', 0
            if not campaign.active:
                return 'closed', 0
            if campaign.owner_id == user_id:
                return 'owner', 0
            if campaign.completed >= campaign.budget // campaign.reward:
                campaign.active = False
                await s.commit()
                return 'closed', 0
            completion = Completion(campaign_id=campaign_id, user_id=user_id, reward=campaign.reward)
            s.add(completion)
            try:
                await s.flush()
            except IntegrityError:
                await s.rollback()
                return 'duplicate', 0
            user.points += campaign.reward
            campaign.completed += 1
            if campaign.completed >= campaign.budget // campaign.reward:
                campaign.active = False
            s.add(Transaction(user_id=user_id, amount=campaign.reward, kind='task_reward', note=f'Campaign #{campaign.id}'))
            await s.commit()
            return 'ok', campaign.reward

    async def transactions(self, user_id, limit=10):
        async with self.session() as s:
            r = await s.execute(select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.id.desc()).limit(limit))
            return r.scalars().all()

    async def my_campaigns(self, user_id, limit=10):
        async with self.session() as s:
            r = await s.execute(select(Campaign).where(Campaign.owner_id == user_id).order_by(Campaign.id.desc()).limit(limit))
            return r.scalars().all()

    async def stats(self):
        async with self.session() as s:
            users = await s.scalar(select(func.count(User.id))) or 0
            active = await s.scalar(select(func.count(Campaign.id)).where(Campaign.active.is_(True))) or 0
            completions = await s.scalar(select(func.count(Completion.id))) or 0
            points = await s.scalar(select(func.coalesce(func.sum(User.points), 0))) or 0
            return users, active, completions, points

    async def set_maintenance(self, enabled: bool):
        async with self.session() as s:
            setting = await s.get(Setting, 'maintenance')
            if not setting:
                setting = Setting(key='maintenance', value='1' if enabled else '0')
                s.add(setting)
            else:
                setting.value = '1' if enabled else '0'
            await s.commit()

    async def maintenance(self):
        async with self.session() as s:
            setting = await s.get(Setting, 'maintenance')
            return bool(setting and setting.value == '1')

    async def all_user_ids(self):
        async with self.session() as s:
            r = await s.execute(select(User.id).where(User.banned.is_(False)))
            return [x[0] for x in r.all()]

    async def set_banned(self, user_id, banned):
        async with self.session() as s:
            u = await s.get(User, user_id)
            if not u:
                return False
            u.banned = banned
            await s.commit()
            return True
