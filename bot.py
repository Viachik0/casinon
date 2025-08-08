import asyncio
import random

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import get_settings
from storage.db import Database
from ui.keyboards import back_menu_kb, main_menu_kb

settings = get_settings()
# Initialize DB with configured starting balance
db = Database(settings.db_path, starting_balance=settings.starting_balance)

router = Router()

# ---- Simple 21 (blackjack-lite) state and helpers ----

# Per-user in-memory game state. Resets when the process restarts.
GAME21_STATE: dict[int, dict] = {}

CARD_VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_POINTS = {
    "A": 11,  # will adjust down to 1 as needed
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 10, "K": 10
}

def draw_card() -> str:
    return random.choice(CARD_VALUES)

def hand_total(cards: list[str]) -> int:
    total = sum(CARD_POINTS[c] for c in cards)
    # Adjust Aces from 11 to 1 while busting
    aces = sum(1 for c in cards if c == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def format_hand(cards: list[str]) -> str:
    return f"{' '.join(cards)} (total: {hand_total(cards)})"

def build_simple21_bet_kb(balance: int) -> InlineKeyboardMarkup:
    min_bet = max(settings.min_bet, 1)
    max_bet = min(settings.max_bet, balance)
    # Suggested bet options within balance
    opts = [min_bet, min_bet * 2, min_bet * 5, min_bet * 10, max_bet]
    # Filter, unique, sorted, and within bounds
    amounts = sorted({a for a in opts if min_bet <= a <= max_bet})
    rows = []
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"Bet {a}", callback_data=f"game:simple21:bet:{a}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_simple21_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 Hit", callback_data="game:simple21:hit"),
            InlineKeyboardButton(text="🛑 Stand", callback_data="game:simple21:stand"),
        ],
        [InlineKeyboardButton(text="⬅️ Menu", callback_data="nav:menu")],
    ])

async def end_simple21_and_payout(user_id: int, delta: int) -> dict:
    # Get current balance, apply delta, persist, clear round, return updated user
    user = await db.get_or_create_user(user_id, None)
    new_balance = user["balance"] + delta
    await db.update_balance(user_id, new_balance)
    GAME21_STATE.pop(user_id, None)
    return await db.get_or_create_user(user_id, None)

# ---- Handlers ----

@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await db.get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"🎰 Welcome to Casinon!\nBalance: {user['balance']} credits",
        reply_markup=main_menu_kb(),
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Commands:\n"
        "/start — main menu\n"
        "/help — this help\n\n"
        "Use the buttons to choose a game.",
        reply_markup=back_menu_kb(),
    )

@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    await cb.message.edit_text(
        f"Choose a game:\n\nYour balance: {user['balance']} credits",
        reply_markup=main_menu_kb()
    )
    GAME21_STATE.pop(cb.from_user.id, None)
    await cb.answer()

@router.callback_query(F.data == "game:blackjack")
async def game_blackjack(cb: CallbackQuery):
    await cb.message.edit_text("🃏 Blackjack — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "game:simple21")
async def game_simple21(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(
            f"2️⃣1️⃣ Simple 21\n\n"
            f"Not enough balance to play. Minimum bet is {settings.min_bet}.\n"
            f"Your balance: {user['balance']} credits",
            reply_markup=back_menu_kb()
        )
        return await cb.answer()
    await cb.message.edit_text(
        f"2️⃣1️⃣ Simple 21\n\n"
        f"Your balance: {user['balance']} credits\n"
        f"Choose your bet:",
        reply_markup=build_simple21_bet_kb(user["balance"])
    )
    await cb.answer()

@router.callback_query(F.data.func(lambda d: d.startswith("game:simple21:bet:")))
async def simple21_place_bet(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    try:
        bet = int(cb.data.split(":")[-1])
    except Exception:
        await cb.answer("Invalid bet.", show_alert=True)
        return
    min_bet = max(settings.min_bet, 1)
    if bet < min_bet:
        return await cb.answer(f"Bet must be at least {min_bet}.", show_alert=True)
    if bet > settings.max_bet:
        return await cb.answer(f"Bet must be ≤ {settings.max_bet}.", show_alert=True)
    if bet > user["balance"]:
        return await cb.answer("Insufficient balance for that bet.", show_alert=True)

    # Start a new round
    player = [draw_card(), draw_card()]
    dealer = [draw_card()]  # show one dealer card, draw the rest later
    GAME21_STATE[cb.from_user.id] = {"bet": bet, "player": player, "dealer": dealer}

    text = (
        "2️⃣1️⃣ Simple 21\n"
        f"Bet: {bet} credits\n\n"
        f"Your hand: {format_hand(player)}\n"
        f"Dealer shows: {' '.join(dealer)}"
    )
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb())
    await cb.answer()

@router.callback_query(F.data == "game:simple21:hit")
async def simple21_hit(cb: CallbackQuery):
    state = GAME21_STATE.get(cb.from_user.id)
    if not state:
        await cb.answer("No active round. Start a new game.", show_alert=True)
        return
    state["player"].append(draw_card())
    player_total = hand_total(state["player"])

    if player_total > 21:
        # Player busts — lose bet
        updated_user = await end_simple21_and_payout(cb.from_user.id, delta=-state["bet"])
        text = (
            "💥 Bust!\n\n"
            f"Your hand: {format_hand(state['player'])}\n"
            f"Dealer: {' '.join(state['dealer'])}\n\n"
            f"You lost {state['bet']} credits.\n"
            f"New balance: {updated_user['balance']} credits"
        )
        await cb.message.edit_text(text, reply_markup=back_menu_kb())
        return await cb.answer("You busted.")

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
        await cb.answer("No active round. Start a new game.", show_alert=True)
        return

    # Dealer draws to 17+
    dealer = state["dealer"][:]
    while hand_total(dealer) < 17:
        dealer.append(draw_card())

    player_total = hand_total(state["player"])
    dealer_total = hand_total(dealer)

    outcome = ""
    delta = 0
    if dealer_total > 21 or player_total > dealer_total:
        outcome = f"✅ You win! +{state['bet']} credits"
        delta = state["bet"]
    elif player_total < dealer_total:
        outcome = f"❌ You lose! -{state['bet']} credits"
        delta = -state["bet"]
    else:
        outcome = "🤝 Push (tie). Balance unchanged."
        delta = 0

    # Finish round and apply delta
    updated_user = await end_simple21_and_payout(cb.from_user.id, delta=delta)

    text = (
        "🏁 Result — Simple 21\n"
        f"Your hand: {format_hand(state['player'])}\n"
        f"Dealer: {format_hand(dealer)}\n\n"
        f"{outcome}\n"
        f"New balance: {updated_user['balance']} credits"
    )
    await cb.message.edit_text(text, reply_markup=back_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "game:roulette")
async def game_roulette(cb: CallbackQuery):
    await cb.message.edit_text("🎡 Roulette — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()

async def main():
    await db.init()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())