import json
import random
from typing import Dict, Any, List

# European roulette (single zero)
RED_NUMBERS = {
    1,3,5,7,9,12,14,16,18,
    19,21,23,25,27,30,32,34,36
}
BLACK_NUMBERS = {
    2,4,6,8,10,11,13,15,17,
    20,22,24,26,28,29,31,33,35
}

DOZENS = {
    "1st12": range(1,13),
    "2nd12": range(13,25),
    "3rd12": range(25,37),
}

DOZEN_LABEL = {
    "1st12": "1–12",
    "2nd12": "13–24",
    "3rd12": "25–36",
}

def base_state() -> Dict[str, Any]:
    return {
        "bets": [],          # list of {type, value, amount}
        "last_chip": 10,
        "spun": False,
        "result": None
    }

def to_json(state: Dict[str, Any]) -> str:
    return json.dumps(state)

def from_json(data: str) -> Dict[str, Any]:
    return json.loads(data)

def add_bet(state: Dict[str, Any], bet_type: str, value: str, amount: int) -> None:
    state["bets"].append({"type": bet_type, "value": value, "amount": amount})

def pretty_bet_line(b: Dict[str, Any]) -> str:
    t = b["type"]
    v = b["value"]
    amt = b["amount"]
    if t == "straight":
        return f"🎯 {amt} on #{v}"
    if t == "color":
        emoji = "🔴" if v == "red" else "⚫"
        return f"{emoji} {amt} on {v.title()}"
    if t == "parity":
        emoji = "○" if v == "even" else "●"
        label = "Even" if v == "even" else "Odd"
        return f"{emoji} {amt} on {label}"
    if t == "range":
        if v == "low":
            return f"⬇ {amt} on 1–18"
        return f"⬆ {amt} on 19–36"
    if t == "dozen":
        return f"📦 {amt} on {DOZEN_LABEL.get(v, v)}"
    return f"{amt} on {t}: {v}"

def summarize_bets(state: Dict[str, Any]) -> str:
    if not state["bets"]:
        return "No bets placed."
    lines = [pretty_bet_line(b) for b in state["bets"]]
    total = sum(b["amount"] for b in state["bets"])
    return "Your Bets:\n" + "\n".join(lines) + f"\n— Total locked: {total}"

def spin_result() -> int:
    return random.randint(0, 36)

def evaluate(state: Dict[str, Any], number: int) -> int:
    total_return = 0
    for b in state["bets"]:
        t = b["type"]
        v = b["value"]
        amt = b["amount"]
        if t == "straight":
            if number == int(v):
                total_return += amt * 36  # 35:1 + stake
        elif t == "color":
            if number == 0:
                continue
            color = "red" if number in RED_NUMBERS else "black"
            if color == v:
                total_return += amt * 2
        elif t == "parity":
            if number == 0:
                continue
            parity = "even" if number % 2 == 0 else "odd"
            if parity == v:
                total_return += amt * 2
        elif t == "range":
            if v == "low" and 1 <= number <= 18:
                total_return += amt * 2
            elif v == "high" and 19 <= number <= 36:
                total_return += amt * 2
        elif t == "dozen":
            if number in DOZENS[v]:
                total_return += amt * 3  # 2:1 + stake
    return total_return