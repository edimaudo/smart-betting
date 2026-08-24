"""
Backtesting engine.

PRD section 22 sequence: Historical data -> Strategy -> Historical
decisions -> Historical outcomes -> Performance.

PRD section 23 (CRITICAL): backtesting must only use information that
would have been available at the time of the simulated decision. This
implementation enforces that by only ever reading ODDS marked
`is_opening` (i.e. the earliest known price for the event) as the
"decision-time" price — it never reads closing odds or the event
outcome until performance is scored at the end, and events are always
processed in chronological order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.calculations.edge import edge as calc_edge
from app.calculations.edge import expected_value
from app.calculations.odds import implied_probability, to_decimal
from app.calculations.stake import fixed_unit_stake
from app.decision.engine import Classification, Decision, DecisionEngine, DecisionInput
from app.models.entities import Event, Market, ModelOutput, Odds, Selection, Strategy
from app.models.prediction import BettingModel


@dataclass
class BacktestBet:
    event_id: str
    event_label: str
    selection_id: str
    selection_name: str
    start_time: str
    decimal_odds: float
    model_probability: float
    market_probability: float
    edge: float
    stake: float
    classification: str
    result: str  # "win" | "loss" | "push"
    profit: float


@dataclass
class BacktestResult:
    bets: list[BacktestBet] = field(default_factory=list)
    total_staked: float = 0.0
    total_profit: float = 0.0
    roi: float = 0.0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    average_return: float = 0.0
    max_drawdown: float = 0.0
    longest_losing_streak: int = 0
    events_considered: int = 0
    events_bet: int = 0


class BacktestEngine:
    def __init__(self, decision_engine: Optional[DecisionEngine] = None):
        self.decision_engine = decision_engine or DecisionEngine()

    def run(
        self,
        *,
        events: list[Event],
        markets_by_event: dict[str, list[Market]],
        selections_by_market: dict[str, list[Selection]],
        odds_by_market: dict[str, list[Odds]],
        outcomes_by_event: dict[str, dict[str, str]],  # event_id -> {selection_id: result}
        model: BettingModel,
        strategy: Strategy,
        unit_size: float = 10.0,
        market_type: str = "moneyline",
    ) -> BacktestResult:
        result = BacktestResult()

        # Chronological order is required to prevent look-ahead bias.
        ordered_events = sorted(events, key=lambda e: e.start_time)

        running_total = 0.0
        peak = 0.0
        max_drawdown = 0.0
        current_streak = 0
        longest_streak = 0

        for event in ordered_events:
            result.events_considered += 1
            markets = [m for m in markets_by_event.get(event.id, []) if m.market_type == market_type]
            if not markets:
                continue
            market = markets[0]
            selections = selections_by_market.get(market.id, [])
            if len(selections) < 2:
                continue

            all_odds = odds_by_market.get(market.id, [])
            # Decision-time view: ONLY opening odds are visible. This is the
            # look-ahead-bias guard required by PRD section 23.
            opening_odds_by_selection: dict[str, list[Odds]] = {}
            for sel in selections:
                opening_odds_by_selection[sel.id] = [o for o in all_odds if o.selection_id == sel.id and o.is_opening]

            for sel in selections:
                sel_opening = opening_odds_by_selection[sel.id]
                if not sel_opening:
                    continue
                best = min(sel_opening, key=lambda o: implied_probability(o.price, o.odds_format.value))
                decimal_odds = to_decimal(best.price, best.odds_format.value)
                market_prob = implied_probability(best.price, best.odds_format.value)

                is_home = sel.id.endswith("-sel-0")
                model_output: ModelOutput = model.predict({
                    "selection_odds": opening_odds_by_selection,
                    "target_selection_id": sel.id,
                    "home_team_id": event.home_team_id,
                    "away_team_id": event.away_team_id,
                    "target_is_home": is_home,
                })
                if model_output.confidence <= 0:
                    continue

                computed_edge = calc_edge(model_output.probability, market_prob)
                ev = expected_value(model_output.probability, decimal_odds, 1.0)

                decision: Decision = self.decision_engine.decide(DecisionInput(
                    market_probability=market_prob,
                    model_probability=model_output.probability,
                    edge=computed_edge,
                    expected_value=ev.ev_per_unit_staked,
                    confidence=model_output.confidence,
                    strategy=strategy,
                    sport_id=event.sport_id,
                    market_type=market.market_type,
                ))

                if decision.classification not in (Classification.STRONG_CANDIDATE, Classification.CANDIDATE):
                    continue

                # Place the simulated bet.
                stake = fixed_unit_stake(unit_size, min(strategy.max_stake_units, 1))
                actual_result = outcomes_by_event.get(event.id, {}).get(sel.id, "loss")
                if actual_result == "win":
                    profit = stake * (decimal_odds - 1)
                elif actual_result == "push":
                    profit = 0.0
                else:
                    profit = -stake

                result.bets.append(BacktestBet(
                    event_id=event.id,
                    event_label=f"{event.away_team_name} @ {event.home_team_name}",
                    selection_id=sel.id,
                    selection_name=sel.name,
                    start_time=event.start_time.isoformat(),
                    decimal_odds=decimal_odds,
                    model_probability=model_output.probability,
                    market_probability=market_prob,
                    edge=computed_edge,
                    stake=stake,
                    classification=decision.classification.value,
                    result=actual_result,
                    profit=profit,
                ))

                result.total_staked += stake
                result.total_profit += profit
                running_total += profit
                peak = max(peak, running_total)
                max_drawdown = max(max_drawdown, peak - running_total)

                if profit < 0:
                    current_streak += 1
                    longest_streak = max(longest_streak, current_streak)
                else:
                    current_streak = 0

        result.events_bet = len(result.bets)
        wins = sum(1 for b in result.bets if b.result == "win")
        losses = sum(1 for b in result.bets if b.result == "loss")
        n = len(result.bets)
        result.win_rate = wins / n if n else 0.0
        result.loss_rate = losses / n if n else 0.0
        result.roi = (result.total_profit / result.total_staked) if result.total_staked else 0.0
        result.average_return = (result.total_profit / n) if n else 0.0
        result.max_drawdown = max_drawdown
        result.longest_losing_streak = longest_streak

        return result


engine = BacktestEngine()
