"""Database operations for the casino bot."""
import aiosqlite
import time
from typing import Optional, Tuple
from config import config


class Database:
    """Database manager for user data and balances."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
    
    async def init_db(self) -> None:
        """Initialize the database and create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL,
                    last_bonus_at INTEGER NULL
                )
            """)
            await db.commit()
    
    async def get_or_create_user(self, user_id: int) -> Tuple[int, Optional[int]]:
        """
        Get user or create if doesn't exist.
        Returns (balance, last_bonus_at).
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Try to get existing user
            cursor = await db.execute(
                "SELECT balance, last_bonus_at FROM users WHERE id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return row[0], row[1]
            
            # Create new user with starting balance
            await db.execute(
                "INSERT INTO users (id, balance, last_bonus_at) VALUES (?, ?, NULL)",
                (user_id, config.STARTING_BALANCE)
            )
            await db.commit()
            return config.STARTING_BALANCE, None
    
    async def get_balance(self, user_id: int) -> int:
        """Get user's current balance."""
        balance, _ = await self.get_or_create_user(user_id)
        return balance
    
    async def add_balance(self, user_id: int, amount: int) -> int:
        """
        Add amount to user's balance (can be negative for bets).
        Returns new balance.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Ensure user exists
            await self.get_or_create_user(user_id)
            
            # Update balance
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE id = ?",
                (amount, user_id)
            )
            await db.commit()
            
            # Return new balance
            cursor = await db.execute(
                "SELECT balance FROM users WHERE id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def can_claim_bonus(self, user_id: int) -> bool:
        """Check if user can claim daily bonus."""
        _, last_bonus_at = await self.get_or_create_user(user_id)
        
        if last_bonus_at is None:
            return True
        
        current_time = int(time.time())
        cooldown_seconds = config.DAILY_BONUS_COOLDOWN_HOURS * 3600
        
        return current_time - last_bonus_at >= cooldown_seconds
    
    async def claim_bonus(self, user_id: int) -> Tuple[bool, int]:
        """
        Claim daily bonus if available.
        Returns (success, new_balance).
        """
        if not await self.can_claim_bonus(user_id):
            balance = await self.get_balance(user_id)
            return False, balance
        
        async with aiosqlite.connect(self.db_path) as db:
            current_time = int(time.time())
            
            # Update balance and last_bonus_at
            await db.execute(
                "UPDATE users SET balance = balance + ?, last_bonus_at = ? WHERE id = ?",
                (config.DAILY_BONUS_AMOUNT, current_time, user_id)
            )
            await db.commit()
            
            # Get new balance
            cursor = await db.execute(
                "SELECT balance FROM users WHERE id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            new_balance = row[0] if row else 0
            
            return True, new_balance
    
    async def get_bonus_cooldown_remaining(self, user_id: int) -> int:
        """Get remaining cooldown time for bonus in seconds."""
        _, last_bonus_at = await self.get_or_create_user(user_id)
        
        if last_bonus_at is None:
            return 0
        
        current_time = int(time.time())
        cooldown_seconds = config.DAILY_BONUS_COOLDOWN_HOURS * 3600
        elapsed = current_time - last_bonus_at
        
        return max(0, cooldown_seconds - elapsed)


# Global database instance
db = Database()