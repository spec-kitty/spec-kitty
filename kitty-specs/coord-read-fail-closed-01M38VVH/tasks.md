# Tasks — Coord Reads Fail Closed

**Mission**: `coord-read-fail-closed-01M38VVH` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · closes #4959, #4966

Five work packages. WP01 is foundational (the seam raise); WP02 + WP04 depend on it; WP03 is independent (the MATERIALIZED-husk locus); WP05 is docs close-out. All ATDD red-first. No new dependencies.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: UNMATERIALIZED coord read returns empty-PRIMARY (should raise) | WP01 | |
| T002 | Add `CoordinationWorktreeUnmaterialized(StatusReadPathNotFound)` sibling in `surface_resolver.py` (additive; do NOT touch `_coord_branch_exists`) | WP01 | |
| T003 | `_classify_artifact_surface` raises it on `CoordState.UNMATERIALIZED` for coord kinds; DELETED/MATERIALIZED/EMPTY/NONE unchanged | WP01 | |
| T004 | Seam + typed-error regression (DELETED still raises; PRIMARY kinds never raise) | WP01 | |
| T005 | ADR `docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md` | WP01 | |
| T006 | Red-first: tracer-append clobbers a populated file from an unmaterialised checkout | WP02 | |
| T007 | Narrow `_read_current_coord_content` catch → propagate on unresolved/unmaterialised; refuse on undecodable byte | WP02 | |
| T008 | Regression: resolved-absent stays empty (first write); materialised present appends | WP02 | |
| T009 | Red-first: `decision open`/`accept` on a materialised husk → MISSION_NOT_FOUND / permanent block | WP03 | [P] |
| T010 | `_resolve_mission_id`/`_mission_dir` resolve `meta.json` via PRIMARY_METADATA; correct docstring | WP03 | [P] |
| T011 | Integration: decision + accept agree on the PRIMARY ledger (no split-brain); non-coord unchanged | WP03 | [P] |
| T012 | Blast-radius regression: sanctioned read-only degraders still degrade; already-safe catchers unchanged | WP04 | |
| T013 | Verify the named no-catch coord `STATUS_STATE` readers fail loud at a sane boundary; wrap any raw traceback at the CLI edge | WP04 | |
| T014 | Regression coverage for the fail-loud callers + non-coord no-new-raise | WP04 | |
| T015 | CHANGELOG entry (canonical `docs/changelog/CHANGELOG.md`) | WP05 | |
| T016 | Register ADR in `docs/adr/3.x/index.md` + regenerate page-inventory + docs-retrieval-index | WP05 | |
| T017 | #4959/#4966 close-out text (epic #5002 stays open for #4979); terminology + docs-freshness gates | WP05 | |

---

## WP01 — Seam raise contract + sibling exception + ADR (FOUNDATIONAL)

**Priority**: P1 · **Prompt**: [tasks/WP01-seam-raise-contract.md](./tasks/WP01-seam-raise-contract.md) · **Est.** ~430 lines
**Goal**: The placement read seam raises `CoordinationWorktreeUnmaterialized` on `CoordState.UNMATERIALIZED` for coord-partition kinds (was empty-PRIMARY); new sibling exception is additive in `surface_resolver.py`. ADR records the behavioral change.
**Independent test**: an UNMATERIALIZED coord read raises (red-first vs empty-PRIMARY); DELETED still raises `CoordinationBranchDeleted`; PRIMARY kinds never raise.
**Included subtasks**: T001–T005 · **Dependencies**: none
**Risks**: C-002 — only ADD the class to `surface_resolver.py`; do NOT modify `_coord_branch_exists`. Bounding to UNMATERIALIZED (not EMPTY/NONE) is deliberate.

## WP02 — Tracer-append fail-closed (#4959)

**Priority**: P1 · **Prompt**: [tasks/WP02-tracer-fail-closed.md](./tasks/WP02-tracer-fail-closed.md) · **Est.** ~300 lines
**Goal**: `tracer_writer._read_current_coord_content` propagates the seam raise (never `""`→clobber) and refuses on an undecodable byte; resolved-absent stays empty.
**Independent test**: tracer-append from an unmaterialised checkout leaves a populated `traces/<cat>.md` byte-intact (red-first).
**Included subtasks**: T006–T008 · **Dependencies**: WP01

## WP03 — Decision-ledger PRIMARY resolution (#4966)

**Priority**: P1 · **Prompt**: [tasks/WP03-decision-ledger-primary.md](./tasks/WP03-decision-ledger-primary.md) · **Est.** ~330 lines
**Goal**: `decisions/service.py` resolves `meta.json` via PRIMARY_METADATA (not the coord husk) so it agrees with `accept`'s PRIMARY ledger read; correct the wrong docstring.
**Independent test**: `decision open` on a materialised husk resolves (no MISSION_NOT_FOUND); `accept` proceeds (red-first).
**Included subtasks**: T009–T011 · **Dependencies**: none (MATERIALIZED-husk locus, independent of the seam raise)

## WP04 — Caller blast-radius verification

**Priority**: P2 · **Prompt**: [tasks/WP04-caller-blast-radius.md](./tasks/WP04-caller-blast-radius.md) · **Est.** ~380 lines
**Goal**: The no-catch coord `STATUS_STATE` readers newly propagate the seam raise; verify each fails loud at a sane boundary (wrap any raw traceback at the CLI edge), add regression, confirm sanctioned degraders + already-safe catchers unchanged (NFR-002).
**Independent test**: named readers fail loud sanely; sanctioned degraders still degrade; non-coord no new raise.
**Included subtasks**: T012–T014 · **Dependencies**: WP01

## WP05 — Docs & tracker close-out

**Priority**: P2 · **Prompt**: [tasks/WP05-docs-closeout.md](./tasks/WP05-docs-closeout.md) · **Est.** ~200 lines
**Goal**: Consumer-focused CHANGELOG; register the ADR in the index + inventories; #4959/#4966 close-out (epic #5002 stays open for #4979); terminology + docs-freshness gates.
**Included subtasks**: T015–T017 · **Dependencies**: WP01, WP02, WP03, WP04

---

**MVP**: WP01 + WP02 (the active destruction path #4959). WP03 (#4966) is independently landable. WP04 is the seam-raise safety net; WP05 is close-out.
