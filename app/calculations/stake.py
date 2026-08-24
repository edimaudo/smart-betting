"""
Stake sizing calculations.

PRD section 26: stake sizing is intentionally separated from
opportunity evaluation (the Decision Engine). These are analytical
outputs, not guarantees or instructions.
"""
from __future__ import annotations


def fixed_unit_stake(unit_size: float, units: float = 1.0) -> float:
    """A flat stake expressed as a number of bankroll 'units'."""
    if unit_size < 0 or units < 0:
        raise ValueError("unit_size and units cannot be negative")
    return unit_size * units


def percentage_bankroll_stake(bankroll: float, percentage: float) -> float:
    """Stake = bankroll x percentage (percentage as a decimal, e.g. 0.02 = 2%)."""
    if bankroll < 0:
        raise ValueError("bankroll cannot be negative")
    if not (0.0 <= percentage <= 1.0):
        raise ValueError("percentage must be between 0 and 1")
    return bankroll * percentage


def kelly_fraction(probability_win: float, decimal_odds: float) -> float:
    """
    Kelly criterion fraction of bankroll to stake.

    f* = (b*p - q) / b
    where b = decimal_odds - 1 (net odds), p = P(win), q = 1 - p

    Returns 0 when the Kelly criterion suggests no edge exists
    (negative Kelly fraction is clipped to 0 rather than shorting).
    """
    if not (0.0 <= probability_win <= 1.0):
        raise ValueError("probability_win must be between 0 and 1")
    b = decimal_odds - 1
    if b <= 0:
        raise ValueError("decimal_odds must be greater than 1.0")
    q = 1.0 - probability_win
    f = (b * probability_win - q) / b
    return max(f, 0.0)


def kelly_stake(bankroll: float, probability_win: float, decimal_odds: float, fraction: float = 1.0) -> float:
    """
    Kelly-style or fractional-Kelly stake in currency units.

    `fraction` scales the full Kelly recommendation (e.g. 0.5 for
    "half Kelly"), which is common practice to reduce variance and
    protect against model error.
    """
    if bankroll < 0:
        raise ValueError("bankroll cannot be negative")
    if fraction < 0:
        raise ValueError("fraction cannot be negative")
    f_star = kelly_fraction(probability_win, decimal_odds)
    return bankroll * f_star * fraction
