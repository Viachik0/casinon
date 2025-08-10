# (Same as provided earlier; unchanged logic – included for completeness)
import json
import random
import math
from typing import List, Dict, Any

MAX_SPLIT_HANDS = 4
ALLOW_10_VALUE_FAMILY = False
ALLOW_RE_SPLIT = True

try:
    from services.cards import (
        format_hand_with_total,
        calculate_hand_value,
        SUITS,
        HIDDEN_CARD
    )
except Exception:
    SUITS = ["♠", "♥", "♦", "♣"]
    HIDDEN_CARD = "🂠"

    def calculate_hand_value(cards: List[str]) -> int:
        total = 0
        aces = 0
        for c in cards:
            rank = c[:-1]
            if rank in ("J", "Q", "K"):
                total += 10
            elif rank == "A":
                aces += 1
                total += 11
            else:
                try:
                    total += int(rank)
                except Exception:
                    pass
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def format_hand_with_total(cards: List[str]) -> str:
        return f"{' '.join(cards)} (total: {calculate_hand_value(cards)})" if cards else ""


RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def make_deck(shuffle: bool = True) -> List[str]:
    deck = [f"{r}{s}" for r in RANKS for s in SUITS]
    if shuffle:
        random.shuffle(deck)
    return deck


class BlackjackState:
    def __init__(self, bet: int):
        deck = make_deck()
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
            "split_count": 0,
        }

    def to_json(self) -> str:
        return json.dumps(self.state)

    @classmethod
    def from_json(cls, data: str) -> "BlackjackState":
        obj = cls(1)
        obj.state = json.loads(data)
        return obj

    def draw(self) -> str:
        deck = self.state.get("deck", [])
        if not deck:
            deck = make_deck()
            self.state["deck"] = deck
        return deck.pop()

    def current_hand(self) -> List[str]:
        return self.state["player_hands"][self.state["current_hand"]]

    def hand_rank_pair(self, hand: List[str]) -> bool:
        if len(hand) != 2:
            return False
        r1, r2 = hand[0][:-1], hand[1][:-1]
        if r1 == r2:
            return True
        if ALLOW_10_VALUE_FAMILY:
            ten_vals = {"10", "J", "Q", "K"}
            return r1 in ten_vals and r2 in ten_vals
        return False

    def can_split(self) -> bool:
        if len(self.state["player_hands"]) >= MAX_SPLIT_HANDS:
            return False
        if not ALLOW_RE_SPLIT and self.state.get("split_count", 0) > 0:
            return False
        return self.hand_rank_pair(self.current_hand())

    def can_double(self) -> bool:
        return len(self.current_hand()) == 2

    def is_blackjack(self, hand: List[str]) -> bool:
        return len(hand) == 2 and calculate_hand_value(hand) == 21

    def reveal_dealer(self) -> None:
        self.state["dealer_visible"] = self.state["dealer"].copy()

    def dealer_play_step(self) -> bool:
        if calculate_hand_value(self.state["dealer"]) < 17:
            c = self.draw()
            self.state["dealer"].append(c)
            self.state["dealer_visible"].append(c)
            return True
        return False

    def evaluate(self) -> Dict[str, Any]:
        dealer_total = calculate_hand_value(self.state["dealer"])
        results = []
        for i, hand in enumerate(self.state["player_hands"]):
            bet = self.state["bets"][i]
            player_total = calculate_hand_value(hand)

            if i < len(self.state.get("surrendered", [])) and self.state["surrendered"][i]:
                half = bet // 2
                results.append(("surrender", half, f"⚠️ Hand {i+1} surrendered, returned {half}"))
                continue

            if self.is_blackjack(hand):
                if self.is_blackjack(self.state["dealer"]):
                    results.append(("push", bet, f"🤝 Hand {i+1} push (both BJ)"))
                else:
                    extra = math.floor(1.5 * bet)
                    payout = bet + extra
                    results.append(("win", payout, f"🏆 Hand {i+1} Blackjack +{extra}"))
                continue

            if player_total > 21:
                results.append(("loss", 0, f"💥 Hand {i+1} busted -{bet}"))
                continue

            if dealer_total > 21 or player_total > dealer_total:
                results.append(("win", 2 * bet, f"🏆 Hand {i+1} wins +{bet}"))
            elif player_total < dealer_total:
                results.append(("loss", 0, f"💥 Hand {i+1} loses -{bet}"))
            else:
                results.append(("push", bet, f"🤝 Hand {i+1} push"))
        return {"dealer_total": dealer_total, "results": results}


def format_hand(cards: List[str]) -> str:
    return " ".join(cards)

def format_state_for_display(state_obj: BlackjackState, show_dealer_full: bool = False, highlight_current: bool = True) -> str:
    from games.blackjack import calculate_hand_value  # local import for fallback
    dealer_disp = " ".join(state_obj.state["dealer"]) if show_dealer_full else " ".join(state_obj.state["dealer_visible"])
    text = "🃏 <b>Blackjack</b>\n"
    text += f"💰 Base Bet: {state_obj.state.get('original_bet', 0)} credits\n\n"
    for idx, hand in enumerate(state_obj.state["player_hands"]):
        marker = "👉" if highlight_current and idx == state_obj.state["current_hand"] else "  "
        total = calculate_hand_value(hand)
        text += f"{marker} Hand {idx+1}: {format_hand(hand)} (total: {total}, bet {state_obj.state['bets'][idx]})\n"
    text += f"\n🀫 Dealer: {dealer_disp}"
    return text

def format_final_results(state_obj: BlackjackState, eval_res: Dict[str, Any]) -> str:
    from games.blackjack import format_hand_with_total
    out = "🃏 <b>Blackjack — Round Complete</b>\n\n"
    for idx, (hand, (typ, payout, msg)) in enumerate(zip(state_obj.state["player_hands"], eval_res["results"])):
        out += f"🎲 Hand {idx+1}: {format_hand_with_total(hand)} — {msg}\n"
    out += f"\n🀫 Dealer: {format_hand_with_total(state_obj.state['dealer'])}\n"
    return out