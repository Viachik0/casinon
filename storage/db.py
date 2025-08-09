import datetime
from typing import Any, Dict, List, Optional

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
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS active_rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE,
                    game TEXT NOT NULL,
                    bet INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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

    async def start_active_round(self, tg_id: int, game: str, bet: int, state_json: str) -> bool:
        """
        Atomically start a new active round by deducting bet from balance and creating round.
        Returns True if successful, False if insufficient funds or concurrent round exists.
        """
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN EXCLUSIVE")
                
                # Check if user has active round
                cur = await db.execute("SELECT id FROM active_rounds WHERE tg_id = ?", (tg_id,))
                if await cur.fetchone():
                    await db.rollback()
                    return False
                
                # Check user balance
                cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
                user = await cur.fetchone()
                if not user or user["balance"] < bet:
                    await db.rollback()
                    return False
                
                # Deduct bet from balance
                await db.execute("UPDATE users SET balance = balance - ? WHERE tg_id = ?", (bet, tg_id))
                
                # Create active round
                now = datetime.datetime.utcnow().isoformat()
                await db.execute(
                    "INSERT INTO active_rounds (tg_id, game, bet, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (tg_id, game, bet, state_json, now, now)
                )
                
                await db.commit()
                return True
                
            except Exception:
                await db.rollback()
                return False

    async def get_active_round(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """Get active round for user, if any."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM active_rounds WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_active_round(self, tg_id: int, state_json: str) -> bool:
        """Update the state of an active round."""
        async with aiosqlite.connect(self.path) as db:
            now = datetime.datetime.utcnow().isoformat()
            cur = await db.execute(
                "UPDATE active_rounds SET state_json = ?, updated_at = ? WHERE tg_id = ?",
                (state_json, now, tg_id)
            )
            await db.commit()
            return cur.rowcount > 0

    async def resolve_active_round(self, tg_id: int, result: str, payout_delta: int) -> bool:
        """
        Resolve active round by paying out and recording bet.
        payout_delta: amount to add to balance (0 for loss, bet for push, 2*bet for win)
        """
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN EXCLUSIVE")
                
                # Get active round
                cur = await db.execute("SELECT * FROM active_rounds WHERE tg_id = ?", (tg_id,))
                round_data = await cur.fetchone()
                if not round_data:
                    await db.rollback()
                    return False
                
                round_dict = dict(round_data)
                bet = round_dict["bet"]
                game = round_dict["game"]
                
                # Calculate net delta from pre-round perspective
                # Loss: net = -bet (already deducted, payout_delta = 0)
                # Push: net = 0 (already deducted, payout_delta = bet) 
                # Win: net = +bet (already deducted, payout_delta = 2*bet)
                net_delta = payout_delta - bet
                
                # Add payout to balance
                if payout_delta > 0:
                    await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (payout_delta, tg_id))
                
                # Record bet with net delta
                await self._record_bet_internal(db, tg_id, game, bet, result, net_delta)
                
                # Remove active round
                await db.execute("DELETE FROM active_rounds WHERE tg_id = ?", (tg_id,))
                
                await db.commit()
                return True
                
            except Exception:
                await db.rollback()
                return False

    async def _record_bet_internal(self, db, tg_id: int, game: str, amount: int, result: str, delta: int) -> None:
        """Internal method to record bet within existing transaction."""
        cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        user = await cur.fetchone()
        if not user:
            return
        now = datetime.datetime.utcnow().isoformat()
        await db.execute(
            "INSERT INTO bets (user_id, game, amount, result, delta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (int(user["id"]), game, amount, result, delta, now),
        )

    async def get_balance_stats(self, tg_id: int) -> Dict[str, Any]:
        """Get balance and profit statistics for user."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get current balance
            cur = await db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
            user = await cur.fetchone()
            if not user:
                return {"balance": 0, "total_profit": 0, "wins": 0, "losses": 0, "pushes": 0}
            
            balance = user["balance"]
            
            # Get bet statistics
            cur = await db.execute("""
                SELECT 
                    COALESCE(SUM(delta), 0) as total_profit,
                    COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                    COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses,
                    COALESCE(SUM(CASE WHEN result = 'push' THEN 1 ELSE 0 END), 0) as pushes
                FROM bets b
                JOIN users u ON b.user_id = u.id  
                WHERE u.tg_id = ?
            """, (tg_id,))
            
            stats = await cur.fetchone()
            return {
                "balance": balance,
                "total_profit": stats["total_profit"] if stats else 0,
                "wins": stats["wins"] if stats else 0,
                "losses": stats["losses"] if stats else 0,
                "pushes": stats["pushes"] if stats else 0,
            }

    async def get_bet_history(self, tg_id: int, limit: int = 10, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bet history for user with optional filters."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            
            where_clause = "WHERE u.tg_id = ?"
            params = [tg_id]
            
            if filter_type == "today":
                where_clause += " AND DATE(b.created_at) = DATE('now')"
            elif filter_type == "week":
                where_clause += " AND DATE(b.created_at) >= DATE('now', '-7 days')"
            elif filter_type == "month":
                where_clause += " AND DATE(b.created_at) >= DATE('now', '-30 days')"
            
            cur = await db.execute(f"""
                SELECT b.created_at, b.game, b.amount, b.result, b.delta
                FROM bets b
                JOIN users u ON b.user_id = u.id
                {where_clause}
                ORDER BY b.created_at DESC
                LIMIT ?
            """, params + [limit])
            
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
