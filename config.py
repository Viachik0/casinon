"""Configuration management for the casino bot."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for the casino bot."""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Economy Configuration
    STARTING_BALANCE: int = int(os.getenv("STARTING_BALANCE", "1000"))
    DAILY_BONUS_AMOUNT: int = int(os.getenv("DAILY_BONUS_AMOUNT", "500"))
    DAILY_BONUS_COOLDOWN_HOURS: int = int(os.getenv("DAILY_BONUS_COOLDOWN_HOURS", "24"))
    MIN_BET: int = int(os.getenv("MIN_BET", "10"))
    MAX_BET: int = int(os.getenv("MAX_BET", "100000"))
    
    # Database Configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "casino.db")
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration values."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if cls.MIN_BET <= 0:
            raise ValueError("MIN_BET must be positive")
        
        if cls.MAX_BET <= cls.MIN_BET:
            raise ValueError("MAX_BET must be greater than MIN_BET")
        
        if cls.STARTING_BALANCE <= 0:
            raise ValueError("STARTING_BALANCE must be positive")
        
        if cls.DAILY_BONUS_AMOUNT <= 0:
            raise ValueError("DAILY_BONUS_AMOUNT must be positive")
        
        if cls.DAILY_BONUS_COOLDOWN_HOURS <= 0:
            raise ValueError("DAILY_BONUS_COOLDOWN_HOURS must be positive")


# Global config instance
config = Config()