"""
Odds conversion calculations.

Supports Decimal and American odds formats. All functions are pure
and independently testable per PRD section 15 (Odds Calculations).
"""
from __future__ import annotations


def decimal_implied_probability(decimal_odds: float) -> float:
    """Implied Probability = 1 / Decimal Odds"""
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.0")
    return 1.0 / decimal_odds


def american_implied_probability(american_odds: float) -> float:
    """
    Positive: Implied Probability = 100 / (American Odds + 100)
    Negative: Implied Probability = -American Odds / (-American Odds + 100)
    """
    if american_odds == 0:
        raise ValueError("American odds cannot be zero")
    if american_odds > 0:
        return 100.0 / (american_odds + 100.0)
    return (-american_odds) / (-american_odds + 100.0)


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to Decimal odds."""
    if american_odds == 0:
        raise ValueError("American odds cannot be zero")
    if american_odds > 0:
        return 1.0 + (american_odds / 100.0)
    return 1.0 + (100.0 / -american_odds)


def decimal_to_american(decimal_odds: float) -> float:
    """Convert Decimal odds to American odds."""
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.0")
    if decimal_odds >= 2:
        return (decimal_odds - 1) * 100.0
    return -100.0 / (decimal_odds - 1)


def potential_return(stake: float, decimal_odds: float) -> float:
    """Potential Return = Stake x Decimal Odds (total payout, includes stake)."""
    if stake < 0:
        raise ValueError("Stake cannot be negative")
    return stake * decimal_odds


def potential_profit(stake: float, decimal_odds: float) -> float:
    """Profit only (excludes returned stake)."""
    return potential_return(stake, decimal_odds) - stake


def implied_probability(odds: float, odds_format: str = "decimal") -> float:
    """Dispatch helper: implied probability for either odds format."""
    odds_format = odds_format.lower()
    if odds_format == "decimal":
        return decimal_implied_probability(odds)
    if odds_format == "american":
        return american_implied_probability(odds)
    raise ValueError(f"Unsupported odds format: {odds_format}")


def to_decimal(odds: float, odds_format: str = "decimal") -> float:
    """Normalize any supported odds format to decimal odds."""
    odds_format = odds_format.lower()
    if odds_format == "decimal":
        return odds
    if odds_format == "american":
        return american_to_decimal(odds)
    raise ValueError(f"Unsupported odds format: {odds_format}")
