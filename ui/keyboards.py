from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Blackjack", callback_data="game:blackjack")
    kb.button(text="21", callback_data="game:simple21")
    kb.button(text="Roulette", callback_data="game:roulette")
    kb.adjust(2, 1)
    return kb.as_markup()

def back_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back to menu", callback_data="nav:menu")
    return kb.as_markup()

def blackjack_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Hit", callback_data="bj:hit")
    kb.button(text="Stand", callback_data="bj:stand")
    kb.button(text="⬅️ Menu", callback_data="nav:menu")
    kb.adjust(2, 1)
    return kb.as_markup()

def simple21_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Hit", callback_data="s21:hit")
    kb.button(text="Stop", callback_data="s21:stop")
    kb.button(text="⬅️ Menu", callback_data="nav:menu")
    kb.adjust(2, 1)
    return kb.as_markup()

def roulette_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Red", callback_data="rl:bet:color:red")
    kb.button(text="Black", callback_data="rl:bet:color:black")
    kb.button(text="Even", callback_data="rl:bet:parity:even")
    kb.button(text="Odd", callback_data="rl:bet:parity:odd")
    kb.button(text="Pick number", callback_data="rl:bet:number")
    kb.button(text="⬅️ Menu", callback_data="nav:menu")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()
