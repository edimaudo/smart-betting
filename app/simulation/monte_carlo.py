"""
Monte Carlo simulation engine.

PRD section 22 sequence: Probability distribution -> Randomized
trials -> Repeated outcomes -> Distribution of results.

This simulates REPEATED, INDEPENDENT trials of a single betting
strategy applied over a fixed number of bets at a given win
probability and price. It answers "if my assumed probability is
right, what does the range of outcomes look like over N bets?" — it
is a forward-looking simulation, not a backtest, and PRD section 15
requires the UI to keep that distinction clear.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field


@dataclass
class MonteCarloResult:
    trials: int
    bets_per_trial: int
    expected_return: float
    median_return: float
    roi: float
    win_rate: float
    max_drawdown_avg: float
    worst_case_return: float
    best_case_return: float
    longest_losing_streak_avg: float
    return_distribution_sample: list[float] = field(default_factory=list)


def run_monte_carlo(
    *,
    win_probability: float,
    decimal_odds: float,
    stake: float,
    bets_per_trial: int = 50,
    trials: int = 2000,
    seed: int = 7,
) -> MonteCarloResult:
    if not (0.0 < win_probability < 1.0):
        raise ValueError("win_probability must be between 0 and 1 (exclusive)")
    if decimal_odds <= 1:
        raise ValueError("decimal_odds must be greater than 1.0")
    if bets_per_trial <= 0 or trials <= 0:
        raise ValueError("bets_per_trial and trials must be positive")

    rng = random.Random(seed)
    profit_per_win = stake * (decimal_odds - 1)

    trial_returns: list[float] = []
    trial_drawdowns: list[float] = []
    trial_streaks: list[int] = []
    trial_win_rates: list[float] = []

    for _ in range(trials):
        running = 0.0
        peak = 0.0
        drawdown = 0.0
        streak = 0
        longest_streak = 0
        wins = 0

        for _ in range(bets_per_trial):
            if rng.random() < win_probability:
                running += profit_per_win
                wins += 1
                streak = 0
            else:
                running -= stake
                streak += 1
                longest_streak = max(longest_streak, streak)
            peak = max(peak, running)
            drawdown = max(drawdown, peak - running)

        trial_returns.append(running)
        trial_drawdowns.append(drawdown)
        trial_streaks.append(longest_streak)
        trial_win_rates.append(wins / bets_per_trial)

    total_staked = stake * bets_per_trial
    expected_return = statistics.mean(trial_returns)
    median_return = statistics.median(trial_returns)
    roi = expected_return / total_staked if total_staked else 0.0

    return MonteCarloResult(
        trials=trials,
        bets_per_trial=bets_per_trial,
        expected_return=expected_return,
        median_return=median_return,
        roi=roi,
        win_rate=statistics.mean(trial_win_rates),
        max_drawdown_avg=statistics.mean(trial_drawdowns),
        worst_case_return=min(trial_returns),
        best_case_return=max(trial_returns),
        longest_losing_streak_avg=statistics.mean(trial_streaks),
        return_distribution_sample=sorted(trial_returns)[:: max(1, trials // 40)],
    )
