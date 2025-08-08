"""Cryptographically secure random number generation."""
import secrets
from typing import List, Any


class SecureRNG:
    """Cryptographically secure random number generator using secrets module."""
    
    def __init__(self):
        self.rng = secrets.SystemRandom()
    
    def randint(self, a: int, b: int) -> int:
        """Generate secure random integer between a and b (inclusive)."""
        return self.rng.randint(a, b)
    
    def choice(self, sequence: List[Any]) -> Any:
        """Choose secure random element from sequence."""
        return self.rng.choice(sequence)
    
    def shuffle(self, sequence: List[Any]) -> None:
        """Securely shuffle sequence in place."""
        self.rng.shuffle(sequence)
    
    def sample(self, population: List[Any], k: int) -> List[Any]:
        """Secure random sample of k elements from population."""
        return self.rng.sample(population, k)


# Global secure RNG instance
rng = SecureRNG()