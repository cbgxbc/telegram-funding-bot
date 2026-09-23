import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _ids(value: str) -> set[int]:
    out = set()
    for part in (value or '').split(','):
        part = part.strip()
        if part:
            out.add(int(part))
    return out


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_id: int
    admin_ids: set[int]
    database_url: str
    bot_username: str


def load_settings() -> Settings:
    token = os.getenv('BOT_TOKEN', '').strip()
    owner = os.getenv('OWNER_ID', '').strip()
    if not token:
        raise RuntimeError('BOT_TOKEN is missing. Put it in .env or hosting environment variables.')
    if not owner.isdigit():
        raise RuntimeError('OWNER_ID must be a numeric Telegram user ID.')
    admins = _ids(os.getenv('ADMIN_IDS', ''))
    admins.add(int(owner))
    db = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./data/bot.db').strip()
    username = os.getenv('BOT_USERNAME', '').strip().lstrip('@')
    return Settings(token, int(owner), admins, db, username)
