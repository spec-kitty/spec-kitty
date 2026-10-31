# Implementation Plan: One activation spelling at the effective-set seam

**Mission**: `effective-set-one-spelling-01M68ZYF`
**Issue**: #6435 (charter effective-set union mixes declared ids and activation stems)
**Branch**: `issue-6435-effective-set-one-spelling`

## Summary

The seam's union is already converged on stems (`a8dd1812a6`); this plan closes the
issue's remaining acceptance in two small, independent slices plus their proof:

1. **The live defect** — `ActiveCharterManager.activate` materialises an absent
   required-only key (`skill`) from the raw org `required_<kind>` declared ids
   (`PackContext.allow_for`), so the written list carries a declared id beside a
   stem. Route that floor through the identity authority the same function
   already consults (`org_required_stems` → `IdentityIndex.stored_spelling`), and
   let that one call's collision refusal replace the separate
   `_refuse_required_collisions` probe — one call, one authority, no extra scan.
2. **The assurance** — the union's spelling rule is written twice
   (`_resolve_one` and `_fallback_ids`); the fallback copy is unguarded by any
   test while `fallback_ids` is a writer input. Extract one helper both paths
   call, so the rule cannot drift, and pin it.

No stored-format contract changes (#6518/#6527 own that), no ambiguity-policy
change (#6433 owns that), no scanner reimplementation.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `ruamel.yaml`, `pydantic`, `typer` (existing; none added)
**Storage**: `.kittify/config.yaml` / `.kittify/charter/activation.yaml` activation lists (read-only in this change, except the materialisation under test)
**Testing**: pytest; targeted module suites plus the specific architectural gates for the touched packages
**Target Platform**: Linux/macOS CLI (`spec-kitty`), Python 3.11+
**Project Type**: single Python package (`src/charter`, `src/specify_cli`)
**Performance Goals**: no additional artifact scan or `IdentityIndex` build on the `activate` path (NFR-001)
**Constraints**: no new dependency; `src/charter` must not import `specify_cli` (C-001 layer ratchet)
**Scale/Scope**: 3 source files (2 touched for behaviour, 1 helper extraction), 2 test modules, 1 changelog line

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — both slices delete a second copy of a rule and
  route through the authority that already exists (`IdentityIndex`,
  `org_required_stems`). No new authority, no second scanner.
- **Locality of change (DIRECTIVE_024)** — the edits sit in the two functions the
  issue names; no neighbouring contract is renegotiated.
- **ATDD-first / red-first** — each slice lands a failing test through the
  production entry point (`charter activate` CLI; `resolve_effective_sets`) before
  the fix, then pins it.
- **Terminology** — "activation stem" (file name) vs "declared id" (`id:` field)
  are used as `docs/context/` defines them; no synonym is introduced.
- **Pre-existing failure reporting** — any red outside this diff is reported, not
  worked around.
- **Pass** — no charter rule blocks this plan.

## Project Structure

### Documentation (this mission)

```
kitty-specs/effective-set-one-spelling-01M68ZYF/
├── spec.md          # requirements (FR-001..FR-005, NFR-001..003, C-001..004)
├── plan.md          # this file
├── research.md      # discovery evidence (D1..D4)
├── tasks.md         # work packages
└── traces/          # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/charter/activation/
├── effective_set.py   # _resolve_one + _fallback_ids → one shared union helper
├── pack_manager.py    # _preservation_ids: required floor via org_required_stems
└── (unchanged)        identity_index.py, org_charter.py, pack_context.py

tests/
├── charter/activation/test_effective_set.py                       # mixed two-pack union, fallback
└── specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py   # CLI consumer
```

## Complexity Tracking

No complexity is added: the change removes a duplicated rule (item 1) and a
duplicated required-floor read (item 2). No new module, no new public API, no new
configuration key.

## Implementation Concern Map

### IC-01 — The required-only floor is materialised as declared ids

**Where**: `src/charter/activation/pack_manager.py`, `_preservation_ids`
(`when_absent != "all"` branch) and `_refuse_required_collisions`.

**Now**: the branch returns `sorted(PackContext.from_config(...).allow_for(kind))`,
i.e. the raw `required_<kind>` ids; the collision probe above it discards the
stems `org_required_stems` already computed.

**Change**: compute the floor once through `org_required_stems(repo_root,
kind.plural, [])` and return those stems; drop `_refuse_required_collisions` (its
only caller is this branch and the new call raises the same
`ActivationIdCollisionError`). Keep the warnings list untouched, so the
user-visible output does not grow.

**Proof**: `tests/specify_cli/cli/commands/charter/test_activate_required_key_stems_6435.py`
red on `main` (`activated_skills: [acme-skill-id, other-skill-file]`) → green
after; a second case pins the collision refusal on the same fixture family
(FR-005 positive control: the non-colliding required id *is* materialised).

**Risk**: a reader relying on declared ids in `activated_skills`. Mitigated: the
gate (`resolver._gated` → `identity.activation_id`) accepts either spelling, and
`stored_spelling` is the contract every other writer already follows.

### IC-02 — The union's spelling rule has two copies; the fallback copy is unguarded

**Where**: `src/charter/activation/effective_set.py`, `_resolve_one` and
`_fallback_ids`.

**Now**: both call `_as_stems(_service_keys(...))` in their own body; the
fallback copy is covered by no test (mutation-proven in `research.md`).

**Change**: one module-private helper (`_union_ids(scan_ids, service_ids, kind,
identity)` — or an equivalent single call site) that owns the merge and the
mapping; `_resolve_one` and `_fallback_ids` call it. Behaviour is identical: the
unknown-token rule (keep as given, so a service-only artifact cannot vanish) is
preserved and documented in one place.

**Proof**: `tests/charter/activation/test_effective_set.py` gains the mixed
two-pack cases; reverting the helper's mapping turns them red (half-by-half
mutation check for NFR/FR-003).

**Risk**: none to stored state; the resolved path's behaviour is unchanged.

### IC-03 — Coverage: every applicable kind, both pack orders, both spellings

**Where**: `tests/charter/activation/test_effective_set.py` (extend the existing
two-org-pack fixture), `tests/specify_cli/cli/commands/charter/`.

**Change**: an id≠stem artifact of each activatable kind that the union resolves
(tactic, styleguide, toolguide, paradigm, procedure, agent-profile,
mission-step-contract, glossary-pack, directive) appears once, by stem, in its
effective set — with the id≠stem artifact in the lower-precedence pack as well as
the higher one; `IdentityIndex.stored_spelling(kind, declared_id) == stem` for
each, so both spellings provably converge.

**Proof**: the same fixture drives the declared-id and the stem spelling.

### IC-04 — Close-out: changelog, docs, traces, PR

**Change**: one `[Unreleased] … Fixed` entry only if the behaviour is
user-visible (it is: an activation list that previously stored a declared id now
stores the stem), impact-first, with `(#6435)`; tracer files appended; PR body
from the template with the five sections.

**Proof**: `validate-pr-body.py`, `check_docs_freshness --ci`, the targeted test
modules, `ruff`, `mypy` on touched files.
