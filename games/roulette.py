from typing import Literal

from services.rng import randint

RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK = set(range(1, 37)) - RED

def spin() -> int:
    # 0..36
    return randint(0, 36)

def color(n: int) -> Literal["red", "black", "green"]:
    if n == 0:
        return "green"
    return "red" if n in RED else "black"

def payout(bet_type: str, bet_value: int | str, amount: int) -> int:
    n = spin()
    if bet_type == "number":
        return amount * 35 if n == bet_value else -amount
    if bet_type == "color":
        return amount if color(n) == bet_value else -amount
    if bet_type == "parity":
        if n == 0:
            return -amount
        parity = "even" if n % 2 == 0 else "odd"
        return amount if parity == bet_value else -amount
    return -amount
