# Semantic Enums Contract Report

## Files Changed

- /Users/jedgore/dev/asof123/PRODUCT_CONTRACT.md
  - Section 3 (Required Ontology): the ExecutionState, PriceBasis,
    PublicationState, and CanonicalState entries previously described
    their values inline as "for example" prose. They now point to the
    normative sections below. The prior lowercase sketch
    ("none, intended, working, partially_filled, filled, canceled,
    rejected") is removed; the normative names in section 7 are the
    only authoritative form.
  - Five new normative sections inserted after section 6:
    section 7 (ExecutionState), section 8 (PriceBasis),
    section 9 (PublicationState), section 10 (CanonicalState),
    section 11 (Market Identity Convention).
  - Existing sections renumbered to make room: UTC and Timezone Rule
    is now section 12 (was 7), Fail-Closed Rule is now section 13
    (was 8), API Direction is now section 14 (was 9), Open-Source
    Boundary is now section 15 (was 10), README Seed Language is now
    section 16 (was 11), Coding Discipline is now section 17 (was 12).
  - Internal cross-references updated: the API Direction section now
    points at "section 12 and the fail-closed rule in section 13"; the
    Open-Source Boundary section now refers to "endpoints in section
    14".

No other files were changed. README.md already used the pinned uppercase
enum values in its JSON example and Python example, and its only
contract section reference is to section 3 (Required Ontology), which
did not shift. docs/unified_diff.md does not exist in this repository
and was not created.

## Exact Enum Groups Pinned

ExecutionState (section 7):
- NOT_EXECUTED
- INTENDED
- WORKING
- PARTIALLY_FILLED
- FILLED
- CANCELED
- REJECTED
- UNKNOWN

PriceBasis (section 8):
- PRIOR_CLOSE
- LAST_TRADE
- INDICATIVE
- OFFICIAL_CLOSE
- SETTLEMENT
- MODEL
- UNKNOWN

PublicationState (section 9):
- NOT_PUBLISHED
- PRE_PUBLISHED
- PUBLISHED
- EMBARGOED
- WITHDRAWN
- FAILED
- UNKNOWN

CanonicalState (section 10):
- PROVISIONAL
- CANONICAL
- SUPERSEDED
- NOT_CANONICAL
- NOT_AVAILABLE
- UNKNOWN

Each new section also pins its fail-safe default and adds short rules
that bind the enum to the fail-closed regime in section 13 and to the
perspective semantics in section 4. Specifically:

- ExecutionState: NOT_EXECUTED is the default when no execution context
  applies; UNKNOWN is reserved for retrieval failure; INTENDED and
  WORKING must never be reported under perspective EXECUTED or
  CANONICAL.
- PriceBasis: UNKNOWN is the default; MODEL must never be reported as
  OFFICIAL_CLOSE or SETTLEMENT; OFFICIAL_CLOSE and SETTLEMENT are
  reserved for venue-published canonical prices.
- PublicationState: NOT_PUBLISHED is the default; EMBARGOED must not be
  treated as PUBLISHED before the embargo lifts; WITHDRAWN must not be
  treated as historical; UNKNOWN forces fail-closed.
- CanonicalState: PROVISIONAL is the default when no canonical authority
  has asserted the answer; SUPERSEDED must not be treated as current; a
  call under perspective CANONICAL must resolve to CANONICAL or fail
  closed.

## Market Identity Decision

Section 11 (Market Identity Convention) pins the public market-identity
shape:

- Public requests and responses must identify markets using a MIC-style
  market code where available (for example XNYS for NYSE, XNAS for
  Nasdaq).
- Every market code must be paired with an explicit IANA timezone in a
  separate field (for example market_timezone).
- A MarketCalendar may also expose an internal calendar_id for
  resolver-internal use, but calendar_id must not replace market plus
  market_timezone in public API models.
- US equities examples use market = XNYS and market_timezone =
  America/New_York.
- No API response may expose a market_phase, business_date, or other
  market-relative field without also exposing the market and
  market_timezone that resolved it.
- If the requested market code has no recognized MarketCalendar, the
  resolver must fail closed per section 13. It must not silently fall
  back to a default market.

This matches the convention already used by README.md and by the JSON
example in section 16 (README Seed Language), and makes it normative
rather than illustrative.

## README Changes Made

None. README.md was audited against the newly pinned enumerations:

- "perspective": "LIVE" matches Perspective (section 4).
- "market_phase": "MARKET_OPEN" matches MarketPhase (section 5).
- "price_basis": "LAST_TRADE" and "PRIOR_CLOSE" match PriceBasis
  (section 8).
- "publication_state": "PUBLISHED" matches PublicationState (section 9).
- "canonical_state": "PROVISIONAL" matches CanonicalState (section 10).
- "freshness": "FRESH", "PRIOR_CLOSE", "NOT_PUBLISHED" match
  SourceFreshness (section 6).
- The Python example's `ctx.execution_state == "NOT_EXECUTED"` matches
  ExecutionState (section 7).
- README's only contract section reference is to section 3 (Required
  Ontology), which did not shift.

