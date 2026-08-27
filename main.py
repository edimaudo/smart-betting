"""
SmartBet: FastAPI application entrypoint.

Server-rendered (FastAPI + Jinja2) per requirements.md section 1.
HTML routes live here; JSON API routes live in app/api.py and are
mounted under /api, kept conceptually separate per section 28.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import router as api_router
from app.calculations.odds import to_decimal
from app.calculations.stake import fixed_unit_stake, kelly_stake, percentage_bankroll_stake
from app.data import CONFIGURED, provider
from app.data.live_provider import LiveDataUnavailable
from app.decision.engine import DecisionEngine, DecisionInput
from app.models.entities import EventStatus, Strategy
from app.models.prediction import MODEL_REGISTRY
from app.services.view_helpers import (
    analyze_selection,
    get_market_bundle,
    list_events,
    list_sports,
    upcoming_moneyline_options,
)
from app.strategies.engine import DEFAULT_STRATEGIES, engine as strategy_engine
from app.simulation.monte_carlo import run_monte_carlo

app = FastAPI(title="SmartBet")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_router)

templates = Jinja2Templates(directory="templates")
templates.env.globals["data_status"] = lambda: {"mode": "live" if CONFIGURED else "unconfigured", "configured": CONFIGURED}
templates.env.globals["today_iso"] = lambda: date.today().isoformat()


@app.exception_handler(LiveDataUnavailable)
async def live_data_unavailable_handler(request: Request, exc: LiveDataUnavailable):
    return templates.TemplateResponse(
        "data_unavailable.html", {"request": request, "reason": str(exc)}, status_code=503,
    )

decision_engine = DecisionEngine()

STRATEGIES_BY_ID: dict[str, Strategy] = {s.id: s for s in DEFAULT_STRATEGIES}


def _strategy_or_default(strategy_id: Optional[str]) -> Strategy:
    return STRATEGIES_BY_ID.get(strategy_id, DEFAULT_STRATEGIES[0])


# ----------------------------------------------------------------------------
# Query params arrive as plain strings from HTML forms, including an empty
# string "" for any <select> left on "All ..." or a cleared date/number
# field. FastAPI's typed Optional[date]/Optional[int] params reject "" as
# invalid and return a raw 422 JSON error instead of the page, so every
# optional date/int/float filter below is accepted as a plain string and
# parsed here, tolerating blank or malformed input instead of crashing.
# ----------------------------------------------------------------------------
def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: Optional[str], default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


# ----------------------------------------------------------------------------
# Date bounds: Overview/Markets only ever show upcoming (scheduled) events, so
# a "date" filter there can never usefully be in the past. History only ever
# shows resolved (past) events, so its date_from/date_to can never usefully be
# in the future. Both directions are clamped here (not just via the <input
# max/min attributes in the templates, which a hand-built URL can bypass).
# ----------------------------------------------------------------------------
def _clamp_not_before_today(d: Optional[date]) -> Optional[date]:
    today = date.today()
    return today if (d is not None and d < today) else d


def _clamp_not_after_today(d: Optional[date]) -> Optional[date]:
    today = date.today()
    return today if (d is not None and d > today) else d


# ============================================================================
# 1. Overview
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def overview(
    request: Request,
    sport: Optional[str] = None,
    date: Optional[str] = None,
    market_type: str = "moneyline",
    q: Optional[str] = None,
):
    on_date = _clamp_not_before_today(_parse_date(date))
    sports = await list_sports()
    events = await list_events(
        sport_id=sport, on_date=on_date, search=q, status=EventStatus.SCHEDULED, limit=24,
    )

    cards = []
    for event in events:
        market, selections, odds = await get_market_bundle(event.id, market_type)
        if not market or len(selections) != 2:
            continue
        home_sel = next((s for s in selections if s.id.endswith("-sel-0")), selections[0])
        analysis = await analyze_selection(event.id, market_type, home_sel.id, model_key="synthetic_elo")
        cards.append({"event": event, "market": market, "analysis": analysis})

    return templates.TemplateResponse("index.html", {
        "request": request, "sports": sports, "cards": cards,
        "filters": {"sport": sport, "date": on_date, "market_type": market_type, "q": q or ""},
        "market_types": ["moneyline", "spread", "total"],
    })


# ============================================================================
# 2. Learn
# ============================================================================
@app.get("/learn", response_class=HTMLResponse)
async def learn(request: Request, tab: str = "overview"):
    if tab not in ("overview", "glossary", "quiz"):
        tab = "overview"
    return templates.TemplateResponse("learn.html", {"request": request, "active_tab": tab})


@app.get("/learn/quiz")
async def learn_quiz():
    return RedirectResponse(url="/learn?tab=quiz")


@app.get("/learn/simulator", response_class=HTMLResponse)
async def learn_simulator(request: Request):
    return templates.TemplateResponse("simulator.html", {"request": request})


# ============================================================================
# 3. Markets
# ============================================================================
@app.get("/markets", response_class=HTMLResponse)
async def markets(
    request: Request,
    sport: Optional[str] = None,
    date: Optional[str] = None,
    market_type: str = "moneyline",
    q: Optional[str] = None,
    sportsbook: Optional[str] = None,
):
    on_date = _clamp_not_before_today(_parse_date(date))
    sports = await list_sports()
    events = await list_events(
        sport_id=sport, on_date=on_date, search=q, status=EventStatus.SCHEDULED, limit=40,
    )

    rows = []
    all_books: set[str] = set()
    for event in events:
        market, selections, odds = await get_market_bundle(event.id, market_type)
        if not market:
            continue
        all_books.update(o.sportsbook for o in odds if not o.is_opening)
        if sportsbook:
            odds = [o for o in odds if o.sportsbook == sportsbook]
        current = [o for o in odds if not o.is_opening]
        if sportsbook and not current:
            continue
        rows.append({"event": event, "market": market, "selections": selections, "odds": current})

    books = sorted(all_books)

    return templates.TemplateResponse("markets.html", {
        "request": request, "sports": sports, "rows": rows, "sportsbooks": books,
        "filters": {"sport": sport, "date": on_date, "market_type": market_type, "q": q or "", "sportsbook": sportsbook or ""},
        "market_types": ["moneyline", "spread", "total"],
    })


@app.get("/markets/{event_id}", response_class=HTMLResponse)
async def market_detail(request: Request, event_id: str):
    event = provider.get_event(event_id)
    if not event:
        return templates.TemplateResponse("markets.html", {
            "request": request, "sports": await list_sports(), "rows": [], "sportsbooks": [],
            "filters": {"sport": None, "date": None, "market_type": "moneyline", "q": "", "sportsbook": ""},
            "market_types": ["moneyline", "spread", "total"], "not_found": True,
        }, status_code=404)

    market_blocks = []
    for mt in ["moneyline", "spread", "total"]:
        market, selections, odds = await get_market_bundle(event_id, mt)
        if not market:
            continue
        by_selection = []
        for sel in selections:
            by_selection.append({"selection": sel, "current": [o for o in odds if o.selection_id == sel.id]})
        market_blocks.append({"market": market, "by_selection": by_selection})

    return templates.TemplateResponse("market_detail.html", {
        "request": request, "event": event, "market_blocks": market_blocks,
    })


# ============================================================================
# 4. Data History
# ============================================================================
@app.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    sport: Optional[str] = None,
    season: Optional[str] = None,
    team: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    season_i = _parse_int(season)
    from_d = _clamp_not_after_today(_parse_date(date_from))
    to_d = _clamp_not_after_today(_parse_date(date_to))

    sports = await list_sports()
    sport_ids = [sport] if sport else ["nba", "nfl", "epl"]
    for sid in sport_ids:
        await provider.ensure_scores_loaded(sid)
    events = provider.get_finished_events(sport_id=sport)

    if season_i:
        events = [e for e in events if e.start_time.year == season_i]
    if from_d:
        events = [e for e in events if e.start_time.date() >= from_d]
    if to_d:
        events = [e for e in events if e.start_time.date() <= to_d]
    if team:
        needle = team.lower()
        events = [e for e in events if needle in (e.home_team_name or "").lower() or needle in (e.away_team_name or "").lower()]

    events = sorted(events, key=lambda e: e.start_time, reverse=True)[:60]

    rows = []
    for event in events:
        selections = provider.finished_event_selections(event)
        outcomes = {o.selection_id: o.result for o in provider.get_outcomes(event.id)}
        rows.append({"event": event, "selections": selections, "outcomes": outcomes})

    seasons = sorted({e.start_time.year for e in provider.get_finished_events()}, reverse=True)

    return templates.TemplateResponse("history.html", {
        "request": request, "sports": sports, "rows": rows, "seasons": seasons,
        "filters": {"sport": sport, "season": season_i, "team": team or "", "date_from": from_d, "date_to": to_d},
    })


# ============================================================================
# 5. Analyze
# ============================================================================
@app.get("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    sport: Optional[str] = None,
    event: Optional[str] = None,
    selection: Optional[str] = None,
    model: str = "synthetic_elo",
    stake: Optional[str] = None,
):
    stake_f = _parse_float(stake, 10.0)
    sports = await list_sports()
    options = await upcoming_moneyline_options(sport_id=sport)

    chosen_event_id = event or (options[0]["event"].id if options else None)
    chosen = next((o for o in options if o["event"].id == chosen_event_id), None)
    chosen_selection_id = selection
    if chosen and not chosen_selection_id:
        chosen_selection_id = chosen["selections"][0].id

    analysis = None
    if chosen_event_id and chosen_selection_id:
        analysis = await analyze_selection(chosen_event_id, "moneyline", chosen_selection_id, model_key=model, stake=stake_f)

    return templates.TemplateResponse("analyze.html", {
        "request": request, "sports": sports, "options": options,
        "models": MODEL_REGISTRY, "analysis": analysis,
        "filters": {"sport": sport, "event": chosen_event_id, "selection": chosen_selection_id, "model": model, "stake": stake_f},
    })


# ============================================================================
# 6. Strategies
# ============================================================================
@app.get("/strategies", response_class=HTMLResponse)
async def strategies(request: Request, strategy_id: str = "balanced", model: str = "synthetic_elo", sport: Optional[str] = None):
    active_strategy = _strategy_or_default(strategy_id)
    options = await upcoming_moneyline_options(sport_id=sport, limit=25)

    scanned = []
    counts = {"Strong Candidate": 0, "Candidate": 0, "Weak Candidate": 0, "Pass": 0, "Insufficient Data": 0}
    for opt in options:
        event = opt["event"]
        for sel in opt["selections"]:
            analysis = await analyze_selection(event.id, "moneyline", sel.id, model_key=model)
            if not analysis or not analysis["result"]:
                continue
            res = analysis["result"]
            market_prob = res.market_normalized_probability if res.market_normalized_probability is not None else res.market_implied_probability
            decision = decision_engine.decide(DecisionInput(
                market_probability=market_prob,
                model_probability=res.model_probability,
                edge=res.edge,
                expected_value=res.expected_value_per_unit,
                confidence=res.model_confidence,
                strategy=active_strategy,
                sport_id=event.sport_id,
                market_type="moneyline",
            ))
            counts[decision.classification.value] = counts.get(decision.classification.value, 0) + 1
            if decision.classification.value in ("Strong Candidate", "Candidate", "Weak Candidate"):
                scanned.append({"event": event, "selection": sel, "result": res, "decision": decision})

    scanned.sort(key=lambda r: (r["result"].edge or 0), reverse=True)

    return templates.TemplateResponse("strategies.html", {
        "request": request, "strategies": DEFAULT_STRATEGIES, "active_strategy": active_strategy,
        "scanned": scanned[:15], "counts": counts, "models": MODEL_REGISTRY,
        "filters": {"strategy_id": active_strategy.id, "model": model, "sport": sport},
    })


# ============================================================================
# 7. Simulate
# ============================================================================
@app.get("/simulate", response_class=HTMLResponse)
async def simulate(
    request: Request,
    mode: str = "backtest",
    sport: Optional[str] = "nba",
    strategy_id: str = "balanced",
    model: str = "synthetic_elo",
    unit_size: Optional[str] = None,
    win_probability: Optional[str] = None,
    decimal_odds: Optional[str] = None,
    stake: Optional[str] = None,
    bets_per_trial: Optional[str] = None,
    trials: Optional[str] = None,
):
    unit_size_f = _parse_float(unit_size, 10.0)
    win_probability_f = _parse_float(win_probability, 55.0)
    decimal_odds_f = _parse_float(decimal_odds, 1.91)
    stake_f = _parse_float(stake, 10.0)
    bets_per_trial_i = _parse_int(bets_per_trial) or 50
    trials_i = _parse_int(trials) or 2000

    backtest_result = None
    backtest_unavailable_reason = None
    mc_result = None

    if mode == "backtest":
        # A real backtest needs the price that was available at decision
        # time for each historical bet. The live provider's free tier has
        # no historical-odds endpoint (only real recent final scores via
        # /scores, used for History and the Elo model) — so rather than
        # backtest against a fabricated or substituted price, this mode
        # is disabled with an honest explanation. See README.md.
        backtest_unavailable_reason = (
            "Backtesting needs the odds that were actually available at the time of each "
            "historical bet. This app's live data source (The Odds API) only exposes that "
            "on a separate paid historical-odds add-on it doesn't have, so rather than "
            "substitute a fabricated price, backtesting is disabled here. Monte Carlo "
            "simulation below doesn't need historical prices and is fully available."
        )
    else:
        p = max(0.001, min(0.999, win_probability_f / 100.0))
        mc_result = run_monte_carlo(
            win_probability=p, decimal_odds=decimal_odds_f, stake=stake_f,
            bets_per_trial=max(1, bets_per_trial_i), trials=max(100, min(trials_i, 20000)),
        )
        if mc_result.return_distribution_sample:
            lo, hi = min(mc_result.return_distribution_sample), max(mc_result.return_distribution_sample)
            span = (hi - lo) or 1
            mc_result.bars = [round(((v - lo) / span) * 100, 1) for v in mc_result.return_distribution_sample]

    return templates.TemplateResponse("simulate.html", {
        "request": request, "strategies": DEFAULT_STRATEGIES, "models": MODEL_REGISTRY,
        "backtest_result": backtest_result, "backtest_unavailable_reason": backtest_unavailable_reason, "mc_result": mc_result,
        "filters": {
            "mode": mode, "sport": sport, "strategy_id": strategy_id, "model": model, "unit_size": unit_size_f,
            "win_probability": win_probability_f, "decimal_odds": decimal_odds_f, "stake": stake_f,
            "bets_per_trial": bets_per_trial_i, "trials": trials_i,
        },
    })


# ============================================================================
# 8. Decide
# ============================================================================
@app.get("/decide", response_class=HTMLResponse)
async def decide(
    request: Request,
    sport: Optional[str] = None,
    event: Optional[str] = None,
    selection: Optional[str] = None,
    strategy_id: str = "balanced",
    model: str = "synthetic_elo",
    unit_size: Optional[str] = None,
    bankroll: Optional[str] = None,
    kelly_fraction_pct: Optional[str] = None,
):
    unit_size_f = _parse_float(unit_size, 10.0)
    bankroll_f = _parse_float(bankroll, 1000.0)
    kelly_fraction_pct_f = _parse_float(kelly_fraction_pct, 50.0)

    sports = await list_sports()
    options = await upcoming_moneyline_options(sport_id=sport)
    active_strategy = _strategy_or_default(strategy_id)

    chosen_event_id = event or (options[0]["event"].id if options else None)
    chosen = next((o for o in options if o["event"].id == chosen_event_id), None)
    chosen_selection_id = selection
    if chosen and not chosen_selection_id:
        chosen_selection_id = chosen["selections"][0].id

    analysis = None
    decision = None
    stakes = None
    if chosen_event_id and chosen_selection_id:
        analysis = await analyze_selection(chosen_event_id, "moneyline", chosen_selection_id, model_key=model, stake=unit_size_f)
        if analysis and analysis["result"]:
            res = analysis["result"]
            market_prob = res.market_normalized_probability if res.market_normalized_probability is not None else res.market_implied_probability
            decision = decision_engine.decide(DecisionInput(
                market_probability=market_prob,
                model_probability=res.model_probability,
                edge=res.edge,
                expected_value=res.expected_value_per_unit,
                confidence=res.model_confidence,
                strategy=active_strategy,
                sport_id=analysis["event"].sport_id,
                market_type="moneyline",
                historical_sample_size=len(provider.get_finished_events(sport_id=analysis["event"].sport_id)),
            ))
            if res.model_probability is not None and res.decimal_odds:
                stakes = {
                    "fixed_unit": fixed_unit_stake(unit_size_f, active_strategy.max_stake_units),
                    "percent_bankroll_2pct": percentage_bankroll_stake(bankroll_f, 0.02),
                    "kelly_full": kelly_stake(bankroll_f, res.model_probability, res.decimal_odds, fraction=1.0),
                    "kelly_fractional": kelly_stake(bankroll_f, res.model_probability, res.decimal_odds, fraction=kelly_fraction_pct_f / 100.0),
                }

    return templates.TemplateResponse("decide.html", {
        "request": request, "sports": sports, "options": options, "strategies": DEFAULT_STRATEGIES,
        "models": MODEL_REGISTRY, "analysis": analysis, "decision": decision, "stakes": stakes,
        "filters": {
            "sport": sport, "event": chosen_event_id, "selection": chosen_selection_id,
            "strategy_id": active_strategy.id, "model": model, "unit_size": unit_size_f,
            "bankroll": bankroll_f, "kelly_fraction_pct": kelly_fraction_pct_f,
        },
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
