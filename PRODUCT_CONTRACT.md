# asof123 Product Contract

Tagline: Every bug in finance software is secretly an "as of" bug.

This document is the canonical contract for the asof123 open-source project.
It defines what asof123 is, what it is not, the ontology it must expose, and
the rules its implementation must follow. Any code, API surface, or
documentation that contradicts this contract is wrong and must be changed to
conform to it.

asof123 is an open-source temporal semantics layer for financial and
institutional systems. It is not a clock service. It is not a scheduler. It
is not a workflow engine. It resolves what "as of" means for a business
context by combining market and session calendars, source freshness, source
authority, publication state, execution state, and named temporal
perspectives.

Core principle:

    External systems report facts.
    asof123 resolves temporal meaning.

---

## 1. What asof123 Is

asof123 is:

- A semantic "as of" resolver.
- A central authority for temporal context in a financial or institutional
  system.
- A library and an API that answers questions of the form:
  - What business date are we in?
  - What market phase are we in (pre-open, open, post-close, weekend,
    holiday, closed)?
  - What source states are fresh, stale, missing, failed, partial, or
    not yet published?
  - Is the caller operating in a preview, pre-trade intent, live,
    executed, canonical, replay, or historical perspective?
  - What knowledge cutoff applies to the answer being produced?
  - What price basis applies (for example last trade, prior close,
    indicative, official close, settlement)?
  - What publication state applies to a given dataset or report?

asof123 answers these questions in a single, consistent, auditable way so
that downstream systems do not each invent their own incompatible notion of
"now" or "as of".

## 2. What asof123 Is Not

asof123 is not, and must not become:

- A time clock or a wall-clock service.
- A distributed clock synchronization system. It does not replace NTP, PTP,
  Spanner TrueTime, or any vector clock or hybrid logical clock scheme.
- A scheduler. It does not run jobs, fire cron triggers, or wake workers.
- An orchestrator. It does not coordinate DAGs, retries, or task graphs.
- A data warehouse. It does not store historical fact tables for analytics.
- A temporal database. It does not provide bitemporal storage or
  system-time versioning of arbitrary rows.
- An order management system (OMS) or portfolio management system (PMS).
- A replacement for pandas, numpy, market calendar libraries (such as
  pandas-market-calendars or exchange_calendars), Airflow, Dagster, Prefect,
  dbt, or data lineage tools.

asof123 sits next to these systems and tells them, and each other, what
"as of" means in a given call. It does not absorb their responsibilities.

## 3. Required Ontology

The following nouns are the initial public ontology of asof123. Every
implementation, API response, and documentation example must use these
names exactly.

- TemporalContext
  The top-level resolved answer. Bundles a business date, market phase,
  perspective, source statuses, knowledge cutoff, price basis, publication
  state, and the UTC instant of resolution.

- Perspective
  A named temporal viewpoint the caller is operating under. See section 4
  for the initial set.

- MarketPhase
  The current phase of a given market or session. See section 5 for the
  initial set.

- SourceStatus
  The resolved state of a named source provider at the resolution instant.
  Carries a SourceFreshness value and optional publication metadata.

- SourceFreshness
  The freshness classification of a source. See section 6 for the initial
  set.

- KnowledgeCutoff
  The latest instant for which information is considered admissible in the
  current TemporalContext. Used to prevent leakage of future-dated facts
  into preview, replay, and historical perspectives.

- PriceBasis
  The pricing convention that applies for the current TemporalContext. See
  section 8 for the initial set.

- ExecutionState
  The execution lifecycle state relevant to the caller. See section 7 for
  the initial set.

- PublicationState
  The publication state of a given dataset, report, or document in the
  current TemporalContext. See section 9 for the initial set.

- CanonicalState
  Whether the answer is considered canonical (the system of record) or
  provisional, and which authority asserts that status. See section 10
  for the initial set.

- BusinessDate
  The business date associated with the current TemporalContext. This is
  not necessarily the calendar date in UTC and is not necessarily the
  calendar date in the caller's local time.

- MarketCalendar
  A named calendar that defines sessions, holidays, half-days, and
  early-close rules for one market or venue.

- SourceProvider
  A named external system that reports facts to asof123 (for example a
  price feed, an OMS connector, an internal warehouse).

