import asyncio
from datetime import date

import pytest

from app.data.mock_provider import MockSportsDataProvider
from app.models.entities import Event, Market, Odds, Outcome, Selection, Sport


@pytest.fixture(scope="module")
def provider():
    return MockSportsDataProvider()


def run(coro):
    return asyncio.run(coro)


class TestProviderNormalization:
    def test_get_sports_returns_normalized_entities(self, provider):
        sports = run(provider.get_sports())
        assert len(sports) > 0
        assert all(isinstance(s, Sport) for s in sports)

    def test_get_events_returns_normalized_entities(self, provider):
        events = run(provider.get_events(sport_id="nba"))
        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)
        assert all(e.sport_id == "nba" for e in events)

    def test_get_markets_returns_normalized_entities(self, provider):
        events = run(provider.get_events(sport_id="nba"))
        markets = run(provider.get_markets(events[0].id))
        assert len(markets) == 3  # moneyline, spread, total
        assert all(isinstance(m, Market) for m in markets)

    def test_get_selections_returns_two_sided_market(self, provider):
        events = run(provider.get_events(sport_id="nba"))
        markets = run(provider.get_markets(events[0].id))
        selections = run(provider.get_selections(markets[0].id))
        assert len(selections) == 2
        assert all(isinstance(s, Selection) for s in selections)

    def test_get_odds_preserves_provenance(self, provider):
        events = run(provider.get_events(sport_id="nba"))
        odds = run(provider.get_odds(event_id=events[0].id))
        assert len(odds) > 0
        assert all(isinstance(o, Odds) for o in odds)
        assert all(o.provider == "mock" for o in odds)
        assert all(o.timestamp is not None for o in odds)

    def test_odds_distinguish_opening_and_current_or_closing(self, provider):
        events = run(provider.get_events(sport_id="nba"))
        odds = run(provider.get_odds(event_id=events[0].id))
        has_opening = any(o.is_opening for o in odds)
        has_other = any((not o.is_opening) for o in odds)
        assert has_opening
        assert has_other


class TestHistoricalDataRetrieval:
    def test_historical_data_only_returns_final_events(self, provider):
        outcomes = run(provider.get_historical_data(sport_id="nba"))
        assert len(outcomes) > 0
        assert all(isinstance(o, Outcome) for o in outcomes)

    def test_historical_data_respects_date_filters(self, provider):
        all_outcomes = run(provider.get_historical_data(sport_id="nba"))
        far_future = run(provider.get_historical_data(sport_id="nba", start_date=date(2999, 1, 1)))
        assert len(far_future) == 0
        assert len(all_outcomes) > 0

    def test_filtering_by_sport_is_isolated(self, provider):
        nba = run(provider.get_events(sport_id="nba"))
        nfl = run(provider.get_events(sport_id="nfl"))
        nba_ids = {e.id for e in nba}
        nfl_ids = {e.id for e in nfl}
        assert nba_ids.isdisjoint(nfl_ids)
