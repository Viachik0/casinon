#!/usr/bin/env python3
"""
Test script to verify bot functionality without starting it.
This validates all components work together correctly.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_bot_components():
    """Test all bot components."""
    print("🤖 Testing Telegram Casino Bot Components...")
    print("=" * 50)
    
    try:
        # Test 1: Configuration
        print("1. Testing configuration...")
        os.environ['TELEGRAM_BOT_TOKEN'] = '1234567890:TEST_TOKEN_FOR_VALIDATION'
        from config import config
        config.validate()
        print(f"   ✅ Starting balance: {config.STARTING_BALANCE:,}")
        print(f"   ✅ Daily bonus: {config.DAILY_BONUS_AMOUNT:,}")
        print(f"   ✅ Bet limits: {config.MIN_BET:,} - {config.MAX_BET:,}")
        
        # Test 2: Database
        print("\n2. Testing database...")
        from storage.db import db
        await db.init_db()
        
        # Test user operations
        user_id = 999999
        balance, _ = await db.get_or_create_user(user_id)
        print(f"   ✅ User created with balance: {balance:,}")
        
        new_balance = await db.add_balance(user_id, -100)
        print(f"   ✅ After bet: {new_balance:,}")
        
        success, final_balance = await db.claim_bonus(user_id)
        print(f"   ✅ Bonus claimed: {success}, balance: {final_balance:,}")
        
        # Test 3: RNG and Games
        print("\n3. Testing random number generation...")
        from services.rng import rng
        random_numbers = [rng.randint(1, 100) for _ in range(5)]
        print(f"   ✅ Secure random numbers: {random_numbers}")
        
        # Test 4: Card System
        print("\n4. Testing card system...")
        from services.deck import BlackjackShoe, SingleDeck, Hand, Card
        
        # Test blackjack shoe
        shoe = BlackjackShoe()
        print(f"   ✅ Blackjack shoe: {shoe.cards_left} cards")
        
        # Test hand evaluation
        hand = Hand()
        hand.add_card(Card('A', '♠️'))
        hand.add_card(Card('K', '♥️'))
        print(f"   ✅ Blackjack hand: {hand} = {hand.value} (blackjack: {hand.is_blackjack})")
        
        # Test 5: Game Logic
        print("\n5. Testing game engines...")
        
        # Blackjack
        from games.blackjack import BlackjackGame
        bj_game = BlackjackGame()
        bj_game.start_new_round(100)
        print(f"   ✅ Blackjack: Player {bj_game.player_hand.value}, Dealer {bj_game.dealer_hand.value}")
        
        # Simple 21
        from games.simple21 import Simple21Game
        s21_game = Simple21Game()
        s21_game.start_new_round(50)
        print(f"   ✅ Simple 21: Player {s21_game.player_hand.value}, Dealer {s21_game.dealer_hand.value}")
        
        # Roulette
        from games.roulette import RouletteGame
        roulette_game = RouletteGame()
        roulette_game.bet_type = "red"
        roulette_game.bet_amount = 25
        spin = roulette_game.spin()
        is_win, payout = roulette_game.check_win()
        print(f"   ✅ Roulette: Spin {spin} ({roulette_game.get_number_color(spin)}), Win: {is_win}")
        
        # Test 6: UI Components
        print("\n6. Testing UI components...")
        from ui.keyboards import main_menu_keyboard, bet_amount_keyboard, roulette_bet_type_keyboard
        
        main_kb = main_menu_keyboard()
        bet_kb = bet_amount_keyboard()
        roulette_kb = roulette_bet_type_keyboard()
        
        print(f"   ✅ Main menu: {len(main_kb.inline_keyboard)} rows")
        print(f"   ✅ Bet selection: {len(bet_kb.inline_keyboard)} rows")
        print(f"   ✅ Roulette bets: {len(roulette_kb.inline_keyboard)} rows")
        
        # Test 7: Bot Framework
        print("\n7. Testing bot framework...")
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        # Create bot instance (won't connect with fake token)
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Import routers
        from games import blackjack, simple21, roulette
        
        print("   ✅ Bot instance created")
        print("   ✅ Dispatcher with memory storage")
        print("   ✅ All game routers imported")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("\n📋 Bot is ready for deployment with a real Telegram bot token!")
        print("\n🚀 To start the bot:")
        print("   1. Get a bot token from @BotFather on Telegram")
        print("   2. Copy .env.example to .env")
        print("   3. Set TELEGRAM_BOT_TOKEN in .env")
        print("   4. Run: python bot.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_bot_components())
    sys.exit(0 if success else 1)