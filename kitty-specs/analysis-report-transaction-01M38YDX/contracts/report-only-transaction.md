# Report-only transaction contract

The implemented CLI contract is `agent mission record-analysis --report-only`.
Without that option the existing broad dirty-tree refusal remains authoritative.

## Inputs and authority

The canonical placement seam selects the PRIMARY report partition and declared
planning target. A conservative material manifest covers mission definitions,
configuration, declared governance and selected templates. Dirty material inputs,
external mutable authority, unsupported index states and unsafe branch states
refuse qualification. Unrelated partial staging is supported.

## Observable outcomes

Only the analysis report may enter the commit. Unrelated index entries and flags,
working bytes and untracked bytes must remain unchanged. The implementation uses
the canonical path-scoped commit layer; it never stashes operator work.

Outcomes distinguish `committed`, `unchanged`, `failed_before_write`,
`written_uncommitted` and `committed_unqualified`. A qualified unchanged report
preserves its exact bytes and HEAD. Failure never implies rollback of concurrent
operator changes.

## Qualification and recovery

A report transaction token refers to a local pending or qualified receipt. The
freshness reader requires qualified receipt state, matching report and material
digests, and reachable verified commit evidence. Missing or pending receipts fail
closed. Post-commit verification failure retains evidence for recovery and never
qualifies the report. Checks detect cooperative-writer races; they are not an
operating-system-wide exclusion lock.

The writer and every lifecycle freshness consumer must use the qualified reader.
The older PR5009-only runtime predates receipt semantics and is insufficient.
The separate integration qualification combines both reviewed source lines before
use by Aletheia; it is neither an upstream release nor deployment evidence.

## Evidence

The owning recorder/Git/report qualification passed 203 tests with two skips.
The final CLI suite passed 26 tests, including real-Git preservation, default
refusal, material changes, hook failures, HEAD/index races, missing receipts and
semantic no-op controls. Input-authority tests passed 11 cases; diff coverage was
92 percent. Four documented fast-suite baseline failures remain distinct from
these passing scoped checks. Independent review cleared source through
`f5c35e71ad4b46fa4170040189c92b91ac585193`.
