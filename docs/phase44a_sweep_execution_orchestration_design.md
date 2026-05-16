# Phase 44a Sweep Execution Orchestration Design

Date: 2026-05-15

Scope: design and audit only. This phase defines the first governed Sweep
execution and orchestration contract. It does not implement execution,
workers, retries, routes, UI, Replay changes, Run Diff changes, provider
runtime calls, background jobs, async orchestration, directory scanning
authority, child reconstruction, or mutable artifact repair.

The repository inspected for this pass does not currently contain Sweep
runtime implementation. The design below is therefore a forward contract for
future phases.

## Completed Authority Chain

The completed chain this design preserves is:

- deterministic Sweep planning;
- typed child assembly;
- typed Run Set rows;
- append-only Run Set artifact write;
- pointer-only discovery index;
- private lookup;
- `run_set_get` integration;
- `audit_run_set` integration;
- `run_set_list` summary integration;
- Replay and Run Diff remain artifact-only.

The invariant remains:

    Model -> Version -> Scenario -> Run -> Results -> Audit

And:

    saved Model Version + immutable Universe snapshot
      -> deterministic child execution plan
      -> normal child Runs
      -> authoritative Run Set artifact
      -> pointer-only discovery
      -> artifact-only Replay/Audit/Run Diff

## Child Run Execution Ownership

Child Runs are executed by the same normal Run execution mechanism that
executes any other governed Run. Sweep orchestration owns only the
deterministic plan, dispatch order, idempotency envelope, and Run Set artifact
assembly. It must not embed provider/runtime execution logic in Sweep core.

Child Runs should be persisted individually before the Run Set artifact is
written. A Run Set artifact may reference only authoritative child run_ids
that already exist as normal child Runs, including failed child Runs when the
Run Set policy allows partial failure.

Ordering guarantees:

- The child execution plan has deterministic child ordering.
- The Run Set artifact records children in deterministic plan order, not
  completion order.
- Operational worker scheduling may vary, but it must not change the planned
  child order stored in the Run Set artifact.
- Run Set rows must be typed values only forever.
- DATA aggregate metadata remains outside Results rows forever.

Local core owns deterministic ordering. Hosted orchestration may own worker
placement, queue timing, and parallelism, but not child ordering semantics.

## Child Run Identity Semantics

Authoritative child run_id generation must happen at the child Run creation
boundary, not during read paths and not during artifact reconstruction.

The future implementation must choose and pin one authoritative mechanism:

- deterministic child run_id derived from the parent Sweep idempotency key
  plus child plan key; or
- append-only normal Run allocation protected by a unique idempotency key.

Either mechanism is acceptable only if duplicate prevention is enforced before
child execution can write a second authoritative child Run for the same child
plan key.

Placeholder ids are not authoritative. A planning placeholder may be used
inside an execution plan, but it must be replaced by an authoritative child
run_id before any Run Set artifact is written. A Run Set artifact must never
store placeholder child ids as if they were executed child Runs.

Retry semantics:

- Retrying an unstarted child may reuse the same child idempotency key and
  produce the same authoritative child run_id if no child Run was written.
- Retrying a completed child must not create a duplicate successful child Run
  for the same child plan key.
- Retrying a failed child must either reuse the same authoritative child
  run_id as a failed Run attempt record model, or create a new Run only under
  an explicit attempt/version policy. The policy must be locked before
  implementation.
- Silent replacement of a failed child Run with a successful one under the
  same run_id is forbidden.

## Run Set Creation Boundary

A Run Set artifact is allowed to exist only after the orchestration layer has
resolved every planned child into an authoritative terminal child state:

- succeeded;
- failed;
- canceled; or
- explicitly omitted by a governed policy encoded in the artifact.

Minimum successful child requirements must be policy-explicit:

- all-success Run Set: artifact may be written only when every child Run
  succeeded;
- partial-failure Run Set: artifact may be written when at least one child is
  terminal and every planned child has a terminal or explicitly omitted state;
- failed-closed Run Set: no artifact is written unless the policy can encode
  every failed child deterministically.

Partial-failure Run Sets are allowed only if the artifact records:

