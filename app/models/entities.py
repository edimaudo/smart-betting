"""
Core data entities, per PRD section 12 (Data Model) and section 10
(Data Layer core entities).

These are the normalized internal representations that ALL providers
must map their responses into. The analysis engine and templates
should only ever operate on these shapes, never on provider-specific
payloads (PRD section 13).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class OddsFormat(str, Enum):
    DECIMAL = "decimal"
    AMERICAN = "american"


class Sport(BaseModel):
    id: str
    name: str


class League(BaseModel):
    id: str
    sport_id: str
    name: str


class Team(BaseModel):
    id: str
    league_id: str
    name: str
    abbreviation: Optional[str] = None


class Player(BaseModel):
    id: str
    team_id: str
    name: str


class Event(BaseModel):
    id: str
    sport_id: str
    league_id: str
    home_team_id: str
    away_team_id: str
    start_time: datetime
    status: EventStatus = EventStatus.SCHEDULED

    # Denormalized display fields (populated by providers for convenience;
    # not treated as sources of truth).
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None
    league_name: Optional[str] = None
    sport_name: Optional[str] = None


class Market(BaseModel):
    id: str
    event_id: str
    market_type: str  # e.g. "moneyline", "spread", "total"
    name: str


class Selection(BaseModel):
    id: str
    market_id: str
    name: str


class Sportsbook(BaseModel):
    id: str
    name: str


class Odds(BaseModel):
    id: str
    selection_id: str
    sportsbook: str
    price: float
    odds_format: OddsFormat = OddsFormat.AMERICAN
    timestamp: datetime
    is_opening: bool = False
    is_closing: bool = False

    # Provenance (PRD section 14 — Data Quality)
    provider: Optional[str] = None
    provider_event_id: Optional[str] = None
    provider_market_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class Outcome(BaseModel):
    id: str
    event_id: str
    selection_id: str
    result: str  # e.g. "win", "loss", "push"
    timestamp: datetime


class ModelOutput(BaseModel):
    """PRD section 20 — common Model output shape."""
    model_config = {"protected_namespaces": ()}

    probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str
    assumptions: list[str] = Field(default_factory=list)


class Strategy(BaseModel):
    """PRD section 14 / 21 — Strategy definition."""
    id: str
    name: str
    sport: Optional[str] = None
    market_type: Optional[str] = None
    min_edge: float = 0.0
    min_ev: float = 0.0
    min_confidence: float = 0.0
    max_stake_units: float = 1.0
