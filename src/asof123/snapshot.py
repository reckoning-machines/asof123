"""Snapshot helpers for asof123.

`make_snapshot(asof, snapshot_id)` produces a replay-safe
`AsOfSnapshot` from an `AsOf`. The snapshot's `content_hash`
is a SHA256 over a deterministic canonical JSON representation of the
versioned snapshot payload, so two callers building snapshots from
byte-equal AsOf answers under the same schema and semantic contract will
compute the same hash.

`canonicalize_asof(asof)` returns the canonical JSON string used
to compare a bare AsOf. `canonicalize_snapshot_payload(asof)`
returns the hash preimage used for `AsOfSnapshot.content_hash`.

No persistence, no scheduling. The captured instant comes from
`datetime.now(timezone.utc)`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .models import (
    SEMANTIC_CONTRACT_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    AsOfSnapshot,
    AsOf,
)


def canonicalize_asof(asof: AsOf) -> str:
    """Return a deterministic JSON string for `asof`.

    The output uses Pydantic's JSON-mode dump (so enum members serialize
    to their string values and datetimes serialize to ISO 8601 UTC),
    then re-serializes with `sort_keys=True` and tight separators so the
    byte representation is stable across runs. The input AsOf is not
    mutated.
    """
    payload = asof.model_dump(mode="json")
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def canonicalize_snapshot_payload(asof: AsOf) -> str:
    """Return the hash-affecting canonical snapshot payload.

    Audit-only fields such as `snapshot_id`, `captured_at_utc`,
    `hash_algorithm`, and `content_hash` are intentionally excluded.
    Schema and semantic contract versions are included so identical AsOf
    bytes under different rules cannot share a semantic content identity.
    """
    payload: dict[str, Any] = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "asof": asof.model_dump(mode="json"),
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def make_snapshot(asof: AsOf, snapshot_id: str) -> AsOfSnapshot:
    """Return a validated `AsOfSnapshot` for `asof`.

    `captured_at_utc` is `datetime.now(timezone.utc)`. `content_hash` is
    the SHA256 hex digest of the UTF-8 bytes of
    `canonicalize_snapshot_payload`.
    The returned `AsOfSnapshot` is fully validated by its own model
    validator before it is returned; invalid `snapshot_id` (empty
    string) raises `pydantic.ValidationError` rather than silently
    producing a broken snapshot.
    """
    canonical = canonicalize_snapshot_payload(asof)
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    frozen_asof = AsOf.model_validate(asof.model_dump(mode="json"))
    return AsOfSnapshot(
        snapshot_id=snapshot_id,
        captured_at_utc=datetime.now(timezone.utc),
        asof=frozen_asof,
        content_hash=content_hash,
    )
