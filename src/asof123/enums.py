"""Pinned semantic enumerations for asof123.

Every value here is normative per PRODUCT_CONTRACT.md sections 4 through 10.
Adding values requires a contract change first.
"""

from __future__ import annotations

from enum import Enum


class Perspective(str, Enum):
    PREVIEW = "PREVIEW"
    PRE_TRADE_INTENT = "PRE_TRADE_INTENT"
    LIVE = "LIVE"
    EXECUTED = "EXECUTED"
    CANONICAL = "CANONICAL"
    REPLAY = "REPLAY"
    HISTORICAL = "HISTORICAL"


class MarketPhase(str, Enum):
    PRE_OPEN = "PRE_OPEN"
    MARKET_OPEN = "MARKET_OPEN"
    POST_CLOSE = "POST_CLOSE"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    CLOSED = "CLOSED"


class SourceFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    FAILED = "FAILED"
    PRIOR_CLOSE = "PRIOR_CLOSE"
    PARTIAL = "PARTIAL"
    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"


class ExecutionState(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    INTENDED = "INTENDED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class PriceBasis(str, Enum):
    PRIOR_CLOSE = "PRIOR_CLOSE"
    LAST_TRADE = "LAST_TRADE"
    INDICATIVE = "INDICATIVE"
    OFFICIAL_CLOSE = "OFFICIAL_CLOSE"
    SETTLEMENT = "SETTLEMENT"
    MODEL = "MODEL"
    UNKNOWN = "UNKNOWN"


class PublicationState(str, Enum):
    NOT_PUBLISHED = "NOT_PUBLISHED"
    PRE_PUBLISHED = "PRE_PUBLISHED"
    PUBLISHED = "PUBLISHED"
    EMBARGOED = "EMBARGOED"
    WITHDRAWN = "WITHDRAWN"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class CanonicalState(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    CANONICAL = "CANONICAL"
    SUPERSEDED = "SUPERSEDED"
    NOT_CANONICAL = "NOT_CANONICAL"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    UNKNOWN = "UNKNOWN"


DEFAULT_MARKET_PHASE: MarketPhase = MarketPhase.CLOSED
DEFAULT_EXECUTION_STATE: ExecutionState = ExecutionState.NOT_EXECUTED
DEFAULT_PRICE_BASIS: PriceBasis = PriceBasis.UNKNOWN
DEFAULT_PUBLICATION_STATE: PublicationState = PublicationState.NOT_PUBLISHED
DEFAULT_CANONICAL_STATE: CanonicalState = CanonicalState.PROVISIONAL
