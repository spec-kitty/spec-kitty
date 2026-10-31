# Implementation Plan: untrusted audit relocation pairing

**Mission**: untrusted-audit-relocation-pairing-01M66F6X
**Issue**: spec-kitty/spec-kitty#6642
**Branch contract**: planning lands on `issue-6642-untrusted-audit-relocation-pairing` (topic branch off `main@512567ee`); merge target for the PR is `main` on the canonical remote. The operator merges; this mission never merges or pushes `main`.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib `ast` only on the audit path)
**Primary Dependencies**: none new — stdlib (`ast`, `argparse`, `pathlib`, `dataclasses`); pytest for tests
**Storage**: `tests/architectural/untrusted_path_audit/inventory.md` (single hand-curated markdown table)
**Testing**: pytest architectural suite; the audit's existing "acceptance theater" pattern — tests import `audit.py`'s public seams (`check_undercount`, `check_overcount`, …) and drive them with synthetic key maps, plus `main()`/`--fix` end-to-end on a temp copy of the inventory
**Target Platform**: developer workstation / CI (Linux); the audit runs as a pytest architectural test and as `python -m tests.architectural.untrusted_path_audit.audit`
**Project Type**: single (monorepo: `src/specify_cli` + `tests/`)
**Performance Goals**: pairing pass is O(n) over the unmatched key sets; audit total runtime within 2× the pre-mission runtime on this tree
**Constraints**: `--fix` must never write unless a full in-memory re-audit of the would-be file is green (fail-closed); existing seam signatures unchanged (C-003)
**Scale/Scope**: 1 audit module (~600 lines), 1 inventory file, 1 test module (+ new test cases); no `src/` changes

## Charter Check

- *ATDD-First Discipline (C-011) / DIRECTIVE_034*: red-first — the failing relocation-pairing test lands before the fix (C-004).
- *smallest-viable-diff*: no format restructuring (proposal 2 rejected in research.md D-2); pairing is a new pure seam, `check_undercount`/`check_overcount` untouched.
- *NO_FULL_HEAVY_SUITES_IN_MISSION*: run only the architectural containment module + focused new tests, not the full suite.
- *Identifier Safety / terminology*: reuse the audit's existing vocabulary ("ghost", "undercount", "overcount", "composite row identity"); new term "relocation pair" defined in spec.md Key Entities.
- No charter violations to justify.

## Project Structure

### Documentation (this mission)

```
kitty-specs/untrusted-audit-relocation-pairing-01M66F6X/
├── plan.md              # this file
├── research.md          # grounding + decisions (D-1..D-5)
├── reasons-canvas.md    # SPDD canvas
├── decisions/           # resolved specify Decision Moments
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
tests/architectural/untrusted_path_audit/
├── audit.py             # pairing seam + --fix (this mission's core change)
├── inventory.md         # locator re-pins via --fix + rationale chain trim
└── RULESET.md           # freshen-path docs update

tests/architectural/
└── test_untrusted_path_containment.py   # new test cases (existing ones unchanged)

docs/changelog/CHANGELOG.md              # [Unreleased] entry
```

**Structure Decision**: single-project layout; all changes live under `tests/architectural/` (the audit is test infrastructure — no `src/` surface is touched).

## Implementation Concern Map

### IC-01 — Relocation pairing seam

- **Purpose**: Recognise a pure move — pair one ghost key with one missing key sharing `(token, untrusted source)` uniquely — and report a single "moved" finding instead of a ghost + undercount pair.
- **Relevant requirements**: FR-001, FR-004, FR-005, FR-006
- **Affected surfaces**: `tests/architectural/untrusted_path_audit/audit.py` (new pure seam + `main` wiring); `tests/architectural/test_untrusted_path_containment.py` (new tests)
- **Sequencing/depends-on**: none
- **Risks**: pairing the wrong rows when a `(token, source)` group is non-unique — mitigated by the uniqueness condition (exactly one ghost AND exactly one missing in the group, else both guards stay red); truncated-token collisions — mitigated by uniqueness + the `--fix` in-memory re-audit.

### IC-02 — `--fix` mode (fail-closed locator re-pin)

