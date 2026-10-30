# Mission Specification: Chain gate classifies subscript assignment and name-keyed dict comprehensions correctly

**Mission Branch**: `kitty/mission-chain-gate-subscript-name-pairing-01M66YGY`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue #6732 (follow-up from #6418, pre-merge squad, architecture lens, MINOR).

## Context

`tests/architectural/test_org_pack_chain_single_authority.py` is the class gate that
stops charter callers assembling the ordered org-pack ROOT chain by hand instead of
calling `charter.activation.layer_roots.resolve_pack_chain`. Its Rule 2 is deliberately
ROOT-and-names semantics: collecting BARE `pack.effective_root(...)` Paths is a
violation; collecting `pack.name` too (a name-paired pair) is not, because the Path-only
authority cannot provide names.

The classifier only recognises hand assembly through `append` / `add` / `extend` calls
inside a `for` over `<registry>.packs`, and through list/set/generator/dict
comprehensions over the same. Two real idioms land on the wrong side of that test:

- **False negative.** `for i, p in enumerate(reg.packs): roots[i] = p.effective_root(r)`
  assembles a roots-only chain by hand through subscript assignment, and the gate passes
  it. The iteration is also wrapped in `enumerate(...)`, which the current
  `_is_packs_iter` check does not see through.
- **False positive.** `{p.name: p.effective_root(r) for p in reg.packs}` is name-paired
  (the key carries `pack.name`), which the gate's own docstring allows, yet the gate
  flags it and #6418 had to rewrite a `for` loop to get past it.

Both misclassifications were reproduced on `main@512567ee`: the subscript loop yields no
hit, the name-keyed dict comprehension yields a hit. Each idiom therefore gets planted
fixtures on both sides — a violation and a paired non-violation — so that a fix in one
direction cannot silently regress the other.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subscript assembly is caught (Priority: P1)

A maintainer writes a roots-only chain by hand with
`for i, p in enumerate(reg.packs): roots[i] = p.effective_root(r)`. The class gate reds
the PR and names the line, so the caller is fixed to call `resolve_pack_chain`.

**Why this priority**: this is the defect the issue reports as a false negative — the gate
lets a real off-authority chain through, which is the failure mode the gate exists for.

**Independent Test**: plant the subscript fixture and assert the scanner reports a
`registry.packs iteration assembling roots` hit at the assignment line.

**Acceptance Scenarios**:

1. **Given** a `for ... in enumerate(<registry>.packs)` loop, **When** its body assigns
   `<x>[<key>] = p.effective_root(...)` where `<key>` is not a `*.name` attribute,
   **Then** the scanner reports the loop as a `registry.packs iteration assembling roots`
   hit.
2. **Given** the same loop shape whose body assigns
   `<x>[p.name] = p.effective_root(...)`, **When** the scanner runs, **Then** it reports
   no hit, because the subscript key makes the collection name-paired.

---

### User Story 2 - Name-keyed dict comprehensions are not flagged (Priority: P1)

A maintainer writes `{p.name: p.effective_root(r) for p in reg.packs}` — a name-paired
reader the gate's docstring explicitly permits — and the gate stays green.

**Why this priority**: this is the reported false positive; it forces callers to reshape
legitimate code to satisfy the gate, which is the failure mode that erodes trust in it.

**Independent Test**: plant the name-keyed dict comprehension and assert the scanner
returns no hits; plant the root-keyed sibling and assert it still reports a hit.

**Acceptance Scenarios**:

1. **Given** a `DictComp` over `<registry>.packs` whose key is `<x>.name` and whose value
   is a bare `effective_root(...)` call, **When** the scanner runs, **Then** no hit is
   reported.
2. **Given** a `DictComp` over `<registry>.packs` whose key is a bare
   `effective_root(...)` call and whose value is something else (for example
   `{p.effective_root(r): p.name ...}`), **When** the scanner runs, **Then** the hit is
   still reported, so the name-pairing exemption cannot swallow root-keyed assembly.

---

### User Story 3 - The gate stays non-vacuous (Priority: P2)

A maintainer changes the classifier and a paired fixture reds, so the change cannot pass
by widening the exemption until nothing is reported.

