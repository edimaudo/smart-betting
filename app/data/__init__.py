"""
Active data provider: live-only, no sample/mock data fallback.

This app requires ODDS_API_KEY. If it isn't set, or a live request
fails, every provider method raises LiveDataUnavailable — main.py
turns that into a clear, honest error page rather than ever silently
substituting fabricated data.
"""
from __future__ import annotations

import os

from .live_provider import LiveDataUnavailable, TheOddsApiProvider
from .provider import SportsDataProvider  # noqa: F401


class UnconfiguredProvider(SportsDataProvider):
    """Used when ODDS_API_KEY isn't set. Every call raises the same
    LiveDataUnavailable error a failed live call would, so app code has
    exactly one error path to handle regardless of the reason."""

    _MESSAGE = (
        "Live data isn't configured: set the ODDS_API_KEY environment "
        "variable (a free key is available at https://the-odds-api.com/) "
        "and restart the app. See README.md."
    )

    def _unavailable(self):
        raise LiveDataUnavailable(self._MESSAGE)

    async def get_sports(self):
        self._unavailable()

    async def get_events(self, sport_id=None, league_id=None, on_date=None):
        self._unavailable()

    async def get_markets(self, event_id):
        self._unavailable()

    async def get_selections(self, market_id):
        self._unavailable()

    async def get_odds(self, event_id=None, market_type=None, sportsbook=None):
        self._unavailable()

    async def get_historical_data(self, sport_id=None, start_date=None, end_date=None):
        self._unavailable()

    def get_event(self, event_id):
        self._unavailable()

    def get_team_name(self, sport_id, team_id):
        self._unavailable()

    def get_finished_events(self, sport_id=None):
        self._unavailable()

    def get_outcomes(self, event_id):
        self._unavailable()

    async def ensure_scores_loaded(self, sport_id, days_from=3):
        self._unavailable()


_api_key = os.environ.get("ODDS_API_KEY", "").strip()
CONFIGURED = bool(_api_key)
provider = TheOddsApiProvider(_api_key) if CONFIGURED else UnconfiguredProvider()
