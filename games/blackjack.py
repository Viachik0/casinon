from typing import List, Tuple

from services.deck import Deck, hand_value_blackjack, Card

class BlackjackGame:
    def __init__(self, num_decks: int = 4):
        self.deck = Deck(num_decks)
        self.player: List[Card] = []
        self.dealer: List[Card] = []

    def start(self) -> None:
        self.player = [self.deck.draw(), self.deck.draw()]
        self.dealer = [self.deck.draw(), self.deck.draw()]

    def hit(self) -> None:
        self.player.append(self.deck.draw())

    def dealer_play(self) -> None:
        while hand_value_blackjack(self.dealer) < 17:
            self.dealer.append(self.deck.draw())

    def values(self) -> Tuple[int, int]:
        return hand_value_blackjack(self.player), hand_value_blackjack(self.dealer)

    def outcome(self) -> str:
        # Returns: "win" | "lose" | "push"
        pv, _ = self.values()
        if pv > 21:
            return "lose"
        self.dealer_play()
        _, dv = self.values()
        if dv > 21:
            return "win"
        if pv > dv:
            return "win"
        if pv < dv:
            return "lose"
        return "push"
