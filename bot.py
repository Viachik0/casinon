import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import get_settings
from storage.db import Database
from ui.keyboards import back_menu_kb, main_menu_kb

settings = get_settings()
# Initialize DB with configured starting balance
db = Database(settings.db_path, starting_balance=settings.starting_balance)

router = Router()

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
    await cb.message.edit_text("Choose a game:", reply_markup=main_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "game:blackjack")
async def game_blackjack(cb: CallbackQuery):
    await cb.message.edit_text("🃏 Blackjack — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "game:simple21")
async def game_simple21(cb: CallbackQuery):
    await cb.message.edit_text("2️⃣1️⃣ Simple 21 — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()

@router.callback_query(F.data == "game:roulette")
async def game_roulette(cb: CallbackQuery):
    await cb.message.edit_text("🎡 Roulette — coming soon!", reply_markup=back_menu_kb())
    await cb.answer()

async def main():
    await db.init()
    bot = Bot(token=settings.bot_token, parse_mode="HTML")
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
