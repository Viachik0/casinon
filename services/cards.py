"""
Card display utilities for casino games, unified on (rank, suit) tuples,
with backward-compatible normalization for legacy string representations.
"""

from typing import List, Sequence, Tuple, Union

# Core suit and rank definitions (should match services.deck)
SUITS = ["♠", "♥", "♦", "♣"]

# Rank -> blackjack value (A initially 11, adjusted later)
CARD_VALUES = {
    "A": 11,
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 10, "Q": 10, "K": 10
}

# Hidden dealer card symbol
HIDDEN_CARD = "🂠"

Card = Tuple[str, str]
CardInput = Union[str, Card]

def _split_decorated(s: str) -> Card:
    """
    Attempt to split a decorated string like '10♦' into ('10','♦').
    If no final suit match, returns (s, '?') as placeholder suit.
    """
    if s and s[-1] in SUITS:
        return (s[:-1], s[-1])
    return (s, "?")

def normalize_cards(cards: Sequence[CardInput]) -> List[Card]:
    """
    Convert a heterogeneous sequence of cards (tuples, rank strings, decorated strings)
    into a list of (rank, suit) tuples. Unknown suit becomes '?'.
    """
    norm: List[Card] = []
    for c in cards:
        if isinstance(c, tuple):
            norm.append(c)
        else:
            norm.append(_split_decorated(str(c)))
    return norm

def calculate_hand_value(cards: Sequence[CardInput]) -> int:
    """
    Blackjack hand value. Accepts tuples, plain ranks, or decorated rank+suit strings.
    Handles Ace adjustment.
    """
    norm = normalize_cards(cards)
    ranks = [r for r, _ in norm]
    total = sum(CARD_VALUES[r] for r in ranks)
    aces = ranks.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def format_card_unicode(card: Card) -> str:
    rank, suit = card
    return f"{rank}{'' if suit == '?' else suit}"

def format_hand_unicode(cards: Sequence[CardInput], hide_first: bool = False) -> str:
    if not cards:
        return ""
    norm = normalize_cards(cards)
    parts: List[str] = []
    for i, card in enumerate(norm):
        if hide_first and i == 0 and len(norm) > 1:
            parts.append(HIDDEN_CARD)
        else:
            parts.append(format_card_unicode(card))
    return " ".join(parts)

def format_hand_with_total(cards: Sequence[CardInput], hide_first: bool = False) -> str:
    """
    Format a hand plus total (or partial 'showing' total if first card hidden).
    """
    if not cards:
        return ""
    if hide_first and len(cards) > 1:
        visible = cards[1:]
        total = calculate_hand_value(visible)
        return f"{format_hand_unicode(cards, hide_first=True)} (showing: {total})"
    total = calculate_hand_value(cards)
    return f"{format_hand_unicode(cards)} (total: {total})"