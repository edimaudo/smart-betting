"""
Mock data provider.

No live sports/odds API is configured for this environment, so this
provider generates deterministic, realistic-looking sample data that
satisfies the `SportsDataProvider` interface. Swapping in a real
provider later only requires implementing that interface (see
provider.py) and pointing `app/data/__init__.py` at it — nothing in
the templates, routes, or analysis engine needs to change, because
they only ever see normalized `app.models.entities` objects.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.models.entities import (
    Event,
    EventStatus,
    Market,
    Odds,
    OddsFormat,
    Outcome,
    Selection,
    Sport,
)

_RNG_SEED = 42

SPORTS = [
    {"id": "nba", "name": "Basketball (NBA)"},
    {"id": "nfl", "name": "Football (NFL)"},
    {"id": "epl", "name": "Soccer (EPL)"},
]

LEAGUES = {
    "nba": {"id": "nba-main", "name": "National Basketball Association"},
    "nfl": {"id": "nfl-main", "name": "National Football League"},
    "epl": {"id": "epl-main", "name": "English Premier League"},
}

TEAMS = {
    "nba": [
        "Boston Celtics", "Denver Nuggets", "Los Angeles Lakers", "Golden State Warriors",
        "Milwaukee Bucks", "Miami Heat", "Phoenix Suns", "New York Knicks",
        "Dallas Mavericks", "Minnesota Timberwolves",
    ],
    "nfl": [
        "Kansas City Chiefs", "San Francisco 49ers", "Buffalo Bills", "Philadelphia Eagles",
        "Dallas Cowboys", "Baltimore Ravens", "Detroit Lions", "Miami Dolphins",
    ],
    "epl": [
        "Arsenal", "Manchester City", "Liverpool", "Chelsea",
        "Manchester United", "Tottenham Hotspur", "Newcastle United", "Aston Villa",
    ],
}

SPORTSBOOKS = ["Northgate", "Pinbook", "Meridian Bet", "Harborline"]

MARKET_TYPES = [
    {"market_type": "moneyline", "name": "Moneyline"},
    {"market_type": "spread", "name": "Point Spread"},
    {"market_type": "total", "name": "Total Points"},
]


def _rng_for(*parts: str) -> random.Random:
    """Deterministic RNG seeded from the given parts, so regenerating
    data for the same event/market always yields the same values."""
    return random.Random("|".join(parts) + f"|{_RNG_SEED}")


class MockSportsDataProvider:
    name = "mock"

    def __init__(self) -> None:
        self._sports = [Sport(**s) for s in SPORTS]
        self._teams: dict[str, list[dict]] = {
            sport_id: [
                {"id": f"{sport_id}-team-{i}", "league_id": LEAGUES[sport_id]["id"], "name": name}
                for i, name in enumerate(names)
            ]
            for sport_id, names in TEAMS.items()
        }
        self._events: dict[str, Event] = {}
        self._markets: dict[str, list[Market]] = {}
        self._selections: dict[str, list[Selection]] = {}
        self._odds: dict[str, list[Odds]] = {}
        self._outcomes: dict[str, list[Outcome]] = {}
        self._generate_events()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _generate_events(self) -> None:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        event_counter = 0

        for sport_id, teams in self._teams.items():
            rng = _rng_for("events", sport_id)
            # Past events (completed, for history/backtesting): 45 days back
            for day_offset in range(45, 0, -1):
                if rng.random() > 0.55:
                    continue
                home, away = rng.sample(teams, 2)
                start_time = now - timedelta(days=day_offset, hours=rng.randint(0, 5))
                event_counter += 1
                event_id = f"{sport_id}-evt-{event_counter:04d}"
                event = Event(
                    id=event_id,
                    sport_id=sport_id,
                    league_id=LEAGUES[sport_id]["id"],
                    home_team_id=home["id"],
                    away_team_id=away["id"],
                    start_time=start_time,
                    status=EventStatus.FINAL,
                    home_team_name=home["name"],
                    away_team_name=away["name"],
                    league_name=LEAGUES[sport_id]["name"],
                    sport_name=LEAGUES[sport_id]["name"].split(" ")[-1] if False else self._sport_name(sport_id),
                )
                self._events[event_id] = event
                self._generate_markets_and_odds(event, is_final=True, rng=rng)

            # Upcoming events: next 10 days
            for day_offset in range(0, 10):
                if rng.random() > 0.5:
                    continue
                home, away = rng.sample(teams, 2)
                start_time = now + timedelta(days=day_offset, hours=rng.randint(0, 8))
                event_counter += 1
                event_id = f"{sport_id}-evt-{event_counter:04d}"
                event = Event(
                    id=event_id,
                    sport_id=sport_id,
                    league_id=LEAGUES[sport_id]["id"],
                    home_team_id=home["id"],
                    away_team_id=away["id"],
                    start_time=start_time,
                    status=EventStatus.SCHEDULED,
                    home_team_name=home["name"],
                    away_team_name=away["name"],
                    league_name=LEAGUES[sport_id]["name"],
                    sport_name=self._sport_name(sport_id),
                )
                self._events[event_id] = event
                self._generate_markets_and_odds(event, is_final=False, rng=rng)

    def _sport_name(self, sport_id: str) -> str:
        return next(s["name"] for s in SPORTS if s["id"] == sport_id)

    def _generate_markets_and_odds(self, event: Event, is_final: bool, rng: random.Random) -> None:
        markets: list[Market] = []
        for i, mt in enumerate(MARKET_TYPES):
            market = Market(
                id=f"{event.id}-mkt-{mt['market_type']}",
                event_id=event.id,
                market_type=mt["market_type"],
                name=mt["name"],
            )
            markets.append(market)

            if mt["market_type"] == "moneyline":
                sel_names = [event.home_team_name, event.away_team_name]
            elif mt["market_type"] == "spread":
                line = round(rng.uniform(-9.5, 9.5) * 2) / 2
                sel_names = [f"{event.home_team_name} {line:+g}", f"{event.away_team_name} {-line:+g}"]
            else:  # total
                total_line = round(rng.uniform(195, 235) * 2) / 2 if event.sport_id == "nba" else round(rng.uniform(38, 52) * 2) / 2
                sel_names = [f"Over {total_line}", f"Under {total_line}"]

            selections = [
                Selection(id=f"{market.id}-sel-{j}", market_id=market.id, name=name)
                for j, name in enumerate(sel_names)
            ]
            self._selections[market.id] = selections

            fav_index = rng.randint(0, 1)
            base_prob = rng.uniform(0.52, 0.72)
            probs = [base_prob, 1 - base_prob] if fav_index == 0 else [1 - base_prob, base_prob]
            # add overround
            overround = rng.uniform(1.03, 1.07)
            priced_probs = [p * overround for p in probs]

            odds_list: list[Odds] = []
            retrieved_at = datetime.now(timezone.utc)
            for book in rng.sample(SPORTSBOOKS, k=3):
                for sel, p in zip(selections, priced_probs):
                    # jitter odds slightly per sportsbook
                    p_book = min(max(p * rng.uniform(0.97, 1.03), 0.02), 0.98)
                    american = self._prob_to_american(p_book)
                    opening_american = self._prob_to_american(
                        min(max(p * rng.uniform(0.95, 1.05), 0.02), 0.98)
                    )
                    if is_final:
                        odds_list.append(Odds(
                            id=f"{market.id}-{book}-{sel.id}-open",
                            selection_id=sel.id, sportsbook=book, price=opening_american,
                            odds_format=OddsFormat.AMERICAN, timestamp=event.start_time - timedelta(days=2),
                            is_opening=True, provider="mock", provider_event_id=event.id,
                            provider_market_id=market.id, retrieved_at=retrieved_at,
                        ))
                        odds_list.append(Odds(
                            id=f"{market.id}-{book}-{sel.id}-close",
                            selection_id=sel.id, sportsbook=book, price=american,
                            odds_format=OddsFormat.AMERICAN, timestamp=event.start_time,
                            is_closing=True, provider="mock", provider_event_id=event.id,
                            provider_market_id=market.id, retrieved_at=retrieved_at,
                        ))
                    else:
                        odds_list.append(Odds(
                            id=f"{market.id}-{book}-{sel.id}-open",
                            selection_id=sel.id, sportsbook=book, price=opening_american,
                            odds_format=OddsFormat.AMERICAN, timestamp=event.start_time - timedelta(days=3),
                            is_opening=True, provider="mock", provider_event_id=event.id,
                            provider_market_id=market.id, retrieved_at=retrieved_at,
                        ))
                        odds_list.append(Odds(
                            id=f"{market.id}-{book}-{sel.id}-current",
                            selection_id=sel.id, sportsbook=book, price=american,
                            odds_format=OddsFormat.AMERICAN, timestamp=retrieved_at,
                            provider="mock", provider_event_id=event.id,
                            provider_market_id=market.id, retrieved_at=retrieved_at,
                        ))
            self._odds[market.id] = odds_list

            if is_final:
                winner_index = 0 if rng.random() < probs[0] else 1
                for j, sel in enumerate(selections):
                    result = "win" if j == winner_index else "loss"
                    self._outcomes.setdefault(event.id, []).append(
                        Outcome(
                            id=f"{sel.id}-outcome",
                            event_id=event.id,
                            selection_id=sel.id,
                            result=result,
                            timestamp=event.start_time + timedelta(hours=3),
                        )
                    )

        self._markets[event.id] = markets

    @staticmethod
    def _prob_to_american(p: float) -> float:
        from app.calculations.odds import decimal_to_american
        decimal = 1.0 / p
        return round(decimal_to_american(decimal))

    # ------------------------------------------------------------------
    # SportsDataProvider interface
    # ------------------------------------------------------------------
    async def get_sports(self) -> list[Sport]:
        return list(self._sports)

    async def get_events(
        self,
        sport_id: Optional[str] = None,
        league_id: Optional[str] = None,
        on_date: Optional[date] = None,
    ) -> list[Event]:
        events = list(self._events.values())
        if sport_id:
            events = [e for e in events if e.sport_id == sport_id]
        if league_id:
            events = [e for e in events if e.league_id == league_id]
        if on_date:
            events = [e for e in events if e.start_time.date() == on_date]
        return sorted(events, key=lambda e: e.start_time)

    async def get_markets(self, event_id: str) -> list[Market]:
        return self._markets.get(event_id, [])

    async def get_selections(self, market_id: str) -> list[Selection]:
        return self._selections.get(market_id, [])

    async def get_odds(
        self,
        event_id: Optional[str] = None,
        market_type: Optional[str] = None,
        sportsbook: Optional[str] = None,
    ) -> list[Odds]:
        results: list[Odds] = []
        market_ids = []
        if event_id:
            market_ids = [m.id for m in self._markets.get(event_id, [])]
        else:
            market_ids = list(self._odds.keys())

        for mid in market_ids:
            for o in self._odds.get(mid, []):
                if market_type and market_type not in mid:
                    continue
                if sportsbook and o.sportsbook != sportsbook:
                    continue
                results.append(o)
        return results

    async def get_historical_data(
        self,
        sport_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Outcome]:
        events = [e for e in self._events.values() if e.status == EventStatus.FINAL]
        if sport_id:
            events = [e for e in events if e.sport_id == sport_id]
        if start_date:
            events = [e for e in events if e.start_time.date() >= start_date]
        if end_date:
            events = [e for e in events if e.start_time.date() <= end_date]
        outcomes: list[Outcome] = []
        for e in events:
            outcomes.extend(self._outcomes.get(e.id, []))
        return outcomes

    # ------------------------------------------------------------------
    # Convenience accessors used by routes (not part of the abstract
    # interface, but useful for a server-rendered MVP)
    # ------------------------------------------------------------------
    def get_event(self, event_id: str) -> Optional[Event]:
        return self._events.get(event_id)

    def get_team_name(self, sport_id: str, team_id: str) -> str:
        for t in self._teams.get(sport_id, []):
            if t["id"] == team_id:
                return t["name"]
        return team_id

    def get_finished_events(self, sport_id: Optional[str] = None) -> list[Event]:
        events = [e for e in self._events.values() if e.status == EventStatus.FINAL]
        if sport_id:
            events = [e for e in events if e.sport_id == sport_id]
        return sorted(events, key=lambda e: e.start_time)


# Module-level singleton so all requests share the same generated dataset
# for the lifetime of the process (mirrors an in-memory cache layer).
provider = MockSportsDataProvider()
