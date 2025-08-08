import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    db_path: str
    starting_balance: int
    daily_bonus_amount: int
    daily_bonus_cooldown_hours: int
    min_bet: int
    max_bet: int

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN (or BOT_TOKEN) is not set. Create a .env file based on .env.example."
        )

    db_path = os.getenv("DATABASE_PATH") or os.getenv("DB_PATH") or "data/casino.db"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        bot_token=token,
        db_path=db_path,
        starting_balance=_get_int("STARTING_BALANCE", 1000),
        daily_bonus_amount=_get_int("DAILY_BONUS_AMOUNT", 500),
        daily_bonus_cooldown_hours=_get_int("DAILY_BONUS_COOLDOWN_HOURS", 24),
        min_bet=_get_int("MIN_BET", 10),
        max_bet=_get_int("MAX_BET", 100000),
    )
