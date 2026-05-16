# Error Contract Hardening Audit

Date: 2026-05-15

Scope: standalone asof123 resolver, API, CLI, provider, and snapshot error
contract. This was not a fin123 integration pass, replay engine pass,
persistence pass, scheduler pass, database pass, or external integration pass.

`docs/unified_diff.md` does not exist and was not created.

## Resolver Error Findings

Resolver failures now carry structured machine-readable identity:

- `ResolverError.reason_code`
- `ResolverError.explanation`
- `str(error)` remains `REASON_CODE: explanation` for compatibility.

The reason code is stable and programmatic. The explanation is advisory.

Resolver fail-closed cases covered by typed reason codes include:

- unknown market;
- calendar market mismatch;
- calendar timezone mismatch;
- duplicate provider name;
- canonical unsupported.

Data-bearing unresolved states continue to use model-level `reason_code` and
`explanation`, including price basis and execution fact gaps.

## API Error Findings

API resolver failures return structured JSON with:

- `error`
- `reason_code`
- `explanation`
- `message`

Malformed requests are distinguishable from semantic resolver failures:

- malformed or invalid request payload: HTTP 422,
  `error=VALIDATION_ERROR`, `reason_code=VALIDATION_ERROR`;
- semantic resolver failure: HTTP 400, `error=RESOLVER_ERROR`, specific
  resolver `reason_code`;
- duplicate provider names in `/sources/status`: HTTP 409,
  `reason_code=DUPLICATE_PROVIDER_NAME`;
- read-only source reporting endpoint: HTTP 501,
  `reason_code=NOT_IMPLEMENTED`.

Callers no longer need to parse English `message` text to identify
canonical unsupported, unknown market, duplicate provider names, or validation
failure.

## CLI Error Findings

CLI runtime failures now write structured JSON error payloads to stderr for:

- invalid `ResolveRequest`;
- invalid provider construction;
- resolver failures;
- invalid snapshot construction;
- missing serve dependency.

The CLI exit code contract remains:

- `0`: success;
- `2`: validation, resolver, local dependency, or invocation failure.

Argparse syntactic failures may still raise `SystemExit(2)` before command
dispatch. That is acceptable for the current reference CLI but remains a
future hardening opportunity if shell automation needs uniform JSON for every
possible invalid invocation.

## Provider Failure Findings

Provider failures are data-bearing, not process-fatal, once control reaches
the resolver:

- `ProviderReportError` becomes `SourceStatus.freshness=FAILED`;
- `reason_code=PROVIDER_REPORT_FAILED`;
- `explanation` carries advisory provider detail.

The provider protocol still permits a provider to return a FAILED
`SourceStatus` directly. Model validation requires FAILED freshness to carry
reason metadata, so a provider failure cannot silently appear as a complete
fail-closed state without reason fields.

## Snapshot / Error Interaction Findings

UNKNOWN and FAILED states with reason metadata are part of
`TemporalContext`. They are included in deterministic snapshot payloads and
therefore affect `content_hash`.

Semantically invalid states cannot enter snapshots without first passing
`TemporalContext` and `SourceStatus` validation. `make_snapshot()` embeds a
validated copy of the context, preserving fail-closed metadata and hash
stability.

## Error Taxonomy Recommendations

Reason codes are now centralized in `ErrorReasonCode`. Future governance:

- additions require contract review;
- renames are not compatible;
- removals are not compatible;
- reusing a reason code for different semantics is forbidden;
- semantic reuse or meaning changes require a
  `semantic_contract_version` change.

Recommended reserved namespaces for future work:

- resolver semantic failures;
- validation failures;
- provider fact failures;
- snapshot construction failures;
- reference surface limitations.

No broad exception hierarchy is needed yet.

## Stable Vs Advisory Field Definitions

Stable:

- `reason_code`;
- `error`;
- HTTP status code;
- CLI exit code;
- enum values such as `FAILED` and `UNKNOWN`;
- snapshot hash-affecting fail-closed model fields.

Advisory:

- `explanation`;
- `message`;
- validation `details` shape;
- provider prose embedded in explanations.

Consumers must not parse advisory prose for control flow.

## Future Integration Safety Guidance

API consumers should branch on HTTP status and `reason_code`.

CLI automation should parse stderr JSON for command-dispatch failures and use
exit code 2 for failure. Argparse pre-dispatch failures remain conventional
CLI errors.

Replay systems and persistence layers must persist reason codes and
fail-closed model fields as semantic payload, not as discardable diagnostics.

Canonical authority systems must introduce new typed reason codes for
authority failures rather than overloading `CANONICAL_UNSUPPORTED`.

Provider expansion must map unsafe provider conditions to
`PROVIDER_REPORT_FAILED` or a future typed provider reason code, never to
`FRESH`.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Argparse syntax errors are still conventional stderr/SystemExit(2), not the structured CLI JSON shape. | Acceptable for current reference CLI; future hardening if full CLI machine contract is required. |
| WARNING | Validation `details` follows Pydantic/FastAPI structure and is advisory. | Consumers should branch on `reason_code`, not nested validation text. |
| NOTE | API resolver failures now expose explicit `reason_code`. | Removes prior need to parse message text. |
| NOTE | Provider failures remain data-bearing FAILED SourceStatus values. | Consistent with the doctrine that external systems report facts and asof123 resolves meaning. |

## Final Verdict

PASS WITH WARNINGS.

The public runtime failure contract is now typed enough for current API, CLI,
resolver, provider, and snapshot surfaces. Remaining warnings are future
interface-hardening opportunities, not current semantic corruption risks.
