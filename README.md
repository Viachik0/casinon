# Casino Telegram Bot

A feature-rich Telegram casino bot built with Python, offering three exciting games: Blackjack, Simplified 21, and European Roulette. The bot includes a complete economy system with daily bonuses, secure random number generation, and an intuitive inline keyboard interface.

## Features

### 🎮 Games
- **🃏 Blackjack**: Classic blackjack with 6-deck shoe, 3:2 natural blackjack payout, and standard dealer rules
- **♠️ Simple 21**: Simplified version of blackjack with 1:1 payouts and no blackjack bonus
- **🎰 European Roulette**: Single-zero roulette with various bet types (Red/Black, Odd/Even, Low/High, Single Number)

### 💰 Economy System
- Starting balance: 1,000 chips for new users
- Daily bonus: 500 chips every 24 hours
- Configurable bet limits (default: 10 - 100,000 chips)
- SQLite database for persistent user data

### 🔐 Security
- Cryptographically secure random number generation using `secrets.SystemRandom`
- Secure card shuffling and roulette spins
- Input validation and balance checks

### 🎨 User Interface
- Clean, emoji-rich inline keyboard interface
- Responsive game flow with FSM state management
- Quick bet presets and custom bet options
- Detailed game results and balance updates

## Tech Stack

- **Python 3.10+**
- **aiogram v3**: Async Telegram bot framework
- **aiosqlite**: Async SQLite database operations
- **python-dotenv**: Environment configuration
- **secrets**: Cryptographically secure random number generation

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher
- A Telegram bot token (get one from [@BotFather](https://t.me/BotFather))

### 2. Installation

Clone the repository:
```bash
git clone <repository-url>
cd casinon
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# Required: Get this from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: Economy settings (defaults shown)
STARTING_BALANCE=1000
DAILY_BONUS_AMOUNT=500
DAILY_BONUS_COOLDOWN_HOURS=24
MIN_BET=10
MAX_BET=100000

# Optional: Database path
DATABASE_PATH=casino.db
```

### 4. Running the Bot

Start the bot:
```bash
python bot.py
```

The bot will automatically:
- Validate your configuration
- Initialize the SQLite database
- Start polling for Telegram messages

## Usage

### Commands
- `/start` - Show the main menu and initialize your account
- `/balance` - Check your current balance with quick bet options
- `/bonus` - Claim your daily bonus (if available)
- `/help` - Display help information and game rules

### Game Flow

1. **Start**: Use `/start` to access the main menu
2. **Choose Game**: Select from Blackjack, Simple 21, or Roulette
3. **Place Bet**: Choose from preset amounts or enter a custom bet
4. **Play**: 
   - **Blackjack/21**: Hit or Stand to play your hand
   - **Roulette**: Choose bet type (Red/Black/Odd/Even/etc.) and spin
5. **Results**: View results, winnings, and updated balance
6. **Continue**: Play again or return to main menu

### Game Rules

#### 🃏 Blackjack
- 6-deck shoe with automatic shuffling when low
- Goal: Get as close to 21 as possible without going over
- Card values: 2-10 = face value, J/Q/K = 10, Ace = 1 or 11
- Natural blackjack (21 with 2 cards) pays 3:2
- Regular wins pay 1:1
- Dealer hits until 17 (including soft 17)
- Player actions: Hit, Stand

#### ♠️ Simple 21
- Single deck with automatic reshuffling
- Same rules as Blackjack but all wins pay 1:1 (no blackjack bonus)
- Simplified version for faster gameplay

#### 🎰 European Roulette
- Single zero (0-36) for better odds than American roulette
- **Even-chance bets** (1:1 payout):
  - Red/Black
  - Odd/Even  
  - Low (1-18) / High (19-36)
- **Single number bet** (35:1 payout):
  - Choose any number 0-36

## Project Structure

```
casinon/
├── bot.py                 # Main bot entry point
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
├── storage/
│   └── db.py            # Database operations
├── services/
│   ├── rng.py           # Secure random number generation
│   └── deck.py          # Card deck utilities
├── ui/
│   └── keyboards.py     # Inline keyboard layouts
└── games/
    ├── blackjack.py     # Blackjack game logic
    ├── simple21.py      # Simple 21 game logic
    └── roulette.py      # Roulette game logic
```

## Development

### Adding New Games
1. Create a new game module in `games/`
2. Implement FSM states for game flow
3. Add game logic and handlers
4. Register the router in `bot.py`
5. Add UI elements to `ui/keyboards.py`

### Database Schema
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,        -- Telegram user ID
    balance INTEGER NOT NULL,      -- User's chip balance
    last_bonus_at INTEGER NULL     -- Unix timestamp of last bonus claim
);
```

## Security Features

- **Cryptographic RNG**: All randomness uses `secrets.SystemRandom`
- **Input Validation**: Comprehensive validation of bets and user input
- **Balance Verification**: Prevents betting more than available balance
- **Rate Limiting**: Daily bonus cooldown prevents abuse

## Troubleshooting

### Common Issues

1. **Bot doesn't respond**:
   - Check your `TELEGRAM_BOT_TOKEN` in `.env`
   - Ensure the bot is not already running elsewhere
   - Verify your Python version (3.10+ required)

2. **Database errors**:
   - Check file permissions for the database path
   - Ensure the directory exists for the database file

3. **Import errors**:
   - Verify all dependencies are installed: `pip install -r requirements.txt`
   - Check Python path and virtual environment

### Logs
The bot logs important events to the console. Check the output for error messages and debugging information.

## License

This project is a test implementation for educational purposes. Feel free to modify and extend it for your needs.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Disclaimer

This is a test casino bot for educational purposes. No real money is involved. Please gamble responsibly if you modify this for real-world use.