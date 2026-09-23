import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_id: int
    database_url: str
    bot_username: str

def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    owner = os.getenv("OWNER_ID", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Put it in .env")
    if not owner.isdigit():
        raise RuntimeError("OWNER_ID must be a numeric Telegram user ID.")
    return Settings(
        bot_token=token,
        owner_id=int(owner),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db"),
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@"),
    )