- SourcePolicy
  Optional caller-supplied policy for required sources, source max-age
  checks, and replay or historical knowledge-cutoff admissibility. It does
  not discover providers, persist source state, manage SLAs, retry
  providers, or implement a mutable registry.

- AsOfSnapshot
  An immutable, serializable record of a resolved TemporalContext, intended
  for replay, audit, and reproducibility. Carries explicit snapshot schema
  and semantic contract versions so persisted snapshots cannot silently be
  reinterpreted under different rules.

## 4. Required Initial Perspectives

The initial Perspective values are:

- PREVIEW
- PRE_TRADE_INTENT
- LIVE
- EXECUTED
- CANONICAL
- REPLAY
- HISTORICAL

These names are normative. Implementations may add perspectives later, but
must not rename, merge, or drop any of these without a contract change.

## 5. Required Initial Market Phases

The initial MarketPhase values are:

- PRE_OPEN
- MARKET_OPEN
- POST_CLOSE
- WEEKEND
- HOLIDAY
- CLOSED

CLOSED is the fail-safe default when no more specific phase can be
resolved.

## 6. Required Initial Source States

The initial SourceFreshness values are:

- FRESH
- STALE
- MISSING
- FAILED
- PRIOR_CLOSE
- PARTIAL
- PUBLISHED
- NOT_PUBLISHED

A SourceStatus carries one SourceFreshness value plus optional metadata
such as the last observed update instant, the expected publication time,
and the SourceProvider identity.

## 7. Required Initial Execution States

The initial ExecutionState values are:

- NOT_EXECUTED
- INTENDED
- WORKING
- PARTIALLY_FILLED
- FILLED
- CANCELED
- REJECTED
- UNKNOWN

NOT_EXECUTED is the fail-safe default when execution context is not
applicable or cannot be resolved (for example, a PREVIEW or
PRE_TRADE_INTENT call against an instrument with no open orders).
UNKNOWN is reserved for cases where execution status cannot be retrieved
and the call must fail closed rather than guess. INTENDED and WORKING
must never be reported under perspective EXECUTED or CANONICAL.

## 8. Required Initial Price Basis Values

The initial PriceBasis values are:

- PRIOR_CLOSE
- LAST_TRADE
- INDICATIVE
- OFFICIAL_CLOSE
- SETTLEMENT
- MODEL
- UNKNOWN

UNKNOWN is the fail-safe default when no PriceBasis can be resolved for
the current TemporalContext. MODEL covers any model-derived price
(theoretical, mark-to-model, interpolated curve) and must never be
reported as OFFICIAL_CLOSE or SETTLEMENT. OFFICIAL_CLOSE and SETTLEMENT
are reserved for venue-published canonical prices and must not be used
for intraday last-trade values.

## 9. Required Initial Publication States

The initial PublicationState values are:

- NOT_PUBLISHED
- PRE_PUBLISHED
- PUBLISHED
- EMBARGOED
- WITHDRAWN
- FAILED
- UNKNOWN

NOT_PUBLISHED is the fail-safe default when a dataset, report, or
document is expected but has not been released. PRE_PUBLISHED covers
content that has been prepared but is not yet visible to consumers
(for example, a build-and-stage step that has not been promoted).
EMBARGOED covers content held under a release embargo and must not be
treated as PUBLISHED before the embargo lifts. WITHDRAWN covers content
that was previously PUBLISHED and has been retracted; downstream readers
must treat WITHDRAWN as not available, not as historical. FAILED is
reserved for publication attempts that errored. UNKNOWN is reserved for
cases where publication state cannot be determined and the call must
fail closed.

## 10. Required Initial Canonical States

The initial CanonicalState values are:

- PROVISIONAL
- CANONICAL
- SUPERSEDED
- NOT_CANONICAL
- NOT_AVAILABLE
- UNKNOWN

PROVISIONAL is the fail-safe default when an answer can be produced but
no canonical authority has asserted it. CANONICAL is reserved for
answers asserted by the system of record. SUPERSEDED covers values that
were previously CANONICAL and have been replaced by a later canonical
assertion; readers must not treat SUPERSEDED as current. NOT_CANONICAL
covers answers that are valid for other perspectives but explicitly are
not eligible to be canonical (for example, a PREVIEW result).
NOT_AVAILABLE covers cases where a canonical answer exists but cannot be
retrieved at the resolution instant. UNKNOWN is reserved for cases
where canonical state cannot be determined and the call must fail
closed. A call under perspective CANONICAL must resolve to CANONICAL or
fail closed; it must never silently return PROVISIONAL.

