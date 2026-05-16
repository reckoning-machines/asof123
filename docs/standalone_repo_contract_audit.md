# Standalone Repository Contract Audit

Date: 2026-05-15

Scope: audit-only pass. No code, package skeleton, FastAPI, CLI, resolver,
provider, or test implementation was added by this audit.

`docs/unified_diff.md` does not exist and was not created.

## Repository Inventory

Tracked root files:

- `.gitignore`
- `PRODUCT_CONTRACT.md`
- `README.md`
- `pyproject.toml`

Tracked docs:

- `docs/api_reference_surface_report.md`
- `docs/cli_reference_report.md`
- `docs/examples_quickstart_report.md`
- `docs/minimal_resolver_report.md`
- `docs/model_skeleton_report.md`
- `docs/product_contract_report.md`
- `docs/provider_snapshot_report.md`
- `docs/quickstart.md`
- `docs/readme_initial_report.md`
- `docs/request_protocol_report.md`
- `docs/semantic_enums_contract_report.md`
- `docs/standalone_repo_contract_audit.md`

Tracked package files:

- `src/asof123/__init__.py`
- `src/asof123/api.py`
- `src/asof123/calendar.py`
- `src/asof123/calendars/__init__.py`
- `src/asof123/calendars/xnys.py`
- `src/asof123/cli.py`
- `src/asof123/enums.py`
- `src/asof123/models.py`
- `src/asof123/providers/__init__.py`
- `src/asof123/providers/_protocol.py`
- `src/asof123/providers/file.py`
- `src/asof123/providers/static.py`
- `src/asof123/requests.py`
- `src/asof123/resolver.py`
- `src/asof123/snapshot.py`

Tracked examples:

- `examples/resolve_demo.py`
- `examples/snapshot_demo.py`
- `examples/source_status_quotes.json`

Tracked tests:

- `tests/test_api.py`
- `tests/test_calendar.py`
- `tests/test_cli.py`
- `tests/test_enums.py`
- `tests/test_examples.py`
- `tests/test_file_provider.py`
- `tests/test_models.py`
- `tests/test_providers.py`
- `tests/test_requests.py`
- `tests/test_resolver.py`
- `tests/test_snapshot.py`
- `tests/test_static_provider.py`

Additional ignored/generated files exist under `__pycache__/` and
`.pytest_cache/`. They are not tracked by git.

## Contract Conformance Findings

`PRODUCT_CONTRACT.md` is still explicit that it is the canonical contract:
any code, API surface, or documentation that contradicts it is wrong and
must conform to it. README also defers to the contract.

However, the repository is no longer in the "no code yet" state described
by the audit brief and by `PRODUCT_CONTRACT.md` section 17. The repo already
contains a package skeleton, enums, models, request model, provider protocol,
static provider, file provider, snapshot helper, resolver, XNYS calendar,
FastAPI reference app, CLI, examples, and tests.

That is not necessarily product-scope leakage, because most of those
components are listed as allowed future open-source surface in sections 14
and 15. It is a contract/readiness problem for the requested next step:
"Python model skeleton only" is no longer the next step, because that layer
already exists and later layers have also been added.

The strongest internal contradiction is `PRODUCT_CONTRACT.md` section 14,
which says the API endpoints are "not yet implemented", while
`src/asof123/api.py`, `tests/test_api.py`, and README state that a FastAPI
reference app exists. Section 17 also says "No code is written in this pass"
and "No application scaffolding is created in this pass"; that appears to be
historical pass language embedded in the canonical contract. As a canonical
contract, it now reads as a current restriction and conflicts with the
repository state.

## README Conformance Findings

README correctly says `PRODUCT_CONTRACT.md` is canonical and that README is
only a working introduction. Its ontology, JSON example, market identity,
UTC wording, fail-closed examples, and open-source boundary are broadly
aligned with the contract.

README is more current than the contract about implementation status:
it states the repository ships a Python library, CLI, FastAPI reference app,
and examples. That contradicts the contract's "not yet implemented" API
direction and "no code" pass wording. Because the contract is canonical, the
README cannot be treated as the authority for this drift.

