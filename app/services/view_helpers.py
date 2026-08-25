"""
Shared helpers that fetch data from the provider and run it through the
calculation/model/analysis layers. Both the Jinja2 HTML routes (main.py)
and the JSON API routes (app/api.py) call into these so the two surfaces
never duplicate business logic — they only differ in how they render it.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.data import provider
from app.models.entities import Event, EventStatus, Market, Odds, Selection
from app.models.prediction import MODEL_REGISTRY
from app.services.analysis import AnalysisEngine, AnalysisResult, MarketSnapshot

analysis_engine = AnalysisEngine()


async def list_sports():
    return await provider.get_sports()


async def list_events(
    sport_id: Optional[str] = None,
    on_date: Optional[date] = None,
    status: Optional[EventStatus] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Event]:
    events = await provider.get_events(sport_id=sport_id, on_date=on_date)
    if status:
        events = [e for e in events if e.status == status]
    if search:
        needle = search.lower()
        events = [
            e for e in events
            if needle in (e.home_team_name or "").lower() or needle in (e.away_team_name or "").lower()
        ]
    if limit:
        events = events[:limit]
    return events


async def get_market_bundle(event_id: str, market_type: str):
    """Returns (market, selections, all_odds) for the given event/market type."""
    markets = await provider.get_markets(event_id)
    market = next((m for m in markets if m.market_type == market_type), None)
    if not market:
        return None, [], []
    selections = await provider.get_selections(market.id)
    odds = await provider.get_odds(event_id=event_id, market_type=market_type)
    return market, selections, odds


def _current_odds_by_selection(selections: list[Selection], odds: list[Odds]) -> dict[str, list[Odds]]:
    by_sel: dict[str, list[Odds]] = {s.id: [] for s in selections}
    for o in odds:
        if o.selection_id in by_sel and not o.is_opening:
            by_sel[o.selection_id].append(o)
    return by_sel


def _opening_odds_by_selection(selections: list[Selection], odds: list[Odds]) -> dict[str, list[Odds]]:
    by_sel: dict[str, list[Odds]] = {s.id: [] for s in selections}
    for o in odds:
        if o.selection_id in by_sel and o.is_opening:
            by_sel[o.selection_id].append(o)
    return by_sel


async def analyze_selection(
    event_id: str,
    market_type: str,
    selection_id: str,
    model_key: str = "synthetic_elo",
    stake: float = 1.0,
):
    """
    Full pipeline: fetch market -> build snapshot -> run model -> run
    analysis engine. Returns a dict with everything a template or API
    response needs, or None if the event/market/selection isn't found.
    """
    event = provider.get_event(event_id)
    if not event:
        return None
    market, selections, odds = await get_market_bundle(event_id, market_type)
    if not market or selection_id not in {s.id for s in selections}:
        return None

    current_by_sel = _current_odds_by_selection(selections, odds)
    if not any(current_by_sel.values()):
        # Fall back to opening odds if no "current" snapshot exists (e.g. a
        # finished event only has opening/closing markers).
        current_by_sel = _opening_odds_by_selection(selections, odds)

    target_odds = current_by_sel.get(selection_id, [])
    if not target_odds:
        return {
            "event": event, "market": market, "selections": selections,
            "result": None, "model_output": None, "error": "No odds currently available for this selection.",
        }

    best = min(target_odds, key=lambda o: _implied(o))
    snapshot = MarketSnapshot(target_selection_id=selection_id, best_odds=best, all_selection_odds=current_by_sel)

    model = MODEL_REGISTRY.get(model_key, MODEL_REGISTRY["synthetic_elo"])
    is_home = selection_id.endswith("-sel-0")
    model_output = model.predict({
        "selection_odds": current_by_sel,
        "target_selection_id": selection_id,
        "home_team_id": event.home_team_id,
        "away_team_id": event.away_team_id,
        "target_is_home": is_home,
    })

    result: AnalysisResult = analysis_engine.analyze(snapshot, model_output, stake=stake)

    return {
        "event": event, "market": market, "selections": selections,
        "result": result, "model_output": model_output, "error": None,
        "target_selection": next(s for s in selections if s.id == selection_id),
    }


def _implied(o: Odds) -> float:
    from app.calculations.odds import implied_probability
    return implied_probability(o.price, o.odds_format.value)


async def upcoming_moneyline_options(sport_id: Optional[str] = None, limit: int = 60):
    """Convenience list for <select> menus: upcoming events that have a
    moneyline market, with both selections attached."""
    events = await list_events(sport_id=sport_id, status=EventStatus.SCHEDULED, limit=limit)
    options = []
    for e in events:
        market, selections, _odds = await get_market_bundle(e.id, "moneyline")
        if market and len(selections) == 2:
            options.append({"event": e, "market": market, "selections": selections})
    return options
