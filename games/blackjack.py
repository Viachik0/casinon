"""Blackjack game implementation with FSM."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Optional

from services.deck import BlackjackShoe, Hand
from storage.db import db
from ui.keyboards import (
    bet_amount_keyboard, blackjack_action_keyboard, 
    game_end_keyboard, main_menu_keyboard
)
from config import config

router = Router()


class BlackjackStates(StatesGroup):
    """States for blackjack game flow."""
    waiting_for_bet = State()
    waiting_for_custom_bet = State()
    playing = State()


class BlackjackGame:
    """Blackjack game engine."""
    
    def __init__(self):
        self.shoe = BlackjackShoe()
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.bet_amount = 0
    
    def start_new_round(self, bet: int) -> None:
        """Start a new blackjack round."""
        self.bet_amount = bet
        self.player_hand.clear()
        self.dealer_hand.clear()
        
        # Deal initial cards
        self.player_hand.add_card(self.shoe.deal_card())
        self.dealer_hand.add_card(self.shoe.deal_card())
        self.player_hand.add_card(self.shoe.deal_card())
        self.dealer_hand.add_card(self.shoe.deal_card())  # Second dealer card
    
    def hit_player(self) -> None:
        """Player takes another card."""
        self.player_hand.add_card(self.shoe.deal_card())
    
    def play_dealer(self) -> None:
        """Dealer plays according to rules (hit until 17)."""
        while self.dealer_hand.value < 17:
            self.dealer_hand.add_card(self.shoe.deal_card())
    
    def get_result(self) -> tuple[str, int]:
        """
        Get game result and payout multiplier.
        Returns (result_text, payout_multiplier).
        """
        player_value = self.player_hand.value
        dealer_value = self.dealer_hand.value
        
        # Player bust
        if self.player_hand.is_bust:
            return "Player busts! Dealer wins.", 0
        
        # Player blackjack
        if self.player_hand.is_blackjack:
            if self.dealer_hand.is_blackjack:
                return "Both have blackjack! Push.", 1  # Return bet
            else:
                return "Blackjack! Player wins!", 2.5  # 3:2 payout
        
        # Dealer blackjack (player doesn't have it)
        if self.dealer_hand.is_blackjack:
            return "Dealer blackjack! Dealer wins.", 0
        
        # Dealer bust
        if self.dealer_hand.is_bust:
            return "Dealer busts! Player wins!", 2
        
        # Compare values
        if player_value > dealer_value:
            return "Player wins!", 2
        elif dealer_value > player_value:
            return "Dealer wins!", 0
        else:
            return "Push! It's a tie.", 1  # Return bet
    
    def format_hands(self, hide_dealer_card: bool = False) -> str:
        """Format hands for display."""
        player_str = f"🎰 Your hand: {self.player_hand} (Value: {self.player_hand.value})"
        
        if hide_dealer_card:
            # Show only first dealer card
            first_card = str(self.dealer_hand.cards[0]) if self.dealer_hand.cards else ""
            dealer_str = f"🎩 Dealer: {first_card} ❓"
        else:
            dealer_str = f"🎩 Dealer: {self.dealer_hand} (Value: {self.dealer_hand.value})"
        
        return f"{player_str}\n{dealer_str}"


# Global game instances per user (in production, use Redis or similar)
games = {}


def get_game(user_id: int) -> BlackjackGame:
    """Get or create game instance for user."""
    if user_id not in games:
        games[user_id] = BlackjackGame()
    return games[user_id]


@router.callback_query(F.data == "game_blackjack")
async def start_blackjack(callback: CallbackQuery, state: FSMContext):
    """Start blackjack game - ask for bet."""
    await state.set_state(BlackjackStates.waiting_for_bet)
    await state.update_data(game_type="blackjack")
    
    user_balance = await db.get_balance(callback.from_user.id)
    
    text = (
        f"🃏 **Blackjack**\n\n"
        f"💰 Your balance: {user_balance:,} chips\n\n"
        f"Place your bet to start!\n"
        f"Min bet: {config.MIN_BET}, Max bet: {config.MAX_BET:,}"
    )
    
    await callback.message.edit_text(text, reply_markup=bet_amount_keyboard())


@router.callback_query(BlackjackStates.waiting_for_bet, F.data.startswith("bet_"))
async def process_bet(callback: CallbackQuery, state: FSMContext):
    """Process bet amount selection."""
    bet_data = callback.data.split("_")[1]
    
    if bet_data == "custom":
        await state.set_state(BlackjackStates.waiting_for_custom_bet)
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


@router.message(BlackjackStates.waiting_for_custom_bet)
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
    """Finalize bet and start game."""
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
    
    # Deduct bet from balance
    await db.add_balance(user_id, -bet_amount)
    
    # Start game
    game = get_game(user_id)
    game.start_new_round(bet_amount)
    
    await state.set_state(BlackjackStates.playing)
    await state.update_data(bet_amount=bet_amount)
    
    # Check for immediate blackjack
    if game.player_hand.is_blackjack:
        result_text, payout_multiplier = game.get_result()
        winnings = int(bet_amount * payout_multiplier)
        await db.add_balance(user_id, winnings)
        new_balance = await db.get_balance(user_id)
        
        text = (
            f"🃏 **Blackjack**\n\n"
            f"{game.format_hands()}\n\n"
            f"🎉 {result_text}\n"
            f"💰 Winnings: {winnings:,} chips\n"
            f"💳 Balance: {new_balance:,} chips"
        )
        
        if is_message:
            await update.answer(text, reply_markup=game_end_keyboard())
        else:
            await update.message.edit_text(text, reply_markup=game_end_keyboard())
        
        await state.clear()
        return
    
    # Show game state
    text = (
        f"🃏 **Blackjack**\n\n"
        f"💰 Bet: {bet_amount:,} chips\n\n"
        f"{game.format_hands(hide_dealer_card=True)}\n\n"
        f"Choose your action:"
    )
    
    if is_message:
        await update.answer(text, reply_markup=blackjack_action_keyboard())
    else:
        await update.message.edit_text(text, reply_markup=blackjack_action_keyboard())


@router.callback_query(BlackjackStates.playing, F.data == "bj_hit")
async def hit_action(callback: CallbackQuery, state: FSMContext):
    """Player hits (takes another card)."""
    user_id = callback.from_user.id
    game = get_game(user_id)
    data = await state.get_data()
    bet_amount = data["bet_amount"]
    
    game.hit_player()
    
    # Check if player busts
    if game.player_hand.is_bust:
        result_text, payout_multiplier = game.get_result()
        winnings = int(bet_amount * payout_multiplier)
        if winnings > 0:
            await db.add_balance(user_id, winnings)
        
        new_balance = await db.get_balance(user_id)
        
        text = (
            f"🃏 **Blackjack**\n\n"
            f"{game.format_hands()}\n\n"
            f"💥 {result_text}\n"
            f"💰 Winnings: {winnings:,} chips\n"
            f"💳 Balance: {new_balance:,} chips"
        )
        
        await callback.message.edit_text(text, reply_markup=game_end_keyboard())
        await state.clear()
        return
    
    # Continue playing
    text = (
        f"🃏 **Blackjack**\n\n"
        f"💰 Bet: {bet_amount:,} chips\n\n"
        f"{game.format_hands(hide_dealer_card=True)}\n\n"
        f"Choose your action:"
    )
    
    await callback.message.edit_text(text, reply_markup=blackjack_action_keyboard())


@router.callback_query(BlackjackStates.playing, F.data == "bj_stand")
async def stand_action(callback: CallbackQuery, state: FSMContext):
    """Player stands - dealer plays and game resolves."""
    user_id = callback.from_user.id
    game = get_game(user_id)
    data = await state.get_data()
    bet_amount = data["bet_amount"]
    
    # Dealer plays
    game.play_dealer()
    
    # Get result
    result_text, payout_multiplier = game.get_result()
    winnings = int(bet_amount * payout_multiplier)
    if winnings > 0:
        await db.add_balance(user_id, winnings)
    
    new_balance = await db.get_balance(user_id)
    
    # Determine result emoji
    if "wins!" in result_text and "Player" in result_text:
        emoji = "🎉"
    elif "Push" in result_text:
        emoji = "🤝"
    else:
        emoji = "😔"
    
    text = (
        f"🃏 **Blackjack**\n\n"
        f"{game.format_hands()}\n\n"
        f"{emoji} {result_text}\n"
        f"💰 Winnings: {winnings:,} chips\n"
        f"💳 Balance: {new_balance:,} chips"
    )
    
    await callback.message.edit_text(text, reply_markup=game_end_keyboard())
    await state.clear()


@router.callback_query(F.data == "play_again")
async def play_again(callback: CallbackQuery, state: FSMContext):
    """Start another round of the same game."""
    data = await state.get_data()
    game_type = data.get("game_type", "blackjack")
    
    if game_type == "blackjack":
        await start_blackjack(callback, state)
    elif game_type == "21":
        # Will be handled by simple21.py
        from games.simple21 import start_simple21
        await start_simple21(callback, state)
    elif game_type == "roulette":
        # Will be handled by roulette.py
        from games.roulette import start_roulette
        await start_roulette(callback, state)