README includes OMS/PMS, warehouse, fills, and broker-style examples only
as adjacent systems, bug examples, or out-of-scope adapters. I found no
README claim that asof123 should become an OMS/PMS, broker adapter,
warehouse, or internal fund system.

## Enum Consistency Findings

`PRODUCT_CONTRACT.md` pins the expected values for:

- `Perspective`
- `MarketPhase`
- `SourceFreshness`
- `ExecutionState`
- `PriceBasis`
- `PublicationState`
- `CanonicalState`

`src/asof123/enums.py` matches those pinned values exactly and uses uppercase
string values where `.value == .name`. Tests in `tests/test_enums.py` pin
the value sets.

Searches for lowercase enum-like values found many ordinary English prose
matches, especially in historical reports and README explanatory text, but
no stale lowercase enum value presented as normative in `PRODUCT_CONTRACT.md`,
README, code, examples, or tests. The historical report
`docs/semantic_enums_contract_report.md` explicitly mentions an old lowercase
set as removed; that is boundary/history, not a current normative claim.

## UTC, Timezone, and Fail-Closed Findings

The contract clearly states:

- all machine instants are UTC;
- market-facing interpretation requires explicit IANA timezone;
- no naive datetimes are allowed in public models, API requests, or API
  responses;
- market-relative fields require `market` plus `market_timezone`;
- unknown calendars must fail closed without default-market fallback;
- unsafe resolution must not silently guess or fall back to wall-clock now.

The current model/request/calendar/CLI code mostly implements these rules:
UTC-aware datetime validators reject naive and non-UTC values, market
timezone validation uses `zoneinfo`, market codes are uppercase, and public
models include `market` plus `market_timezone`.

Important risks:

- `GET /asof/current` in `src/asof123/api.py` defaults `perspective=LIVE`,
  `market=XNYS`, and `market_timezone=America/New_York`. The contract says
  asof123 must not assume a default perspective or market. This default may
  be acceptable only if explicitly classified as a reference-app convenience,
  but as a public API route it weakens the fail-closed rule.
- `asof123 resolve` in `src/asof123/cli.py` also defaults to LIVE/XNYS/
  America-New_York. This is similarly convenient but contract-risky unless
  the contract explicitly permits CLI defaults while preserving API/model
  strictness.
- `resolve()` uses `datetime.now(timezone.utc)` when `as_of_utc` is omitted.
  The contract permits current-context resolution, but section 13 says not to
  "fall back to wall-clock now". This is currently controlled by
  `ResolveRequest` perspective rules, but the contract should distinguish
  an explicit current request from a silent fallback.
- Unknown market in `resolve()` raises `ResolverError` rather than returning
  a `TemporalContext` with `market_phase=CLOSED` and machine-readable reason.
  Section 13 says unknown MarketCalendar should resolve to CLOSED with an
  explicit reason. Section 11 says unknown market must fail closed. The code
  is fail-closed, but the response shape is not yet aligned with the more
  concrete section 13 wording.

## Open-Source Boundary Findings

The implemented components are within the broad open-source allowance in
section 15: timezone handling, basic calendar, XNYS example calendar, static
and file providers, FastAPI reference app, CLI, examples, and tests.

No Bloomberg adapter, OMS/PMS integration, broker fill adapter, proprietary
warehouse adapter, or internal fund system implementation exists in
`src/`, `examples/`, or `tests/`.

Forbidden-scope terms appear as boundary descriptions, examples of adjacent
systems, or explanatory prose. One provider example uses
`internal_ca_warehouse` in README JSON as a source-provider name. That is an
example of an external system reporting facts, not an implemented warehouse
adapter. It is acceptable, though future examples should prefer neutral names
if the project wants to keep the boundary visually clean.

## HOLD / WARNING / NOTE Table

