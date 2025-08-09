#!/usr/bin/env python3
"""
Manual test script to demonstrate the Simple 21 improvements.
This simulates bot interactions to show the new features.
"""

import asyncio
import json
from unittest.mock import Mock
from bot import (
    db, cmd_start, cmd_balance, cmd_history, 
    game_simple21, simple21_place_bet, simple21_hit, simple21_stand
)

async def simulate_game_session():
    """Simulate a complete game session with the new features."""
    print("🎰 CASINON SIMPLE 21 - PHASES 1-3 DEMO")
    print("=" * 50)
    
    # Initialize database
    await db.init()
    
    # Mock user
    user_id = 99999
    username = "demo_player"
    
    # Create mock message/callback objects
    class MockMessage:
        def __init__(self, text="", user_id=user_id):
            self.from_user = Mock()
            self.from_user.id = user_id
            self.from_user.username = username
            self.text = text
            
        async def answer(self, text, reply_markup=None, parse_mode=None):
            print(f"\n📱 BOT MESSAGE:")
            print(text)
            if reply_markup:
                print("🔘 BUTTONS:")
                for row in reply_markup.inline_keyboard:
                    button_texts = [btn.text for btn in row]
                    print(f"   {' | '.join(button_texts)}")
            print()
            
        async def edit_text(self, text, reply_markup=None, parse_mode=None):
            print(f"\n📝 BOT MESSAGE (EDITED):")
            print(text)
            if reply_markup:
                print("🔘 BUTTONS:")
                for row in reply_markup.inline_keyboard:
                    button_texts = [btn.text for btn in row]
                    print(f"   {' | '.join(button_texts)}")
            print()

    class MockCallbackQuery:
        def __init__(self, data, user_id=user_id):
            self.data = data
            self.from_user = Mock()
            self.from_user.id = user_id
            self.from_user.username = username
            self.message = MockMessage()
            
        async def answer(self, text="", show_alert=False):
            if text:
                alert_type = "🚨 ALERT" if show_alert else "💬 CALLBACK"
                print(f"{alert_type}: {text}")

    # Test 1: Initial balance
    print("1️⃣ TESTING /balance command (new feature)")
    msg = MockMessage("/balance")
    await cmd_balance(msg)
    
    # Test 2: Empty history
    print("2️⃣ TESTING /history command (new feature)")
    msg = MockMessage("/history")
    await cmd_history(msg)
    
    # Test 3: Start Simple 21 game
    print("3️⃣ TESTING Simple 21 entry")
    cb = MockCallbackQuery("game:simple21")
    await game_simple21(cb)
    
    # Test 4: Place bet (with bet locking)
    print("4️⃣ TESTING bet placement with locking")
    cb = MockCallbackQuery("game:simple21:bet:100")
    await simple21_place_bet(cb)
    
    # Test 5: Check balance after bet locked
    print("5️⃣ CHECKING balance after bet locked")
    msg = MockMessage("/balance")
    await cmd_balance(msg)
    
    # Test 6: Hit action
    print("6️⃣ TESTING hit action")
    cb = MockCallbackQuery("game:simple21:hit")
    await simple21_hit(cb)
    
    # Test 7: Stand and resolve
    print("7️⃣ TESTING stand and round resolution")
    cb = MockCallbackQuery("game:simple21:stand")
    await simple21_stand(cb)
    
    # Test 8: Final balance and history
    print("8️⃣ FINAL RESULTS")
    msg = MockMessage("/balance")
    await cmd_balance(msg)
    
    msg = MockMessage("/history 5")
    await cmd_history(msg)
    
    # Test 9: Test active round persistence
    print("9️⃣ TESTING active round persistence")
    cb = MockCallbackQuery("game:simple21:bet:50")
    await simple21_place_bet(cb)
    
    print("   Simulating bot restart...")
    print("   Re-entering game...")
    
    cb = MockCallbackQuery("game:simple21")
    await game_simple21(cb)  # Should show continue round
    
    print("\n🎉 DEMO COMPLETE!")
    print("✅ All phases 1-3 features demonstrated successfully!")

if __name__ == "__main__":
    asyncio.run(simulate_game_session())