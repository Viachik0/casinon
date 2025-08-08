import datetime
from typing import Any, Dict, Optional

import aiosqlite


class Database:
    def __init__(self, path: str, starting_balance: int = 1000):
        self.path = path
        self.starting_balance = starting_balance

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE,
                    username TEXT,
                    balance INTEGER DEFAULT 1000,
                    created_at TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game TEXT,
                    amount INTEGER,
                    result TEXT,
                    delta INTEGER,
                    created_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            await db.commit()

    async def get_or_create_user(self, tg_id: int, username: Optional[str]) -> Dict[str, Any]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            if row:
                return dict(row)

            now = datetime.datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO users (tg_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                (tg_id, username, self.starting_balance, now),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            return dict(row)

    async def update_balance(self, tg_id: int, delta: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (delta, tg_id))
            await db.commit()
            cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            return int(row["balance"])

    async def record_bet(self, tg_id: int, game: str, amount: int, result: str, delta: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
            user = await cur.fetchone()
            if not user:
                return
            now = datetime.datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO bets (user_id, game, amount, result, delta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (int(user["id"]), game, amount, result, delta, now),
            )
            await db.commit()
