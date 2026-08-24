"""
Internal JSON API.

PRD section 28: internal API endpoints, kept conceptually separate
from the Jinja2 HTML routes in main.py. Mounted under /api by main.py.

This is a read-oriented MVP API (GET + query params throughout,
including for the simulation/decision endpoints) so every endpoint is
trivially callable from a browser or curl without a request body.
"""
from __future__ import annotations

import dataclasses
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.data.mock_provider import provider
from app.decision.engine import DecisionEngine, DecisionInput
from app.models.entities import EventStatus
from app.models.prediction import MODEL_REGISTRY
from app.services.view_helpers import analyze_selection, get_market_bundle, list_events, list_sports
from app.simulation.backtest import BacktestEngine
from app.simulation.monte_carlo import run_monte_carlo
from app.strategies.engine import DEFAULT_STRATEGIES

router = APIRouter(prefix="/api", tags=["api"])
decision_engine = DecisionEngine()
backtest_engine = BacktestEngine(decision_engine)
STRATEGIES_BY_ID = {s.id: s for s in DEFAULT_STRATEGIES}


def _asdict(obj):
    if dataclasses.is_dataclass(obj):
        out = {}
        for f in dataclasses.fields(obj):
            out[f.name] = _asdict(getattr(obj, f.name))
        return out
    if isinstance(obj, list):
        return [_asdict(x) for x in obj]
    if hasattr(obj, "value") and hasattr(obj, "name") and not isinstance(obj, (int, str)):
        return obj.value  # Enum
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


@router.get("/sports")
async def api_sports():
    return {"sports": [s.model_dump() for s in await list_sports()]}


@router.get("/events")
async def api_events(
    sport: Optional[str] = None,
    on_date: Optional[date] = Query(None, alias="date"),
    status: Optional[EventStatus] = None,
    limit: int = 50,
):
    events = await list_events(sport_id=sport, on_date=on_date, status=status, limit=limit)
    return {"count": len(events), "events": [e.model_dump(mode="json") for e in events]}


@router.get("/markets")
async def api_markets(event_id: str):
    markets = await provider.get_markets(event_id)
    if not markets:
        raise HTTPException(status_code=404, detail="No markets found for this event_id.")
    return {"event_id": event_id, "markets": [m.model_dump() for m in markets]}


@router.get("/odds")
async def api_odds(event_id: Optional[str] = None, market_type: Optional[str] = None, sportsbook: Optional[str] = None):
    odds = await provider.get_odds(event_id=event_id, market_type=market_type, sportsbook=sportsbook)
    return {"count": len(odds), "odds": [o.model_dump(mode="json") for o in odds]}


@router.get("/history")
async def api_history(sport: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
    outcomes = await provider.get_historical_data(sport_id=sport, start_date=start_date, end_date=end_date)
    return {"count": len(outcomes), "outcomes": [o.model_dump(mode="json") for o in outcomes]}


@router.get("/analyze")
async def api_analyze(event_id: str, selection_id: str, market_type: str = "moneyline", model: str = "synthetic_elo", stake: float = 1.0):
    if model not in MODEL_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'. Options: {list(MODEL_REGISTRY.keys())}")
    outcome = await analyze_selection(event_id, market_type, selection_id, model_key=model, stake=stake)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Event, market, or selection not found.")
    if outcome["error"]:
        return {"error": outcome["error"]}
    return {
        "event_id": event_id,
        "selection_id": selection_id,
        "model_output": _asdict(outcome["model_output"]) if outcome["model_output"] else None,
        "analysis": _asdict(outcome["result"]),
    }


@router.get("/strategies")
async def api_strategies():
    return {"strategies": [s.model_dump() for s in DEFAULT_STRATEGIES]}


@router.get("/decisions")
async def api_decisions(
    event_id: str,
    selection_id: str,
    market_type: str = "moneyline",
    model: str = "synthetic_elo",
    strategy_id: str = "balanced",
):
    strategy = STRATEGIES_BY_ID.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=400, detail=f"Unknown strategy_id '{strategy_id}'. Options: {list(STRATEGIES_BY_ID.keys())}")

    outcome = await analyze_selection(event_id, market_type, selection_id, model_key=model)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Event, market, or selection not found.")
    if outcome["error"] or not outcome["result"]:
        decision = decision_engine.decide(DecisionInput(
            market_probability=None, model_probability=None, edge=None,
            expected_value=None, confidence=None, strategy=strategy,
        ))
        return {"decision": _asdict(decision)}

    res = outcome["result"]
    event = outcome["event"]
    market_prob = res.market_normalized_probability if res.market_normalized_probability is not None else res.market_implied_probability
    decision = decision_engine.decide(DecisionInput(
        market_probability=market_prob,
        model_probability=res.model_probability,
        edge=res.edge,
        expected_value=res.expected_value_per_unit,
        confidence=res.model_confidence,
        strategy=strategy,
        sport_id=event.sport_id,
        market_type=market_type,
    ))
    return {"analysis": _asdict(res), "decision": _asdict(decision)}


@router.get("/simulations/backtest")
async def api_backtest(sport: str = "nba", strategy_id: str = "balanced", model: str = "synthetic_elo", unit_size: float = 10.0):
    strategy = STRATEGIES_BY_ID.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=400, detail=f"Unknown strategy_id '{strategy_id}'.")
    active_model = MODEL_REGISTRY.get(model)
    if not active_model:
        raise HTTPException(status_code=400, detail=f"Unknown model '{model}'.")

    events = provider.get_finished_events(sport_id=sport)
    markets_by_event, selections_by_market, odds_by_market, outcomes_by_event = {}, {}, {}, {}
    for e in events:
        mkts = await provider.get_markets(e.id)
        markets_by_event[e.id] = mkts
        for m in mkts:
            sels = await provider.get_selections(m.id)
            selections_by_market[m.id] = sels
            odds_by_market[m.id] = await provider.get_odds(event_id=e.id, market_type=m.market_type)
        outcomes_by_event[e.id] = {o.selection_id: o.result for o in provider._outcomes.get(e.id, [])}

    result = backtest_engine.run(
        events=events, markets_by_event=markets_by_event, selections_by_market=selections_by_market,
        odds_by_market=odds_by_market, outcomes_by_event=outcomes_by_event,
        model=active_model, strategy=strategy, unit_size=unit_size,
    )
    return {"result": _asdict(result)}


@router.get("/simulations/monte-carlo")
async def api_monte_carlo(
    win_probability: float = 0.55,
    decimal_odds: float = 1.91,
    stake: float = 10.0,
    bets_per_trial: int = 50,
    trials: int = 2000,
):
    if trials > 20000:
        raise HTTPException(status_code=400, detail="trials must be <= 20000")
    result = run_monte_carlo(
        win_probability=win_probability, decimal_odds=decimal_odds, stake=stake,
        bets_per_trial=bets_per_trial, trials=trials,
    )
    return {"result": _asdict(result)}