| Level | Finding | Impact |
| --- | --- | --- |
| HOLD | The repository already contains much more than a Python model skeleton: resolver, providers, calendar, FastAPI app, CLI, examples, and tests. | The requested next implementation step cannot safely be "create only the Python model skeleton" because that layer already exists and later layers are present. |
| HOLD | `PRODUCT_CONTRACT.md` section 14 says the HTTP API is not yet implemented, and section 17 says no code/scaffolding is written in this pass. | The canonical contract contradicts the actual repo state. Fix the contract or revert implementation before further implementation planning. |
| WARNING | API and CLI defaults for perspective/market/timezone weaken the "no default perspective or market" rule. | Implementation can proceed only if defaults are explicitly scoped as reference-app/CLI conveniences or removed. |
| WARNING | Unknown market currently raises `ResolverError` rather than returning a CLOSED unresolved response with reason fields. | Fail-closed behavior exists, but the exact contract shape is ambiguous/inconsistent. |
| WARNING | Current-context resolution uses `datetime.now(timezone.utc)` when `as_of_utc` is omitted. | This needs contract wording that distinguishes explicit current resolution from forbidden wall-clock fallback. |
| WARNING | `docs/api_reference_surface_report.md` contains non-ASCII em dash characters. | This violates the contract's ASCII documentation discipline, though not product semantics. |
| NOTE | Enum groups are pinned consistently in the contract and code. | No enum blocker found. |
| NOTE | README defers to the contract and does not introduce a competing specification. | README is acceptable once contract/current-state drift is resolved. |
| NOTE | Forbidden-scope terms are boundary-only or examples; no proprietary adapter implementation was found. | Open-source boundary is preserved in code. |

## Final Verdict

HOLD.

The repository does not currently conform to the chronological/pass-state
claims in its own canonical contract. The product semantics are mostly
coherent, but the canonical contract still describes an earlier phase while
the repo contains resolver/provider/API/CLI implementation.

Explicit recommendation: the next pass should not create the Python model
skeleton. That skeleton already exists. Before any implementation pass,
choose one of two paths:

1. Update `PRODUCT_CONTRACT.md` to remove historical pass language, mark the
   model/resolver/provider/API/CLI layers as current or accepted reference
   surfaces, and clarify the API/CLI default behavior and unknown-market
   fail-closed shape.
2. Or revert the repository to the intended pre-code state and then perform
   a true model-skeleton-only implementation pass.

Until that choice is made, the next implementation step is not safe.

## Validation Commands

Commands run:

- `rg --files`
- `git status --short`
- `find . -maxdepth 3 -type f | sort`
- `git ls-files | sort`
- `git ls-files --others --exclude-standard | sort`
- `test -e docs/unified_diff.md && sed -n '1,220p' docs/unified_diff.md || true`
- `LC_ALL=C rg -n "[^\\x00-\\x7F]" --glob '*.md'`
- `rg -n "\\b(preview|pre_trade_intent|live|executed|canonical|replay|historical|pre_open|market_open|post_close|weekend|holiday|closed|fresh|stale|missing|failed|prior_close|partial|published|not_published|not_executed|intended|working|partially_filled|filled|canceled|rejected|unknown|last_trade|indicative|official_close|settlement|model|pre_published|embargoed|withdrawn|provisional|superseded|not_canonical|not_available)\\b" .`
- `rg -n "naive|timezone|time zone|UTC|Z\\\"|now\\(|datetime\\.now|fromisoformat|local time|wall-clock|default market|fallback|fall back" .`
- `rg -n "Bloomberg|OMS|PMS|broker|warehouse|fills|fill|filled|fund" .`
- `git diff --check`

Validation results:

- Non-ASCII Markdown search found five em dash matches in
  `docs/api_reference_surface_report.md`.
- Lowercase enum-like search found prose/history matches only; no current
  normative stale lowercase enum values found.
- Naive datetime/timezone search found strict validation language and tests,
  plus the default/current-time risks listed above.
- Forbidden-scope search found boundary/example usage only; no scope leakage
  implementation found.
- `git diff --check` passed.
