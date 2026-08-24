"""
Prediction model interface and example implementations.

PRD section 20: models implement a common interface and must expose
their assumptions. PRD section 13: the system supports multiple
analytical model categories rather than a single prediction model.

These are intentionally simple, transparent reference
implementations — not production-grade forecasting models. Swapping
in a more sophisticated model (regression, gradient boosting, a
proper Elo pipeline fit on real results, etc.) only requires
implementing `BettingModel.predict`.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

from app.calculations.odds import implied_probability
from app.calculations.vig import has_sufficient_market_info, normalize_probabilities
from app.models.entities import ModelOutput, Odds


class BettingModel(ABC):
    """Common interface every prediction model must implement."""

    name: str = "base-model"
    assumptions: list[str] = []

    @abstractmethod
    def predict(self, data: dict) -> ModelOutput:
        """
        `data` is expected to contain at least:
          - "selection_odds": dict[selection_id, list[Odds]] for the
            full market (all selections), used for de-vigging and as
            model input.
          - "target_selection_id": the selection being evaluated.
        """
        ...


class MarketConsensusModel(BettingModel):
    """
    Baseline model: averages the de-vigged implied probability across
    all available sportsbooks for the target selection.

    This model has no independent view of the event — by
    construction its edge against the (also de-vigged) market will
    hover near zero. It exists as a transparent baseline / sanity
    check for the pipeline, and as a component other models can
    compare themselves against.
    """
    name = "Market Consensus"
    assumptions = [
        "Uses the de-vigged average of currently available sportsbook prices.",
        "Assumes proportional (multiplicative) vig removal.",
        "Has no independent signal beyond the market itself; edge vs. "
        "market should be close to zero by construction.",
    ]

    def predict(self, data: dict) -> ModelOutput:
        selection_odds: dict[str, list[Odds]] = data["selection_odds"]
        target_id: str = data["target_selection_id"]

        selection_ids = list(selection_odds.keys())
        avg_probs = []
        for sid in selection_ids:
            odds_list = selection_odds[sid]
            if not odds_list:
                avg_probs.append(None)
                continue
            probs = [implied_probability(o.price, o.odds_format.value) for o in odds_list]
            avg_probs.append(sum(probs) / len(probs))

        if any(p is None for p in avg_probs) or not has_sufficient_market_info(
            sum(1 for p in avg_probs if p is not None), len(selection_ids)
        ):
            return ModelOutput(probability=0.0, confidence=0.0, model_name=self.name,
                                assumptions=self.assumptions)

        normalized = normalize_probabilities(avg_probs)
        target_index = selection_ids.index(target_id)
        n_books = len(selection_odds[target_id])
        confidence = min(0.5 + 0.1 * n_books, 0.9)

        return ModelOutput(
            probability=normalized[target_index],
            confidence=confidence,
            model_name=self.name,
            assumptions=self.assumptions,
        )


class SyntheticEloModel(BettingModel):
    """
    Illustrative Elo-style rating model.

    Team ratings are DETERMINISTICALLY DERIVED from the team id (a
    stable hash), since no historical results feed a real rating
    update in this environment. This makes the model reproducible and
    clearly synthetic rather than presenting invented ratings as if
    they were fit to real history.

    Replace `_rating_for_team` with a real Elo pipeline (updated from
    `get_historical_data`) to use this model with genuine signal.
    """
    name = "Synthetic Elo (illustrative)"
    assumptions = [
        "Team ratings are deterministically derived placeholders, not "
        "fit to real historical results — for demonstration of the "
        "model pipeline only.",
        "Uses a standard logistic Elo win-probability curve.",
        "Ignores home/away, injuries, rest, and matchup-specific context.",
    ]

    @staticmethod
    def _rating_for_team(team_id: str) -> float:
        digest = hashlib.sha256(team_id.encode()).hexdigest()
        # Map hash to a rating spread of roughly 1400-1700
        offset = int(digest[:6], 16) % 300
        return 1400 + offset

    def predict(self, data: dict) -> ModelOutput:
        home_team_id: str = data["home_team_id"]
        away_team_id: str = data["away_team_id"]
        target_is_home: bool = data["target_is_home"]

        r_home = self._rating_for_team(home_team_id)
        r_away = self._rating_for_team(away_team_id)
        home_edge = 60  # small synthetic home-field bump

        p_home = 1.0 / (1.0 + 10 ** (((r_away) - (r_home + home_edge)) / 400))
        p_target = p_home if target_is_home else (1 - p_home)

        return ModelOutput(
            probability=p_target,
            confidence=0.55,
            model_name=self.name,
            assumptions=self.assumptions,
        )


MODEL_REGISTRY: dict[str, BettingModel] = {
    "market_consensus": MarketConsensusModel(),
    "synthetic_elo": SyntheticEloModel(),
}
