# Product Contract Report

## Current Status

`PRODUCT_CONTRACT.md` is the canonical contract for this repository.

The current PyPI-facing ontology is:

- `AsOf`
- `AsOfRequest`
- `AsOfSnapshot`
- `Perspective`
- `MarketPhase`
- `SourceStatus`
- `SourceFreshness`
- `SourcePolicy`
- `KnowledgeCutoff`
- `PriceBasis`
- `ExecutionState`
- `PublicationState`
- `CanonicalState`
- `BusinessDate`
- `MarketCalendar`
- `SourceProvider`

An As-Of answer is represented by `AsOf`.

## Current Runtime Boundary

The repository implements the reference resolver boundary:

- external systems report facts through `SourceProvider` and `SourceStatus`;
- optional `SourcePolicy` normalizes required-source, source-age, and
  replay/historical cutoff admissibility;
- `resolve(AsOfRequest(...))` returns an `AsOf` or fails closed;
- `make_snapshot(asof, snapshot_id=...)` returns an `AsOfSnapshot`;
- `AsOfSnapshot.asof` is the snapshot payload field;
- snapshot schema is `asof123.snapshot.v2`.

## Current Open-Source Boundary

The open-source core may include:

- public models and enums;
- a minimal resolver;
- static and file-backed source providers;
- a minimal XNYS reference calendar;
- `SourcePolicy`;
- deterministic snapshot helpers;
- CLI commands;
- a reference FastAPI app;
- examples, recipes, and tests.

The open-source core must not include:

- Bloomberg adapters;
- OMS/EMS/PMS integrations;
- broker adapters;
- proprietary warehouse adapters;
- schedulers;
- workflow engines;
- auth, persistence, or deployment-specific infrastructure.

## Notes

This file is a short companion report. `PRODUCT_CONTRACT.md` remains the
source of truth. If this report and the contract disagree, the contract wins.
