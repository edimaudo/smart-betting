"""
Vig / market margin calculations.

PRD section 18. Margin-removal ("de-vigging") methods can differ by
market and sport; this module implements the standard proportional
(multiplicative) method and documents that assumption explicitly.

Assumption: normalization is proportional (each outcome's raw implied
probability is divided by the sum of all raw implied probabilities in
the market). This is the most common approach for two- and
three-outcome markets and is a reasonable default, but it is not the
only valid method (additive/Shin methods exist and can differ,
particularly in markets with strong favorites/longshots). Callers who
need a different de-vigging method should implement it as an
alternative function rather than assume this one is universal.
"""
from __future__ import annotations

from typing import Sequence


def market_overround(implied_probabilities: Sequence[float]) -> float:
    """
    Raw Market Probability = sum(implied probabilities)

    A value above 1.0 indicates the bookmaker margin (vig). E.g. 1.05
    means a 5% overround.
    """
    if not implied_probabilities:
        raise ValueError("At least one implied probability is required")
    return sum(implied_probabilities)


def vig_percentage(implied_probabilities: Sequence[float]) -> float:
    """Overround expressed as a percentage margin above 100%."""
    return market_overround(implied_probabilities) - 1.0


def normalize_probabilities(implied_probabilities: Sequence[float]) -> list[float]:
    """
    Normalized Probability = Individual Implied Probability / Total Implied Probability

    Removes the bookmaker margin proportionally so the resulting
    probabilities sum to 1.0. Requires implied probabilities for ALL
    outcomes in the market to be meaningful.
    """
    total = market_overround(implied_probabilities)
    if total <= 0:
        raise ValueError("Sum of implied probabilities must be positive")
    return [p / total for p in implied_probabilities]


def has_sufficient_market_info(num_outcomes_priced: int, num_outcomes_total: int) -> bool:
    """
    Vig adjustment requires odds for every outcome in the market. This
    guard lets callers fall back to INSUFFICIENT_DATA rather than
    silently normalizing against a partial market.
    """
    return num_outcomes_priced > 0 and num_outcomes_priced == num_outcomes_total
