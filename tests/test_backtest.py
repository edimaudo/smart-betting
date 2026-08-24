from datetime import datetime, timedelta, timezone

import pytest

from app.decision.engine import DecisionEngine
from app.models.entities import Event, EventStatus, Market, ModelOutput, Odds, OddsFormat, Selection, Strategy
from app.models.prediction import BettingModel
from app.simulation.backtest import BacktestEngine


class _AlwaysConfidentModel(BettingModel):
    """A stub model used to assert the backtester never leaks
    closing-odds or future information into a decision."""
    name = "stub"
    assumptions = ["Test stub"]

    def __init__(self, probability=0.65, confidence=0.9):
        self._probability = probability
        self._confidence = confidence
        self.seen_odds_prices: list[float] = []

    def predict(self, data: dict) -> ModelOutput:
        # Record every odds price this model was ever shown, so tests can
        # assert closing odds never reached it.
        for odds_list in data["selection_odds"].values():
            self.seen_odds_prices.extend(o.price for o in odds_list)
        return ModelOutput(probability=self._probability, confidence=self._confidence, model_name=self.name)


def _build_single_event_fixture():
    start = datetime(2026, 1, 10, tzinfo=timezone.utc)
    event = Event(
        id="evt-1", sport_id="nba", league_id="nba-main",
        home_team_id="home", away_team_id="away",
        start_time=start, status=EventStatus.FINAL,
        home_team_name="Home Team", away_team_name="Away Team",
    )
    market = Market(id="evt-1-mkt-moneyline", event_id="evt-1", market_type="moneyline", name="Moneyline")
    sel_home = Selection(id="evt-1-mkt-moneyline-sel-0", market_id=market.id, name="Home Team")
    sel_away = Selection(id="evt-1-mkt-moneyline-sel-1", market_id=market.id, name="Away Team")

    # Opening odds (available at decision time) vs. closing odds (must
    # NEVER be used by the backtester as a decision-time input).
    opening_home = Odds(
        id="open-home", selection_id=sel_home.id, sportsbook="Book A", price=-120,
        odds_format=OddsFormat.AMERICAN, timestamp=start - timedelta(days=2), is_opening=True,
    )
    opening_away = Odds(
        id="open-away", selection_id=sel_away.id, sportsbook="Book A", price=110,
        odds_format=OddsFormat.AMERICAN, timestamp=start - timedelta(days=2), is_opening=True,
    )
    # Deliberately distinctive closing prices (a canary value) that should
    # never appear in the model's recorded inputs.
    closing_home = Odds(
        id="close-home", selection_id=sel_home.id, sportsbook="Book A", price=-999,
        odds_format=OddsFormat.AMERICAN, timestamp=start, is_closing=True,
    )
    closing_away = Odds(
        id="close-away", selection_id=sel_away.id, sportsbook="Book A", price=999,
        odds_format=OddsFormat.AMERICAN, timestamp=start, is_closing=True,
    )

    markets_by_event = {"evt-1": [market]}
    selections_by_market = {market.id: [sel_home, sel_away]}
    odds_by_market = {market.id: [opening_home, opening_away, closing_home, closing_away]}
    outcomes_by_event = {"evt-1": {sel_home.id: "win", sel_away.id: "loss"}}

    return event, markets_by_event, selections_by_market, odds_by_market, outcomes_by_event