## 11. Market Identity Convention

- Public requests and responses must identify markets using a MIC-style
  market code where available. For example, NYSE is XNYS and Nasdaq is
  XNAS.
- Every market code in a public request or response must be paired with
  an explicit IANA timezone in a separate field (for example
  market_timezone).
- A MarketCalendar may also expose an internal calendar_id for use by
  resolver internals, but calendar_id must not replace market plus
  market_timezone in public API models.
- For US equities examples, the contract uses market = XNYS and
  market_timezone = America/New_York.
- No API response may expose a market_phase, business_date, or any
  market-relative field without also exposing the market and
  market_timezone that were used to resolve it.
- If the requested market code has no recognized MarketCalendar, the
  resolver must fail closed per section 13. It must not fall back to a
  default market.

## 12. UTC and Timezone Rule

- All machine instants in asof123 must be represented in UTC.
- All market-facing interpretation (business date, market phase, session
  boundaries) must include an explicit IANA timezone identifier.
- For US equities examples, the IANA timezone is America/New_York.
- No naive datetime values are allowed in public models, API requests, or
  API responses. Every datetime field must carry timezone information, and
  every stored instant must be UTC.
- Conversions between UTC and a market timezone must go through a named
  MarketCalendar. Ad hoc offset arithmetic is not acceptable.

## 13. Fail-Closed Rule

If asof123 cannot resolve temporal semantics safely, it must return an
explicit unresolved or failed status. It must not silently guess, must not
fall back to wall-clock now, and must not assume a default perspective or
market phase.

Core public models and resolver request models must require callers to
provide the market, market_timezone, and perspective needed to resolve a
TemporalContext. The resolver must not silently supply these values on
behalf of an underspecified request.

The reference CLI and reference HTTP app may expose documented convenience
defaults for interactive use, such as LIVE / XNYS / America/New_York. These
defaults are surface-level conveniences only. They are not core resolver
semantics, they must be visible in help text or API parameter defaults, and
they must still pass through the same request validation as explicit caller
input.

Resolving a current context is allowed when the caller explicitly chooses a
current-oriented surface or perspective, such as GET /asof/current or a LIVE
ResolveRequest with no as_of_utc. In that case, the implementation may read
datetime.now(timezone.utc) to set the resolution instant. That is different
from a forbidden silent wall-clock fallback. REPLAY and HISTORICAL requests
must provide as_of_utc and knowledge_cutoff_utc; they must not substitute the
current wall-clock instant when those fields are missing. CANONICAL requests
must resolve against canonical publication semantics, not an arbitrary
wall-clock fallback.

Concretely:

- If a SourcePolicy declares a required source and that source has not
  reported, the resolved SourceStatus must be MISSING with
  reason_code=REQUIRED_SOURCE_MISSING, not FRESH.
- If SourcePolicy max-age checks determine that a source is too old, the
  resolved SourceStatus must be STALE with reason_code=SOURCE_STALE unless
  the provider has already reported a stronger fail-closed state such as
  FAILED, MISSING, STALE, or NOT_PUBLISHED.
- If a REPLAY or HISTORICAL source reports last_update_utc after
  knowledge_cutoff_utc, SourcePolicy must mark it NOT_PUBLISHED with
  reason_code=SOURCE_NOT_ADMISSIBLE. Equality at the cutoff is admissible.
- If a MarketCalendar is unknown, the resolver must fail closed with an
  explicit reason, not MARKET_OPEN. The core Python resolver may raise a
  typed ResolverError for this condition. API and CLI surfaces must translate
  that error into an explicit failed response or process error that carries a
  machine-readable reason and human-readable explanation.
- If a Perspective cannot be determined from the request, the response
  must be an explicit error, not a guessed PREVIEW or LIVE.
- Every fail-closed response must carry a machine-readable reason code and
  a human-readable explanation.

## 14. API Reference Surface

The standalone open-source repository may include a FastAPI reference
application exposing the following HTTP shape. The reference app is not an
orchestrator, scheduler, source registry, persistence layer, or production
auth boundary. It exists to demonstrate the contract over HTTP.