- **Purpose**: Rewrite only the paired rows' `file:line` and `qualname` cells in `inventory.md`, after verifying the would-be file passes every audit check in memory.
- **Relevant requirements**: FR-002, FR-003
- **Affected surfaces**: `tests/architectural/untrusted_path_audit/audit.py` (arg parsing, row rewriting); `tests/architectural/untrusted_path_containment.py` (end-to-end `--fix` tests on a temp inventory copy)
- **Sequencing/depends-on**: IC-01 (fix consumes the pairing output)
- **Risks**: overwriting human columns (#3011 precedent) — mitigated by cell-indexed rewrite of columns 0 and 1 only, plus tests asserting the disposition/rationale cells are byte-identical; writing a non-green file — mitigated by the mandatory in-memory re-audit gate before any write.

### IC-03 — Rationale chain trim + docs

- **Purpose**: Drop the hand-kept "line shifted N→M by mission …" chains from inventory rationale cells (git history already records them) and document the new freshen path.
- **Relevant requirements**: FR-007
- **Affected surfaces**: `tests/architectural/untrusted_path_audit/inventory.md` (rationale prose only), `RULESET.md`, `audit.py` module docstring, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (the trim is only honest once the locator is machine-maintainable)
- **Risks**: over-trimming substantive provenance — mitigation: only mechanical line-number-shift history is removed; every disposition justification and identity note stays; the audit's green run proves the identity columns are untouched.

## Approach (SPDD)

**Chosen**: issue proposal 1 — automatic pure-move pairing on `(token, untrusted source)` with a unique-pairing condition, plus a fail-closed `--fix` that re-pins only the locator columns; proposal 3 (rationale chain trim) rides along. Pair-key hardening from the spec+plan review round (all findings accepted): the source comparand is the exact canonical machine string (hand-prose or empty source cells never pair, with a distinct diagnostic note); `…`-truncated tokens never auto-pair (a removal-plus-new-sink collision on a shared 60-char prefix is indistinguishable from a move); and the path-level tripwires (`KNOWN_CANDIDATE_FILES`, FR-009) are a documented scope boundary — relocating the last sink out of a known-candidate module still needs the hand tripwire edit and stays red.

**Rejected alternatives**:
- *Proposal 2 (split machine/human columns into a key-stable file + generated locator table)*: rewrites the audit's contract with every downstream consumer (the containment test module, RULESET's reproducibility promise, the hand-curation workflow) for no additional acceptance value over pairing; the single-file table stays the disposition source of truth (research.md D-2).
- *Auto-green on pairing (no `--fix`)*: the issue's own acceptance allows green-after-one-fix; auto-green would let a relocated sink pass review without any artifact change, weakening the ratchet's "the inventory is the reviewed record" property.
- *Pairing on token only*: the current inventory has live rows sharing a token across different untrusted sources; including the source keeps the pair key honest about *which taint* moved.

## Testing Strategy

Red-first (C-004): a test that simulates a pure relocation and asserts the single moved finding fails on current `main` (it asserts the new behaviour; before the fix it fails because two errors fire instead of one paired finding).

New test cases (all through the real seams, no reimplementation):
1. Pure relocation → exactly one relocation finding naming both locators; no ghost/undercount error for that sink (FR-001).
2. `--fix` on a temp inventory copy → only `file:line` + `qualname` cells rewritten; token/source/sink-op/disposition/rationale byte-identical; plain audit green afterwards (FR-002, SC-002).
3. `--fix` with an unrelated error present → no write, errors reported (FR-003).
4. Pure removal → overcount fires (FR-004). 5. New sink → undercount fires (FR-005). 6. Token-changed move → both fire, no pairing (FR-006). 7. Ambiguous 2-ghost/1-missing and 1-ghost/2-missing → both fire (FR-006).
8. Green-tree no-op: `main()` output and exit code unchanged (NFR-001); existing containment tests pass unchanged (SC-005).
9. Two ghosts sharing `(token, source)` with zero missing → no pairing, both ghost errors (uniqueness).
10. Ghost + missing sharing token but *different* source cells (hand-prose / empty inventory source) → no pairing, both errors, plus the distinct non-pairing diagnostic note.
11. Truncated (`…`) token → never auto-paired, even when the pairing would otherwise be unique.
12. Multiple simultaneous distinct relocations → each reported and fixed independently; `--fix` with nothing to fix and `--fix` run twice → no write, idempotent.
13. No rationale cell matches `\d+\s*→\s*\d+` after the trim (SC-004).

Pairing seam signature (NFR-003): a new pure function in `audit.py`, e.g.
`pair_relocations(discovered_rows, inventory_rows) -> (pairs, notes)` where
`pairs` is a list of `(ghost_key, missing_key)` tuples with their locators and
`notes` are diagnostic strings for token-matches that did not pair (source
mismatch, truncated token, ambiguity); `main` consumes it after
`check_undercount`/`check_overcount` and before reporting; `--fix` consumes the
same output. `check_undercount`/`check_overcount` keep their signatures and
filter out paired keys only inside `main`'s reporting (the seams themselves
stay pure and unchanged).
