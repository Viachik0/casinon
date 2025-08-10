import aiosqlite
import datetime
from typing import Optional, Dict, Any


class Database:
    def __init__(self, path: str, starting_balance: int):
        self.path = path
        self.starting_balance = starting_balance

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    balance INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS active_rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    bet INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Optional performance / locking mitigation
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.commit()

    # ---------------- Users ----------------
    async def get_or_create_user(self, tg_id: int, username: Optional[str]) -> Dict[str, Any]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            if row:
                if username and username != row["username"]:
                    await db.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
                    await db.commit()
                    cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
                    row = await cur.fetchone()
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
        """
        Adjust balance and return new balance.
        (Fixed: added row_factory so row['balance'] works; prevents TypeError.)
        """
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (delta, tg_id))
            await db.commit()
            cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            if not row:
                # Edge case: user disappeared (shouldn't happen) -> recreate
                now = datetime.datetime.utcnow().isoformat()
                await db.execute(
                    "INSERT INTO users (tg_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                    (tg_id, None, self.starting_balance, now)
                )
                await db.commit()
                return self.starting_balance
            return int(row["balance"])

    # ---------------- Bets history ----------------
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

    # ---------------- Active round lifecycle ----------------
    async def start_active_round(self, tg_id: int, game: str, bet: int, state_json: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")
                cur = await db.execute("SELECT id FROM active_rounds WHERE tg_id = ?", (tg_id,))
                if await cur.fetchone():
                    await db.rollback()
                    return False

                cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
                user = await cur.fetchone()
                if not user or user["balance"] < bet:
                    await db.rollback()
                    return False

                if bet > 0:
                    await db.execute("UPDATE users SET balance = balance - ? WHERE tg_id = ?", (bet, tg_id))

                now = datetime.datetime.utcnow().isoformat()
                await db.execute(
                    """INSERT INTO active_rounds (tg_id, game, bet, state_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (tg_id, game, bet, state_json, now, now)
                )
                await db.commit()
                return True
            except Exception:
                await db.rollback()
                return False

    async def adjust_active_round_bet(self, tg_id: int, delta: int) -> bool:
        if delta <= 0:
            return False
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")
                cur = await db.execute("SELECT * FROM active_rounds WHERE tg_id = ?", (tg_id,))
                ar = await cur.fetchone()
                if not ar:
                    await db.rollback()
                    return False
                cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
                user = await cur.fetchone()
                if not user or user["balance"] < delta:
                    await db.rollback()
                    return False
                await db.execute("UPDATE users SET balance = balance - ? WHERE tg_id = ?", (delta, tg_id))
                await db.execute(
                    "UPDATE active_rounds SET bet = bet + ?, updated_at = ? WHERE tg_id = ?",
                    (delta, datetime.datetime.utcnow().isoformat(), tg_id)
                )
                await db.commit()
                return True
            except Exception:
                await db.rollback()
                return False

    async def get_active_round(self, tg_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM active_rounds WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_active_round(self, tg_id: int, state_json: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE active_rounds SET state_json = ?, updated_at = ? WHERE tg_id = ?",
                (state_json, datetime.datetime.utcnow().isoformat(), tg_id)
            )
            await db.commit()

    async def resolve_active_round(self, tg_id: int, result: str, total_payout: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")
                cur = await db.execute("SELECT * FROM active_rounds WHERE tg_id = ?", (tg_id,))
                active = await cur.fetchone()
                if not active:
                    await db.rollback()
                    return
                locked = active["bet"]
                await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (total_payout, tg_id))
                cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
                user_row = await cur.fetchone()
                if user_row:
                    net_delta = total_payout - locked
                    now = datetime.datetime.utcnow().isoformat()
                    await db.execute(
                        "INSERT INTO bets (user_id, game, amount, result, delta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (user_row["id"], active["game"], locked, result, net_delta, now)
                    )
                await db.execute("DELETE FROM active_rounds WHERE tg_id = ?", (tg_id,))
                await db.commit()
            except Exception:
                await db.rollback()

    async def delete_active_round(self, tg_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM active_rounds WHERE tg_id = ?", (tg_id,))
            await db.commit()