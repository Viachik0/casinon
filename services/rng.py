import secrets
from typing import List, Sequence, TypeVar

T = TypeVar("T")

def randint(a: int, b: int) -> int:
    # Inclusive range
    return secrets.randbelow(b - a + 1) + a

def choice(seq: Sequence[T]) -> T:
    return secrets.choice(seq)

def shuffle(seq: List[T]) -> None:
    # Fisher-Yates using secrets for unbiased shuffling
    for i in range(len(seq) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        seq[i], seq[j] = seq[j], seq[i]
