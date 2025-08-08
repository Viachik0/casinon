"""Main bot entry point."""
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from config import config
from storage.db import db
from ui.keyboards import main_menu_keyboard, balance_keyboard, back_to_menu_keyboard
from games import blackjack, simple21, roulette

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create bot and dispatcher
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Main router for common handlers
main_router = Router()


@main_router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    
    # Initialize user in database
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Player"
    balance, _ = await db.get_or_create_user(user_id)
    
    text = (
        f"🎰 **Welcome to Casino Bot, {user_name}!**\n\n"
        f"💰 Your balance: {balance:,} chips\n\n"
        f"Choose a game to play or check your balance:"
    )
    
    await message.answer(text, reply_markup=main_menu_keyboard())


@main_router.message(Command("help"))
async def help_command(message: Message, state: FSMContext):
    """Handle /help command."""
    await state.clear()
    await show_help(message)


@main_router.message(Command("balance"))
async def balance_command(message: Message, state: FSMContext):
    """Handle /balance command."""
    await state.clear()
    await show_balance(message)


@main_router.message(Command("bonus"))
async def bonus_command(message: Message, state: FSMContext):
    """Handle /bonus command."""
    await state.clear()
    await claim_bonus(message)


@main_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name or "Player"
    balance = await db.get_balance(user_id)
    
    text = (
        f"🎰 **Casino Bot Menu**\n\n"
        f"💰 Your balance: {balance:,} chips\n\n"
        f"Choose a game to play or check your balance:"
    )
    
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())


@main_router.callback_query(F.data == "balance")
async def balance_callback(callback: CallbackQuery, state: FSMContext):
    """Show balance screen."""
    await state.clear()
    await show_balance(callback.message, is_callback=True)


@main_router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery, state: FSMContext):
    """Show help screen."""
    await state.clear()
    await show_help(callback.message, is_callback=True)


@main_router.callback_query(F.data == "bonus")
async def bonus_callback(callback: CallbackQuery, state: FSMContext):
    """Claim daily bonus."""
    await state.clear()
    await claim_bonus(callback.message, is_callback=True)


async def show_balance(message, is_callback: bool = False):
    """Show user balance with quick bet options."""
    user_id = message.chat.id if not is_callback else message.chat.id
    if is_callback:
        user_id = message.chat.id
    else:
        user_id = message.from_user.id
    
    balance = await db.get_balance(user_id)
    
    text = (
        f"💰 **Your Balance**\n\n"
        f"💳 Current balance: {balance:,} chips\n\n"
        f"Use quick bet buttons to start playing:"
    )
    
    if is_callback:
        await message.edit_text(text, reply_markup=balance_keyboard())
    else:
        await message.answer(text, reply_markup=balance_keyboard())


async def show_help(message, is_callback: bool = False):
    """Show help information."""
    text = (
        f"ℹ️ **Casino Bot Help**\n\n"
        f"**Available Games:**\n"
        f"🃏 **Blackjack** - Classic 21 with 3:2 blackjack bonus\n"
        f"♠️ **Simple 21** - Get to 21, all wins pay 1:1\n"
        f"🎰 **Roulette** - European roulette with single zero\n\n"
        f"**Commands:**\n"
        f"/start - Show main menu\n"
        f"/balance - Check your balance\n"
        f"/bonus - Claim daily bonus\n"
        f"/help - Show this help\n\n"
        f"**Economy:**\n"
        f"💰 Starting balance: {config.STARTING_BALANCE:,} chips\n"
        f"🎁 Daily bonus: {config.DAILY_BONUS_AMOUNT:,} chips every {config.DAILY_BONUS_COOLDOWN_HOURS}h\n"
        f"📊 Bet limits: {config.MIN_BET:,} - {config.MAX_BET:,} chips\n\n"
        f"**Roulette Payouts:**\n"
        f"• Red/Black/Odd/Even/Low/High: 1:1\n"
        f"• Single number: 35:1\n\n"
        f"Good luck! 🍀"
    )
    
    if is_callback:
        await message.edit_text(text, reply_markup=back_to_menu_keyboard())
    else:
        await message.answer(text, reply_markup=back_to_menu_keyboard())


async def claim_bonus(message, is_callback: bool = False):
    """Handle bonus claiming."""
    user_id = message.chat.id if is_callback else message.from_user.id
    
    success, new_balance = await db.claim_bonus(user_id)
    
    if success:
        text = (
            f"🎁 **Daily Bonus Claimed!**\n\n"
            f"✅ You received {config.DAILY_BONUS_AMOUNT:,} chips!\n"
            f"💳 New balance: {new_balance:,} chips\n\n"
            f"Come back in {config.DAILY_BONUS_COOLDOWN_HOURS} hours for your next bonus!"
        )
    else:
        cooldown_remaining = await db.get_bonus_cooldown_remaining(user_id)
        hours_remaining = cooldown_remaining // 3600
        minutes_remaining = (cooldown_remaining % 3600) // 60
        
        text = (
            f"🎁 **Daily Bonus**\n\n"
            f"❌ Bonus already claimed today!\n"
            f"💳 Current balance: {new_balance:,} chips\n\n"
            f"⏰ Next bonus available in: {hours_remaining}h {minutes_remaining}m"
        )
    
    if is_callback:
        await message.edit_text(text, reply_markup=back_to_menu_keyboard())
    else:
        await message.answer(text, reply_markup=back_to_menu_keyboard())


# Handle quick bet callbacks from balance screen
@main_router.callback_query(F.data.startswith("quick_bet_"))
async def quick_bet_callback(callback: CallbackQuery, state: FSMContext):
    """Handle quick bet selections from balance screen."""
    bet_amount = int(callback.data.split("_")[2])
    
    # Show game selection with pre-selected bet
    await state.update_data(quick_bet=bet_amount)
    
    text = (
        f"💰 **Quick Bet: {bet_amount:,} chips**\n\n"
        f"Choose your game:"
    )
    
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())


async def main():
    """Main function to start the bot."""
    try:
        # Validate configuration
        config.validate()
        
        # Initialize database
        await db.init_db()
        
        # Register routers
        dp.include_router(main_router)
        dp.include_router(blackjack.router)
        dp.include_router(simple21.router)
        dp.include_router(roulette.router)
        
        logger.info("Starting casino bot...")
        
        # Start polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())