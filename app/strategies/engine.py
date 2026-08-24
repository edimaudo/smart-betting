"""
Strategy Engine.

PRD section 14 & 21: strategies are configurable rules. The engine
evaluates whether a given analytical opportunity satisfies a
strategy's thresholds. Stake sizing is deliberately NOT decided here
(see PRD section 26 / app/calculations/stake.py) — this engine only
answers "does this opportunity fit the strategy's criteria?".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.models.entities import Strategy


@dataclass
class StrategyEvaluation:
    strategy: Strategy
    meets_strategy: bool
    failed_criteria: list[str] = field(default_factory=list)


class StrategyEngine:
    def evaluate(
        self,
        strategy: Strategy,
        *,
        edge: Optional[float],
        expected_value: Optional[float],
        confidence: Optional[float],
        sport_id: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> StrategyEvaluation:
        failed: list[str] = []

        if strategy.sport and sport_id and strategy.sport != sport_id:
            failed.append(f"Sport does not match strategy scope ({strategy.sport}).")
        if strategy.market_type and market_type and strategy.market_type != market_type:
            failed.append(f"Market type does not match strategy scope ({strategy.market_type}).")

        if edge is None:
            failed.append("Edge is unavailable.")
        elif edge < strategy.min_edge:
            failed.append(f"Edge {edge:.1%} is below the strategy minimum of {strategy.min_edge:.1%}.")

        if expected_value is None:
            failed.append("Expected value is unavailable.")
        elif expected_value < strategy.min_ev:
            failed.append(f"Expected value {expected_value:.1%} is below the strategy minimum of {strategy.min_ev:.1%}.")

        if confidence is None:
            failed.append("Model confidence is unavailable.")
        elif confidence < strategy.min_confidence:
            failed.append(f"Model confidence {confidence:.0%} is below the strategy minimum of {strategy.min_confidence:.0%}.")

        return StrategyEvaluation(strategy=strategy, meets_strategy=(len(failed) == 0), failed_criteria=failed)


DEFAULT_STRATEGIES: list[Strategy] = [
    Strategy(id="balanced", name="Balanced Value", min_edge=0.03, min_ev=0.0, min_confidence=0.55, max_stake_units=2),
    Strategy(id="conservative", name="Conservative Edge", min_edge=0.06, min_ev=0.02, min_confidence=0.65, max_stake_units=1),
    Strategy(id="aggressive", name="Aggressive Value Hunter", min_edge=0.01, min_ev=-0.02, min_confidence=0.5, max_stake_units=3),
]

engine = StrategyEngine()
