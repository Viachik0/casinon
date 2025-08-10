# games/simple21.py
import random
import json
import asyncio
from typing import Dict, Tuple, Any, List

# Try to reuse services.cards if available (your repo had it).
try:
    from services.cards import format_hand_with_total, calculate_hand_value, SUITS, HIDDEN_CARD
except Exception:
    # Minimal fallbacks if services.cards isn't available.
    SUITS = ["♠", "♥", "♦", "♣"]
    HIDDEN_CARD = "🂠"

    def calculate_hand_value(cards: List[str]) -> int:
        total = 0
        aces = 0
        for c in cards:
            rank = c[:-1] if len(c) > 1 else c
            if rank in ("J", "Q", "K"):
                total += 10
            elif rank == "A":
                aces += 1
                total += 11
            else:
                total += int(rank)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def format_hand_with_total(cards: List[str]) -> str:
        if not cards:
            return ""
        return f"{' '.join(cards)} (total: {calculate_hand_value(cards)})"


CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def draw_card() -> str:
    """Return single-rank + random suit for display consistency with blackjack."""
    rank = random.choice(CARD_RANKS)
    suit = random.choice(SUITS)
    return f"{rank}{suit}"


def new_round_state(bet: int) -> Dict[str, Any]:
    """Create initial JSON-serializable state for simple21."""
    player = [draw_card(), draw_card()]
    dealer = [draw_card()]  # dealer second card is not in state until stand
    state = {
        "player": player,
        "dealer": dealer,
        "bet": bet,
        "finished": False,
        "result": None,
    }
    return state


def player_hit_logic(state: Dict[str, Any]) -> Tuple[Dict[str, Any], str, bool]:
    """Add a card to player, evaluate, and return (state, text, finished)."""
    state["player"].append(draw_card())
    total = calculate_hand_value(state["player"])
    bet = state["bet"]

    if total > 21:
        state["finished"] = True
        state["result"] = "loss"
        text = (
            f"💥 <b>BUST!</b>\n\n"
            f"🃏 <b>Your hand:</b> {format_hand_with_total(state['player'])}\n"
            f"🀫 <b>Dealer hand:</b> {format_hand_with_total(state['dealer'])}\n\n"
            f"❌ <b>Result:</b> Lost {bet} credits."
        )
        return state, text, True

    text = (
        f"2️⃣1️⃣ <b>Simple 21</b>\n"
        f"💵 <b>Bet:</b> {bet} credits\n\n"
        f"🃏 <b>Your hand:</b> {format_hand_with_total(state['player'])}\n"
        f"🀫 <b>Dealer shows:</b> {format_hand_with_total(state['dealer']) if len(state['dealer'])==1 else format_hand_with_total(state['dealer'])}"
    )
    return state, text, False


def player_stand_logic(state: Dict[str, Any]) -> Tuple[Dict[str, Any], str, bool]:
    """Dealer reveals second card and draws to 17+. Then produce final text."""
    # reveal dealer second card and draw until >=17
    dealer = state.get("dealer", [])[:]
    while calculate_hand_value(dealer) < 17:
        dealer.append(draw_card())

    player_total = calculate_hand_value(state["player"])
    dealer_total = calculate_hand_value(dealer)
    bet = state["bet"]

    if dealer_total > 21 or player_total > dealer_total:
        result = "win"
        outcome_text = f"🏆 <b>YOU WIN!</b> You won {bet} credits!"
    elif player_total < dealer_total:
        result = "loss"
        outcome_text = f"💸 <b>YOU LOSE!</b> You lost {bet} credits."
    else:
        result = "push"
        outcome_text = f"🤝 <b>PUSH!</b> Bet returned."

    state["dealer"] = dealer
    state["finished"] = True
    state["result"] = result

    text = (
        f"{outcome_text}\n\n"
        f"🃏 <b>Your hand:</b> {format_hand_with_total(state['player'])}\n"
        f"🀫 <b>Dealer hand:</b> {format_hand_with_total(dealer)}"
    )
    return state, text, True