- GET /asof/current
  Resolve the current TemporalContext for a given perspective, market, and
  market timezone. The reference app may document convenience defaults for
  interactive use, but those defaults are not core resolver defaults.

- POST /asof/resolve
  Resolve a TemporalContext for an explicit request body. The reference app
  supports both a bare ResolveRequest and an optional wrapper with:
  - request: ResolveRequest
  - policy: SourcePolicy or null
  The wrapper is the API surface for required-source, max-age, and
  replay/historical cutoff policy. When policy is omitted, resolver behavior
  must match the bare ResolveRequest path.

- POST /sources/report
  Reserved contract shape for future source reporting. The current reference
  app is read-only and must return NOT_IMPLEMENTED / HTTP 501 for this
  endpoint because it has no mutable registry or persistence layer.

- GET /sources/status
  Read the current resolved state of one or more SourceProviders.

- POST /asof/snapshot
  Materialize the current or specified TemporalContext as an immutable
  AsOfSnapshot suitable for replay and audit.

All request and response bodies must obey the UTC and timezone rule in
section 12 and the fail-closed rule in section 13.

## 15. Implemented Reference Surfaces

The standalone open-source repository may include the following implemented
reference surfaces, provided they continue to obey this contract:

- Python package.
- Pinned enum modules.
- Public model modules.
- Resolver request models.
- Minimal resolver.
- SourceProvider protocol.
- Static SourceProvider.
- File SourceProvider.
- SourcePolicy.
- Pure source-policy evaluator.
- Pure publication-readiness evaluator.
- Snapshot helper.
- XNYS reference calendar.
- FastAPI reference app.
- CLI.
- Examples.
- Tests.

These surfaces are reference implementations of the temporal semantics
contract. They must not broaden asof123 into scheduling, orchestration,
warehouse storage, temporal database behavior, OMS/PMS behavior, broker
adapter behavior, proprietary warehouse integration, or internal fund system
logic.

## 16. Open-Source Boundary

The open-source core of asof123 may ship with:

- Timezone handling built on standard IANA tz data.
- Basic market calendar support.
- NYSE-style and Nasdaq-style example calendars and phase definitions.
- Static SourceProvider implementations (constant fixtures for tests and
  demos).
- File-based SourceProvider implementations (read freshness from a local
  file or directory).
- A FastAPI reference application exposing the endpoints in section 14.
- CLI reference commands for resolving a TemporalContext and materializing an
  AsOfSnapshot from a shell.

The following are explicitly out of scope for the open-source core. They
may exist as private adapters, commercial integrations, or downstream
projects, but they must not be required by, or merged into, the
open-source core:

- Bloomberg adapters or Bloomberg-derived data.
- OMS or PMS integrations.
- Broker fill adapters.
- Proprietary data warehouse adapters.
- Internal fund accounting or fund administration systems.

This boundary protects the open-source core from depending on commercial
licenses and from leaking proprietary schemas.

## 17. README Relationship

README.md is an introduction to the project and may contain examples,
quickstart notes, and current implementation status. It must remain
subordinate to this contract. If README.md and PRODUCT_CONTRACT.md ever
disagree, this contract wins and README.md must be corrected.

## 18. Coding Discipline

- All documents use plain ASCII punctuation only. No smart quotes, em
  dashes, ellipses, or other non-ASCII typography.
- The contract must remain direct, concrete, and implementation-guiding.
  It is a working specification, not marketing copy.
- Future changes to this contract must be made by editing this file, not
  by adding parallel documents that quietly disagree with it.

## 19. Snapshot Schema and Replay Contract

AsOfSnapshot is the immutable audit and replay artifact. Snapshot identity
has two layers:

- Record identity: snapshot_id identifies one captured audit record.
- Semantic content identity: hash_algorithm plus content_hash identifies
  the versioned semantic payload.

The current snapshot schema version is:

    asof123.snapshot.v1

The current semantic contract version is:

    asof123.contract.v1

The current hash algorithm is:

    sha256

The hash-affecting payload is exactly:

- snapshot_schema_version
- semantic_contract_version
- context

The audit-only fields are:

- snapshot_id
- captured_at_utc
- hash_algorithm
- content_hash

