# Canonical Authority Boundary Contract

Date: 2026-05-15

This document is contract-derived from `PRODUCT_CONTRACT.md`. If it ever
disagrees with `PRODUCT_CONTRACT.md`, the product contract wins and this
document must be corrected.

`docs/unified_diff.md` exists and was updated.

## Definition Of Canonicality

Canonicality is an asserted institutional truth boundary. It is not latest,
freshest, most recent, inferred, provider majority vote, or best effort.

Perspective distinctions:

- `LIVE`: resolves current temporal meaning. It may be provisional.
- `EXECUTED`: resolves execution-context meaning. It does not imply canonical
  truth.
- `REPLAY`: reproduces a frozen historical interpretation.
- `HISTORICAL`: resolves a pinned historical context without implying system
  of record authority.
- `CANONICAL`: asks a system-of-record authority whether an answer has been
  asserted as canonical under explicit publication rules.

Canonicality requires an authoritative assertion. A value is canonical only
when a typed canonical authority asserts `canonical_state=CANONICAL` under
its versioned protocol and publication lifecycle.

`PROVISIONAL` means an answer can be produced but no canonical authority has
asserted it. `SUPERSEDED` means the answer was once canonical and has been
replaced by a later canonical assertion. `WITHDRAWN` means the publication
was retracted and must not be treated as historical truth.

## Authority Boundary Requirements

A future canonical authority must be a typed boundary separate from ordinary
`SourceProvider` facts. It must provide, at minimum:

- `authority_id`
- `authority_version`
- authority protocol version
- publication schema version
- assertion instant
- publication instant
- canonical_state assertion
- publication_state assertion
- provenance for the asserted fact
- supersession identity when replacing a prior assertion
- withdrawal identity and reason when retracting an assertion
- semantic contract version used by the authority

Hash-affecting in future canonical snapshots or replay envelopes:

- authority identity and version;
- authority protocol version;
- publication schema version;
- assertion instant;
- publication instant;
- canonical_state and publication_state assertions;
- provenance identity;
- supersession identity;
- withdrawal identity;
- semantic contract version.

Audit-only:

- capture job identifier;
- operator note;
- display label;
- non-semantic diagnostics.

Advisory:

- human explanation text;
- non-semantic comments;
- UI grouping labels.

Advisory metadata must never decide canonical truth.

## Canonical Publication Lifecycle

Allowed lifecycle transitions:

- `NOT_PUBLISHED` may become `PRE_PUBLISHED`, `EMBARGOED`, `PUBLISHED`,
  `FAILED`, or `UNKNOWN` with reason metadata.
- `PRE_PUBLISHED` may become `PUBLISHED`, `EMBARGOED`, `WITHDRAWN`,
  `FAILED`, or `UNKNOWN` with reason metadata.
- `EMBARGOED` may become `PUBLISHED`, `WITHDRAWN`, `FAILED`, or `UNKNOWN`
  with reason metadata.
- `PUBLISHED` may become `WITHDRAWN` or may be paired with
  `canonical_state=SUPERSEDED` when a later canonical assertion replaces it.
- `WITHDRAWN` is terminal for that publication identity unless an explicit
  new publication identity is asserted.
- `FAILED` is terminal for that publication attempt unless a new attempt
  identity is asserted.
- `SUPERSEDED` is terminal for that canonical assertion identity and must not
  be treated as current canonical truth.

Terminal states require explicit provenance:

- withdrawal event identity;
- withdrawal instant;
- withdrawing authority;
- superseding assertion identity;
- supersession instant;
- superseding authority.

## Replay-Safe Canonical Semantics

Historical replay must preserve canonical assertions exactly as asserted at
the time, including superseded and withdrawn states.

Replay must not silently upgrade `PROVISIONAL` history into `CANONICAL`
history. Replay must not silently reinterpret a historical `WITHDRAWN` or
`SUPERSEDED` assertion under newer authority state.

Two replay modes are allowed:

- reproduction mode: use the recorded authority, publication, semantic,
  calendar, provider, and timezone regimes;
