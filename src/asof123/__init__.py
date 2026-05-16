"""asof123: a temporal semantics layer for financial and institutional systems.

This package exposes the contract-aligned ontology, the resolver request
and provider protocol boundary, a minimal `XNYS` reference calendar, a
minimal in-process resolver, the first concrete provider implementations
(`StaticProvider`, `FileProvider`), and a deterministic snapshot helper
(`make_snapshot`, `canonicalize_context`,
`canonicalize_snapshot_payload`). Optional reference surfaces include a
FastAPI app and CLI. It still ships no persistence layer, no scheduler,
no orchestration logic, no async behavior, and no network IO in the core
resolver path.
"""

from .calendar import MarketCalendar
from .calendars import XNYSCalendar
from .enums import (
    CanonicalState,
    DEFAULT_CANONICAL_STATE,
    DEFAULT_EXECUTION_STATE,
    DEFAULT_MARKET_PHASE,
    DEFAULT_PRICE_BASIS,
    DEFAULT_PUBLICATION_STATE,
    ExecutionState,
    MarketPhase,
    Perspective,
    PriceBasis,
    PublicationState,
    SourceFreshness,
)
from .errors import ErrorReasonCode, ErrorResponse
from .models import (
    SEMANTIC_CONTRACT_VERSION,
    SNAPSHOT_HASH_ALGORITHM,
    SNAPSHOT_SCHEMA_VERSION,
    AsOfSnapshot,
    MarketIdentity,
    SourceStatus,
    TemporalContext,
)
from .providers import (
    FileProvider,
    ProviderReportError,
    SourceProvider,
    StaticProvider,
)
from .requests import ResolveRequest
from .resolver import ResolverError, resolve
from .snapshot import (
    canonicalize_context,
    canonicalize_snapshot_payload,
    make_snapshot,
)


def __getattr__(name: str):
    """Lazily expose `create_app` only when FastAPI is installed.

    Importing `asof123.api` would fail if the optional `api` extra is
    not installed. Surfacing `create_app` lazily keeps `import asof123`
    cheap and free of FastAPI as a hard dependency.
    """
    if name == "create_app":
        from .api import create_app as _create_app
        return _create_app
    raise AttributeError(f"module 'asof123' has no attribute {name!r}")

__all__ = [
    "Perspective",
    "MarketPhase",
    "SourceFreshness",
    "ExecutionState",
    "PriceBasis",
    "PublicationState",
    "CanonicalState",
    "DEFAULT_MARKET_PHASE",
    "DEFAULT_EXECUTION_STATE",
    "DEFAULT_PRICE_BASIS",
    "DEFAULT_PUBLICATION_STATE",
    "DEFAULT_CANONICAL_STATE",
    "ErrorReasonCode",
    "ErrorResponse",
    "SNAPSHOT_SCHEMA_VERSION",
    "SEMANTIC_CONTRACT_VERSION",
    "SNAPSHOT_HASH_ALGORITHM",
    "MarketIdentity",
    "SourceStatus",
    "TemporalContext",
    "AsOfSnapshot",
    "ResolveRequest",
    "SourceProvider",
    "ProviderReportError",
    "StaticProvider",
    "FileProvider",
    "MarketCalendar",
    "XNYSCalendar",
    "ResolverError",
    "resolve",
    "make_snapshot",
    "canonicalize_context",
    "canonicalize_snapshot_payload",
    "create_app",
]

__version__ = "0.0.1"
