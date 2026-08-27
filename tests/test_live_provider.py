"""
Tests for the live-odds provider's parsing logic.

These do NOT hit the real network (this environment's outbound access
is restricted to package registries) — they feed a realistic fixture
payload, shaped exactly like The Odds API's documented v4 response,
directly into the parsing methods and assert the normalized
Event/Market/Selection/Odds objects come out correctly. This is the
part of the integration that's actually verifiable here; the live
HTTP round-trip itself should be checked by whoever supplies a real
ODDS_API_KEY.
"""
from __future__ import annotations

import pytest

from app.data.live_provider import TheOddsApiProvider

FIXTURE_EVENT = {
    "id": "evt-fixture-001",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2026-09-01T23:10:00Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Denver Nuggets",
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "last_update": "2026-08-24T12:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "last_update": "2026-08-24T12:00:00Z",
                    "outcomes": [
                        {"name": "Denver Nuggets", "price": 130},
                        {"name": "Los Angeles Lakers", "price": -155},
                    ],
                },
                {
                    "key": "spreads",
                    "last_update": "2026-08-24T12:00:00Z",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": -110, "point": -3.5},
                        {"name": "Denver Nuggets", "price": -110, "point": 3.5},
                    ],
                },
                {
                    "key": "totals",
                    "last_update": "2026-08-24T12:00:00Z",
                    "outcomes": [
                        {"name": "Over", "price": -108, "point": 224.5},
                        {"name": "Under", "price": -112, "point": 224.5},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2026-08-24T12:05:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "last_update": "2026-08-24T12:05:00Z",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": -150},
                        {"name": "Denver Nuggets", "price": 125},
                    ],
                },
            ],
        },
    ],
}


@pytest.fixture
def live_provider():
    # A syntactically valid but obviously-fake key is fine: construction
    # never makes a network call, only .get_events()/.get_odds() etc do.
    return TheOddsApiProvider(api_key="test-key-not-real")


def test_parse_event_maps_core_fields(live_provider):
    event = live_provider._parse_event("nba", FIXTURE_EVENT)
    assert event.id == "evt-fixture-001"
    assert event.sport_id == "nba"
    assert event.home_team_name == "Los Angeles Lakers"
    assert event.away_team_name == "Denver Nuggets"
    assert event.start_time.year == 2026 and event.start_time.month == 9 and event.start_time.day == 1
    assert event.status.value == "scheduled"


def test_home_selection_is_always_index_zero_regardless_of_outcome_order(live_provider):
    """DraftKings lists the away team (Nuggets) first in its h2h outcomes;
    FanDuel lists the home team (Lakers) first. Selection index 0 must be
    the home team in both cases, because the rest of the app (Elo model,
    Overview's `-sel-0` convention) depends on that invariant."""
    event = live_provider._parse_event("nba", FIXTURE_EVENT)
    _, selections_by_market, odds_by_market = live_provider._build_markets_and_odds(event, FIXTURE_EVENT)

    ml_market_id = "evt-fixture-001-mkt-moneyline"
    selections = selections_by_market[ml_market_id]
    assert selections[0].name == "Los Angeles Lakers"
    assert selections[1].name == "Denver Nuggets"

    # Both books' Lakers price should attach to selection 0, regardless of
    # each book's own outcome ordering.
    lakers_sel_id = selections[0].id
    lakers_odds = [o for o in odds_by_market[ml_market_id] if o.selection_id == lakers_sel_id]
    prices_by_book = {o.sportsbook: o.price for o in lakers_odds}
    assert prices_by_book["DraftKings"] == -155
    assert prices_by_book["FanDuel"] == -150


def test_all_three_market_types_are_parsed(live_provider):
    event = live_provider._parse_event("nba", FIXTURE_EVENT)
    markets, _, _ = live_provider._build_markets_and_odds(event, FIXTURE_EVENT)
    market_types = {m.market_type for m in markets}
    assert market_types == {"moneyline", "spread", "total"}


def test_totals_selections_are_over_under(live_provider):
    event = live_provider._parse_event("nba", FIXTURE_EVENT)
    _, selections_by_market, odds_by_market = live_provider._build_markets_and_odds(event, FIXTURE_EVENT)
    total_market_id = "evt-fixture-001-mkt-total"
    names = [s.name for s in selections_by_market[total_market_id]]
    assert names == ["Over", "Under"]
    over_sel_id = selections_by_market[total_market_id][0].id
    over_price = next(o.price for o in odds_by_market[total_market_id] if o.selection_id == over_sel_id)
    assert over_price == -108


def test_odds_are_tagged_with_provenance(live_provider):
    event = live_provider._parse_event("nba", FIXTURE_EVENT)
    _, _, odds_by_market = live_provider._build_markets_and_odds(event, FIXTURE_EVENT)
    any_odds = next(iter(odds_by_market["evt-fixture-001-mkt-moneyline"]))
    assert any_odds.provider == "the-odds-api"
    assert any_odds.provider_event_id == "evt-fixture-001"
    assert any_odds.odds_format.value == "american"


