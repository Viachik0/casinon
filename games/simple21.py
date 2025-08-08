from typing import List

from services.deck import Card, Deck, hand_value_blackjack

class Simple21:
    def __init__(self):
        self.deck = Deck(1)
        self.cards: List[Card] = []

    def start(self) -> None:
        self.cards = [self.deck.draw(), self.deck.draw()]

    def hit(self) -> None:
        self.cards.append(self.deck.draw())

    def value(self) -> int:
        return hand_value_blackjack(self.cards)