- parent Sweep identity;
- deterministic plan identity;
- child plan keys;
- authoritative child run_ids for executed children;
- child terminal state;
- failure reason_code and explanation for failed children;
- policy name/version permitting partial failure.

Run Set creation should be append-only eventual, not mutable transactional
repair. A future implementation may use a transactional local append to write
the artifact and discovery pointer as a durability optimization, but authority
must still come from the append-only Run Set artifact. If index append fails
after artifact write, recovery must append the missing pointer; it must not
rewrite the artifact.

## Retry And Idempotency Contract

The parent Sweep idempotency key must include:

- saved Model Version identity;
- immutable Universe snapshot identity;
- Scenario identity;
- deterministic Sweep plan parameters;
- Sweep planning algorithm version;
- semantic contract version;
- execution policy version.

Each child idempotency key must include:

- parent Sweep idempotency key;
- deterministic child plan key;
- child Run input payload hash;
- child execution policy version.

Run Set artifact idempotency key must include:

- parent Sweep idempotency key;
- deterministic ordered list of child plan keys;
- authoritative child run_ids and terminal states;
- Run Set schema version;
- artifact authority contract version.

Crash outcomes:

- Before child Run writes: retry may resume from the same parent idempotency
  key and create missing child Runs.
- After some child Run writes: retry must discover existing child Runs by
  idempotency key, not by reconstructing from Results rows or directory
  scanning authority.
- After Run Set artifact write: retry must return or discover the existing
  authoritative artifact by artifact id/key and must not create a duplicate
  Run Set artifact.
- After discovery index append: retry must be idempotent and must not append
  a conflicting pointer for the same Run Set authority key.

Retries must not create duplicate child Runs or duplicate Run Sets. Duplicate
prevention must be enforced by unique idempotency keys and append-only
authority checks. If the implementation cannot prove uniqueness, it must fail
closed and expose an operator-visible recovery state.

## Recovery Semantics

Safe resumability is required before execution implementation.

Operator-visible failure states must include:

- planned but not started;
- child Run allocation failed;
- child Run execution failed;
- partial children terminal, Run Set not written;
- Run Set artifact written, discovery index missing;
- discovery pointer exists but private lookup missing or unavailable;
- conflicting idempotency record detected;
- reconciliation required.

Orphan child Runs are allowed only as visible recovery artifacts. They are not
Run Set reconstruction authority. A recovery tool may link an orphan child
Run to a still-open parent idempotency record if and only if the child
idempotency key matches the deterministic child plan key.

Orphan Run Set artifacts are authoritative artifacts whose discovery pointer
was not appended. Recovery may append a missing pointer to the discovery
index. Recovery must not mutate the stored Run Set artifact.

Orphan discovery records are pointers without usable authority. They must fail
closed during lookup/audit and must not synthesize Results rows or reconstruct
Run Sets from child Runs.

Reconciliation/recovery tooling is required before production execution. It
may append missing pointers or mark recovery state. It must not repair stored
Run Set artifacts in place, mutate Results rows, or infer authority from
directory scanning.

## Authority Boundaries

Non-negotiable authority rules:

- Run Set artifact is authority.
- Child Runs are execution evidence, not reconstruction authority for Run Set
  artifacts.
- Discovery index is discoverability only.
- Discovery index is not Results authority.
- Replay remains artifact-only.
- Run Diff remains artifact-only.
- Audit rendering must use artifact authority only.
- No Replay recomputation.
- No Run Diff recomputation.
- No provider/runtime calls during Replay, Run Diff, Audit, get, list, or
  lookup rendering.
- No current Universe authority in read paths.
- No current Binding authority in read paths.
- No workbook/grid authority.
- No mutable artifact repair.
- No directory scanning authority.
- No pod/provider imports into core Sweep orchestration.
- No child reconstruction as authority.

Read paths may dereference pointers to fetch authoritative artifacts. They
must not execute providers, rebuild children, recompute Runs, scan
directories for truth, or consult mutable workbook/grid state.

## Hosted And Orchestration Boundaries

Local core owns:

