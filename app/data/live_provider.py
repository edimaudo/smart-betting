"""
Live data provider: real sportsbook odds via The Odds API. This is the
ONLY data source in this app; there is no sample/mock data fallback.

Honest scope of what "live" means here, since this matters a lot in a
betting app:

  * EVENTS + ODDS (moneyline / spread / total, across real sportsbooks)
    are genuinely live: this calls https://the-odds-api.com/'s public v4
    REST API directly.
  * RECENT RESULTS are also real and live, via the free `/scores`
    endpoint, but limited to completed events from the last few days
    (the free tier's `daysFrom` maximum is 3). This powers History and
    the Elo model's rating build.
  * What that endpoint does NOT include is the historical PRICE (odds)
    that was available at decision time for those completed games;
    that's a separate paid "historical odds" add-on this integration
    does not have. Because a real backtest needs to know the price at
    decision time, Simulate's Backtest mode is disabled with an honest
    explanation rather than run against fabricated prices. History
    shows the real final results but marks the closing-price column as
    unavailable rather than inventing a number.
  * The Elo model (app/models/prediction.py) trains on whatever recent
    real results are available (up to ~3 days per sport), which is a
    real but small sample; see its own docstring for that caveat.

If ODDS_API_KEY is missing or a request fails, every method here raises
LiveDataUnavailable rather than returning fabricated data; app-level
code (main.py) turns that into a clear, honest error page.

Get a free API key (500 requests/month on the free tier) at
https://the-odds-api.com/ and set it as the ODDS_API_KEY environment
variable before starting the app — see README.md.

Note on how this was verified: this environment's outbound network
access turned out to reach api.the-odds-api.com directly, so the HTTP
request below was exercised against the real, live endpoint. With a
placeholder key it correctly received a genuine 403 from their server
(not a connection failure), confirming the URL/params/request shape
are well-formed. What was NOT verified is a full successful 200
response, since that requires an actual key this environment doesn't
have. Response *parsing* is covered independently by
`tests/test_live_provider.py` against fixture payloads shaped exactly
like the documented v4 schema.
"""
from __future__ import annotations

import os
import re
import time
from datetime import date, datetime, timezone
from typing import Optional

import httpx

from app.data.provider import SportsDataProvider
from app.models.entities import Event, EventStatus, Market, Odds, OddsFormat, Outcome, Selection, Sport

ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Maps this app's internal sport ids to The Odds API's sport keys.
SPORT_KEYS: dict[str, str] = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "epl": "soccer_epl",
}
SPORT_NAMES: dict[str, str] = {
    "nba": "Basketball (NBA)",
    "nfl": "Football (NFL)",
    "epl": "Soccer (EPL)",
}
MARKET_KEY_TO_TYPE = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
MARKET_TYPE_NAME = {"moneyline": "Moneyline", "spread": "Point Spread", "total": "Total Points"}

_CACHE_TTL_SECONDS = 300  # avoid burning the free tier's monthly quota


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class LiveDataUnavailable(RuntimeError):
    """Raised when live mode is requested but no API key / a failed call."""


