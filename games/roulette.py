"""Roulette game implementation with FSM."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.rng import rng
from storage.db import db
from ui.keyboards import (
    bet_amount_keyboard, roulette_bet_type_keyboard, 
    game_end_keyboard
)
from config import config

router = Router()


class RouletteStates(StatesGroup):
    """States for roulette game flow."""
    waiting_for_bet = State()
    waiting_for_custom_bet = State()
    waiting_for_bet_type = State()
    waiting_for_number = State()


class RouletteGame:
    """European roulette game engine."""
    
    # European roulette numbers and colors
    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    def __init__(self):
        self.bet_amount = 0
        self.bet_type = ""
        self.bet_value = None
        self.result_number = 0
    
    def spin(self) -> int:
        """Spin the roulette wheel (0-36)."""
        self.result_number = rng.randint(0, 36)
        return self.result_number
    
    def get_number_color(self, number: int) -> str:
        """Get the color of a number."""
        if number == 0:
            return "🟢 Green"
        elif number in self.RED_NUMBERS:
            return "🔴 Red"
        else:
            return "⚫ Black"
    
    def check_win(self) -> tuple[bool, int]:
        """
        Check if the bet wins and return payout multiplier.
        Returns (is_win, payout_multiplier).
        """
        number = self.result_number
        
        if self.bet_type == "red":
            return number in self.RED_NUMBERS, 2  # 1:1 + original bet
        
        elif self.bet_type == "black":
            return number in self.BLACK_NUMBERS, 2  # 1:1 + original bet
        
        elif self.bet_type == "odd":
            return number > 0 and number % 2 == 1, 2  # 1:1 + original bet
        
        elif self.bet_type == "even":
            return number > 0 and number % 2 == 0, 2  # 1:1 + original bet
        
        elif self.bet_type == "low":
            return 1 <= number <= 18, 2  # 1:1 + original bet
        
        elif self.bet_type == "high":
            return 19 <= number <= 36, 2  # 1:1 + original bet
        
        elif self.bet_type == "number":
            return number == self.bet_value, 36  # 35:1 + original bet
        
        return False, 0
    
    def format_result(self) -> str:
        """Format the spin result."""
        color = self.get_number_color(self.result_number)
        return f"🎰 **{self.result_number}** ({color})"
    
    def format_bet(self) -> str:
        """Format the current bet."""
        if self.bet_type == "number":
            return f"{self.bet_value}"
        else:
            bet_names = {
                "red": "🔴 Red",
                "black": "⚫ Black", 
                "odd": "📊 Odd",
                "even": "📈 Even",
                "low": "⬇️ Low (1-18)",
                "high": "⬆️ High (19-36)"
            }
            return bet_names.get(self.bet_type, self.bet_type)


# Global game instances per user
roulette_games = {}


def get_game(user_id: int) -> RouletteGame:
    """Get or create game instance for user."""
    if user_id not in roulette_games:
        roulette_games[user_id] = RouletteGame()
    return roulette_games[user_id]


@router.callback_query(F.data == "game_roulette")
async def start_roulette(callback: CallbackQuery, state: FSMContext):
    """Start roulette game - ask for bet."""
    await state.set_state(RouletteStates.waiting_for_bet)
    await state.update_data(game_type="roulette")
    
    user_balance = await db.get_balance(callback.from_user.id)
    
    text = (
        f"🎰 **European Roulette**\n\n"
        f"💰 Your balance: {user_balance:,} chips\n\n"
        f"Place your bet to start!\n"
        f"Min bet: {config.MIN_BET}, Max bet: {config.MAX_BET:,}"
    )
    
    await callback.message.edit_text(text, reply_markup=bet_amount_keyboard())


@router.callback_query(RouletteStates.waiting_for_bet, F.data.startswith("bet_"))
async def process_bet(callback: CallbackQuery, state: FSMContext):
    """Process bet amount selection."""
    bet_data = callback.data.split("_")[1]
    
    if bet_data == "custom":
        await state.set_state(RouletteStates.waiting_for_custom_bet)
        await callback.message.edit_text(
            f"Enter your custom bet amount ({config.MIN_BET}-{config.MAX_BET:,}):"
        )
        return
    
    try:
        bet_amount = int(bet_data)
    except ValueError:
        await callback.answer("Invalid bet amount!")
        return
    
    await finalize_bet(callback, state, bet_amount)


@router.message(RouletteStates.waiting_for_custom_bet)
async def process_custom_bet(message: Message, state: FSMContext):
    """Process custom bet amount."""
    try:
        bet_amount = int(message.text)
    except ValueError:
        await message.reply("Please enter a valid number!")
        return
    
    # Delete the user's message
    await message.delete()
    
    await finalize_bet(message, state, bet_amount, is_message=True)


async def finalize_bet(update, state: FSMContext, bet_amount: int, is_message: bool = False):
    """Finalize bet amount and ask for bet type."""
    user_id = update.from_user.id
    user_balance = await db.get_balance(user_id)
    
    # Validate bet
    if bet_amount < config.MIN_BET:
        text = f"❌ Minimum bet is {config.MIN_BET} chips!"
        if is_message:
            await update.answer(text)
        else:
            await update.answer(text, show_alert=True)
        return
    
    if bet_amount > config.MAX_BET:
        text = f"❌ Maximum bet is {config.MAX_BET:,} chips!"
        if is_message:
            await update.answer(text)
        else:
            await update.answer(text, show_alert=True)
        return
    
    if bet_amount > user_balance:
        text = f"❌ Insufficient balance! You have {user_balance:,} chips."
        if is_message:
            await update.answer(text)
        else:
            await update.answer(text, show_alert=True)
        return
    
    # Store bet amount and ask for bet type
    await state.update_data(bet_amount=bet_amount)
    await state.set_state(RouletteStates.waiting_for_bet_type)
    
    text = (
        f"🎰 **European Roulette**\n\n"
        f"💰 Bet amount: {bet_amount:,} chips\n\n"
        f"Choose your bet type:"
    )
    
    if is_message:
        await update.answer(text, reply_markup=roulette_bet_type_keyboard())
    else:
        await update.message.edit_text(text, reply_markup=roulette_bet_type_keyboard())


@router.callback_query(RouletteStates.waiting_for_bet_type, F.data.startswith("roulette_"))
async def process_bet_type(callback: CallbackQuery, state: FSMContext):
    """Process bet type selection."""
    bet_type = callback.data.split("_")[1]
    data = await state.get_data()
    bet_amount = data["bet_amount"]
    
    if bet_type == "number":
        await state.set_state(RouletteStates.waiting_for_number)
        await callback.message.edit_text(
            f"🎯 **Single Number Bet**\n\n"
            f"💰 Bet: {bet_amount:,} chips\n"
            f"🎁 Payout: 35:1\n\n"
            f"Enter a number (0-36):"
        )
        return
    
    # Direct bet types (red, black, odd, even, low, high)
    await execute_roulette_bet(callback, state, bet_type, bet_amount)


@router.message(RouletteStates.waiting_for_number)
async def process_number_bet(message: Message, state: FSMContext):
    """Process number bet."""
    try:
        number = int(message.text)
    except ValueError:
        await message.reply("Please enter a valid number (0-36)!")
        return
    
    if not (0 <= number <= 36):
        await message.reply("Number must be between 0 and 36!")
        return
    
    # Delete the user's message
    await message.delete()
    
    data = await state.get_data()
    bet_amount = data["bet_amount"]
    
    await execute_roulette_bet(message, state, "number", bet_amount, number, is_message=True)


async def execute_roulette_bet(update, state: FSMContext, bet_type: str, bet_amount: int, bet_value: int = None, is_message: bool = False):
    """Execute the roulette bet and show result."""
    user_id = update.from_user.id
    
    # Deduct bet from balance
    await db.add_balance(user_id, -bet_amount)
    
    # Set up game
    game = get_game(user_id)
    game.bet_amount = bet_amount
    game.bet_type = bet_type
    game.bet_value = bet_value
    
    # Spin the wheel
    result_number = game.spin()
    
    # Check win and calculate payout
    is_win, payout_multiplier = game.check_win()
    winnings = int(bet_amount * payout_multiplier) if is_win else 0
    
    if winnings > 0:
        await db.add_balance(user_id, winnings)
    
    new_balance = await db.get_balance(user_id)
    
    # Format result message
    result_emoji = "🎉" if is_win else "😔"
    win_text = "You win!" if is_win else "You lose!"
    
    text = (
        f"🎰 **European Roulette**\n\n"
        f"💰 Bet: {bet_amount:,} chips on {game.format_bet()}\n\n"
        f"{game.format_result()}\n\n"
        f"{result_emoji} {win_text}\n"
        f"💰 Winnings: {winnings:,} chips\n"
        f"💳 Balance: {new_balance:,} chips"
    )
    
    if is_message:
        await update.answer(text, reply_markup=game_end_keyboard())
    else:
        await update.message.edit_text(text, reply_markup=game_end_keyboard())
    
    await state.clear()