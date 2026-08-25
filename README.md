# SmartBet

A structured, educational betting **decision-support** tool. It turns market odds and a
model's probability estimate into implied probability, vig-adjusted probability, edge,
expected value, and a strategy-gated verdict, with a Learn module, quiz, and a
no-real-money Learner Simulator to build the underlying intuition first.

Built to `prd.md` (included in this folder). Visual design follows IBM's Carbon Design
Language (IBM Plex Sans/Mono, flat rectangular surfaces, Carbon's blue/gray palette).

## Live data vs. sample data

By default SmartBet runs on a seeded, deterministic **mock data provider**
(`app/data/mock_provider.py`) with zero configuration. It also has a real, working
integration with **[The Odds API](https://the-odds-api.com/)** for genuine sportsbook
odds:

```bash
export ODDS_API_KEY=your-key-here   # free tier: 500 requests/month
uvicorn main:app --reload
```

The sidebar shows which mode is active. A few honest caveats about what "live" covers:

- **Live**: upcoming events and real moneyline/spread/total odds across real sportsbooks
  (Overview, Markets, Analyze, Decide).
- **Always sample data, even in live mode**: History and Simulate's Backtest, because
  The Odds API's free tier has no historical-odds endpoint (that's a separate paid add-on).
  The app tells you this in-page rather than silently substituting fake history.
- **If a live request fails** (bad key, rate limit, network issue), SmartBet falls back
  to sample data automatically rather than crashing the page, and the sidebar reflects that.
- This integration's live HTTP round-trip was exercised against the real API from this
  environment (confirmed via a real 403 with a placeholder key), and its response parsing
  is separately covered by `tests/test_live_provider.py` against a realistic fixture. It
  hasn't been verified end-to-end with an actual valid key, since this environment doesn't
  have one, so it's worth double-checking that first request once you add yours.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000**.

Run the test suite:

```bash
pytest -q
```

## What's here

| Area | Route | Purpose |
|---|---|---|
| Overview | `/` | Snapshot of upcoming events, filterable, with quick edge signals |
| Learn | `/learn` | Tabbed: Overview (concepts), Glossary (filterable), Quiz |
| Learner Simulator | `/learn/simulator` | Practice scenarios with reveal, no real wagers |
| Markets | `/markets`, `/markets/{event_id}` | Upcoming odds board + per-event opening vs. current |
| History | `/history` | Resolved events with closing prices and outcomes |
| Analyze | `/analyze` | Implied probability, de-vigged probability, model probability, edge, EV |
| Strategies | `/strategies` | Scan upcoming markets against configurable strategy thresholds |
| Simulate | `/simulate` | **Backtest** (historical, no look-ahead) or **Monte Carlo** (forward-looking) |
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
  data/          Provider interface, mock provider, live provider (The Odds API),
                 and a HybridProvider that prefers live and falls back to sample data
  calculations/  Pure functions: odds conversion, implied probability, vig removal, edge, EV, stake sizing
  services/      Analysis pipeline + shared view helpers used by both HTML and JSON routes
  strategies/    Strategy definitions + evaluator (min edge / EV / confidence gates)
  decision/      Decision engine: classification, reasons, and failed-criteria explanations
  simulation/    Backtest engine (no look-ahead) + Monte Carlo simulator
  api.py         JSON API router
templates/       Jinja2 templates (server-rendered)
static/          CSS design system + vanilla JS (theme, font scale, tabs, quiz, simulator, glossary)
tests/           pytest suite for calculations, decision rules, backtest integrity, both providers
```

**The Elo rating model** (`app/models/prediction.py: EloRatingModel`) is a real, working
Elo implementation: it replays every resolved event in the historical dataset in
chronological order and updates each team's rating with the standard logistic Elo formula
(K=20, +65 home-field advantage). It is not a placeholder or a hash-based stand-in. Its
one honest limitation is what it learns from: in sample mode that's this app's generated
dataset, and in live mode there's currently no free historical-results feed to learn from
at all (see above), so ratings there stay at a neutral baseline until one is connected.

**Swapping in another real data provider:** implement the same interface as
`app/data/provider.py` and register it in `app/data/__init__.py`'s `HybridProvider`.
Nothing in `calculations/`, `services/`, `strategies/`, `decision/`, or `simulation/`
needs to change.

## Design notes

- Built on IBM's Carbon Design Language: IBM Plex Sans for UI/copy, IBM Plex Mono for
  numeric readouts (odds, probabilities, EV), flat rectangular surfaces (no drop shadows,
  no soft rounded corners), and Carbon's Gray 100 (dark) / White (light) themes.
- Dark theme by default, light theme and 3-step font scaling available from the top bar
  (persisted client-side).
- Every EV/edge figure is shown alongside its formula inputs. This app is meant to explain
  its reasoning, not just output a verdict.

## Honest limitations (MVP scope)

- Historical data and backtesting always use the sample dataset; see "Live data vs.
  sample data" above for why.
- Only moneyline markets are fully wired through Analyze/Strategies/Decide; spread and
  total markets exist in the data layer and Markets/History browser but aren't yet run
  through the analysis pipeline.
- No accounts, persistence, or real transactions anywhere in the app.

## Responsible use

This tool is for **decision support and education**. It does not guarantee outcomes,
and positive expected value does not prevent losses on any individual bet. If betting
isn't enjoyable or feels out of control, please reach out to a local problem-gambling
support service.
