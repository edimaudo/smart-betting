"""
Analysis Engine.

PRD section 19: accepts market data, historical data, model
probability, market probability, and strategy parameters; produces
implied probability, model probability, edge, expected value,
confidence, and risk metrics.

Critically, the analysis engine must NOT directly access external
APIs — it only operates on normalized data already fetched by a
provider (PRD section 19 & 13). Routes are responsible for fetching
data via the provider and passing it in here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.calculations.edge import edge as calc_edge
from app.calculations.edge import expected_value
from app.calculations.odds import implied_probability, to_decimal
from app.calculations.vig import has_sufficient_market_info, normalize_probabilities
from app.models.entities import ModelOutput, Odds


@dataclass
class MarketSnapshot:
    """Best (highest decimal-odds / most favorable) currently available
    price for the target selection, plus the full market for de-vigging."""
    target_selection_id: str
    best_odds: Odds
    all_selection_odds: dict[str, list[Odds]]  # selection_id -> odds across books


@dataclass
class AnalysisResult:
    selection_id: str
    market_implied_probability: Optional[float]
    market_normalized_probability: Optional[float]
    model_probability: Optional[float]
    model_confidence: Optional[float]
    model_name: Optional[str]
    edge: Optional[float]
    expected_value_per_unit: Optional[float]
    decimal_odds: Optional[float]
    overround: Optional[float]
    data_sufficient: bool
    notes: list[str] = field(default_factory=list)


class AnalysisEngine:
    """Converts market + model data into analytical signals."""

    def analyze(
        self,
        snapshot: MarketSnapshot,
        model_output: Optional[ModelOutput],
        stake: float = 1.0,
    ) -> AnalysisResult:
        notes: list[str] = []

        decimal_odds = to_decimal(snapshot.best_odds.price, snapshot.best_odds.odds_format.value)
        market_prob = implied_probability(snapshot.best_odds.price, snapshot.best_odds.odds_format.value)

        selection_ids = list(snapshot.all_selection_odds.keys())
        avg_probs = []
        for sid in selection_ids:
            odds_list = snapshot.all_selection_odds.get(sid, [])
            if not odds_list:
                avg_probs.append(None)
                continue
            probs = [implied_probability(o.price, o.odds_format.value) for o in odds_list]
            avg_probs.append(sum(probs) / len(probs))

        overround = None
        market_normalized_probability = None
        n_priced = sum(1 for p in avg_probs if p is not None)
        if has_sufficient_market_info(n_priced, len(selection_ids)):
            overround = sum(avg_probs)
            normalized = normalize_probabilities(avg_probs)
            market_normalized_probability = normalized[selection_ids.index(snapshot.target_selection_id)]
        else:
            notes.append("Vig adjustment skipped: odds not available for every outcome in this market.")

        if model_output is None or model_output.confidence <= 0:
            notes.append("No usable model probability available for this selection.")
            return AnalysisResult(
                selection_id=snapshot.target_selection_id,
                market_implied_probability=market_prob,
                market_normalized_probability=market_normalized_probability,
                model_probability=None,
                model_confidence=None,
                model_name=None,
                edge=None,
                expected_value_per_unit=None,
                decimal_odds=decimal_odds,
                overround=overround,
                data_sufficient=False,
                notes=notes,
            )

        reference_prob = market_normalized_probability if market_normalized_probability is not None else market_prob
        computed_edge = calc_edge(model_output.probability, reference_prob)
        ev_result = expected_value(model_output.probability, decimal_odds, stake)

        return AnalysisResult(
            selection_id=snapshot.target_selection_id,
            market_implied_probability=market_prob,
            market_normalized_probability=market_normalized_probability,
            model_probability=model_output.probability,
            model_confidence=model_output.confidence,
            model_name=model_output.model_name,
            edge=computed_edge,
            expected_value_per_unit=ev_result.ev_per_unit_staked,
            decimal_odds=decimal_odds,
            overround=overround,
            data_sufficient=True,
            notes=notes,
        )


engine = AnalysisEngine()