captured_at_utc is not hash-affecting. It records when the snapshot record
was materialized, not what semantic TemporalContext it represents.

snapshot_schema_version and semantic_contract_version are hash-affecting.
The same TemporalContext under a different serialization schema or semantic
contract must not share the same semantic content identity.

Canonical snapshot payload serialization must use:

- Pydantic JSON-mode model data.
- JSON object keys sorted with sort_keys=True.
- Tight JSON separators: comma and colon, with no inserted spaces.
- Enum values serialized as their pinned string values.
- UTC datetime fields serialized by Pydantic JSON mode after UTC validation.
- Null values included when present in the model dump.
- Only deterministic JSON-compatible metadata values.

Future persisted replay must not silently reinterpret history. It must either:

- reproduce the original interpretation under the recorded schema,
  semantic contract, calendar, timezone, and provider regimes; or
- explicitly declare reinterpretation under a newer regime.

Before persistent replay is introduced, persisted snapshots must record any
calendar, timezone, provider, and source artifact identities needed to
reproduce their interpretation. At minimum, future persisted replay designs
must define:

- calendar_id or equivalent calendar identity;
- calendar_version or equivalent rule publication version;
- timezone database identity/version when timezone conversion affects
  historical meaning;
- provider_id for each source assertion;
- provider_version or source artifact version/hash for provider-backed facts;
- assertion or observation instants for provider freshness claims.

Forbidden future behavior:

- Recomputing historical market phase from a newer calendar without
  explicit reinterpretation mode.
- Recomputing historical source freshness from live provider state.
- Treating enum additions, renames, or semantic changes as replay-neutral.
- Changing the hash-affecting payload without changing
  snapshot_schema_version.
- Changing the meaning of any hash-affecting value without changing
  semantic_contract_version.

## 20. Calendar, Timezone, and Provider Freeze Contract

Current in-memory snapshots do not implement persisted replay execution. The
v1 snapshot hash remains limited to snapshot_schema_version,
semantic_contract_version, and context. Calendar, timezone, and provider
freeze metadata are required before any future persisted replay execution is
allowed.

Future persisted replay must distinguish two operations:

- Reproduce original interpretation: use the same recorded calendar,
  timezone, provider, schema, and semantic regimes that produced the original
  snapshot.
- Reinterpret under newer semantics: explicitly declare the newer calendar,
  timezone, provider, schema, or semantic regime and produce a distinct
  result.

Silent reinterpretation is forbidden.

Calendar freeze metadata must identify the rules used for market-facing
interpretation. A future replay-safe snapshot or replay envelope must pin, at
minimum:

- calendar_id;
- calendar_version;
- market;
- market_timezone;
- market definition version when market identity rules can change;
- exchange rule version when exchange session rules can change;
- holiday table version when holidays are table-driven;
- early-close version when early closes are modeled;
- ad hoc closure version when ad hoc closures are modeled.

Timezone freeze metadata must identify the timezone rules used for
market-facing interpretation. A future replay-safe snapshot or replay
envelope must pin, at minimum:

- the explicit IANA timezone name used for interpretation;
- tzdata_version or equivalent timezone rule identity;
- any runtime timezone source identity when not supplied by a pinned tzdata
  package.

Provider freeze metadata must identify the source facts used by the resolver.
A future replay-safe snapshot or replay envelope must pin, at minimum, for
each provider-backed assertion:

- provider_id;
- provider_version;
- provider schema version when provider output schema can change;
- provider semantic contract when provider meaning can change;
- immutable source artifact hash or source version;
- assertion, observation, or publication instant used for freshness claims.

For future persisted replay, calendar, timezone, and provider freeze metadata
are part of the replay interpretation boundary and must be hash-affecting in
the persisted replay payload or in a linked immutable replay envelope whose
own identity is hash-addressed. For current in-memory snapshots, these fields
are not present and are not part of the v1 content_hash.

Advisory metadata may exist outside the hash only if it cannot change replay
meaning. Any metadata that can alter market phase, business date, source
freshness, publication state, price basis, canonical state, or admissibility
must be hash-affecting before persisted replay is allowed.

Future persistence guardrails:

- No persisted replay execution may be introduced until the freeze envelope
  is defined in code and tests.
- No calendar provider may silently upgrade historical rules for reproduction
  mode.