- explicit reinterpretation mode: declare the newer regime and produce a
  distinct result that cannot be mistaken for original reproduction.

Canonical replay requires frozen authority metadata before persistence or
replay execution is allowed.

## Supersession And Withdrawal Policy

Supersession:

- A superseded assertion must identify the replacing assertion.
- The superseded assertion remains part of historical reproduction.
- Readers must not treat `SUPERSEDED` as current canonical truth.
- A supersession event must identify authority, instant, and reason or
  publication event.

Withdrawal:

- A withdrawn publication must identify the withdrawal event.
- The withdrawn assertion remains part of historical reproduction as
  withdrawn, not as published truth.
- Readers must not treat `WITHDRAWN` as available historical data.
- A withdrawal event must identify authority, instant, and reason.

Neither supersession nor withdrawal may be inferred from missing current data,
latest timestamps, provider freshness, or publication state alone.

## Resolver Safety Rules

Current v1 behavior remains correct: `CANONICAL` fails closed with
`CANONICAL_UNSUPPORTED` because no canonical authority exists.

Future resolver rules:

- The resolver must not infer canonical state from ordinary providers.
- Providers must not self-assert canonicality unless they implement the typed
  canonical authority protocol.
- Canonicality must come from a typed authority protocol.
- If authority is unavailable, incomplete, contradictory, or unsupported, the
  resolver must fail closed.
- If authority disagrees with providers, the resolver must surface the
  disagreement explicitly or fail closed.
- The resolver must not downgrade a `CANONICAL` request to `LIVE`,
  `HISTORICAL`, `REPLAY`, or `PROVISIONAL`.
- `CANONICAL` must resolve to `canonical_state=CANONICAL` or fail closed.

## Future Integration Prohibitions

Future integrations must not:

- infer canonicality from freshness;
- infer canonicality from publication_state alone;
- infer canonicality from execution_state;
- infer canonicality from price basis;
- infer canonicality from latest timestamp;
- infer canonicality from provider majority vote;
- treat `OFFICIAL_CLOSE` or `SETTLEMENT` as canonical without authority;
- silently reinterpret withdrawn assertions;
- silently reinterpret superseded assertions;
- call providers or runtime authority during Replay, Run Diff, Audit, or read
  path rendering to recompute historical canonical meaning;
- let mutable current authority state rewrite historical snapshots.

## Semantic And Version Governance Requirements

Canonical authority requires governance over:

- asof123 `semantic_contract_version`;
- authority protocol version;
- publication schema version;
- `authority_version`;
- replay freeze metadata;
- reason codes for authority failure modes.

Additive authority metadata may be compatible only when it cannot change
canonical meaning. Any change to canonical_state meaning, publication_state
meaning, supersession semantics, withdrawal semantics, or authority
interpretation requires contract review and may require a
`semantic_contract_version` change.

Future reason codes should distinguish:

- authority unavailable;
- authority incomplete;
- authority version unsupported;
- authority/provider disagreement;
- assertion withdrawn;
- assertion superseded;
- publication schema unsupported.

`CANONICAL_UNSUPPORTED` remains the correct current reason code when no
canonical authority boundary exists at all.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | No canonical authority protocol exists. | Current fail-closed behavior is correct; implementation must wait for a typed boundary. |
| WARNING | Canonical authority metadata is not yet represented in snapshots. | Required before persisted canonical replay, intentionally deferred. |
| WARNING | Authority-specific failure reason codes beyond `CANONICAL_UNSUPPORTED` are not implemented. | Required when an authority protocol is introduced. |
| NOTE | Current resolver fails closed for `CANONICAL`. | This prevents silent canonical inference. |
| NOTE | Ordinary providers cannot assert canonicality. | Future authority must be a separate typed boundary. |

## Final Verdict

PASS WITH WARNINGS.

The future canonical authority boundary is now contract-defined. The current
runtime remains safe because `CANONICAL` fails closed and no implementation
claims canonical authority.
