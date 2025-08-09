import asyncio
import random
from typing import Dict, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import get_settings
from storage.db import Database
from ui.keyboards import main_menu_kb, back_menu_kb

# ------------------------------------------------------------------------------------
# Settings / DB
# ------------------------------------------------------------------------------------
settings = get_settings()
db = Database(settings.db_path, starting_balance=settings.starting_balance)

router = Router()

# ------------------------------------------------------------------------------------
# Simple 21 (Blackjack-lite) implementation
# ------------------------------------------------------------------------------------
# In-memory per-user active round state (not persisted)
# Structure:
# GAME21_STATE[user_id] = {
#     "bet": int,
#     "player": List[str],
#     "dealer": List[str]
# }
GAME21_STATE: Dict[int, Dict] = {}

CARD_VALUES: List[str] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_POINTS = {
    "A": 11,  # Adjust down to 1 as needed
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 10, "Q": 10, "K": 10
}


def draw_card() -> str:
    return random.choice(CARD_VALUES)


def hand_total(cards: List[str]) -> int:
    total = sum(CARD_POINTS[c] for c in cards)
    aces = sum(1 for c in cards if c == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def format_hand(cards: List[str]) -> str:
    return f"{' '.join(cards)} (total: {hand_total(cards)})"


def build_simple21_bet_kb(balance: int) -> InlineKeyboardMarkup:
    min_bet = max(settings.min_bet, 1)
    max_bet = min(settings.max_bet, balance)
    suggestions = [min_bet, min_bet * 2, min_bet * 5, min_bet * 10, max_bet]
    amounts = sorted({a for a in suggestions if min_bet <= a <= max_bet})
    rows = []
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"Bet {a}", callback_data=f"game:simple21:bet:{a}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_simple21_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🃏 Hit", callback_data="game:simple21:hit"),
                InlineKeyboardButton(text="🛑 Stand", callback_data="game:simple21:stand"),
            ],
            [InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")],
        ]
    )


async def end_simple21_and_payout(user_id: int, bet: int, delta: int, result: str) -> Dict:
    """
    Apply the net delta (win=+bet, loss=-bet, push=0), record the bet,
    clear the in-memory round, and return the updated user row.
    """
    # Apply balance delta (update_balance already adds the delta atomically)
    new_balance = await db.update_balance(user_id, delta)
    # Record bet for history / analytics
    await db.record_bet(user_id, "simple21", bet, result, delta)
    # Clear round state
    GAME21_STATE.pop(user_id, None)
    # Return updated user (could also reuse new_balance if we want)
    user = await db.get_or_create_user(user_id, None)
    user["balance"] = new_balance
    return user


# ------------------------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await db.get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"🎰 Welcome to Casinon!\nBalance: {user['balance']} credits\n\nChoose a game:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Help:\n"
        "/start — Show main menu\n"
        "/help — This help\n\n"
        "Use inline buttons to navigate and play games.",
        reply_markup=back_menu_kb(),
    )


# ------------------------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    GAME21_STATE.pop(cb.from_user.id, None)  # Abandon any active round
    await cb.message.edit_text(
        f"Choose a game:\n\nYour balance: {user['balance']} credits",
        reply_markup=main_menu_kb(),
    )
    await cb.answer()


