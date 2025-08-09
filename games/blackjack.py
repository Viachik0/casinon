# games/blackjack.py
"""
Full Blackjack game engine module compatible with the existing bot.
Provides BlackjackState (serializable), helpers to evaluate rounds and UI formatting.
Designed to be imported as `from games import blackjack`.

It expects the bot to store the JSON-serialized state returned by BlackjackState.to_json()
in the `active_rounds` table (via your existing Database API).

Payout convention: payout values are "gross" like in your DB: 0 for loss, bet for push,
2*bet for normal win, blackjack pays bet + floor(1.5*bet) (so returned value = bet + 1.5*bet).
This matches the existing `resolve_active_round` contract in your db.py.
"""

import json
import random
import math
from typing import List, Dict, Any

# try to reuse formatting / calc helpers from services.cards if present
try:
    from services.cards import format_hand_with_total, calculate_hand_value, SUITS, HIDDEN_CARD
except Exception:  # fallback minimal implementations
    SUITS = ["♠", "♥", "♦", "♣"]
    HIDDEN_CARD = "🂠"

    def calculate_hand_value(cards: List[str]) -> int:
        total = 0
        aces = 0
        for c in cards:
            # card format: <rank><suit> (e.g. 10♠ or A♦)
            rank = c[:-1] if len(c) > 1 else c
            if rank in ("J", "Q", "K"):
                total += 10
            elif rank == "A":
                aces += 1
                total += 11
            else:
                try:
                    total += int(rank)
                except Exception:
                    total += 0
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def format_hand_with_total(cards: List[str]) -> str:
        if not cards:
            return ""
        return f"{' '.join(cards)} (total: {calculate_hand_value(cards)})"


RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def make_deck(shuffle: bool = True) -> List[str]:
    deck = [f"{r}{s}" for r in RANKS for s in SUITS]
    if shuffle:
        random.shuffle(deck)
    return deck


class BlackjackState:
    """Serializable state for a blackjack round.

    Structure (stored in .state dict):
      - deck: list[str] remaining deck
      - player_hands: list[list[str]]
      - bets: list[int]
      - current_hand: int
      - dealer: list[str]
      - dealer_visible: list[str] (HIDDEN_CARD for hidden spots)
      - doubled: list[bool]
      - surrendered: list[bool]
      - finished: bool
      - result: Optional[str]
      - original_bet: int
    """

    def __init__(self, bet: int):
        deck = make_deck()
        # initial draws: two to player, two to dealer
        p1 = [deck.pop(), deck.pop()]
        d1 = [deck.pop(), deck.pop()]
        self.state: Dict[str, Any] = {
            "deck": deck,
            "player_hands": [p1],
            "bets": [bet],
            "current_hand": 0,
            "dealer": d1,
            "dealer_visible": [d1[0], HIDDEN_CARD],
            "doubled": [False],
            "surrendered": [False],
            "finished": False,
            "result": None,
            "original_bet": bet,
        }

    def to_json(self) -> str:
        return json.dumps(self.state)

    @classmethod
    def from_json(cls, data: str) -> "BlackjackState":
        obj = cls(1)
        loaded = json.loads(data)
        obj.state = loaded
        return obj

    # deck operations
    def draw(self) -> str:
        deck = self.state.get("deck", [])
        if not deck:
            deck = make_deck()
            self.state["deck"] = deck
        return self.state["deck"].pop()

    # helpers for current player hand
    def current_hand(self) -> List[str]:
        return self.state["player_hands"][self.state["current_hand"]]

    def can_split(self) -> bool:
        hand = self.current_hand()
        return len(hand) == 2 and hand[0][:-1] == hand[1][:-1]

    def can_double(self) -> bool:
        return len(self.current_hand()) == 2

    def is_blackjack(self, hand: List[str]) -> bool:
        return calculate_hand_value(hand) == 21 and len(hand) == 2

    def reveal_dealer(self) -> None:
        self.state["dealer_visible"] = self.state["dealer"].copy()

    def dealer_play(self) -> None:
        # Dealer stands on soft 17 (standard casino rule implemented)
        while calculate_hand_value(self.state["dealer"]) < 17:
            card = self.draw()
            self.state["dealer"].append(card)
            # make card visible immediately
            self.state["dealer_visible"].append(card)

    def evaluate(self) -> Dict[str, Any]:
        """Evaluate each player hand vs dealer and produce results.

        Returns a dict with keys:
          - dealer_total: int
          - results: list of tuples (result_type, payout, message)
            where payout is the gross amount to credit (0/loss, bet/push, 2*bet/win,
            blackjack -> bet + floor(1.5*bet)).
        """
        results = []
        dealer_total = calculate_hand_value(self.state["dealer"])

        for idx, hand in enumerate(self.state["player_hands"]):
            bet = self.state["bets"][idx]
            player_total = calculate_hand_value(hand)

            # surrender
            if idx < len(self.state.get("surrendered", [])) and self.state.get("surrendered")[idx]:
                # return half of bet as payout (gross)
                half = math.floor(bet / 2)
                msg = f"⚠️ Hand {idx+1} surrendered, returned {half} credits"
                results.append(("surrender", half, msg))
                continue

            # natural blackjack
            if self.is_blackjack(hand):
                if self.is_blackjack(self.state["dealer"]):
                    results.append(("push", bet, f"🤝 Hand {idx+1} push (both BJ)"))
                else:
                    bj_extra = math.floor(1.5 * bet)
                    payout = bet + bj_extra
                    results.append(("win", payout, f"🏆 Hand {idx+1} Blackjack +{bj_extra}"))
                continue

            # bust
            if player_total > 21:
                results.append(("loss", 0, f"💥 Hand {idx+1} busted -{bet}"))
                continue

            # compare
            if dealer_total > 21 or player_total > dealer_total:
                payout = 2 * bet
                results.append(("win", payout, f"🏆 Hand {idx+1} wins +{bet}"))
            elif player_total < dealer_total:
                results.append(("loss", 0, f"💥 Hand {idx+1} loses -{bet}"))
            else:
                results.append(("push", bet, f"🤝 Hand {idx+1} push"))

        return {"dealer_total": dealer_total, "results": results}


# UI helpers
def format_hand(cards: List[str], hide_first: bool = False) -> str:
    if not cards:
        return ""
    if hide_first and len(cards) > 1:
        visible = " ".join(cards[1:])
        return f"{HIDDEN_CARD} {visible}"
    return " ".join(cards)


def format_state_for_display(state_obj: BlackjackState, reveal_dealer: bool = False) -> str:
    dealer_display = (
        " ".join(state_obj.state["dealer"]) if reveal_dealer else " ".join(state_obj.state.get("dealer_visible", []))
    )
    text = f"🃏 <b>Blackjack</b>\n"
    text += f"💰 Bet: {state_obj.state.get('original_bet', 0)} credits\n\n"
    for i, hand in enumerate(state_obj.state["player_hands"]):
        prefix = "👉 " if i == state_obj.state["current_hand"] else "   "
        text += f"{prefix}Your hand #{i+1}: {format_hand(cards=hand)} (total: {calculate_hand_value(hand)})\n"
    text += f"\n🀫 Dealer: {dealer_display}"
    return text
