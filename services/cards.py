"""
Card display utilities for casino games.
"""

from typing import List, Tuple

# Unicode card suits
SUITS = ["♠", "♥", "♦", "♣"]

# Card rank to value mapping for 21 games
CARD_VALUES = {
    "A": 11,  # Adjust down to 1 as needed
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 10, "Q": 10, "K": 10
}

# Hidden card symbol
HIDDEN_CARD = "🂠"

def format_card_unicode(rank: str, suit: str) -> str:
    """Format a card as rank + Unicode suit."""
    return f"{rank}{suit}"

def format_hand_unicode(cards: List[Tuple[str, str]], hide_first: bool = False) -> str:
    """Format a hand of cards with Unicode suits."""
    if not cards:
        return ""
    
    formatted_cards = []
    for i, (rank, suit) in enumerate(cards):
        if i == 0 and hide_first:
            formatted_cards.append(HIDDEN_CARD)
        else:
            formatted_cards.append(format_card_unicode(rank, suit))
    
    return " ".join(formatted_cards)

def calculate_hand_value(cards: List[str]) -> int:
    """Calculate hand value for blackjack/21 games."""
    total = sum(CARD_VALUES[rank] for rank in cards)
    aces = sum(1 for rank in cards if rank == "A")
    
    # Adjust aces from 11 to 1 if needed
    while total > 21 and aces:
        total -= 10
        aces -= 1
    
    return total

def format_hand_with_total(cards: List[str], hide_first: bool = False) -> str:
    """Format hand as cards + total, with option to hide first card."""
    if not cards:
        return ""
    
    if hide_first and len(cards) > 1:
        visible_cards = cards[1:]
        total = calculate_hand_value(visible_cards)
        card_display = f"{HIDDEN_CARD} {' '.join(visible_cards)}"
        return f"{card_display} (showing: {total})"
    else:
        total = calculate_hand_value(cards)
        card_display = ' '.join(cards)
        return f"{card_display} (total: {total})"