def test_failed_live_call_raises_rather_than_fabricating_data():
    """With no mocked HTTP layer, this hits the real API with a fake key.
    It must raise LiveDataUnavailable (a real 403 from their server) —
    never silently substitute empty/fake historical data."""
    import asyncio

    from app.data.live_provider import LiveDataUnavailable

    provider = TheOddsApiProvider(api_key="test-key-not-real")
    with pytest.raises(LiveDataUnavailable):
        asyncio.run(provider.get_historical_data(sport_id="nba"))

    # Caches are empty before any successful fetch, which is a distinct,
    # honest "not loaded yet" state — not to be confused with "confirmed
    # no results". Callers must call ensure_scores_loaded() first.
    assert provider.get_finished_events(sport_id="nba") == []
    assert provider.get_outcomes("any-event-id") == []


def test_missing_api_key_raises():
    from app.data.live_provider import LiveDataUnavailable

    with pytest.raises(LiveDataUnavailable):
        TheOddsApiProvider(api_key="")


FIXTURE_SCORES = [
    {
        "id": "score-fixture-001",
        "sport_key": "basketball_nba",
        "commence_time": "2026-08-23T23:00:00Z",
        "completed": True,
        "home_team": "Los Angeles Lakers",
        "away_team": "Denver Nuggets",
        "scores": [
            {"name": "Los Angeles Lakers", "score": "110"},
            {"name": "Denver Nuggets", "score": "104"},
        ],
        "last_update": "2026-08-24T02:00:00Z",
    },
    {
        # Not completed yet: must be skipped entirely.
        "id": "score-fixture-002",
        "sport_key": "basketball_nba",
        "commence_time": "2026-08-25T23:00:00Z",
        "completed": False,
        "home_team": "Boston Celtics",
        "away_team": "Miami Heat",
        "scores": None,
    },
]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patch_scores_endpoint(monkeypatch, provider, payload=FIXTURE_SCORES):
    async def fake_get(url, params=None):
        assert "/scores" in url
        return _FakeResponse(payload)

    monkeypatch.setattr(provider._client, "get", fake_get)


def test_ensure_scores_loaded_parses_real_completed_games(live_provider, monkeypatch):
    import asyncio

    _patch_scores_endpoint(monkeypatch, live_provider)
    asyncio.run(live_provider.ensure_scores_loaded("nba"))
    finished = live_provider.get_finished_events(sport_id="nba")

    assert len(finished) == 1  # the incomplete game must be excluded
    event = finished[0]
    assert event.id == "score-fixture-001"
    assert event.status.value == "final"
    assert event.home_team_name == "Los Angeles Lakers"


def test_ensure_scores_loaded_derives_correct_win_loss(live_provider, monkeypatch):
    import asyncio

    _patch_scores_endpoint(monkeypatch, live_provider)
    asyncio.run(live_provider.ensure_scores_loaded("nba"))
    outcomes = live_provider.get_outcomes("score-fixture-001")
    results_by_selection = {o.selection_id: o.result for o in outcomes}

    # Lakers (home, sel-0) scored higher, so home wins / away loses.
    assert results_by_selection["score-fixture-001-mkt-moneyline-sel-0"] == "win"
    assert results_by_selection["score-fixture-001-mkt-moneyline-sel-1"] == "loss"


def test_get_historical_data_respects_date_range(live_provider, monkeypatch):
    import asyncio
    from datetime import date as date_cls

    _patch_scores_endpoint(monkeypatch, live_provider)

    # The fixture's completed game is on 2026-08-23.
    in_range = asyncio.run(live_provider.get_historical_data(sport_id="nba", start_date=date_cls(2026, 8, 20), end_date=date_cls(2026, 8, 25)))
    assert len(in_range) == 2  # two selections' worth of outcomes

    out_of_range = asyncio.run(live_provider.get_historical_data(sport_id="nba", start_date=date_cls(2026, 1, 1), end_date=date_cls(2026, 1, 2)))
    assert out_of_range == []


def test_finished_event_selections_match_outcome_selection_ids():
    from datetime import datetime as dt_cls, timezone as tz

    from app.models.entities import Event as EventModel
    from app.models.entities import EventStatus as EventStatusEnum

    event = EventModel(
        id="evt-x", sport_id="nba", league_id="nba-live", home_team_id="a", away_team_id="b",
        start_time=dt_cls.now(tz.utc), status=EventStatusEnum.FINAL,
        home_team_name="Team A", away_team_name="Team B",
    )
    selections = TheOddsApiProvider.finished_event_selections(event)
    assert selections[0].id == "evt-x-mkt-moneyline-sel-0"
    assert selections[0].name == "Team A"
    assert selections[1].id == "evt-x-mkt-moneyline-sel-1"
