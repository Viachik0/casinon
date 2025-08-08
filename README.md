# Casinon — Telegram Casino Bot (aiogram v3)

A simple Telegram casino bot featuring Blackjack, 21 (simplified), and Roulette, built with aiogram v3, aiosqlite, and dotenv.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # on Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   - Copy `.env.example` to `.env`
   - Set `TELEGRAM_BOT_TOKEN` to your token from BotFather
   - Optionally adjust `DATABASE_PATH` (default: `data/casino.db`)
   - You can also tweak: `STARTING_BALANCE`, `DAILY_BONUS_AMOUNT`, `DAILY_BONUS_COOLDOWN_HOURS`, `MIN_BET`, `MAX_BET`

4. Run the bot:

   ```bash
   python bot.py
   ```

## Project Structure

```
casinon/
├─ bot.py
├─ config.py
├─ requirements.txt
├─ .env.example
├─ storage/
│  └─ db.py
├─ services/
│  ├─ rng.py
│  └─ deck.py
├─ ui/
│  └─ keyboards.py
└─ games/
   ├─ blackjack.py
   ├─ simple21.py
   └─ roulette.py
```

## Roadmap (from PR checklist)
- [x] Create project structure and dependencies (requirements.txt, .env.example)
- [x] Implement configuration management (config.py)
- [x] Create database layer (storage/db.py)
- [x] Implement RNG and card deck services (services/rng.py, services/deck.py)
- [x] Create UI keyboards (ui/keyboards.py)
- [x] Implement Blackjack game (games/blackjack.py)
- [x] Implement 21 simplified game (games/simple21.py)
- [x] Implement Roulette game (games/roulette.py)
- [x] Create main bot entry point (bot.py)
- [x] Update README with setup instructions
- [ ] Test bot functionality
- [ ] Verify all features work as specified
