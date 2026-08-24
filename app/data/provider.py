"""
Data provider abstraction.

PRD section 13: external sports/betting APIs must be isolated behind
a provider interface, and the analysis engine must operate on
normalized internal models rather than provider-specific structures.

To add a real provider (e.g. a sportsbook odds API), implement
`SportsDataProvider` and normalize that API's responses into the
`app.models.entities` shapes. Nothing outside app/data/ should ever
import a provider-specific payload shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from app.models.entities import Event, Market, Odds, Outcome, Selection, Sport


class SportsDataProvider(ABC):
    """Common interface every data provider (mock or real) must implement."""

    name: str = "base"

    @abstractmethod
    async def get_sports(self) -> list[Sport]:
        ...

    @abstractmethod
    async def get_events(
        self,
        sport_id: Optional[str] = None,
        league_id: Optional[str] = None,
        on_date: Optional[date] = None,
    ) -> list[Event]:
        ...

    @abstractmethod
    async def get_markets(self, event_id: str) -> list[Market]:
        ...

    @abstractmethod
    async def get_selections(self, market_id: str) -> list[Selection]:
        ...

    @abstractmethod
    async def get_odds(
        self,
        event_id: Optional[str] = None,
        market_type: Optional[str] = None,
        sportsbook: Optional[str] = None,
    ) -> list[Odds]:
        ...

    @abstractmethod
    async def get_historical_data(
        self,
        sport_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Outcome]:
        ...
