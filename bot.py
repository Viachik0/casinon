import asyncio
import json
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
from services.cards import format_hand_with_total, calculate_hand_value, SUITS, HIDDEN_CARD

# ------------------------------------------------------------------------------------
# Settings / DB
# ------------------------------------------------------------------------------------
settings = get_settings()
db = Database(settings.db_path, starting_balance=settings.starting_balance)

router = Router()

# ------------------------------------------------------------------------------------
# Simple 21 (Blackjack-lite) implementation with persistent state
# ------------------------------------------------------------------------------------

CARD_VALUES: List[str] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def draw_card() -> str:
    """Draw a random card rank."""
    return random.choice(CARD_VALUES)


def draw_card_with_suit() -> str:
    """Draw a random card with Unicode suit for display."""
    rank = random.choice(CARD_VALUES)
    suit = random.choice(SUITS)
    return f"{rank}{suit}"


def format_hand_display(cards: List[str]) -> str:
    """Format a list of card ranks with Unicode suits for display."""
    if not cards:
        return ""
    
    # Add random suits to ranks for display
    display_cards = []
    for rank in cards:
        if len(rank) > 2:  # Already has suit
            display_cards.append(rank)
        else:  # Just rank, add suit
            suit = random.choice(SUITS)
            display_cards.append(f"{rank}{suit}")
    
    total = calculate_hand_value(cards)
    return f"{' '.join(display_cards)} (total: {total})"


def format_hand_display_with_hidden(cards: List[str], hide_first: bool = False) -> str:
    """Format hand with optional hidden first card and Unicode suits."""
    if not cards:
        return ""
    
    if hide_first and len(cards) > 1:
        visible_cards = cards[1:]
        total = calculate_hand_value(visible_cards)
        
        # Add suits to visible cards
        display_cards = []
        for rank in visible_cards:
            if len(rank) > 2:  # Already has suit
                display_cards.append(rank)
            else:  # Just rank, add suit
                suit = random.choice(SUITS)
                display_cards.append(f"{rank}{suit}")
        
        card_display = f"{HIDDEN_CARD} {' '.join(display_cards)}"
        return f"{card_display} (showing: {total})"
    else:
        return format_hand_display(cards)


def build_simple21_bet_kb(balance: int, has_active_round: bool = False) -> InlineKeyboardMarkup:
    """Build betting keyboard, with Same Bet option if there's an active round."""
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
    
    if has_active_round:
        rows.append([InlineKeyboardButton(text="📄 Continue Round", callback_data="game:simple21:continue")])
    
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_simple21_actions_kb(can_same_bet: bool = False, last_bet: int = 0) -> InlineKeyboardMarkup:
    """Build action keyboard with enhanced buttons."""
    rows = [
        [
            InlineKeyboardButton(text="🃏 Hit", callback_data="game:simple21:hit"),
            InlineKeyboardButton(text="🛑 Stand", callback_data="game:simple21:stand"),
        ],
        [InlineKeyboardButton(text="📋 Menu", callback_data="nav:menu")],
    ]
    
    if can_same_bet and last_bet > 0:
        rows.insert(-1, [InlineKeyboardButton(text=f"🔄 Same Bet ({last_bet})", callback_data=f"game:simple21:same_bet:{last_bet}")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_simple21_result_kb(last_bet: int, balance: int) -> InlineKeyboardMarkup:
    """Build result keyboard with replay options."""
    rows = []
    
    if last_bet <= balance:
        rows.append([InlineKeyboardButton(text=f"🔄 Same Bet ({last_bet})", callback_data=f"game:simple21:same_bet:{last_bet}")])
    
    rows.extend([
        [InlineKeyboardButton(text="🎰 New Game", callback_data="game:simple21")],
        [InlineKeyboardButton(text="📋 Menu", callback_data="nav:menu")],
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ------------------------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    
    # Check if user has active round and offer to abandon it
    active_round = await db.get_active_round(cb.from_user.id)
    if active_round:
        await cb.message.edit_text(
            f"⚠️ You have an active {active_round['game']} round with bet {active_round['bet']}.\n\n"
            "Returning to menu will abandon this round and forfeit your bet.\n"
            "Are you sure?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Yes, abandon", callback_data="nav:menu:confirm"),
                    InlineKeyboardButton(text="❌ No, go back", callback_data=f"game:{active_round['game']}")
                ]
            ])
        )
    else:
        await cb.message.edit_text(
            f"Choose a game:\n\n<b>Your balance:</b> {user['balance']} credits",
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML
        )
    await cb.answer()