No edits to README.md were required.

## Validation Performed

1. grep for non-ASCII characters in PRODUCT_CONTRACT.md and README.md
   (`LC_ALL=C grep -nP '[^\x00-\x7F]' PRODUCT_CONTRACT.md README.md`).
   Result: no matches.

2. grep for stale lowercase ExecutionState-style values
   (`grep -nE '\b(none|intended|working|partially_filled|filled|canceled|rejected)\b'`).
   The previously offending line in PRODUCT_CONTRACT.md section 3 is
   gone. Remaining matches are ordinary English prose ("intended for
   replay", "working specification", "intended to sit above", "filled
   orders with intended orders", "still working, some have been
   canceled", "intended to be called in-process"). None of them appear
   as enum value claims, in quotes, or as bound enum bindings.

3. grep for stale lowercase PriceBasis-style prose
   (`grep -nE '\b(last trade|prior close|last_trade|prior_close)\b'`).
   The only remaining lowercase usages are descriptive prose
   ("at prior close", "Pre-open PM dashboard using prior close",
   "(for example last trade, prior close, ...)" in the section 1
   question list). None are enum value claims; the normative names are
   in section 8.

4. grep for stale lowercase PublicationState and CanonicalState
   prose (`grep -nE '\b(published|pre[- ]published|embargoed|withdrawn|provisional|canonical|superseded|not_canonical|not[- ]available)\b' PRODUCT_CONTRACT.md`).
   All remaining matches are ordinary English usages ("the canonical
   contract", "considered canonical", "venue-published canonical
   prices", "no canonical authority", etc.). No conflicting enum claims.

5. JSON enum values in PRODUCT_CONTRACT.md and README.md
   (`grep -nE '"perspective"|"market_phase"|"price_basis"|"publication_state"|"canonical_state"|"freshness"|execution_state'`).
   Every quoted value is a member of its pinned enumeration.

6. Section numbering monotonic check (`grep -n '^## '`).
   Result: sections 1 through 17, no gaps, no duplicates.

7. `git diff --check`. Result: no whitespace errors.

## Recommended Next Step

The ontology now has enough pinned vocabulary to safely begin the Python
model skeleton. The next pass is:

1. Create the `asof123/` Python package with empty modules that mirror
   the ontology in section 3 (for example `context.py`, `perspective.py`,
   `market_phase.py`, `source_status.py`, `execution_state.py`,
   `price_basis.py`, `publication_state.py`, `canonical_state.py`,
   `calendar.py`, `snapshot.py`).
2. Define each enumeration as a `str`-valued enum with exactly the
   names pinned in sections 4, 5, 6, 7, 8, 9, and 10. Each enum should
   expose its fail-safe default as a class attribute (for example
   `MarketPhase.DEFAULT = MarketPhase.CLOSED`, `ExecutionState.DEFAULT
   = ExecutionState.NOT_EXECUTED`, `PriceBasis.DEFAULT =
   PriceBasis.UNKNOWN`, `PublicationState.DEFAULT =
   PublicationState.NOT_PUBLISHED`, `CanonicalState.DEFAULT =
   CanonicalState.PROVISIONAL`).
3. Define the Pydantic (or dataclass) model for `TemporalContext`,
   `SourceStatus`, and `AsOfSnapshot` with strict UTC validation on
   all datetime fields and strict IANA-timezone validation on
   `market_timezone` per section 11 and section 12.
4. Define a typed market identifier wrapper that enforces the section
   11 rule that market codes always travel paired with a
   `market_timezone`, and that rejects responses exposing
   `market_phase` or `business_date` without that pair.

No FastAPI app, no CLI, no providers, and no resolver logic in the next
pass. The next pass should produce only types, enums, model validation,
and the tests that pin those.