- No timezone conversion may silently use an unrecorded rule source for
  reproduction mode.
- No provider-backed replay may call live provider state for reproduction
  mode.
- Reinterpretation mode must preserve the original snapshot and original
  content_hash and must emit a distinct result under the declared newer
  regime.

## 21. Public Error Contract

Fail-closed errors must be explicit, machine-readable, deterministic, and
stable across public surfaces.

Stable fields:

- reason_code: pinned machine-readable failure identity.
- error: broad surface/category identifier.
- HTTP status code for API responses.
- CLI exit code.
- SourceStatus.freshness when provider failures are embedded as data.

Advisory fields:

- explanation: English detail for humans.
- message: backward-compatible English text, when present.
- details: structured validation diagnostics whose exact shape may follow
  Pydantic/FastAPI validation details.

Consumers must not parse explanation or message to determine semantics. They
must branch on reason_code, enum values, HTTP status, CLI exit code, and
model fields.

ResolverError carries:

- reason_code;
- explanation;
- string form "REASON_CODE: explanation" for backward compatibility.

The pinned public reason codes are:

- CALENDAR_MARKET_MISMATCH
- CALENDAR_TIMEZONE_MISMATCH
- CANONICAL_NOT_CANONICAL
- CANONICAL_UNSUPPORTED
- CLI_ARGUMENT_ERROR
- DUPLICATE_PROVIDER_NAME
- EXECUTION_FACTS_UNAVAILABLE
- INVALID_PROVIDER
- INVALID_REQUEST
- INVALID_SNAPSHOT
- NOT_IMPLEMENTED
- PRICE_BASIS_UNRESOLVED
- PUBLICATION_AFTER_CUTOFF
- PUBLICATION_ASSERTION_AFTER_CUTOFF
- PUBLICATION_ASSERTION_AMBIGUOUS
- PUBLICATION_METADATA_INCOMPLETE
- PUBLICATION_METADATA_INVALID
- PUBLICATION_METADATA_MISSING
- PUBLICATION_METADATA_UNSUPPORTED
- PUBLICATION_NOT_PUBLISHED
- PROVIDER_REPORT_FAILED
- REQUIRED_SOURCE_MISSING
- SOURCE_NOT_ADMISSIBLE
- SOURCE_STALE
- UNKNOWN_MARKET
- VALIDATION_ERROR

API resolver failures must return a structured payload with error,
reason_code, explanation, and message. Malformed requests must be
distinguishable from semantic resolver failures by error=VALIDATION_ERROR
and reason_code=VALIDATION_ERROR.

CLI runtime failures must write a structured JSON error payload to stderr
for resolver, request validation, provider construction, snapshot validation,
and serve dependency failures. CLI exit code 0 means success; exit code 2
means request, validation, resolver, or local runtime failure. Argparse may
raise SystemExit(2) for syntactically malformed invocations.

Provider failures are data-bearing by default. ProviderReportError is
translated by the resolver into SourceStatus.freshness=FAILED with
reason_code=PROVIDER_REPORT_FAILED and explanation. A provider must never
silently report FRESH when it cannot safely report facts.

UNKNOWN enum states and FAILED provider states must carry reason_code and
explanation wherever the model contract requires fail-closed metadata. Such
states are deterministic snapshot content and therefore hash-affecting.

Future reason code changes require product contract review. New reason codes
may be additive under the same semantic contract only when they do not change
the meaning of existing reason codes. Renames, removals, and semantic reuse
of an existing reason code require a semantic_contract_version change.

## 22. Canonical Authority Boundary

Canonicality is an asserted institutional truth boundary. It is not a
convenience label and must not mean latest, freshest, most recent, inferred,
provider majority vote, or best effort.

CANONICAL differs from other perspectives:

- LIVE resolves current temporal meaning and may remain provisional.
- EXECUTED resolves execution-context meaning and may remain non-canonical.
- REPLAY reproduces a historical interpretation from frozen inputs.
- HISTORICAL resolves a pinned historical context without implying system of
  record authority.
- CANONICAL asks the system of record whether an answer has been asserted as
  canonical under its publication rules.

The current resolver implements a narrow canonical publication-readiness
gate. This is not a full canonical authority. A CANONICAL request may return
a TemporalContext with canonical_state=CANONICAL only when exactly one
caller-supplied SourceStatus.metadata["publication"] assertion validates and
proves all of the following:

