from typing import List, Tuple

from .rng import shuffle

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

Card = Tuple[str, str]  # (rank, suit)

def card_value_for_blackjack(rank: str) -> int:
    if rank in {"J", "Q", "K"}:
        return 10
    if rank == "A":
        return 11
    return int(rank)

class Deck:
    def __init__(self, num_decks: int = 1):
        self.cards: List[Card] = []
        for _ in range(num_decks):
            for s in SUITS:
                for r in RANKS:
                    self.cards.append((r, s))
        shuffle(self.cards)

    def draw(self) -> Card:
        return self.cards.pop()

    def remaining(self) -> int:
        return len(self.cards)

def hand_value_blackjack(cards: List[Card]) -> int:
    total = 0
    aces = 0
    for r, _ in cards:
        total += card_value_for_blackjack(r)
        if r == "A":
            aces += 1
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total
