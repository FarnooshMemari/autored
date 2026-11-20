"""Small statistics helpers for honest confidence reporting.

We avoid presenting arbitrary 0-1 'confidence scores' as probabilities. The only
statistical claim we make is a Wilson score interval on the *reproduction rate*:
of N independent fresh-context trials, k reproduced the strong evidence. That is a
real, defensible frequency with an interval — not a hand-tuned confidence number.
"""
from __future__ import annotations

import math


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion. Returns (low, high)."""
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    z2 = z * z
    denom = 1 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denom
    half = (z * math.sqrt((p * (1 - p) + z2 / (4 * trials)) / trials)) / denom
    return (round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3))
