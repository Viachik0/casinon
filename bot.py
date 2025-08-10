# NOTE: This is your existing bot.py with ONLY:
# - safe_edit helper added
# - all cb.message.edit_text(...) replaced by await safe_edit(...)
# Nothing else altered intentionally.

import asyncio
import json
import random
from typing import Set

import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)
from aiogram.exceptions import TelegramBadRequest

from config import get_settings
from storage.db import Database
from games import blackjack
from games import roulette

settings = get_settings()
db = Database(settings.db_path, starting_balance=settings.starting_balance)
router = Router()

# =========================================================
# admin kostil
# =========================================================

import aiosqlite  # if not already

ADMIN_IDS = {945409731}  # your Telegram numeric ID(s)

def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS

@router.message(Command("me"))
async def cmd_me(msg: Message):
    await msg.reply(f"Your Telegram ID: {msg.from_user.id}")

# /give <tg_id|@username> <amount>
@router.message(Command("give"))
async def cmd_give(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Not authorized.")
    parts = msg.text.split()
    if len(parts) != 3:
        return await msg.reply("Usage: /give <tg_id|@username> <amount>")
    target, amt_str = parts[1], parts[2]
    if not amt_str.isdigit(): return await msg.reply("Amount must be integer.")
    amount = int(amt_str)
    if amount <= 0: return await msg.reply("Amount must be > 0.")
    tg_id, username = await _get_user_id_and_username(target)
    if tg_id is None: return await msg.reply("User not found.")
    await db.get_or_create_user(tg_id, username)
    new_balance = await db.update_balance(tg_id, amount)
    await msg.reply(f"✅ Added {amount}. New balance: {new_balance}")

# /setbal <tg_id|@username> <amount>
@router.message(Command("setbal"))
async def cmd_setbal(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Not authorized.")
    parts = msg.text.split()
    if len(parts) != 3:
        return await msg.reply("Usage: /setbal <tg_id|@username> <amount>")
    target, amt_str = parts[1], parts[2]
    if not amt_str.isdigit(): return await msg.reply("Amount must be integer.")
    amount = int(amt_str)
    if amount < 0: return await msg.reply("Amount must be >= 0.")
    tg_id, username = await _get_user_id_and_username(target)
    if tg_id is None: return await msg.reply("User not found.")
    await db.get_or_create_user(tg_id, username)
    # Get current
    import aiosqlite
    async with aiosqlite.connect(db.path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        cur_bal = row["balance"] if row else 0
    delta = amount - cur_bal
    await db.update_balance(tg_id, delta)
    await msg.reply(f"✅ Set balance to {amount} (delta {delta:+}).")

# /user <tg_id|@username>
@router.message(Command("user"))
async def cmd_user(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Not authorized.")
    parts = msg.text.split()
    if len(parts) != 2:
        return await msg.reply("Usage: /user <tg_id|@username>")
    target = parts[1]
    tg_id, username = await _get_user_id_and_username(target)
    if tg_id is None: return await msg.reply("User not found.")
    urow = await db.get_or_create_user(tg_id, username)
    active = await db.get_active_round(tg_id)
    import aiosqlite
    async with aiosqlite.connect(db.path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("""
            SELECT game, amount, result, delta, created_at
            FROM bets b
            JOIN users u ON u.id = b.user_id
            WHERE u.tg_id = ?
            ORDER BY b.id DESC LIMIT 5
        """, (tg_id,))
        bets = await cur.fetchall()
    bet_lines = [f"{b['game']} amt={b['amount']} res={b['result']} Δ={b['delta']}" for b in bets] or ["(no bets)"]
    await msg.reply(
        f"👤 {tg_id} ({urow.get('username')})\n"
        f"Balance: {urow['balance']}\n"
        f"Active: {active['game']} bet={active['bet']}" if active else "Active: None" + "\n"
        f"Recent:\n" + "\n".join(bet_lines)
    )

# /top (optional limit)
@router.message(Command("top"))
async def cmd_top(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("❌ Not authorized.")
    parts = msg.text.split()
    limit = 10
    if len(parts) > 1 and parts[1].isdigit():
        limit = min(50, max(1, int(parts[1])))
    import aiosqlite
    async with aiosqlite.connect(db.path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT tg_id, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
    lines = [f"{i+1}. {r['username'] or r['tg_id']}: {r['balance']}" for i, r in enumerate(rows)]
    await msg.reply("🏆 Top Balances\n" + "\n".join(lines))

async def _get_user_id_and_username(identifier: str):
    identifier = identifier.strip()
    import aiosqlite
    async with aiosqlite.connect(db.path) as conn:
        conn.row_factory = aiosqlite.Row
        if identifier.startswith("@"):
            uname = identifier[1:]
            cur = await conn.execute("SELECT tg_id, username FROM users WHERE username = ?", (uname,))
            row = await cur.fetchone()
            return (row["tg_id"], row["username"]) if row else (None, None)
        if identifier.isdigit():
            tg_id = int(identifier)
            cur = await conn.execute("SELECT tg_id, username FROM users WHERE tg_id = ?", (tg_id,))
            row = await cur.fetchone()
            return (tg_id, row["username"] if row else None)
    return (None, None)

# ---------- safe_edit helper (prevents 'message is not modified') ----------
async def safe_edit(message, text: str, **kwargs):
    """
    Edit only if content or markup differ. Swallows the specific
    'message is not modified' TelegramBadRequest.
    """
    try:
        same_text = getattr(message, "text", None) == text
        same_markup = False
        new_markup = kwargs.get("reply_markup")
        old_markup = getattr(message, "reply_markup", None)
        if same_text:
            # Try structural compare for markup if both exist / both None
            if not new_markup and not old_markup:
                same_markup = True
            elif new_markup and old_markup:
                try:
                    same_markup = new_markup.to_python() == old_markup.to_python()
                except Exception:
                    same_markup = str(new_markup) == str(old_markup)
        if same_text and same_markup:
            return
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise

# =========================================================
# Navigation & Shared
# =========================================================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Blackjack", callback_data="game:blackjack")],
        [InlineKeyboardButton(text="🎡 Roulette", callback_data="game:roulette")],
    ])

def back_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")]
    ])

def build_main_menu_text(balance: int) -> str:
    return (
        "🎰 <b>Casinon</b>\n"
        f"💰 <b>Balance:</b> {balance} credits\n\n"
        "🃏 <b>Blackjack</b>\n"
        "Get cards totaling 21 or less, beat dealer’s hand. Split / Double / Surrender available.\n\n"
        "🎡 <b>Roulette</b>\n"
        "Bet on numbers, colors, ranges, dozens — then spin the wheel.\n\n"
        "<b>Commands</b>:\n"
        "/balance – view balance\n"
        "/cancel – cancel active round (refund)\n"
        "/forcecancel – force remove round (no refund)\n\n"
        "Select a game:"
    )

@router.message(Command("start"))
async def cmd_start(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(build_main_menu_text(user['balance']), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

@router.message(Command("balance"))
async def cmd_balance(msg: Message):
    user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(f"💰 Balance: {user['balance']} credits", reply_markup=back_menu_kb())

@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    await safe_edit(cb.message, build_main_menu_text(user['balance']), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    await cb.answer()

# Cancel utilities
async def _cancel_active_round(tg_id: int, refund: bool = True) -> bool:
    active = await db.get_active_round(tg_id)
    if not active:
        return False
    bet = active["bet"]
    await db.delete_active_round(tg_id)
    if refund and bet:
        await db.update_balance(tg_id, bet)
    return True

@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    if await _cancel_active_round(msg.from_user.id, refund=True):
        user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
        await msg.answer(f"✅ Round canceled. Refunded. Balance: {user['balance']}")
    else:
        await msg.answer("ℹ️ No active round.")

@router.message(Command("forcecancel"))
async def cmd_forcecancel(msg: Message):
    if await _cancel_active_round(msg.from_user.id, refund=False):
        user = await db.get_or_create_user(msg.from_user.id, msg.from_user.username)
        await msg.answer(f"🛑 Force-canceled. Balance: {user['balance']}")
    else:
        await msg.answer("ℹ️ No active round.")

# =========================================================
# Blackjack (Bet Builder & Game)
# =========================================================

def bj_bet_builder_kb(current: int, balance: int, min_bet: int, max_bet: int) -> InlineKeyboardMarkup:
    current = max(0, min(current, balance, max_bet))
    row1 = [
        InlineKeyboardButton(text="+1", callback_data=f"bjbet:add:1:{current}"),
        InlineKeyboardButton(text="+5", callback_data=f"bjbet:add:5:{current}"),
        InlineKeyboardButton(text="+10", callback_data=f"bjbet:add:10:{current}"),
    ]
    row2 = [
        InlineKeyboardButton(text="+25", callback_data=f"bjbet:add:25:{current}"),
        InlineKeyboardButton(text="+50", callback_data=f"bjbet:add:50:{current}"),
        InlineKeyboardButton(text="+100", callback_data=f"bjbet:add:100:{current}"),
    ]
    row3 = [
        InlineKeyboardButton(text="x2", callback_data=f"bjbet:mul:2:{current}"),
        InlineKeyboardButton(text="½", callback_data=f"bjbet:half::{current}"),
        InlineKeyboardButton(text="Max", callback_data=f"bjbet:max::{current}"),
        InlineKeyboardButton(text="Clear", callback_data=f"bjbet:clear::{current}"),
    ]
    confirm_ok = current >= min_bet
    row4 = [
        InlineKeyboardButton(
            text=f"✅ Confirm {current}" if confirm_ok else f"❌ Min {min_bet}",
            callback_data=f"bjbet:confirm:{current}" if confirm_ok else "bjbet:noop"
        )
    ]
    row5 = [InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3, row4, row5])

async def _bj_show_bet_builder(cb: CallbackQuery, current: int = None):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if current is None:
        current = settings.min_bet
    current = min(current, user["balance"], settings.max_bet)
    await safe_edit(
        cb.message,
        "🃏 <b>Blackjack Bet Setup</b>\n"
        f"💰 Balance: {user['balance']} credits\n"
        f"🎯 Current Bet: {current}\n\n"
        "Add chips or adjust, then Confirm to start.",
        reply_markup=bj_bet_builder_kb(current, user["balance"], settings.min_bet, settings.max_bet),
        parse_mode=ParseMode.HTML
    )

def build_blackjack_actions_kb(can_double: bool, can_split: bool) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text="🃏 Hit", callback_data="blackjack:hit"),
        InlineKeyboardButton(text="🛑 Stand", callback_data="blackjack:stand"),
    ]
    if can_double:
        row.append(InlineKeyboardButton(text="💰 Double", callback_data="blackjack:double"))
    rows = [row]
    if can_split:
        rows.append([InlineKeyboardButton(text="🔀 Split", callback_data="blackjack:split")])
    rows.append([InlineKeyboardButton(text="⚠️ Surrender", callback_data="blackjack:surrender")])
    rows.append([InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_blackjack_result_kb(original_bet: int, balance: int) -> InlineKeyboardMarkup:
    rows = []
    if original_bet <= balance:
        rows.append([InlineKeyboardButton(text=f"🔄 Same Bet ({original_bet})", callback_data=f"blackjack:same:{original_bet}")])
    rows.append([InlineKeyboardButton(text="🎰 New Blackjack", callback_data="game:blackjack")])
    rows.append([InlineKeyboardButton(text="📋 Menu", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _overall_flag(flags: Set[str]) -> str:
    if "win" in flags and "loss" not in flags:
        return "win"
    if "loss" in flags and "win" not in flags:
        return "loss"
    if flags == {"push"}:
        return "push"
    return "mixed"

async def _save_bj_state(user_id: int, state_obj: blackjack.BlackjackState):
    await db.update_active_round(user_id, state_obj.to_json())

def _decorate_hand_line(idx: int, hand: list[str], state=None) -> str:
    from games.blackjack import calculate_hand_value
    total = calculate_hand_value(hand)
    flags = []
    if state:
        if state["doubled"][idx]:
            flags.append("💰")
        if state["surrendered"][idx]:
            flags.append("⚠️")
    flag_txt = " " + "".join(flags) if flags else ""
    return f"Hand {idx+1}:{flag_txt} {' '.join(hand)} (total {total}, bet {state['bets'][idx]})"

async def _resolve_bj(cb: CallbackQuery, state_obj: blackjack.BlackjackState):
    eval_res = state_obj.evaluate()
    total_payout = sum(p for (_t, p, _m) in eval_res["results"])
    flags = {t for (t, _p, _m) in eval_res["results"]}
    overall = _overall_flag(flags)
    await db.resolve_active_round(cb.from_user.id, overall, total_payout)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    final_txt = "🃏 <b>Blackjack — Round Complete</b>\n"
    for i, (hand, (_t, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
        final_txt += f"\n{_decorate_hand_line(i, hand, state_obj.state)}\n   ➜ {msg} (payout {payout})"
    from games.blackjack import format_hand_with_total
    final_txt += f"\n\n🀫 Dealer: {format_hand_with_total(state_obj.state['dealer'])}\n"
    final_txt += f"\n💰 Balance: {user['balance']} credits"
    await safe_edit(
        cb.message,
        final_txt,
        reply_markup=build_blackjack_result_kb(state_obj.state["original_bet"], user["balance"]),
        parse_mode=ParseMode.HTML
    )

async def _bj_finish(cb: CallbackQuery, state_obj: blackjack.BlackjackState):
    state_obj.reveal_dealer()
    await _save_bj_state(cb.from_user.id, state_obj)
    inter_lines = []
    for i, h in enumerate(state_obj.state["player_hands"]):
        inter_lines.append(_decorate_hand_line(i, h, state_obj.state))
    inter = "🃏 <b>Blackjack</b>\n" + "\n".join(inter_lines) + "\n\n👀 Dealer reveals..."
    await safe_edit(cb.message, inter, parse_mode=ParseMode.HTML)
    await cb.answer()
    await asyncio.sleep(0.6)
    while state_obj.dealer_play_step():
        await _save_bj_state(cb.from_user.id, state_obj)
        draw_txt = "🃏 <b>Blackjack</b>\n" + "\n".join(inter_lines) + "\n\n🀫 Dealer draws..."
        await safe_edit(cb.message, draw_txt, parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.45)
    await _resolve_bj(cb, state_obj)

async def _start_blackjack(cb: CallbackQuery, bet: int):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if bet < settings.min_bet or bet > settings.max_bet or bet > user["balance"]:
        return await cb.answer("Invalid bet.", show_alert=True)
    state_obj = blackjack.BlackjackState(bet)
    if not await db.start_active_round(cb.from_user.id, "blackjack", bet, state_obj.to_json()):
        active = await db.get_active_round(cb.from_user.id)
        if active and active["game"] == "blackjack":
            await _resume_blackjack(cb, active)
            return
        return await cb.answer("Could not start.", show_alert=True)
    if state_obj.is_blackjack(state_obj.state["player_hands"][0]) or state_obj.is_blackjack(state_obj.state["dealer"]):
        await _bj_finish(cb, state_obj)
        return
    lines = []
    for i, h in enumerate(state_obj.state["player_hands"]):
        lines.append(_decorate_hand_line(i, h, state_obj.state))
    txt = "🃏 <b>Blackjack</b>\n" + "\n".join(lines) + f"\n\n🀫 Dealer: {state_obj.state['dealer_visible'][0]} 🂠"
    await safe_edit(
        cb.message,
        txt,
        reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Blackjack started!")

async def _resume_blackjack(cb: CallbackQuery, active_row: dict):
    state_obj = blackjack.BlackjackState.from_json(active_row["state_json"])
    if state_obj.state["current_hand"] >= len(state_obj.state["player_hands"]):
        await _bj_finish(cb, state_obj)
        return
    lines = []
    for i, h in enumerate(state_obj.state["player_hands"]):
        marker = "👉 " if i == state_obj.state["current_hand"] else ""
        lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
    dealer_info = " ".join(state_obj.state["dealer_visible"])
    txt = "🃏 <b>Blackjack</b>\n" + "\n".join(lines) + f"\n\n🀫 Dealer: {dealer_info}"
    await safe_edit(
        cb.message,
        txt,
        reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Resumed.")

@router.callback_query(F.data == "game:blackjack")
async def blackjack_entry(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if active and active["game"] == "blackjack":
        await _resume_blackjack(cb, active)
        return
    await _bj_show_bet_builder(cb)

@router.callback_query(F.data.func(lambda d: d.startswith("bjbet:")))
async def blackjack_bet_builder(cb: CallbackQuery):
    parts = cb.data.split(":")
    action = parts[1]
    if action == "noop":
        return await cb.answer()
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    current_raw = parts[-1] if parts[-1] else str(settings.min_bet)
    try:
        current = int(current_raw)
    except:
        current = settings.min_bet
    min_bet = settings.min_bet
    max_bet = settings.max_bet

    if action == "add":
        current += int(parts[2])
    elif action == "mul":
        current *= int(parts[2])
    elif action == "half":
        current //= 2
    elif action == "max":
        current = min(user["balance"], max_bet)
    elif action == "clear":
        current = 0
    elif action == "confirm":
        await _start_blackjack(cb, current)
        return

    current = max(0, min(current, user["balance"], max_bet))
    await _bj_show_bet_builder(cb, current)

@router.callback_query(F.data.func(lambda d: d.startswith("blackjack:same:")))
async def blackjack_same(cb: CallbackQuery):
    try:
        bet = int(cb.data.split(":")[-1])
    except:
        return await cb.answer("Bad bet.", show_alert=True)
    await _start_blackjack(cb, bet)

@router.callback_query(F.data == "blackjack:hit")
async def blackjack_hit(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    hand = state_obj.current_hand()
    hand.append(state_obj.draw())
    await _save_bj_state(cb.from_user.id, state_obj)
    lines = []
    for i, h in enumerate(state_obj.state["player_hands"]):
        marker = "👉 " if i == state_obj.state["current_hand"] else ""
        lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
    dealer_info = " ".join(state_obj.state["dealer_visible"])
    txt = "🃏 <b>Blackjack</b>\n" + "\n".join(lines) + f"\n\n🀫 Dealer: {dealer_info}"
    await safe_edit(
        cb.message,
        txt,
        reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
        parse_mode=ParseMode.HTML
    )
    from games.blackjack import calculate_hand_value
    if calculate_hand_value(hand) > 21:
        state_obj.state["current_hand"] += 1
        await _save_bj_state(cb.from_user.id, state_obj)
        if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
            lines = []
            for i, h in enumerate(state_obj.state["player_hands"]):
                marker = "👉 " if i == state_obj.state["current_hand"] else ""
                lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
            dealer_info = " ".join(state_obj.state["dealer_visible"])
            bust_txt = "🃏 <b>Blackjack</b>\n" + "\n".join(lines) + f"\n\n🀫 Dealer: {dealer_info}\n\n💥 Previous hand busted."
            await safe_edit(
                cb.message,
                bust_txt,
                reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
                parse_mode=ParseMode.HTML
            )
        else:
            await _bj_finish(cb, state_obj)
    await cb.answer()

@router.callback_query(F.data == "blackjack:stand")
async def blackjack_stand(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    state_obj.state["current_hand"] += 1
    await _save_bj_state(cb.from_user.id, state_obj)
    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        lines = []
        for i, h in enumerate(state_obj.state["player_hands"]):
            marker = "👉 " if i == state_obj.state["current_hand"] else ""
            lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
        dealer_info = " ".join(state_obj.state["dealer_visible"])
        txt = "🃏 <b>Blackjack</b>\n" + "\n".join(lines) + f"\n\n🀫 Dealer: {dealer_info}"
        await safe_edit(
            cb.message,
            txt,
            reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Next hand.")
    await _bj_finish(cb, state_obj)

@router.callback_query(F.data == "blackjack:double")
async def blackjack_double(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    if len(hand) != 2:
        return await cb.answer("Need 2 cards.", show_alert=True)
    original_bet = state_obj.state["bets"][ci]
    if not await db.adjust_active_round_bet(cb.from_user.id, original_bet):
        return await cb.answer("Balance low.", show_alert=True)
    state_obj.state["bets"][ci] = original_bet * 2
    state_obj.state["doubled"][ci] = True
    hand.append(state_obj.draw())
    await _save_bj_state(cb.from_user.id, state_obj)
    state_obj.state["current_hand"] += 1
    await _save_bj_state(cb.from_user.id, state_obj)
    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        lines = []
        for i, h in enumerate(state_obj.state["player_hands"]):
            marker = "👉 " if i == state_obj.state["current_hand"] else ""
            lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
        dealer_info = " ".join(state_obj.state["dealer_visible"])
        txt = ("🃏 <b>Blackjack</b>\n" + "\n".join(lines) +
               f"\n\n🀫 Dealer: {dealer_info}\n\n💰 Doubled.")
        await safe_edit(
            cb.message,
            txt,
            reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Doubled.")
    await _bj_finish(cb, state_obj)

@router.callback_query(F.data == "blackjack:split")
async def blackjack_split(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    if not state_obj.can_split():
        return await cb.answer("Cannot split.", show_alert=True)
    ci = state_obj.state["current_hand"]
    hand = state_obj.current_hand()
    c1, c2 = hand
    bet_amount = state_obj.state["bets"][ci]
    if not await db.adjust_active_round_bet(cb.from_user.id, bet_amount):
        return await cb.answer("Balance low.", show_alert=True)
    new1 = [c1, state_obj.draw()]
    new2 = [c2, state_obj.draw()]
    state_obj.state["player_hands"][ci] = new1
    state_obj.state["player_hands"].insert(ci + 1, new2)
    state_obj.state["bets"].insert(ci + 1, bet_amount)
    state_obj.state["doubled"].insert(ci + 1, False)
    state_obj.state["surrendered"].insert(ci + 1, False)
    state_obj.state["split_count"] = state_obj.state.get("split_count", 0) + 1
    await _save_bj_state(cb.from_user.id, state_obj)
    lines = []
    for i, h in enumerate(state_obj.state["player_hands"]):
        marker = "👉 " if i == state_obj.state["current_hand"] else ""
        lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
    dealer_info = " ".join(state_obj.state["dealer_visible"])
    txt = ("🃏 <b>Blackjack</b>\n" + "\n".join(lines) +
           f"\n\n🀫 Dealer: {dealer_info}\n\n🔀 Split performed.")
    await safe_edit(
        cb.message,
        txt,
        reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
        parse_mode=ParseMode.HTML
    )
    await cb.answer("Split done.")

@router.callback_query(F.data == "blackjack:surrender")
async def blackjack_surrender(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "blackjack":
        return await cb.answer("No round.", show_alert=True)
    state_obj = blackjack.BlackjackState.from_json(active["state_json"])
    ci = state_obj.state["current_hand"]
    while len(state_obj.state["surrendered"]) <= ci:
        state_obj.state["surrendered"].append(False)
    state_obj.state["surrendered"][ci] = True
    state_obj.state["current_hand"] += 1
    await _save_bj_state(cb.from_user.id, state_obj)
    if state_obj.state["current_hand"] < len(state_obj.state["player_hands"]):
        lines = []
        for i, h in enumerate(state_obj.state["player_hands"]):
            marker = "👉 " if i == state_obj.state["current_hand"] else ""
            lines.append(marker + _decorate_hand_line(i, h, state_obj.state))
        dealer_info = " ".join(state_obj.state["dealer_visible"])
        txt = ("🃏 <b>Blackjack</b>\n" + "\n".join(lines) +
               f"\n\n🀫 Dealer: {dealer_info}\n\n⚠️ Surrendered.")
        await safe_edit(
            cb.message,
            txt,
            reply_markup=build_blackjack_actions_kb(state_obj.can_double(), state_obj.can_split()),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Surrendered.")
    await _bj_finish(cb, state_obj)

# =========================================================
# Roulette
# =========================================================

ROULETTE_CHIPS = [1,5,10,25,50,100,250,500]

def roulette_main_kb(state: dict, can_spin: bool) -> InlineKeyboardMarkup:
    def chip_btn(val: int):
        return InlineKeyboardButton(text=f"+{val}", callback_data=f"roul:chip:{val}")
    rows = [
        [chip_btn(c) for c in ROULETTE_CHIPS[:4]],
        [chip_btn(c) for c in ROULETTE_CHIPS[4:]],
        [
            InlineKeyboardButton(text="🔴 Red", callback_data="roul:add:color:red"),
            InlineKeyboardButton(text="⚫ Black", callback_data="roul:add:color:black"),
            InlineKeyboardButton(text="○ Even", callback_data="roul:add:parity:even"),
            InlineKeyboardButton(text="● Odd", callback_data="roul:add:parity:odd"),
        ],
        [
            InlineKeyboardButton(text="⬇ 1-18", callback_data="roul:add:range:low"),
            InlineKeyboardButton(text="⬆ 19-36", callback_data="roul:add:range:high"),
            InlineKeyboardButton(text="1st12", callback_data="roul:add:dozen:1st12"),
            InlineKeyboardButton(text="2nd12", callback_data="roul:add:dozen:2nd12"),
        ],
        [
            InlineKeyboardButton(text="3rd12", callback_data="roul:add:dozen:3rd12"),
            InlineKeyboardButton(text="🎯 Num", callback_data="roul:numbers"),
            InlineKeyboardButton(text="🧹 CLR", callback_data="roul:clear"),
            InlineKeyboardButton(text="❌ CXL", callback_data="roul:cancel"),
        ],
        [
            InlineKeyboardButton(
                text="🎡 SPIN" if can_spin else "➕ Add bets",
                callback_data="roul:spin" if can_spin else "roul:noop"
            ),
            InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def roulette_numbers_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="0", callback_data="roul:num:0")]]
    for start in range(1, 37, 6):
        row = []
        for n in range(start, min(start + 6, 37)):
            row.append(InlineKeyboardButton(text=str(n), callback_data=f"roul:num:{n}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="roul:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _render_roulette(cb: CallbackQuery, state: dict, balance: int):
    summary = roulette.summarize_bets(state)
    can_spin = bool(state["bets"])
    await safe_edit(
        cb.message,
        "🎡 <b>Roulette</b>\n"
        f"💰 Balance: {balance} credits\n"
        f"🪙 Current Chip: {state['last_chip']}\n\n"
        f"{summary}",
        reply_markup=roulette_main_kb(state, can_spin),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "game:roulette")
async def roulette_entry(cb: CallbackQuery):
    active = await db.get_active_round(cb.from_user.id)
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if active and active["game"] == "roulette":
        state = roulette.from_json(active["state_json"])
        if state.get("spun"):
            await cb.answer("Round finished. Start new from menu.", show_alert=True)
            return
        await _render_roulette(cb, state, user["balance"])
        return
    state = roulette.base_state()
    if not await db.start_active_round(cb.from_user.id, "roulette", 0, roulette.to_json(state)):
        other = await db.get_active_round(cb.from_user.id)
        if other:
            await cb.answer("Another game active. /cancel to free.", show_alert=True)
            return
    await _render_roulette(cb, state, user["balance"])
    await cb.answer("Roulette session started.")

@router.callback_query(F.data.func(lambda d: d.startswith("roul:")))
async def roulette_actions(cb: CallbackQuery):
    data = cb.data.split(":")
    action = data[1]
    active = await db.get_active_round(cb.from_user.id)
    if not active or active["game"] != "roulette":
        return await cb.answer("No roulette session.", show_alert=True)
    state = roulette.from_json(active["state_json"])
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)

    if state.get("spun") and action not in ("cancel", "noop"):
        return await cb.answer("Round done.", show_alert=True)

    if action == "noop":
        return await cb.answer()

    if action == "chip":
        chip = int(data[2])
        state["last_chip"] = chip
        await db.update_active_round(cb.from_user.id, roulette.to_json(state))
        await _render_roulette(cb, state, user["balance"])
        return await cb.answer(f"Chip {chip}")

    if action == "add":
        bet_type = data[2]
        value = data[3]
        amt = state["last_chip"]
        if amt <= 0:
            return await cb.answer("Set chip > 0.")
        if user["balance"] < amt:
            return await cb.answer("Low balance.", show_alert=True)
        if not await db.adjust_active_round_bet(cb.from_user.id, amt):
            return await cb.answer("Failed lock.", show_alert=True)
        roulette.add_bet(state, bet_type, value, amt)
        await db.update_active_round(cb.from_user.id, roulette.to_json(state))
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        await _render_roulette(cb, state, user["balance"])
        return await cb.answer("Bet added.")

    if action == "numbers":
        await safe_edit(cb.message, "🎯 Select a number:", reply_markup=roulette_numbers_kb())
        return await cb.answer()

    if action == "num":
        n = data[2]
        amt = state["last_chip"]
        if user["balance"] < amt:
            return await cb.answer("Low balance.", show_alert=True)
        if not await db.adjust_active_round_bet(cb.from_user.id, amt):
            return await cb.answer("Failed lock.", show_alert=True)
        roulette.add_bet(state, "straight", n, amt)
        await db.update_active_round(cb.from_user.id, roulette.to_json(state))
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        await _render_roulette(cb, state, user["balance"])
        return await cb.answer(f"Bet #{n}")

    if action == "back":
        await _render_roulette(cb, state, user["balance"])
        return await cb.answer()

    if action == "clear":
        refund = sum(b["amount"] for b in state["bets"])
        await db.delete_active_round(cb.from_user.id)
        user_balance = await db.update_balance(cb.from_user.id, refund)
        new_state = roulette.base_state()
        await db.start_active_round(cb.from_user.id, "roulette", 0, roulette.to_json(new_state))
        await _render_roulette(cb, new_state, user_balance)
        return await cb.answer("Cleared.")

    if action == "cancel":
        refund = sum(b["amount"] for b in state["bets"])
        await db.delete_active_round(cb.from_user.id)
        if refund:
            await db.update_balance(cb.from_user.id, refund)
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        await safe_edit(
            cb.message,
            build_main_menu_text(user['balance']),
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Canceled.")

    if action == "spin":
        if not state["bets"]:
            return await cb.answer("Add bets first.", show_alert=True)
        state["spun"] = True
        await db.update_active_round(cb.from_user.id, roulette.to_json(state))
        sequence_len = 10
        for i in range(sequence_len):
            temp_num = random.randint(0, 36)
            color = "🔴" if temp_num in roulette.RED_NUMBERS else "⚫" if temp_num in roulette.BLACK_NUMBERS else "🟢"
            await safe_edit(
                cb.message,
                f"🎡 Spinning...\nRoll: {temp_num} {color} (step {i+1}/{sequence_len})",
                parse_mode=ParseMode.HTML
            )
            await asyncio.sleep(0.22)
        final = roulette.spin_result()
        state["result"] = final
        payout = roulette.evaluate(state, final)
        await db.update_active_round(cb.from_user.id, roulette.to_json(state))
        await db.resolve_active_round(cb.from_user.id, "win" if payout > 0 else "loss", payout)
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        color = "🔴" if final in roulette.RED_NUMBERS else "⚫" if final in roulette.BLACK_NUMBERS else "🟢"
        total_bet = sum(b["amount"] for b in state["bets"])
        net = payout - total_bet
        summary = roulette.summarize_bets(state)
        result_text = (
            "🎡 <b>Roulette Result</b>\n"
            f"{summary}\n\n"
            f"Final: {final} {color}\n"
            f"Total Bet: {total_bet}\n"
            f"Payout: {payout}\n"
            f"Net: {'+' if net>=0 else ''}{net}\n"
            f"💰 Balance: {user['balance']} credits"
        )
        await safe_edit(
            cb.message,
            result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎡 New Roulette", callback_data="game:roulette")],
                [InlineKeyboardButton(text="📋 Menu", callback_data="nav:menu")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Done.")
    await cb.answer()

# =========================================================
# Entrypoint
# =========================================================

async def main():
    await db.init()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())