@router.callback_query(F.data == "nav:menu:confirm")
async def nav_menu_confirm(cb: CallbackQuery):
    # Abandon active round
    active_round = await db.get_active_round(cb.from_user.id)
    if active_round:
        # Resolve as loss (no payout)
        await db.resolve_active_round(cb.from_user.id, "loss", 0)
    
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    await cb.message.edit_text(
        f"Choose a game:\n\n<b>Your balance:</b> {user['balance']} credits",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()
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
        "/balance — Show balance and statistics\n"
        "/history [N|today|week|month] — Show bet history\n"
        "/help — This help\n\n"
        "Use inline buttons to navigate and play games.",
        reply_markup=back_menu_kb(),
    )


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    stats = await db.get_balance_stats(message.from_user.id)
    
    text = (
        f"💰 <b>Balance:</b> {stats['balance']} credits\n"
        f"📊 <b>Total Profit:</b> {stats['total_profit']:+d} credits\n\n"
        f"📈 <b>Game Statistics:</b>\n"
        f"   🏆 Wins: {stats['wins']}\n"
        f"   💥 Losses: {stats['losses']}\n"
        f"   🤝 Pushes: {stats['pushes']}\n"
        f"   🎯 Total Games: {stats['wins'] + stats['losses'] + stats['pushes']}"
    )
    
    await message.answer(text, reply_markup=back_menu_kb(), parse_mode=ParseMode.HTML)


@router.message(Command("history"))
async def cmd_history(message: Message):
    # Parse command arguments
    args = message.text.split()[1:] if message.text else []
    limit = 10
    filter_type = None
    
    if args:
        arg = args[0].lower()
        if arg.isdigit():
            limit = min(int(arg), 50)  # Max 50 records
        elif arg in ["today", "week", "month"]:
            filter_type = arg
    
    history = await db.get_bet_history(message.from_user.id, limit, filter_type)
    
    if not history:
        text = "📊 <b>Bet History</b>\n\nNo bets found."
    else:
        filter_text = f" ({filter_type})" if filter_type else ""
        text = f"📊 <b>Bet History{filter_text}</b>\n\n"
        
        for bet in history:
            # Parse datetime and format
            dt = bet['created_at'][:19].replace('T', ' ')
            result_icon = {"win": "🏆", "loss": "💥", "push": "🤝"}.get(bet['result'], "❓")
            delta_str = f"{bet['delta']:+d}" if bet['delta'] != 0 else "±0"
            
            text += (
                f"{dt} | <b>{bet['game']}</b>\n"
                f"Bet: {bet['amount']} | {result_icon} {bet['result'].title()} | {delta_str}\n\n"
            )
    
    await message.answer(text, reply_markup=back_menu_kb(), parse_mode=ParseMode.HTML)


# ------------------------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "nav:menu")
async def nav_menu(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    
    # Check if user has active round and offer to abandon it
    active_round = await db.get_active_round(cb.from_user.id)
    if active_round:
        await cb.message.edit_text(
            f"⚠️ You have an active {active_round['game']} round with bet {active_round['bet']}.\n\n"
            "Returning to menu will abandon this round and forfeit your bet.\n"
            "Are you sure?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Yes, abandon", callback_data="nav:menu:confirm"),
                    InlineKeyboardButton(text="❌ No, go back", callback_data=f"game:{active_round['game']}")
                ]
            ])
        )
    else:
        await cb.message.edit_text(
            f"Choose a game:\n\n<b>Your balance:</b> {user['balance']} credits",
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML
        )
    await cb.answer()


