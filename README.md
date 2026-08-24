# Smart Betting

A structured, educational betting **decision-support** tool: it turns market odds and a
model's probability estimate into implied probability, vig-adjusted probability, edge,
expected value, and a strategy-gated verdict — with a Learn module, quiz, and a
no-real-money Learner Simulator to build the underlying intuition first.

Built to `prd.md` (included in this folder). All market/odds/historical data is produced
by a seeded, deterministic **mock data provider** (`app/data/mock_provider.py`) — there is
no live sportsbook integration and no real money ever changes hands anywhere in this app.

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
| Overview | `/` | Snapshot of today's markets, filterable, with quick edge signals |
| Learn | `/learn` | Betting overview, searchable glossary, approaches, risks, strategic-thinking model |
| Quiz | `/learn/quiz` | 10-question readiness check (client-side, immediate feedback) |
| Learner Simulator | `/learn/simulator` | Practice scenarios with reveal — no real wagers |
| Markets | `/markets`, `/markets/{event_id}` | Current odds board + per-event opening vs. current |
| History | `/history` | Resolved events with closing prices and outcomes |
| Analyze | `/analyze` | Implied probability, de-vigged probability, model probability, edge, EV |
| Strategies | `/strategies` | Scan upcoming markets against configurable strategy thresholds |
| Simulate | `/simulate` | **Backtest** (historical, no look-ahead) or **Monte Carlo** (forward-looking) |
| Decide | `/decide` | Final strategy-gated verdict with reasons, failed criteria, and stake sizing |

A parallel JSON API is mounted under `/api` (`app/api.py`) — the HTML routes in `main.py`
and the JSON API both call the same `app/services/view_helpers.py` functions, so business
logic is never duplicated between the two surfaces. See `/docs` for the interactive API
reference once the server is running.

## Architecture

```
app/
  models/        Pydantic entities (Event, Market, Selection, Odds, Strategy, ...)
  data/          Provider interface + seeded mock provider (swap in a real API later)
  calculations/  Pure functions: odds conversion, implied probability, vig removal, edge, EV, stake sizing
  services/      Analysis pipeline + shared view helpers used by both HTML and JSON routes
  strategies/    Strategy definitions + evaluator (min edge / EV / confidence gates)
  decision/      Decision engine — classification, reasons, and failed-criteria explanations
  simulation/    Backtest engine (no look-ahead) + Monte Carlo simulator
  api.py         JSON API router
templates/       Jinja2 templates (server-rendered)
static/          CSS design system + vanilla JS (theme, font scale, quiz, simulator, glossary)
tests/           pytest suite for calculations, decision rules, backtest integrity, provider
```

**Swapping in a real data provider:** implement the same interface as
`app/data/provider.py` against a real odds API and point `app/data/mock_provider.py`'s
import in `main.py` / `app/api.py` at it. Nothing in `calculations/`, `services/`,
`strategies/`, `decision/`, or `simulation/` needs to change.

## Design notes

- Dark theme by default, light theme and 3-step font scaling available from the top bar
  (persisted client-side).
- Numeric/data fields render in a monospace face (tabular figures) so odds, probabilities,
  and EV are easy to scan and compare at a glance; prose stays in Inter.
- Every EV/edge figure is shown alongside its formula inputs — this app is meant to explain
  its reasoning, not just output a verdict.

## Honest limitations (MVP scope)

- All data is synthetic and deterministic (seeded), not live odds.
- Only moneyline markets are fully wired through Analyze/Strategies/Decide; spread and
  total markets exist in the data layer and Markets/History browser but aren't yet run
  through the analysis pipeline.
- Models in `app/models/prediction.py` are simple, explainable stand-ins (e.g. a synthetic
  Elo-style model) — not production forecasting models.
- No accounts, persistence, or real transactions anywhere in the app.

## Responsible use

This tool is for **decision support and education**. It does not guarantee outcomes,
and positive expected value does not prevent losses on any individual bet. If betting
isn't enjoyable or feels out of control, please reach out to a local problem-gambling
support service.
