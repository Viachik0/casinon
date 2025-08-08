"""Card deck utilities for blackjack and 21 games."""
from typing import List, Tuple
from services.rng import rng


class Card:
    """Represents a playing card."""
    
    SUITS = ['♠️', '♥️', '♣️', '♦️']
    RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    
    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    def __repr__(self) -> str:
        return f"Card({self.rank}, {self.suit})"
    
    @property
    def value(self) -> int:
        """Get the base value of the card (Ace = 1, Face cards = 10)."""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 1
        else:
            return int(self.rank)


class Hand:
    """Represents a hand of cards."""
    
    def __init__(self):
        self.cards: List[Card] = []
    
    def add_card(self, card: Card) -> None:
        """Add a card to the hand."""
        self.cards.append(card)
    
    def clear(self) -> None:
        """Clear all cards from the hand."""
        self.cards.clear()
    
    def __str__(self) -> str:
        return ' '.join(str(card) for card in self.cards)
    
    @property
    def value(self) -> int:
        """Calculate the best value of the hand (handling Aces)."""
        total = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == 'A')
        
        # Convert Aces from 1 to 11 as beneficial
        while aces > 0 and total + 10 <= 21:
            total += 10
            aces -= 1
        
        return total
    
    @property
    def is_blackjack(self) -> bool:
        """Check if hand is a natural blackjack (21 with 2 cards)."""
        return len(self.cards) == 2 and self.value == 21
    
    @property
    def is_bust(self) -> bool:
        """Check if hand is over 21."""
        return self.value > 21
    
    @property
    def is_soft(self) -> bool:
        """Check if hand contains an Ace counted as 11."""
        if not any(card.rank == 'A' for card in self.cards):
            return False
        
        # Check if any ace is being counted as 11
        base_total = sum(card.value for card in self.cards)  # All aces as 1
        return self.value != base_total


class Deck:
    """Represents a deck of cards."""
    
    def __init__(self, num_decks: int = 1):
        self.num_decks = num_decks
        self.cards: List[Card] = []
        self.reset()
    
    def reset(self) -> None:
        """Reset and shuffle the deck."""
        self.cards.clear()
        for _ in range(self.num_decks):
            for suit in Card.SUITS:
                for rank in Card.RANKS:
                    self.cards.append(Card(rank, suit))
        self.shuffle()
    
    def shuffle(self) -> None:
        """Shuffle the deck using secure RNG."""
        rng.shuffle(self.cards)
    
    def deal_card(self) -> Card:
        """Deal one card from the deck."""
        if not self.cards:
            self.reset()  # Auto-shuffle when empty
        return self.cards.pop()
    
    @property
    def cards_left(self) -> int:
        """Get number of cards remaining in deck."""
        return len(self.cards)
    
    @property
    def should_shuffle(self) -> bool:
        """Check if deck should be shuffled (less than 25% remaining)."""
        total_cards = self.num_decks * 52
        return self.cards_left < total_cards * 0.25


class BlackjackShoe(Deck):
    """6-deck shoe for blackjack with automatic shuffle when low."""
    
    def __init__(self):
        super().__init__(num_decks=6)
    
    def deal_card(self) -> Card:
        """Deal card and auto-shuffle if needed."""
        if self.should_shuffle:
            self.reset()
        return super().deal_card()


class SingleDeck(Deck):
    """Single deck for simplified 21 game."""
    
    def __init__(self):
        super().__init__(num_decks=1)
    
    def deal_card(self) -> Card:
        """Deal card and reset if empty."""
        if not self.cards:
            self.reset()
        return super().deal_card()