**Why this priority**: the gate is only worth its CI time if each rule still has a
planted violation and a planted non-violation (charter Standing Order #5).

**Independent Test**: run the gate file; it prints the scanned-file floor, one planted
violation per rule, one planted non-violation per rule, and the owner-bypass control.

**Acceptance Scenarios**:

1. **Given** the gate module, **When** the full file runs, **Then** every planted
   violation fixture reports its expected kind and every planted non-violation fixture
   reports nothing.
2. **Given** a mutation that reverts one half of the fix, **When** the gate file runs,
   **Then** at least one fixture reds — the tests for the two idioms fail independently.

### Edge Cases

- A loop over `enumerate(<registry>.packs)` whose body collects `p.name` **and**
  `p.effective_root(r)` through separate collectors stays a non-violation (existing
  `paired-loop` fixture).
- A comprehension over `<registry>.packs` with no `DictComp` key, or a `DictComp` whose
  key is a `*.name`, is name-paired and exempt.
- A loop that reads `p.effective_root(r)` without collecting it stays a non-violation.
- Subscript assignment whose key is a bare name or literal (`roots[i]`, `roots[0]`) is a
  collector; the key is the only thing that makes it name-paired.
- The scan scope, the empty allowlist and the owner exemption are unchanged: this mission
  narrows the classifier's blind spots, it does not widen or empty any allowlist.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Subscript assignment counts as a collector | As a maintainer, I want `x[k] = p.effective_root(r)` inside a `<registry>.packs` loop treated as root collection, so that hand assembly through a preallocated list is caught. | High | Open | [build] | no — the paired name-keyed fixture on the same shape must stay clean |
| FR-002 | Subscript key decides name pairing | As a maintainer, I want `x[p.name] = p.effective_root(r)` treated as name-paired, so that a keyed-by-name collector is not flagged. | High | Open | [build] | no — the unkeyed sibling on the same fixture must still report |
| FR-003 | Iteration through `enumerate(...)` is seen | As a maintainer, I want a `<registry>.packs` iteration wrapped in `enumerate(...)` recognised as a packs iteration, so that adding an index does not hide the loop. | High | Open | [build] | no — the detection is asserted by the same planted loop fixture |
| FR-004 | Name-keyed `DictComp` is exempt | As a maintainer, I want `{p.name: p.effective_root(r) for p in reg.packs}` not flagged, so that permitted name-paired code passes unchanged. | High | Open | [build] | no — a root-keyed sibling comprehension must still report |
| FR-005 | Each idiom pinned red-first on both sides | As a reviewer, I want a planted violation and a planted non-violation per new rule, so that the fix cannot be reverted or over-widened without a red. | High | Open | [build] | no — each new fixture fails on the pre-fix classifier |
| FR-006 | Gate docstring states the new semantics | As a maintainer, I want the module docstring to name subscript collection and the name-keyed dict comprehension, so that the gate's stated rule matches its behaviour. | Medium | Open | [build] | no — the docstring is reviewed against the fixtures |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate stays non-vacuous | The planted-violation and non-violation fixtures all run in the one gate module and the real census still scans at least the existing floor (1200 files) with an empty allowlist. | Reliability | High | Open |
| NFR-002 | Real tree stays green | The live census over `src/` reports zero hits before and after the change; the change adds no allowlist entry and no scan exclusion. | Correctness | High | Open |
| NFR-003 | Gate file stays fast | The gate module's targeted run stays within 2x its pre-change wall-clock on the same machine (measured before and after), with no added tree walk and no extra parse pass per file. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One gate module | The change is confined to `tests/architectural/test_org_pack_chain_single_authority.py`; no production module changes. | Technical | High | Open |
| C-002 | Rule 2 semantics unchanged | Only the ROOTs-only rule is refined; the primitive-call rule, the scope, the offering-tier exclusion and the empty allowlist are untouched. | Technical | High | Open |
| C-003 | No new authority | The gate keeps `resolve_pack_chain` as the single chain authority; the fix must not introduce a second way to satisfy the gate. | Technical | High | Open |

### Key Entities

- **Collector**: a statement inside a `<registry>.packs` loop that accumulates a bare
  `effective_root(...)` value — today an `append`/`add`/`extend` call, now also an
  `ast.Assign` whose target is an `ast.Subscript`.
- **Name pairing**: the presence of a `*.name` attribute in the collected value or in the
  subscript key, which makes the collection legitimate for a caller that needs names.
- **Planted fixture**: a source string scanned by `_scan_source` to assert one hit kind or
  no hits, kept beside the rule it guards.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The gate module reports the subscript-assembly fixture as a hit and the name-keyed subscript fixture as clean; both assertions fail on `main@512567ee`. — [build] · no-op passable: no
- **SC-002**: The name-keyed `DictComp` fixture reports no hit and its root-keyed sibling still reports one; the first assertion fails on `main@512567ee`, the second must keep passing. — [build] · no-op passable: no
- **SC-003**: `uv run pytest tests/architectural/test_org_pack_chain_single_authority.py` passes with the empty-allowlist assertion, the scanned-file floor and the owner-bypass control unchanged. — [ratchet] · no-op passable: no
- **SC-004**: Reverting either half of the classifier change (subscript handling, `DictComp` key handling) reds at least one fixture, proving the two halves are tested independently. — [build] · no-op passable: no
