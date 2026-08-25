"""
Active data provider selection.

If the ODDS_API_KEY environment variable is set, real sportsbook data
(app/data/live_provider.py, via The Odds API) is used. Otherwise the
app falls back to the deterministic mock provider so it still runs
out of the box with zero configuration.

`provider` is a HybridProvider: it always tries the live provider
first (when configured) and falls back to mock data per-call if a
live request fails (missing/invalid key, rate limit, network issue),
rather than crashing the page. `provider.mode` reflects which source
actually served the most recent request ("live" or "sample") so the
UI can show an honest, real-time status rather than just "is a key
configured".
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

from .mock_provider import MockSportsDataProvider
from .provider import SportsDataProvider  # noqa: F401

logger = logging.getLogger("smartbet.data")


class HybridProvider:
    """Prefers live odds data; transparently falls back to the mock
    provider per-call if live data isn't configured or a request fails."""

    def __init__(self) -> None:
        self._mock = MockSportsDataProvider()
        self._live = None
        self.configured = False
        self.mode = "sample"          # what actually served the last request
        self.last_error: Optional[str] = None

        api_key = os.environ.get("ODDS_API_KEY", "").strip()
        if api_key:
            from .live_provider import TheOddsApiProvider  # local import: httpx only needed if live mode is used
            self._live = TheOddsApiProvider(api_key)
            self.configured = True

    def _mark(self, mode: str, error: Optional[str] = None) -> None:
        self.mode = mode
        self.last_error = error

    async def _try_live_then_mock(self, method_name: str, *args, **kwargs):
        if self._live is not None:
            try:
                result = await getattr(self._live, method_name)(*args, **kwargs)
                self._mark("live")
                return result
            except Exception as exc:  # noqa: BLE001 — any live-provider failure falls back
                logger.warning("Live provider %s() failed, falling back to sample data: %s", method_name, exc)
                self._mark("sample", str(exc))
        else:
            self._mark("sample")
        return await getattr(self._mock, method_name)(*args, **kwargs)

    # ------------------------------------------------------------------
    # SportsDataProvider interface (async)
    # ------------------------------------------------------------------
    async def get_sports(self):
        return await self._try_live_then_mock("get_sports")

    async def get_events(self, sport_id: Optional[str] = None, league_id: Optional[str] = None, on_date: Optional[date] = None):
        return await self._try_live_then_mock("get_events", sport_id=sport_id, league_id=league_id, on_date=on_date)

    async def get_markets(self, event_id: str):
        return await self._try_live_then_mock("get_markets", event_id)

    async def get_selections(self, market_id: str):
        return await self._try_live_then_mock("get_selections", market_id)

    async def get_odds(self, event_id: Optional[str] = None, market_type: Optional[str] = None, sportsbook: Optional[str] = None):
        return await self._try_live_then_mock("get_odds", event_id=event_id, market_type=market_type, sportsbook=sportsbook)

    async def get_historical_data(self, sport_id: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
        return await self._try_live_then_mock("get_historical_data", sport_id=sport_id, start_date=start_date, end_date=end_date)

    # ------------------------------------------------------------------
    # Convenience accessors (sync) — delegate to whichever source most
    # recently served a request; both providers implement the same surface.
    # ------------------------------------------------------------------
    def _active(self):
        return self._live if (self._live is not None and self.mode == "live") else self._mock

    def get_event(self, event_id: str):
        found = self._active().get_event(event_id)
        if found is None and self._active() is not self._mock:
            found = self._mock.get_event(event_id)
        return found

    def get_team_name(self, sport_id: str, team_id: str) -> str:
        return self._active().get_team_name(sport_id, team_id)

    def get_finished_events(self, sport_id: Optional[str] = None):
        return self._active().get_finished_events(sport_id=sport_id)

    def get_outcomes(self, event_id: str):
        return self._active().get_outcomes(event_id)

    @property
    def _teams(self):
        # Used only by the Elo model's lazy self-build (app/models/prediction.py)
        # to seed a team roster; the mock provider always has one, live mode
        # has no historical feed to build ratings from regardless.
        return self._mock._teams


provider = HybridProvider()