class TestBacktestLookAheadBias:
    def test_closing_odds_never_shown_to_model(self):
        event, markets_by_event, selections_by_market, odds_by_market, outcomes_by_event = _build_single_event_fixture()
        model = _AlwaysConfidentModel()
        strategy = Strategy(id="s", name="s", min_edge=0.0, min_ev=-1.0, min_confidence=0.0)

        BacktestEngine(DecisionEngine()).run(
            events=[event],
            markets_by_event=markets_by_event,
            selections_by_market=selections_by_market,
            odds_by_market=odds_by_market,
            outcomes_by_event=outcomes_by_event,
            model=model,
            strategy=strategy,
        )

        assert -999 not in model.seen_odds_prices
        assert 999 not in model.seen_odds_prices
        assert -120 in model.seen_odds_prices
        assert 110 in model.seen_odds_prices

    def test_chronological_ordering_enforced(self):
        """Events passed out of order must still be processed chronologically."""
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = []
        markets_by_event, selections_by_market, odds_by_market, outcomes_by_event = {}, {}, {}, {}
        order_seen = []

        class OrderTrackingModel(BettingModel):
            name = "order-tracker"
            assumptions = []

            def predict(self, data):
                order_seen.append(data["target_selection_id"])
                return ModelOutput(probability=0.6, confidence=0.9, model_name=self.name)

        # Build 3 events, deliberately appended out of chronological order.
        for i, day_offset in enumerate([5, 1, 3]):
            eid = f"evt-{i}"
            start = base + timedelta(days=day_offset)
            event = Event(
                id=eid, sport_id="nba", league_id="nba-main",
                home_team_id="h", away_team_id="a", start_time=start,
                status=EventStatus.FINAL, home_team_name="H", away_team_name="A",
            )
            events.append(event)
            market = Market(id=f"{eid}-mkt", event_id=eid, market_type="moneyline", name="Moneyline")
            sel = Selection(id=f"{eid}-sel-0", market_id=market.id, name="H")
            sel2 = Selection(id=f"{eid}-sel-1", market_id=market.id, name="A")
            markets_by_event[eid] = [market]
            selections_by_market[market.id] = [sel, sel2]
            odds_by_market[market.id] = [
                Odds(id=f"{eid}-o1", selection_id=sel.id, sportsbook="B", price=-110,
                     odds_format=OddsFormat.AMERICAN, timestamp=start - timedelta(days=1), is_opening=True),
                Odds(id=f"{eid}-o2", selection_id=sel2.id, sportsbook="B", price=-110,
                     odds_format=OddsFormat.AMERICAN, timestamp=start - timedelta(days=1), is_opening=True),
            ]
            outcomes_by_event[eid] = {sel.id: "win", sel2.id: "loss"}

        strategy = Strategy(id="s", name="s", min_edge=0.0, min_ev=-1.0, min_confidence=0.0)
        BacktestEngine(DecisionEngine()).run(
            events=events, markets_by_event=markets_by_event,
            selections_by_market=selections_by_market, odds_by_market=odds_by_market,
            outcomes_by_event=outcomes_by_event, model=OrderTrackingModel(), strategy=strategy,
        )
        # evt-1 (day 1) should be evaluated before evt-2 (day 3) before evt-0 (day 5)
        assert order_seen[0].startswith("evt-1")
        assert order_seen[-1].startswith("evt-0")


class TestBacktestPerformance:
    def test_win_produces_correct_profit(self):
        event, markets_by_event, selections_by_market, odds_by_market, outcomes_by_event = _build_single_event_fixture()
        model = _AlwaysConfidentModel(probability=0.65, confidence=0.9)
        strategy = Strategy(id="s", name="s", min_edge=0.0, min_ev=-1.0, min_confidence=0.0, max_stake_units=1)

        result = BacktestEngine(DecisionEngine()).run(
            events=[event], markets_by_event=markets_by_event,
            selections_by_market=selections_by_market, odds_by_market=odds_by_market,
            outcomes_by_event=outcomes_by_event, model=model, strategy=strategy, unit_size=10,
        )
        assert result.events_bet >= 1
        home_bets = [b for b in result.bets if b.selection_name == "Home Team"]
        assert len(home_bets) == 1
        # -120 decimal odds ~1.833; win profit = stake * (decimal_odds - 1)
        assert home_bets[0].result == "win"
        assert home_bets[0].profit == pytest.approx(10 * (home_bets[0].decimal_odds - 1))

    def test_no_odds_available_skips_event_without_error(self):
        event, markets_by_event, selections_by_market, _, outcomes_by_event = _build_single_event_fixture()
        strategy = Strategy(id="s", name="s")
        result = BacktestEngine(DecisionEngine()).run(
            events=[event], markets_by_event=markets_by_event,
            selections_by_market=selections_by_market, odds_by_market={},
            outcomes_by_event=outcomes_by_event, model=_AlwaysConfidentModel(), strategy=strategy,
        )
        assert result.events_bet == 0
