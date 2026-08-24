"""
Edge and Expected Value calculations.

PRD sections 16 & 17. Precision is preserved internally (plain floats,
no premature rounding); display rounding is the caller's / template's
responsibility so it can be made configurable later.
"""
from __future__ import annotations

from dataclasses import dataclass


def edge(model_probability: float, market_probability: float) -> float:
    """Edge = Model Probability - Market Implied Probability"""
    return model_probability - market_probability


@dataclass(frozen=True)
class ExpectedValueResult:
    """
    Distinguishes expected profit, total payout, stake, and return, as
    required by PRD section 17.
    """
    expected_profit: float
    expected_payout: float
    stake: float
    profit_if_win: float
    payout_if_win: float

    @property
    def ev_per_unit_staked(self) -> float:
        if self.stake == 0:
            return 0.0
        return self.expected_profit / self.stake


def expected_value(probability_win: float, decimal_odds: float, stake: float) -> ExpectedValueResult:
    """
    For a binary outcome:
        EV = (P(win) x Profit) - (P(loss) x Stake)

    `Profit` here is the profit earned on a win (payout minus stake).
    """
    if not (0.0 <= probability_win <= 1.0):
        raise ValueError("probability_win must be between 0 and 1")
    if stake < 0:
        raise ValueError("Stake cannot be negative")

    payout_if_win = stake * decimal_odds
    profit_if_win = payout_if_win - stake
    probability_loss = 1.0 - probability_win

    expected_profit = (probability_win * profit_if_win) - (probability_loss * stake)
    expected_payout = probability_win * payout_if_win

    return ExpectedValueResult(
        expected_profit=expected_profit,
        expected_payout=expected_payout,
        stake=stake,
        profit_if_win=profit_if_win,
        payout_if_win=payout_if_win,
    )
