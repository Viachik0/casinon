"""Inline keyboards for the casino bot UI."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu with all available options."""
    keyboard = [
        [
            InlineKeyboardButton(text="🎰 Roulette", callback_data="game_roulette"),
            InlineKeyboardButton(text="🃏 Blackjack", callback_data="game_blackjack")
        ],
        [
            InlineKeyboardButton(text="♠️ 21", callback_data="game_21"),
            InlineKeyboardButton(text="💰 Balance", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="🎁 Bonus", callback_data="bonus"),
            InlineKeyboardButton(text="ℹ️ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def bet_amount_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting bet amounts."""
    keyboard = [
        [
            InlineKeyboardButton(text="💰 10", callback_data="bet_10"),
            InlineKeyboardButton(text="💰 50", callback_data="bet_50")
        ],
        [
            InlineKeyboardButton(text="💰 100", callback_data="bet_100"),
            InlineKeyboardButton(text="💰 500", callback_data="bet_500")
        ],
        [
            InlineKeyboardButton(text="✏️ Custom", callback_data="bet_custom")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def blackjack_action_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for blackjack actions."""
    keyboard = [
        [
            InlineKeyboardButton(text="🎯 Hit", callback_data="bj_hit"),
            InlineKeyboardButton(text="✋ Stand", callback_data="bj_stand")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def game_end_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after game ends."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔄 Play Again", callback_data="play_again"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def roulette_bet_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting roulette bet type."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔴 Red", callback_data="roulette_red"),
            InlineKeyboardButton(text="⚫ Black", callback_data="roulette_black")
        ],
        [
            InlineKeyboardButton(text="📊 Odd", callback_data="roulette_odd"),
            InlineKeyboardButton(text="📈 Even", callback_data="roulette_even")
        ],
        [
            InlineKeyboardButton(text="⬇️ Low (1-18)", callback_data="roulette_low"),
            InlineKeyboardButton(text="⬆️ High (19-36)", callback_data="roulette_high")
        ],
        [
            InlineKeyboardButton(text="🎯 Number", callback_data="roulette_number")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def balance_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for balance screen with quick bet presets."""
    keyboard = [
        [
            InlineKeyboardButton(text="Quick Bet: 💰 10", callback_data="quick_bet_10"),
            InlineKeyboardButton(text="Quick Bet: 💰 50", callback_data="quick_bet_50")
        ],
        [
            InlineKeyboardButton(text="Quick Bet: 💰 100", callback_data="quick_bet_100"),
            InlineKeyboardButton(text="Quick Bet: 💰 500", callback_data="quick_bet_500")
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def confirm_bet_keyboard() -> InlineKeyboardMarkup:
    """Keyboard to confirm bet before playing."""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_bet"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back to menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)