class TheOddsApiProvider(SportsDataProvider):
    """Real sportsbook data via The Odds API v4. See module docstring for
    exactly what is and isn't "live" here."""

    name = "the-odds-api"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LiveDataUnavailable("ODDS_API_KEY is not set.")
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)
        # sport_id -> (fetched_at_epoch, raw_events_json)
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        # event_id -> raw event json, populated as sports are fetched
        self._events_raw: dict[str, dict] = {}
        # Real recent-results cache, from the free /scores endpoint.
        # sport_id -> fetched_at_epoch
        self._scores_fetched_at: dict[str, float] = {}
        self._finished_events_cache: dict[str, list[Event]] = {}
        self._outcomes_cache: dict[str, list[Outcome]] = {}

    async def _raw_events(self, sport_id: str) -> list[dict]:
        cached = self._cache.get(sport_id)
        now = time.time()
        if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

        sport_key = SPORT_KEYS.get(sport_id)
        if not sport_key:
            return []

        url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
        params = {
            "apiKey": self._api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveDataUnavailable(f"The Odds API request failed: {exc}") from exc

        self._cache[sport_id] = (now, data)
        for raw in data:
            self._events_raw[raw["id"]] = raw
        return data

    @staticmethod
    def _parse_event(sport_id: str, raw: dict) -> Event:
        home_name = raw.get("home_team") or ""
        away_name = raw.get("away_team") or ""
        return Event(
            id=raw["id"],
            sport_id=sport_id,
            league_id=f"{sport_id}-live",
            home_team_id=_slugify(home_name) or "home",
            away_team_id=_slugify(away_name) or "away",
            start_time=datetime.fromisoformat(raw["commence_time"].replace("Z", "+00:00")),
            status=EventStatus.SCHEDULED,
            home_team_name=home_name,
            away_team_name=away_name,
            league_name=SPORT_NAMES.get(sport_id, sport_id.upper()),
            sport_name=SPORT_NAMES.get(sport_id, sport_id.upper()),
        )

    @staticmethod
    def _selection_names(market_type: str, home_name: str, away_name: str) -> list[str]:
        if market_type in ("moneyline", "spread"):
            return [home_name, away_name]
        return ["Over", "Under"]

    def _build_markets_and_odds(self, event: Event, raw: dict) -> tuple[list[Market], dict[str, list[Selection]], dict[str, list[Odds]]]:
        markets: list[Market] = []
        selections_by_market: dict[str, list[Selection]] = {}
        odds_by_market: dict[str, list[Odds]] = {}
        present_market_types: set[str] = set()

        for bookmaker in raw.get("bookmakers", []):
            book_name = bookmaker.get("title") or bookmaker.get("key") or "Unknown"
            for market_json in bookmaker.get("markets", []):
                mtype = MARKET_KEY_TO_TYPE.get(market_json.get("key"))
                if not mtype:
                    continue
                market_id = f"{event.id}-mkt-{mtype}"
                if mtype not in present_market_types:
                    present_market_types.add(mtype)
                    markets.append(Market(id=market_id, event_id=event.id, market_type=mtype, name=MARKET_TYPE_NAME[mtype]))
                    sel_names = self._selection_names(mtype, event.home_team_name or "", event.away_team_name or "")
                    selections_by_market[market_id] = [
                        Selection(id=f"{market_id}-sel-{i}", market_id=market_id, name=n) for i, n in enumerate(sel_names)
                    ]
                    odds_by_market[market_id] = []

                selections = selections_by_market[market_id]
                # Match each priced outcome to the selection with the same
                # name (home/away team name, or Over/Under) so selection
                # index 0 is always "home" (or "Over") regardless of the
                # order the sportsbook happened to list outcomes in.
                for outcome in market_json.get("outcomes", []):
                    sel = next((s for s in selections if s.name == outcome.get("name")), None)
                    if not sel:
                        continue
                    price = outcome.get("price")
                    if price is None:
                        continue
                    ts = market_json.get("last_update") or bookmaker.get("last_update") or raw.get("commence_time")
                    try:
                        timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    except ValueError:
                        timestamp = datetime.now(timezone.utc)
                    odds_by_market[market_id].append(Odds(
                        id=f"{market_id}-{_slugify(book_name)}-{sel.id}",
                        selection_id=sel.id,
                        sportsbook=book_name,
                        price=float(price),
                        odds_format=OddsFormat.AMERICAN,
                        timestamp=timestamp,
                        is_opening=False,
                        is_closing=False,
                        provider=self.name,
                        provider_event_id=event.id,
                        provider_market_id=market_id,
                        retrieved_at=datetime.now(timezone.utc),
                    ))

        return markets, selections_by_market, odds_by_market

    # ------------------------------------------------------------------
    # SportsDataProvider interface
    # ------------------------------------------------------------------
    async def get_sports(self) -> list[Sport]:
        return [Sport(id=sid, name=name) for sid, name in SPORT_NAMES.items()]

    async def get_events(
        self,
        sport_id: Optional[str] = None,
        league_id: Optional[str] = None,
        on_date: Optional[date] = None,
    ) -> list[Event]:
        sport_ids = [sport_id] if sport_id else list(SPORT_KEYS.keys())
        events: list[Event] = []
        for sid in sport_ids:
            raw_list = await self._raw_events(sid)
            for raw in raw_list:
                event = self._parse_event(sid, raw)
                if on_date and event.start_time.date() != on_date:
                    continue
                events.append(event)
        return sorted(events, key=lambda e: e.start_time)

    async def get_markets(self, event_id: str) -> list[Market]:
        raw = self._events_raw.get(event_id)
        if not raw:
            return []
        # sport_id isn't stored on the raw payload; recover it from cache keys
        sport_id = next((sid for sid, (_, evs) in self._cache.items() if any(e["id"] == event_id for e in evs)), "nba")
        event = self._parse_event(sport_id, raw)
        markets, _, _ = self._build_markets_and_odds(event, raw)
        return markets

    async def get_selections(self, market_id: str) -> list[Selection]:
        event_id = market_id.rsplit("-mkt-", 1)[0]
        raw = self._events_raw.get(event_id)
        if not raw:
            return []
        sport_id = next((sid for sid, (_, evs) in self._cache.items() if any(e["id"] == event_id for e in evs)), "nba")
        event = self._parse_event(sport_id, raw)
        _, sels_by_market, _ = self._build_markets_and_odds(event, raw)
        return sels_by_market.get(market_id, [])

    async def get_odds(
        self,
        event_id: Optional[str] = None,
        market_type: Optional[str] = None,
        sportsbook: Optional[str] = None,
    ) -> list[Odds]:
        results: list[Odds] = []
        event_ids = [event_id] if event_id else list(self._events_raw.keys())
        for eid in event_ids:
            raw = self._events_raw.get(eid)
            if not raw:
                continue
            sport_id = next((sid for sid, (_, evs) in self._cache.items() if any(e["id"] == eid for e in evs)), "nba")
            event = self._parse_event(sport_id, raw)
            _, _, odds_by_market = self._build_markets_and_odds(event, raw)
            for market_id, odds_list in odds_by_market.items():
                if market_type and not market_id.endswith(f"-mkt-{market_type}"):
                    continue
                for o in odds_list:
                    if sportsbook and o.sportsbook != sportsbook:
                        continue
                    results.append(o)
        return results

    async def ensure_scores_loaded(self, sport_id: str, days_from: int = 3) -> None:
        """Fetch real, recently-completed results for one sport from the
        free `/scores` endpoint (max `daysFrom=3` on the free tier) and
        populate the finished-events/outcomes caches from them."""
        now = time.time()
        fetched_at = self._scores_fetched_at.get(sport_id)
        if fetched_at and (now - fetched_at) < _CACHE_TTL_SECONDS:
            return

        sport_key = SPORT_KEYS.get(sport_id)
        if not sport_key:
            return

        url = f"{ODDS_API_BASE}/sports/{sport_key}/scores"
        params = {"apiKey": self._api_key, "daysFrom": min(max(days_from, 1), 3), "dateFormat": "iso"}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LiveDataUnavailable(f"The Odds API scores request failed: {exc}") from exc

        finished_events: list[Event] = []
        outcomes_by_event: dict[str, list[Outcome]] = {}

        for raw in data:
            if not raw.get("completed"):
                continue
            scores = raw.get("scores")
            home_name, away_name = raw.get("home_team"), raw.get("away_team")
            if not scores or not home_name or not away_name:
                continue
            score_by_name = {s.get("name"): s.get("score") for s in scores if s.get("score") is not None}
            if home_name not in score_by_name or away_name not in score_by_name:
                continue
            try:
                home_score = float(score_by_name[home_name])
                away_score = float(score_by_name[away_name])
            except (TypeError, ValueError):
                continue

            event = Event(
                id=raw["id"], sport_id=sport_id, league_id=f"{sport_id}-live",
                home_team_id=_slugify(home_name) or "home", away_team_id=_slugify(away_name) or "away",
                start_time=datetime.fromisoformat(raw["commence_time"].replace("Z", "+00:00")),
                status=EventStatus.FINAL, home_team_name=home_name, away_team_name=away_name,
                league_name=SPORT_NAMES.get(sport_id, sport_id.upper()), sport_name=SPORT_NAMES.get(sport_id, sport_id.upper()),
            )
            finished_events.append(event)

            market_id = f"{event.id}-mkt-moneyline"
            ts = datetime.now(timezone.utc)
            if home_score > away_score:
                home_result, away_result = "win", "loss"
            elif home_score < away_score:
                home_result, away_result = "loss", "win"
            else:
                home_result, away_result = "push", "push"
            outcomes_by_event[event.id] = [
                Outcome(id=f"{market_id}-sel-0-outcome", event_id=event.id, selection_id=f"{market_id}-sel-0", result=home_result, timestamp=ts),
                Outcome(id=f"{market_id}-sel-1-outcome", event_id=event.id, selection_id=f"{market_id}-sel-1", result=away_result, timestamp=ts),
            ]

        self._finished_events_cache[sport_id] = sorted(finished_events, key=lambda e: e.start_time)
        self._outcomes_cache.update(outcomes_by_event)
        self._scores_fetched_at[sport_id] = now

    async def get_historical_data(
        self,
        sport_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Outcome]:
        sport_ids = [sport_id] if sport_id else list(SPORT_KEYS.keys())
        results: list[Outcome] = []
        for sid in sport_ids:
            await self.ensure_scores_loaded(sid)
            for event in self.get_finished_events(sport_id=sid):
                if start_date and event.start_time.date() < start_date:
                    continue
                if end_date and event.start_time.date() > end_date:
                    continue
                results.extend(self.get_outcomes(event.id))
        return results

    # ------------------------------------------------------------------
    # Convenience accessors (match MockSportsDataProvider's extra surface
    # so main.py / prediction.py can treat either provider identically)
    # ------------------------------------------------------------------
    def get_event(self, event_id: str) -> Optional[Event]:
        raw = self._events_raw.get(event_id)
        if not raw:
            return None
        sport_id = next((sid for sid, (_, evs) in self._cache.items() if any(e["id"] == event_id for e in evs)), "nba")
        return self._parse_event(sport_id, raw)

    def get_team_name(self, sport_id: str, team_id: str) -> str:
        return team_id.replace("-", " ").title()

    def get_finished_events(self, sport_id: Optional[str] = None) -> list[Event]:
        if sport_id:
            return list(self._finished_events_cache.get(sport_id, []))
        all_events: list[Event] = []
        for events in self._finished_events_cache.values():
            all_events.extend(events)
        return sorted(all_events, key=lambda e: e.start_time)

    def get_outcomes(self, event_id: str) -> list[Outcome]:
        return list(self._outcomes_cache.get(event_id, []))

    @staticmethod
    def finished_event_selections(event: Event) -> list[Selection]:
        """Synthesize the two moneyline selections for a finished event.
        Real completed games aren't present in the /odds endpoint cache
        anymore, so there's no live market/selection payload for them;
        this only needs to produce display names + ids matching the
        `{event.id}-mkt-moneyline-sel-{0,1}` convention used by
        ensure_scores_loaded()'s outcomes, so History can label rows and
        the Elo model can match selections to results."""
        market_id = f"{event.id}-mkt-moneyline"
        return [
            Selection(id=f"{market_id}-sel-0", market_id=market_id, name=event.home_team_name or "Home"),
            Selection(id=f"{market_id}-sel-1", market_id=market_id, name=event.away_team_name or "Away"),
        ]
