# SmartBet

A structured, educational betting **decision-support** tool. It turns market odds and a
model's probability estimate into implied probability, vig-adjusted probability, edge,
expected value, and a strategy-gated verdict, with a Learn module, quiz, and a
no-real-money Learner Simulator to build the underlying intuition first.

Built to `prd.md` (included in this folder). Visual design follows IBM's Carbon Design
Language (IBM Plex Sans/Mono, flat rectangular surfaces, Carbon's blue/gray palette).

## Live data only, no sample data

SmartBet uses **[The Odds API](https://the-odds-api.com/)** for real sportsbook data.
There is no synthetic/mock fallback: if live data isn't configured or a request fails,
pages that need it show a clear error explaining why, rather than ever substituting
fabricated data.

```bash
export ODDS_API_KEY=your-key-here   # free tier: 500 requests/month, no credit card
uvicorn main:app --reload
```

Get a key at https://the-odds-api.com/ (about 2 minutes to sign up).

**What "live" covers, precisely:**

| Data | Status | Source |
|---|---|---|
| Upcoming events, moneyline/spread/total odds, across real sportsbooks | Live | `/v4/sports/{sport}/odds` |
| Recent final scores/results (last ~3 days) | Live | `/v4/sports/{sport}/scores` (free tier) |
| Historical odds (the price available at a past decision time) | **Not available** | Requires a separate paid add-on this integration doesn't have |

Because of that last row:
- **History** shows real, recently-completed games with real outcomes, but the
  closing-price column is explicitly labeled "Not available" rather than filled with a
  fabricated number.
- **Simulate → Backtest** is disabled with an on-page explanation, because a real backtest
  needs the price at decision time, which isn't available. **Monte Carlo simulation**
  doesn't need historical prices at all and is fully functional.
- The **Elo rating model** trains on whatever real recent results exist (up to ~3 days
  per sport), a real but small sample. A team that hasn't played recently sits at a
  neutral baseline rating until it does.

If a live request fails (bad key, rate limit, network issue), the affected page shows a
503 error page with the reason, rather than falling back to any substitute data.

**Verification status:** this integration's HTTP request shape was exercised against the
real live endpoint from the environment it was built in (a placeholder key correctly got
a real 403 from The Odds API's server, not a connection failure), and the response
*parsing* is covered by `tests/test_live_provider.py` against fixtures shaped like the
documented schema. A full successful response with a real key hasn't been verified
end-to-end, since that environment didn't have one — worth confirming on first run.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
export ODDS_API_KEY=your-key-here
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000**.

Run the test suite:

```bash
pytest -q
```

(Tests don't require `ODDS_API_KEY` — the live provider's HTTP calls are mocked in
`tests/test_live_provider.py`.)

## What's here

| Area | Route | Purpose |
|---|---|---|
| Overview | `/` | Snapshot of upcoming events, filterable, with quick edge signals |
| Learn | `/learn` | Tabbed: Overview (concepts), Glossary (filterable), Quiz — no live data needed |
| Learner Simulator | `/learn/simulator` | Practice scenarios with reveal, no real wagers, no live data needed |
| Markets | `/markets`, `/markets/{event_id}` | Live upcoming odds board + per-event sportsbook comparison |
| History | `/history` | Real recently-completed games and outcomes (see limitations above) |
| Analyze | `/analyze` | Implied probability, de-vigged probability, model probability, edge, EV |
| Strategies | `/strategies` | Scan upcoming markets against configurable strategy thresholds |
| Simulate | `/simulate` | Monte Carlo (forward-looking); Backtest is disabled, see above |
| Decide | `/decide` | Final strategy-gated verdict with reasons, failed criteria, and stake sizing |

A parallel JSON API is mounted under `/api` (`app/api.py`). The HTML routes in `main.py`
and the JSON API both call the same `app/services/view_helpers.py` functions, so business
logic is never duplicated between the two surfaces. See `/docs` for the interactive API
reference once the server is running.

## Architecture

```
app/
  models/        Pydantic entities (Event, Market, Selection, Odds, Strategy, ...)
                 + prediction.py: market-consensus model and a real Elo rating model
  data/
    provider.py       Abstract provider interface
    live_provider.py  TheOddsApiProvider — the only real data source
    __init__.py       Live-only wiring: TheOddsApiProvider if ODDS_API_KEY is set,
                       else UnconfiguredProvider (every call raises LiveDataUnavailable)
    mock_provider.py  Kept only for isolated unit tests; never used by the running app
  calculations/  Pure functions: odds conversion, implied probability, vig removal, edge, EV, stake sizing
  services/      Analysis pipeline + shared view helpers used by both HTML and JSON routes
  strategies/    Strategy definitions + evaluator (min edge / EV / confidence gates)
  decision/      Decision engine: classification, reasons, and failed-criteria explanations
  simulation/    Monte Carlo simulator (backtest.py exists but is unused; see above)
  api.py         JSON API router
templates/       Jinja2 templates (server-rendered)
static/          CSS design system + vanilla JS (theme, font scale, tabs, quiz, simulator, glossary)
tests/           pytest suite for calculations, decision rules, both providers
```

**Handling live-data failure consistently:** every provider method raises
`LiveDataUnavailable` (in `app/data/live_provider.py`) for both "not configured" and "a
live request failed" — main.py's global exception handler catches that one exception type
and renders `templates/data_unavailable.html`, so there's exactly one error path to reason
about regardless of the cause.

**The Elo rating model** (`app/models/prediction.py: EloRatingModel`) is a real, working
Elo implementation: an async `ensure_ready()` step (called by `analyze_selection` before
every prediction) pulls real recent results from the live provider and replays them
chronologically with the standard logistic Elo update (K=20, +65 home-field advantage).
It is not a placeholder or a hash-based stand-in. Its one honest limitation is the ~3-day
lookback window described above.

**Swapping in another real data provider:** implement the same interface as
`app/data/provider.py` and update `app/data/__init__.py`'s wiring. Nothing in
`calculations/`, `services/`, `strategies/`, `decision/`, or `simulation/` needs to change.

## Design notes

- Built on IBM's Carbon Design Language: IBM Plex Sans for UI/copy, IBM Plex Mono for
  numeric readouts (odds, probabilities, EV), flat rectangular surfaces (no drop shadows,
  no soft rounded corners), and Carbon's Gray 100 (dark) / White (light) themes.
- Dark theme by default, light theme and 3-step font scaling available from the top bar
  (persisted client-side).
- Every EV/edge figure is shown alongside its formula inputs. This app is meant to explain
  its reasoning, not just output a verdict.
- Date filters are bounded to make sense with live-only data: Overview/Markets can't be
  set before today (only upcoming events exist); History can't be set after today (only
  past results exist), both enforced client-side (`min`/`max`) and server-side.

## Honest limitations (MVP scope)

- No historical odds anywhere (see table above); Backtest is disabled as a result.
- The Elo model's training window is limited to ~3 days of recent results per sport.
- Only moneyline markets are fully wired through Analyze/Strategies/Decide; spread and
  total markets exist in the data layer and the Markets browser but aren't yet run
  through the analysis pipeline.
- No accounts, persistence, or real transactions anywhere in the app.

## Responsible use

This tool is for **decision support and education**. It does not guarantee outcomes,
and positive expected value does not prevent losses on any individual bet. If betting
isn't enjoyable or feels out of control, please reach out to a local problem-gambling
support service.