- publication_state=PUBLISHED;
- canonical_state=CANONICAL;
- publication_utc is present and UTC-valid;
- asserted_at_utc is present and UTC-valid;
- for CANONICAL, REPLAY, and HISTORICAL cutoff checks, neither
  publication_utc nor asserted_at_utc is after knowledge_cutoff_utc;
- unsupported lifecycle metadata is absent.

All other CANONICAL cases must fail closed with a typed reason code. Missing,
malformed, incomplete, unsupported, ambiguous, not-published, not-canonical,
or after-cutoff publication metadata must not produce a canonical context.

The resolver must not infer canonical_state=CANONICAL from provider
freshness, latest timestamp, execution_state, majority agreement, price
basis, market phase, or any other non-publication-readiness signal. It must
also not infer canonical_state=CANONICAL from publication_state alone;
canonical_state=CANONICAL is required.

The current narrow gate deliberately uses SourceStatus metadata rather than a
new public ontology noun. A future full canonical authority may require a
typed boundary separate from ordinary SourceProvider facts. Such a boundary
would provide, at minimum:

- authority_id;
- authority_version;
- authority protocol version;
- publication schema version;
- assertion instant;
- publication instant;
- canonical_state assertion;
- publication_state assertion;
- provenance for the asserted fact;
- supersession identity when an assertion replaces a prior assertion;
- withdrawal identity and reason when an assertion is retracted;
- semantic contract version used by the authority.

Providers may report facts used by the resolver. A provider returning FRESH,
PUBLISHED, OFFICIAL_CLOSE, SETTLEMENT, or FILLED is not enough to establish
canonical_state=CANONICAL. Under the current narrow gate, the only accepted
canonical-readiness path is one validated publication metadata assertion with
publication_state=PUBLISHED and canonical_state=CANONICAL.

If a future authority or current publication assertion is unavailable,
incomplete, contradictory, unsupported, ambiguous, or version-incompatible,
CANONICAL must fail closed with a typed reason code. It must not downgrade
silently to LIVE, HISTORICAL, REPLAY, or PROVISIONAL. If authority facts or
publication assertions disagree with ordinary providers, the resolver must
surface the disagreement explicitly or fail closed; it must not hide the
conflict by choosing the newest or freshest source.

Canonical publication lifecycle:

- NOT_PUBLISHED may become PRE_PUBLISHED, EMBARGOED, PUBLISHED, FAILED, or
  UNKNOWN with reason metadata.
- PRE_PUBLISHED may become PUBLISHED, EMBARGOED, WITHDRAWN, FAILED, or
  UNKNOWN with reason metadata.
- EMBARGOED may become PUBLISHED, WITHDRAWN, FAILED, or UNKNOWN with reason
  metadata.
- PUBLISHED may become WITHDRAWN or may be paired with
  canonical_state=SUPERSEDED when replaced by a later canonical assertion.
- WITHDRAWN is terminal for the withdrawn publication identity unless an
  explicit new publication identity is asserted.
- FAILED is terminal for that publication attempt unless a new attempt
  identity is asserted.
- SUPERSEDED is terminal for that canonical assertion identity. It must not be
  treated as current canonical truth.

Supersession and withdrawal require explicit provenance. A superseded
assertion must identify the replacing assertion. A withdrawn assertion must
identify the withdrawal event, withdrawal instant, and authority responsible
for withdrawal. The current narrow publication-readiness gate does not
implement withdrawal or supersession semantics; supplied withdrawal or
supersession metadata must fail closed as unsupported.

Replay-safe canonical semantics:

- Historical replay must preserve the canonical assertion exactly as asserted
  at the time, including CANONICAL, SUPERSEDED, WITHDRAWN, NOT_CANONICAL,
  NOT_AVAILABLE, and UNKNOWN states.
- Replay must never silently upgrade provisional history into canonical
  history.
- Replay under newer authority, publication, calendar, provider, timezone, or
  semantic regimes is reinterpretation and must be explicitly declared.
- Superseded and withdrawn assertions must remain visible to reproduction
  replay as the historical assertion states they were, not as current truth.