@router.callback_query(F.data == "nav:menu:confirm")
async def nav_menu_confirm(cb: CallbackQuery):
    # Abandon active round
    active_round = await db.get_active_round(cb.from_user.id)
    if active_round:
        # Resolve as loss (no payout)
        await db.resolve_active_round(cb.from_user.id, "loss", 0)
    
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    await cb.message.edit_text(
        f"Choose a game:\n\n<b>Your balance:</b> {user['balance']} credits",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()


# ------------------------------------------------------------------------------------
# Simple 21 Entry
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "game:simple21")
async def game_simple21(cb: CallbackQuery):
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    
    # Check for active round first
    active_round = await db.get_active_round(cb.from_user.id)
    if active_round and active_round['game'] == 'simple21':
        # Continue existing round
        state = json.loads(active_round['state_json'])
        bet = active_round['bet']
        
        player_total = calculate_hand_value(state['player'])
        dealer_showing = format_hand_display_with_hidden(state['dealer'], hide_first=True)
        
        text = (
            f"2️⃣1️⃣ <b>Simple 21</b> (continued)\n"
            f"💰 <b>Bet:</b> {bet} credits\n\n"
            f"🎲 <b>Your hand:</b> {format_hand_display(state['player'])}\n"
            f"🎯 <b>Dealer shows:</b> {dealer_showing}"
        )
        
        await cb.message.edit_text(
            text, 
            reply_markup=build_simple21_actions_kb(),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Continuing your round!")
    
    # Check balance for new round
    if user["balance"] < settings.min_bet:
        await cb.message.edit_text(
            f"2️⃣1️⃣ <b>Simple 21</b>\n\n"
            f"❌ Insufficient balance. Minimum bet: {settings.min_bet}\n"
            f"💰 <b>Your balance:</b> {user['balance']} credits",
            reply_markup=back_menu_kb(),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer()
    
    # Show betting options
    await cb.message.edit_text(
        f"2️⃣1️⃣ <b>Simple 21</b>\n\n"
        f"💰 <b>Your balance:</b> {user['balance']} credits\n"
        "💵 Select your bet:",
        reply_markup=build_simple21_bet_kb(user["balance"]),
        parse_mode=ParseMode.HTML
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

    # Start round with bet locking
    player = [draw_card(), draw_card()]
    dealer = [draw_card()]  # dealer gets second card later
    
    state = {
        "player": player,
        "dealer": dealer
    }
    
    success = await db.start_active_round(cb.from_user.id, "simple21", bet, json.dumps(state))
    if not success:
        return await cb.answer("❌ Failed to start round. Try again.", show_alert=True)

    player_total = calculate_hand_value(player)
    dealer_showing = format_hand_display(dealer)  # Only one card, so show it

    text = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💰 <b>Bet:</b> {bet} credits (locked)\n\n"
        f"🎲 <b>Your hand:</b> {format_hand_display(player)}\n"
        f"🎯 <b>Dealer shows:</b> {dealer_showing}"
    )
    
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb(), parse_mode=ParseMode.HTML)
    await cb.answer("Bet locked! Good luck!")


# ------------------------------------------------------------------------------------
# Simple 21 Actions - Same Bet Feature
# ------------------------------------------------------------------------------------
@router.callback_query(F.data.func(lambda d: d.startswith("game:simple21:same_bet:")))
async def simple21_same_bet(cb: CallbackQuery):
    """Handle same bet replay."""
    try:
        bet = int(cb.data.split(":")[-1])
    except Exception:
        return await cb.answer("Invalid bet.", show_alert=True)
    
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
    
    if bet > user["balance"]:
        return await cb.answer("Not enough balance for same bet.", show_alert=True)
    
    # Start new round with same bet
    player = [draw_card(), draw_card()]
    dealer = [draw_card()]
    
    state = {
        "player": player,
        "dealer": dealer
    }
    
    success = await db.start_active_round(cb.from_user.id, "simple21", bet, json.dumps(state))
    if not success:
        return await cb.answer("❌ Failed to start round. Try again.", show_alert=True)

    text = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💰 <b>Bet:</b> {bet} credits (locked)\n\n"
        f"🎲 <b>Your hand:</b> {format_hand_display(player)}\n"
        f"🎯 <b>Dealer shows:</b> {format_hand_display(dealer)}"
    )
    
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb(), parse_mode=ParseMode.HTML)
    await cb.answer("New round started!")


