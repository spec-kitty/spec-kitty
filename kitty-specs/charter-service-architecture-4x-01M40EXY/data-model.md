# Documentation Model

## Canonical Decision

**Fields**: status, context, decision, stages, invariants, non-goals, deferred
choices, consequences, risks, evidence, related decisions.

**Validation**:

- exactly one ADR owns the charter redesign;
- the status is Proposed until implementation evidence exists;
- every deferred choice is visibly deferred;
- the Mission Status Read ADR is cited only as a sibling precedent.

## Transition Stage

| Stage | Read owner | Write owner | Exit evidence |
|---|---|---|---|
| Baseline | Python | Python | Existing behavior pinned |
| Shadow | Python primary; Java compared | Python | Read conformance corpus green |
| Java primary | Java; loud Python fallback | Python | Operational and semantic gates green |
| Java read-only final | Java | Python | Python production reads retired |
| Java write migration | Java | Operation-by-operation | Codec, mapping, and confined-mutation gates |

## Shared Contract

**Fields**: schema versions, artifact identities, relation vocabulary, merge
precedence, activation semantics, query semantics, diagnostic contract,
fixtures, expected outputs.

**Validation**:

- language-neutral;
- consumed by both Python and Java;
- every semantic rule has at least one positive and refusal fixture.

## C4 View

**Kinds**: context, container, component.

**Relationships**:

- every view links to the owning ADR;
- lower-level views refine higher-level elements;
- planned Java containers are visibly marked planned;
- shipped implementation mapping is unchanged.

## Roadmap Placement

| Slice | Milestone | Tracker anchor |
|---|---|---|
| Java read service behind charter API seam | 4.x Work | #645 |
| Later Java write migration | CLI 4.x stable | #2519 |
| 4.0.0 GA | excluded | milestone 11 |

## YAML Write Evidence

| Gate | Evidence | Prevents |
|---|---|---|
| Codec identity | Unchanged source bytes after lossless load/emit | Formatting and comment drift |
| Mapping identity | Domain projection applied back with no change | Mapping loss |
| Confined mutation | Deliberate field change yields only expected diff | Fakeable identity that ignores domain |