Future persisted snapshots or replay envelopes involving CANONICAL must make
authority metadata hash-affecting. At minimum, authority_id,
authority_version, authority protocol version, publication schema version,
assertion instant, publication instant, supersession or withdrawal identity,
and semantic contract version must be frozen for reproduction replay.

Future integration prohibitions:

- Do not infer canonicality from freshness.
- Do not infer canonicality from publication_state alone.
- Do not infer canonicality from execution_state.
- Do not infer canonicality from latest timestamp.
- Do not infer canonicality from provider majority vote.
- Do not choose among multiple publication assertions.
- Do not silently reinterpret withdrawn or superseded assertions.
- Do not let mutable current authority state rewrite historical snapshots.
- Do not let Replay, Run Diff, Audit, or read paths call providers or runtime
  authority to recompute historical canonical meaning.

Canonical semantics require separate governance for:

- asof123 semantic_contract_version;
- canonical authority protocol version;
- publication schema version;
- authority_version;
- replay freeze metadata.

Changing the meaning of canonical_state, publication_state, supersession,
withdrawal, or authority interpretation requires contract review and may
require a semantic_contract_version change.

## 23. Market Calendar Semantics

Market calendars are semantic interpretation boundaries, not convenience
timestamp helpers. They define market-facing meaning such as business_date,
market_phase, session boundaries, holidays, and closure states for a named
market plus explicit IANA timezone.

The current XNYS calendar is a minimal reference calendar only. It guarantees:

- market = XNYS;
- market_timezone = America/New_York;
- UTC input validation for calendar methods;
- conversion through ZoneInfo for America/New_York;
- local-date business_date semantics;
- deterministic weekday handling;
- deterministic regular-session phase boundaries;
- deterministic 2025-2026 hard-coded holiday handling;
- deterministic DST behavior according to the runtime timezone database.

The current XNYS calendar does not guarantee:

- full NYSE exchange-calendar authority;
- production trading calendar completeness;
- full holiday coverage outside the supported hard-coded years;
- modeled early-close sessions;
- modeled half days;
- modeled emergency exchange closures;
- modeled ad hoc market halts;
- modeled unscheduled holidays;
- modeled pre-market or after-hours trading sessions;
- protection against future timezone database reinterpretation drift.

Current XNYS regular-session phase semantics:

- Saturday or Sunday in America/New_York returns WEEKEND.
- Known hard-coded holidays return HOLIDAY.
- Dates outside the supported holiday years return CLOSED.
- Known unsupported early-close dates return CLOSED.
- Regular supported non-holiday weekdays before 09:30 ET return PRE_OPEN.
- Regular supported non-holiday weekdays from 09:30 ET until before 16:00 ET
  return MARKET_OPEN.
- Regular supported non-holiday weekdays at or after 16:00 ET return
  POST_CLOSE.

CLOSED is the fail-safe calendar phase when the reference calendar knows it
cannot safely apply regular-session semantics. The resolver may raise a typed
ResolverError for unknown markets or calendar identity mismatches; the
calendar itself uses CLOSED for supported-market conditions that are known to
be unsupported by the minimal reference calendar.

Future market calendar implementations must preserve:

- explicit market plus market_timezone identity;
- no fallback market;
- no fallback timezone;
- no provider-driven market phase inference;
- UTC-only machine instants;
- explicit fail-closed behavior for unsupported sessions;
- deterministic phase boundaries for the same UTC instant and same calendar
  rule version.

Future persisted replay must pin:

- calendar_id;
- calendar_version;
- market;
- market_timezone;
- holiday table version;
- exchange rule version;
- market session version;
- early-close version when early closes are modeled;
- ad hoc closure version when ad hoc closures are modeled;
- timezone rule identity or tzdata_version.

Reproduction replay must preserve the original calendar interpretation.
Reinterpretation under newer holidays, exchange sessions, market definitions,
or timezone rules is allowed only when explicitly declared. Historical replay
must never silently reinterpret market phases, business dates, or session
boundaries.

Future integrations must not:

- silently update holiday tables in a way that rewrites historical meaning;
- fall back from one market to another;
- use timezone aliases to reinterpret market meaning;
- apply current calendar rules to historical replay without declaring
  reinterpretation;
- infer market phase from provider data;
- use mutable runtime calendars in Replay, Run Diff, Audit, or other read
  paths;
- treat the current XNYS reference calendar as production exchange authority.