# ------------------------------------------------------------------------------------
# Simple 21 Actions
# ------------------------------------------------------------------------------------
@router.callback_query(F.data == "game:simple21:hit")
async def simple21_hit(cb: CallbackQuery):
    active_round = await db.get_active_round(cb.from_user.id)
    if not active_round or active_round['game'] != 'simple21':
        return await cb.answer("No active Simple 21 round.", show_alert=True)

    state = json.loads(active_round['state_json'])
    bet = active_round['bet']
    
    # Add card to player hand
    state["player"].append(draw_card())
    player_total = calculate_hand_value(state["player"])

    if player_total > 21:
        # Bust -> loss (no payout)
        success = await db.resolve_active_round(cb.from_user.id, "loss", 0)
        if not success:
            return await cb.answer("Error resolving round.", show_alert=True)
        
        user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)
        
        text = (
            f"💥 <b>BUST!</b>\n\n"
            f"🎲 <b>Your hand:</b> {format_hand_display(state['player'])}\n"
            f"🎯 <b>Dealer:</b> {format_hand_display(state['dealer'])}\n\n"
            f"❌ <b>Result:</b> Lost {bet} credits\n"
            f"💰 <b>Balance:</b> {user['balance']} credits"
        )
        
        await cb.message.edit_text(
            text, 
            reply_markup=build_simple21_result_kb(bet, user['balance']),
            parse_mode=ParseMode.HTML
        )
        return await cb.answer("Bust!")

    # Update round state and continue
    await db.update_active_round(cb.from_user.id, json.dumps(state))
    
    text = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💰 <b>Bet:</b> {bet} credits\n\n"
        f"🎲 <b>Your hand:</b> {format_hand_display(state['player'])}\n"
        f"🎯 <b>Dealer shows:</b> {format_hand_display(state['dealer'])}"
    )
    
    await cb.message.edit_text(text, reply_markup=build_simple21_actions_kb(), parse_mode=ParseMode.HTML)
    await cb.answer()


@router.callback_query(F.data == "game:simple21:stand")
async def simple21_stand(cb: CallbackQuery):
    active_round = await db.get_active_round(cb.from_user.id)
    if not active_round or active_round['game'] != 'simple21':
        return await cb.answer("No active Simple 21 round.", show_alert=True)

    state = json.loads(active_round['state_json'])
    bet = active_round['bet']
    
    # Dealer draws second card and continues to 17+
    dealer = state["dealer"][:]
    while calculate_hand_value(dealer) < 17:
        dealer.append(draw_card())

    player_total = calculate_hand_value(state["player"])
    dealer_total = calculate_hand_value(dealer)

    # Determine result and payout
    if dealer_total > 21 or player_total > dealer_total:
        result = "win"
        payout_delta = 2 * bet  # Win pays 2x bet (net +bet)
        outcome = f"🏆 <b>YOU WIN!</b> +{bet} credits"
        result_icon = "🏆"
    elif player_total < dealer_total:
        result = "loss"
        payout_delta = 0  # Loss pays 0 (net -bet) 
        outcome = f"💥 <b>YOU LOSE!</b> -{bet} credits"
        result_icon = "💥"
    else:
        result = "push"
        payout_delta = bet  # Push returns bet (net ±0)
        outcome = f"🤝 <b>PUSH!</b> Bet returned"
        result_icon = "🤝"

    success = await db.resolve_active_round(cb.from_user.id, result, payout_delta)
    if not success:
        return await cb.answer("Error resolving round.", show_alert=True)
    
    user = await db.get_or_create_user(cb.from_user.id, cb.from_user.username)

    text = (
        f"{result_icon} <b>ROUND COMPLETE</b>\n\n"
        f"🎲 <b>Your hand:</b> {format_hand_display(state['player'])}\n"
        f"🎯 <b>Dealer hand:</b> {format_hand_display(dealer)}\n\n"
        f"📊 <b>Result:</b> {outcome}\n"
        f"💰 <b>Balance:</b> {user['balance']} credits"
    )
    
    await cb.message.edit_text(
        text, 
        reply_markup=build_simple21_result_kb(bet, user['balance']),
        parse_mode=ParseMode.HTML
    )
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
