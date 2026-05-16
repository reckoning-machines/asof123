# Calendar Provider Timezone Freeze Contract

Date: 2026-05-15

This document is contract-derived from `PRODUCT_CONTRACT.md`. If it ever
disagrees with `PRODUCT_CONTRACT.md`, the product contract wins and this
document must be corrected.

`docs/unified_diff.md` exists and has been updated by later hardening passes.

## Calendar Freeze Contract

Future persisted replay must pin the calendar rules used for market-facing
interpretation. The minimum replay-safe calendar identity is:

- `calendar_id`: stable identifier for the calendar implementation or data
  family.
- `calendar_version`: stable version for the rule set used by replay.
- `market`: MIC-style market code where available.
- `market_timezone`: explicit IANA timezone name.
- `market_definition_version`: version for market identity and session
  definition rules when those rules can change.
- `exchange_rule_version`: version for regular session rules.
- `holiday_table_version`: version for holiday data.
- `early_close_version`: version for early-close data when early closes are
  modeled.
- `ad_hoc_closure_version`: version for ad hoc market closures when ad hoc
  closures are modeled.

For current in-memory snapshots, these fields are not present and are not
hash-affecting. Before persisted replay execution is introduced, calendar
freeze metadata must be hash-affecting in the persisted replay payload or in
a linked immutable replay envelope whose own identity is hash-addressed.

Runtime-only calendar details may remain outside the hash only when they
cannot change replay meaning. Anything that can change market phase, business
date, session boundary, or admissibility must be part of the frozen replay
interpretation boundary.

## Timezone Freeze Contract

Current runtime validation requires explicit IANA timezone names and rejects
naive machine instants. That is sufficient for current in-memory resolution,
but not sufficient for long-term persisted replay because timezone databases
can change historical and future offset rules.

The minimum replay-safe timezone identity is:

- explicit IANA timezone name;
- `tzdata_version` or equivalent timezone rule identity;
- runtime timezone source identity when the process does not use a pinned
  tzdata package;
- the UTC machine instant being interpreted.

For persisted replay, timezone rule identity must be hash-affecting because
the same UTC instant and IANA name can map to different local market meaning
under different timezone rule sets. Replaying with upgraded tzdata is allowed
only as explicit reinterpretation, not reproduction.

## Provider Freeze Contract

Future provider-backed replay must pin the source facts used by the resolver.
The minimum replay-safe provider identity for each provider-backed assertion
is:

- `provider_id`: stable source/provider identity.
- `provider_version`: implementation or adapter version.
- `provider_schema_version`: output schema version when output shape can
  change.
- `provider_semantic_contract`: provider meaning version when interpretation
  can change.
- `source_artifact_hash` or immutable source artifact version.
- assertion, observation, or publication instant used for freshness claims.

Provider metadata is hash-affecting when it can change source freshness,
publication state, price basis, canonical state, or admissibility. Advisory
provider metadata may remain outside the hash only when it cannot change
temporal meaning.

Provider-backed reproduction mode must not call live provider state to decide
what a past provider reported. If the source artifact or provider version is
missing, persisted replay must fail closed unless explicit reinterpretation
mode is requested.

## Snapshot Freeze Envelope Definition

A future persisted replay-safe freeze envelope must bind:

- snapshot schema version;
- semantic contract version;
- snapshot semantic payload;
- content hash and hash algorithm;
- calendar interpretation metadata;
- timezone interpretation metadata;
- provider interpretation metadata for each provider-backed assertion;
- source artifact identities needed to reproduce provider facts.

The current v1 in-memory `AsOfSnapshot` is not a persistence envelope. Its
hash-affecting payload remains exactly:

- `snapshot_schema_version`;
- `semantic_contract_version`;
- `context`.

Before persisted replay exists, the freeze envelope may be designed as a new
schema or as an extension with a new `snapshot_schema_version`. Either way,
the freeze metadata that can change replay meaning must be hash-affecting.

## Replay Reinterpretation Policy

Replay operations must declare one of two modes:

- Reproduction mode: use the recorded schema, semantic contract, calendar,
  timezone, provider, and source artifact regimes.
- Reinterpretation mode: explicitly declare the newer regime being applied.

Allowed reinterpretations include:

- replaying under upgraded tzdata;
- replaying under a revised exchange calendar;
- replaying under a newer provider schema or semantic contract;
- replaying under a newer asof123 semantic contract.

Every reinterpretation result must preserve the original snapshot identity,
original `content_hash`, original freeze metadata, and the declared new
regime. It must produce a distinct result that cannot be mistaken for
original reproduction.

Silent reinterpretation is forbidden.

## Future Persistence Guardrails

Before persistence or replay execution is allowed, the repository must have:

- a concrete freeze envelope schema;
- tests proving freeze metadata is deterministic and hash-affecting;
- snapshot schema migration rules;
- semantic contract migration rules;
- calendar version publication rules;
- provider version pinning rules;
- timezone rule source recording;
- fail-closed behavior for missing freeze metadata;
- explicit reproduction versus reinterpretation mode semantics.

No persisted replay implementation may silently read mutable current
calendar, timezone, or provider state for reproduction mode.

## Hash-Affecting Vs Advisory Metadata Rules

Hash-affecting before persisted replay:

- calendar identity and version fields that affect market interpretation;
- timezone rule identity when local market meaning is derived from UTC;
- provider identity, version, schema, semantic contract, and source artifact
  fields that affect source fact interpretation;
- replay mode and declared reinterpretation regime when reinterpretation is
  requested.

Advisory metadata:

- operator notes;
- display labels;
- non-semantic diagnostics;
- audit storage location;
- capture job identifier, if it cannot affect interpretation.

Advisory metadata must never be used by replay logic to decide temporal
meaning.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | The freeze envelope is contract-defined but not implemented in runtime models. | Required before persisted replay execution, intentionally deferred. |
| WARNING | The current XNYS calendar has no versioned rule publication metadata. | Safe for current in-memory examples; not sufficient for persisted replay. |
| WARNING | The runtime validates IANA timezone names but does not record tzdata version. | Safe for current resolution; future persisted replay must pin timezone rules. |
| WARNING | Static and file providers do not expose provider version/source artifact freeze metadata. | Safe for current reference surfaces; future provider-backed replay must pin it. |
| NOTE | Current v1 `content_hash` remains unchanged. | Calendar/provider/timezone freeze metadata is future replay envelope state, not current in-memory snapshot state. |

## Final Verdict

PASS WITH WARNINGS.

The future calendar, timezone, and provider freeze boundaries are now
contract-defined. The warnings are blockers for future persisted replay
execution, not current runtime corruption risks.