# ------------------------------------------------------------------------------------
# Simple 21 Entry
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "game:simple21")
async def game_simple21(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(
            "2️⃣1️⃣ Simple 21\n\n"
            f"Insufficient balance. Minimum bet: {settings.min_bet}\n"
            f"Your balance: {user['balance']} credits",
            reply_markup=back_menu_kb(),
        )
        return await cb.answer()
    await cb.message.edit_text(
        "2️⃣1️⃣ Simple 21\n\n"
        f"Your balance: {user['balance']} credits\n"
        "Select a bet:",
        reply_markup=build_simple21_bet_kb(user["balance"]),
    )
    await cb.answer()


@router.callback_query(F.data.func(lambda d: d.startswith("game:simple21:bet:")))
async def simple21_place_bet(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    try:
        bet = int(cb.data.split(":")[-1])
    except Exception:
        return await cb.answer("Invalid bet.", show_alert=True)

    min_bet = max(settings.min_bet, 1)
    if bet < min_bet:
        return await cb.answer(f"Min bet: {min_bet}", show_alert=True)
    if bet > settings.max_bet:
        return await cb.answer(f"Max bet: {settings.max_bet}", show_alert=True)
    if bet > user["balance"]:
        return await cb.answer("Not enough balance.", show_alert=True)

    # Start round
    player = [draw_card(), draw_card()]
    dealer = [draw_card()]  # show only first card
    GAME21_STATE[cb.from_user.id] = {"bet": bet, "player": player, "dealer": dealer}

    text = (
        "2️⃣1️⃣ Simple 21\n"
        f"Bet: {bet} credits\n\n"
        f"Your hand: {format_hand(player)}\n"
        f"Dealer shows: {' '.join(dealer)}"
    )
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb())
    await cb.answer()


# ------------------------------------------------------------------------------------
# Simple 21 Actions
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "game:simple21:hit")
async def simple21_hit(cb: CallbackQuery):
    state = GAME21_STATE.get(cb.from_user.id)
    if not state:
        return await cb.answer("No active round.", show_alert=True)

    state["player"].append(draw_card())
    player_total = hand_total(state["player"])

    if player_total > 21:
        # Bust -> loss
        updated_user = await end_simple21_and_payout(
            cb.from_user.id,
            bet=state["bet"],
            delta=-state["bet"],
            result="loss",
        )
        text = (
            "💥 Bust!\n\n"
            f"Your hand: {format_hand(state['player'])}\n"
            f"Dealer: {' '.join(state['dealer'])}\n\n"
            f"You lost {state['bet']} credits.\n"
            f"Balance: {updated_user['balance']} credits"
        )
        await cb.message.edit_text(text, reply_markup=back_menu_kb())
        return await cb.answer("Bust!")

    # Continue round
    text = (
        "2️⃣1️⃣ Simple 21\n"
        f"Bet: {state['bet']} credits\n\n"
        f"Your hand: {format_hand(state['player'])}\n"
        f"Dealer shows: {' '.join(state['dealer'])}"
    )
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb())
    await cb.answer()


@router.callback_query(F.data == "game:simple21:stand")
async def simple21_stand(cb: CallbackQuery):
    state = GAME21_STATE.get(cb.from_user.id)
    if not state:
        return await cb.answer("No active round.", show_alert=True)

    dealer = state["dealer"][:]
    # Dealer draws to 17+
    while hand_total(dealer) < 17:
        dealer.append(draw_card())

    player_total = hand_total(state["player"])
    dealer_total = hand_total(dealer)

    if dealer_total > 21 or player_total > dealer_total:
        result = "win"
        delta = state["bet"]
        outcome = f"✅ You win! +{state['bet']} credits"
    elif player_total < dealer_total:
        result = "loss"
        delta = -state["bet"]
        outcome = f"❌ You lose! -{state['bet']} credits"
    else:
        result = "push"
        delta = 0
        outcome = "🤝 Push (tie). Balance unchanged."

    updated_user = await end_simple21_and_payout(
        cb.from_user.id,
        bet=state["bet"],
        delta=delta,
        result=result,
    )

    text = (
        "🏁 Result — Simple 21\n"
        f"Your hand: {format_hand(state['player'])}\n"
        f"Dealer: {format_hand(dealer)}\n\n"
        f"{outcome}\n"
        f"Balance: {updated_user['balance']} credits"
    )
    await cb.message.edit_text(text, reply_markup=back_menu_kb())
    await cb.answer()


# ------------------------------------------------------------------------------------
# Placeholder other games
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "game:blackjack")
async def game_blackjack(cb: CallbackQuery):
    await cb.message.edit_text("🃏 Full Blackjack — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "game:roulette")
async def game_roulette(cb: CallbackQuery):
    await cb.message.edit_text("🎡 Roulette — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()


# ------------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------------
async def main():
    await db.init()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
