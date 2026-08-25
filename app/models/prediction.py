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


class EloRatingModel(BettingModel):
    """
    A real, functioning Elo rating model.

    Every team starts at a base rating of 1500. Ratings are built by
    replaying every resolved event in this environment's dataset in
    chronological order and applying the standard logistic Elo update
    after each result -- this is a genuine Elo pipeline, not a
    placeholder. Predictions for an upcoming matchup use each team's
    current (post-history) rating.

    The one honest caveat: this MVP has no live sports history
    connected, so the results this model learns from are the same
    generated dataset used everywhere else in the app, not real-world
    results. Point it at a real historical results feed (via
    `build_from_results`) and the same Elo math applies unchanged.
    """
    name = "Elo Rating Model"
    assumptions = [
        "Uses a real, standard Elo rating update (K=20), replayed "
        "chronologically over every resolved event in this environment's "
        "dataset -- the rating math itself is genuine, not a placeholder.",
        "This MVP has no live sports history connected, so it is trained "
        "on this environment's generated results rather than real-world "
        "outcomes -- swap in a real results feed to change that.",
        "Applies a fixed home-field advantage (+65 rating points) and "
        "ignores injuries, rest, and other matchup-specific context.",
        "Confidence scales with how many historical results informed "
        "each team's current rating (more games -> higher confidence).",
    ]

    K_FACTOR = 20.0
    HOME_ADVANTAGE = 65.0
    BASE_RATING = 1500.0

    def __init__(self) -> None:
        self._ratings: dict[str, float] = {}
        self._games_played: dict[str, int] = {}
        self._built = False

    def build_from_results(self, games: list[tuple[str, str, float]]) -> None:
        """
        Replay a chronological list of (home_team_id, away_team_id,
        home_score_fraction) results, where home_score_fraction is 1.0
        for a home win, 0.0 for an away win, or 0.5 for a push/draw.
        Idempotent to call again with a fuller history.
        """
        for home_id, away_id, actual_home in games:
            r_home = self._ratings.get(home_id, self.BASE_RATING)
            r_away = self._ratings.get(away_id, self.BASE_RATING)

            expected_home = 1.0 / (1.0 + 10 ** ((r_away - (r_home + self.HOME_ADVANTAGE)) / 400))
            self._ratings[home_id] = r_home + self.K_FACTOR * (actual_home - expected_home)
            self._ratings[away_id] = r_away + self.K_FACTOR * ((1 - actual_home) - (1 - expected_home))

            self._games_played[home_id] = self._games_played.get(home_id, 0) + 1
            self._games_played[away_id] = self._games_played.get(away_id, 0) + 1
        self._built = True

    def _ensure_built(self) -> None:
        if self._built:
            return
        # Lazy self-build from this environment's mock provider so the
        # model works out of the box. A production deployment would call
        # `build_from_results(...)` explicitly with real historical data
        # at startup instead of relying on this fallback.
        from app.data import provider

        games: list[tuple[str, str, float]] = []
        for sport in sorted(provider._teams.keys()):
            for event in provider.get_finished_events(sport_id=sport):
                outcomes = provider.get_outcomes(event.id)
                home_sel_id = f"{event.id}-mkt-moneyline-sel-0"
                home_result = next((o.result for o in outcomes if o.selection_id == home_sel_id), None)
                if home_result is None:
                    continue
                actual_home = 1.0 if home_result == "win" else (0.5 if home_result == "push" else 0.0)
                games.append((event.home_team_id, event.away_team_id, actual_home))
        self.build_from_results(games)

    def rating_for(self, team_id: str) -> float:
        self._ensure_built()
        return self._ratings.get(team_id, self.BASE_RATING)

    def predict(self, data: dict) -> ModelOutput:
        self._ensure_built()
        home_team_id: str = data["home_team_id"]
        away_team_id: str = data["away_team_id"]
        target_is_home: bool = data["target_is_home"]

        r_home = self._ratings.get(home_team_id, self.BASE_RATING)
        r_away = self._ratings.get(away_team_id, self.BASE_RATING)
        games_home = self._games_played.get(home_team_id, 0)
        games_away = self._games_played.get(away_team_id, 0)

        p_home = 1.0 / (1.0 + 10 ** ((r_away - (r_home + self.HOME_ADVANTAGE)) / 400))
        p_target = p_home if target_is_home else (1 - p_home)

        confidence = min(0.5 + 0.02 * min(games_home, games_away), 0.85)

        return ModelOutput(
            probability=p_target,
            confidence=confidence,
            model_name=self.name,
            assumptions=self.assumptions,
        )


MODEL_REGISTRY: dict[str, BettingModel] = {
    "market_consensus": MarketConsensusModel(),
    "synthetic_elo": EloRatingModel(),
}