- deterministic Sweep planning;
- typed child assembly contract;
- child plan key generation;
- idempotency key derivation rules;
- Run Set artifact schema and validation;
- append-only artifact authority;
- pointer-only discovery semantics;
- artifact-only Replay, Audit, and Run Diff read contracts.

Future hosted orchestration may own:

- job queues;
- worker scheduling;
- leases;
- heartbeats;
- operational retries;
- concurrency limits;
- observability;
- operator recovery workflow;
- infrastructure-specific durability.

Worker/job boundaries:

- A worker may execute one child Run or one governed orchestration step.
- A worker must receive immutable inputs, not mutable workbook/grid state.
- A worker must write through governed append-only Run/Run Set APIs.
- A worker must not import pod/provider runtime modules into core Sweep
  orchestration.
- A worker must not mutate existing artifacts to repair failures.

Operational details may vary outside core only when they do not alter
deterministic plan identity, child ordering, idempotency keys, artifact
content, Results row types, or read-path authority.

## Recommended Implementation Sequence

Phase 44b should remain design-only unless the retry/idempotency choices are
fully locked. Recommended scope:

- finalize parent Sweep idempotency key;
- finalize child idempotency key;
- choose child run_id generation mechanism;
- define duplicate-prevention storage contract;
- define terminal child state enum and partial-failure policy names.

Phase 44c can implement narrow data models and tests only:

- idempotency key model;
- child plan key model;
- child terminal state model;
- Run Set execution policy model;
- validation tests for deterministic ordering and duplicate rejection.

Phase 44d can implement dry-run orchestration planning:

- no child execution;
- no workers;
- no provider/runtime calls;
- no Run Set writes unless using explicit dry-run artifacts outside authority.

Phase 44e can implement append-only child allocation behind idempotency:

- no parallel workers yet;
- no retries beyond safe idempotent re-entry;
- no Replay or Run Diff changes.

Phase 44f can implement governed Run Set artifact creation after terminal
child Runs:

- artifact authority only;
- pointer append only after artifact write;
- no mutable repair.

Must not be implemented before retry/idempotency semantics are locked:

- real child execution orchestration;
- background workers;
- hosted queue integration;
- automatic retry;
- partial-failure Run Set creation;
- recovery tooling that appends missing pointers;
- any route/UI claiming execution status as authoritative.

## Design-Only Classifications

Remain design-only now:

- retry implementation;
- worker implementation;
- hosted orchestration;
- partial-failure policy execution;
- recovery tooling;
- reconciliation tooling;
- routes/UI;
- Replay/Run Diff changes.

Safe to implement next only after Phase 44b locks semantics:

- typed idempotency models;
- typed child plan key models;
- terminal child state enum;
- deterministic validation tests;
- duplicate-prevention contract tests.

Forbidden before later phases:

- provider/runtime execution from Sweep core;
- pod/provider imports into core orchestration;
- directory scanning authority;
- child reconstruction;
- mutable artifact repair;
- Replay recomputation;
- Run Diff recomputation;
- read-path provider calls.

## HOLD / WARNING / NOTE Table

| Level | Finding | Status |
| --- | --- | --- |
| WARNING | Child run_id generation mechanism is not yet chosen. | Must be locked in Phase 44b before execution implementation. |
| WARNING | Retry attempt semantics for failed child Runs are not yet chosen. | Must be locked before retry or worker implementation. |
| WARNING | Partial-failure Run Set policy is allowed only as an explicit future policy. | Must not be implemented until policy name/version and artifact representation are pinned. |
| WARNING | Recovery tooling is required before production execution. | Recovery may append missing pointers or mark state, never mutate artifacts. |
| NOTE | Run Set artifact remains authority. | Discovery, child Runs, and directories are not reconstruction authority. |
| NOTE | Replay and Run Diff remain artifact-only. | No recomputation or provider/runtime calls are allowed in read paths. |

## Final Verdict

PASS WITH WARNINGS.

The design preserves append-only Run Set artifact authority, pointer-only
discovery, typed Results rows, artifact-only Replay/Run Diff, and no child
reconstruction. Remaining warnings are implementation prerequisites for
Phase 44b and later, not permission to start execution.
