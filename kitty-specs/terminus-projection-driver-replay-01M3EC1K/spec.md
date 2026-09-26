# Mission Specification: Terminus Projection Driver-Replay Attribution

**Mission Branch**: `fix/terminus-projection-driver-replay`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Fix #5038 DEFAULT-squash false-REFUSE on the coord-bookkeeping projection proof via driver-replay attribution, and document/narrow the #5021 residual-2 honest xfail.

## Context & Root Cause (Phase R findings)

During a DEFAULT-squash `spec-kitty merge`, when a coord-partition bookkeeping file (e.g.
`kitty-specs/<slug>/traces/WP01.md`) was edited on **both** the merge target and an approved
lane from a shared baseline, the git squash resolves that path through the **deterministic,
lossless** `spec-kitty-traces` union merge driver. The resulting target blob therefore equals
neither the checkpoint blob nor the coordination-branch blob. The squash projection proof
(`_assert_squash_projected_content_landed` → `projected_content_matches_target`) demands
**byte-equality** `coord_bytes == target_bytes` for every post-checkpoint coord-partition path
and REFUSEs — even though the coord content losslessly landed inside the union. This is a
false-REFUSE (#5038): any real mission that edits a tracer/verdict/notes file concurrently on the
target and a lane during merge trips it.

Phase R (3 profile-loaded opus lenses, grounded in real driver/CLI runs) established:
- The originally-filed "clean single-lane" #5038 trigger is unreproducible; the only reproducible
  trigger is the 3-way content divergence above.
- Running the real `merge-driver-traces` on both the additive (P1) and same-line (P2) triples
  produces a lossless union preserving every line of both sides. P1 and P2 are byte-indistinguishable
  to the projection gate — no signal over `(checkpoint, target, coord)` separates them, so **no
  discriminator can flip the P1 false-REFUSE while keeping the codified P2 byte-equality REFUSE**.
- The genuinely sound fix is **driver-replay attribution**: prove the landed blob equals the
  deterministic merge driver's own output from `(checkpoint-blob = %O, pre-merge-target-blob = %A,
  coord-blob = %B)`. This PASSes a legitimate driver union (both P1 and P2) while still REFUSing a
  landed blob that is NOT the driver's output (genuine non-landing / tampering). Adopting it
  requires re-grounding `test_5038_p2` onto a genuinely-lossy scenario — operator-ruled (Option B,
  decision `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`): P2's byte-equality premise is disproven for
  union-driver paths.
- The sibling residual **#5021 residual-2** (attribution axis, product path `src/shared.py`, stock-git
  genuine conflict manually resolved to a third blob) is **soundly unfixable** — stock
  `git merge-file`/`merge-tree` conflicts and the manual resolution is reconstructable by no
  deterministic function; any acceptance green-washes the #4945 data-loss class. It stays an honest
  strict-xfail with a narrowed reason and is split to its own tracked issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Legitimate concurrent bookkeeping edit merges without false-REFUSE (Priority: P1)

An operator (or the fleet merge agent) runs `spec-kitty merge` on a coord-topology mission whose
approved lane edited a coord-partition tracer file that the target branch also edited
independently from the same baseline. The deterministic union driver losslessly merges both edits
onto the target during the squash. The merge must COMPLETE, not refuse.

**Why this priority**: This is the shipped defect (#5038). Today the merge false-REFUSEs
("projected coordination bookkeeping content did not land on the target"), blocking a legitimate,
non-lossy merge and forcing a spurious `--resume` loop that cannot succeed.

**Independent Test**: `tests/terminus/test_repro_5038.py::test_5038_p1_clean_single_lane_squash_must_not_false_refuse`
drives the real `spec-kitty merge` CLI; it is RED (strict-xfail) on the base and GREEN after the fix.

**Acceptance Scenarios**:

1. **Given** an approved lane and the target both edited `traces/WP01.md` from a shared baseline
   with non-conflicting (additive) content, **When** `spec-kitty merge --yes` runs the DEFAULT
   squash, **Then** the merge exits 0 and the projection proof does not emit
   "projected coordination bookkeeping content did not land".
2. **Given** the union driver produced the landed target blob, **When** the projection proof runs,
   **Then** it attributes the landed blob to the driver's own replayed output and PASSes.

---

### User Story 2 - Genuine non-landing / tampering of coord content still REFUSEs (Priority: P1)

The fail-closed floor: if the content that lands on the target for a projected coord-partition path
is NOT what the deterministic merge driver would produce from the three inputs — i.e. coord content
was genuinely dropped, or the blob was tampered — the merge must still REFUSE.

**Why this priority**: Charter Standing Order #9 (never green-wash a fail-closed gate). The
precision fix must not weaken detection of real coord-content loss.

**Independent Test**: `tests/terminus/test_repro_5038.py::test_5038_p2_genuine_projection_failure_still_refuses`,
re-grounded onto a genuinely-lossy scenario (a landed blob that the driver replay does NOT
reproduce). It must REFUSE both before and after the fix.

**Acceptance Scenarios**:

1. **Given** a projected coord-partition path whose landed target blob is NOT the deterministic
   driver output for `(checkpoint, pre-merge-target, coord)` (real content loss/tampering),
   **When** the projection proof runs, **Then** the merge REFUSEs and names the projection-proof
   divergence.
2. **Given** a driver-replay probe cannot be evaluated (missing input blob, git probe error),
   **When** the projection proof runs, **Then** it REFUSEs fail-closed rather than passing on
   unevaluated content.

---

### User Story 3 - Product-content 3-way residual stays an honest, clearly-scoped xfail (Priority: P2)

The attribution-axis 3-way residual (#5021-r2) is documented as soundly unfixable and kept as a
strict-xfail with a narrowed reason that distinguishes it from the now-fixed driver-governed
projection case, and split to its own tracked issue.

**Why this priority**: Honest-red discipline — a residual we do not fix must be transparently
recorded, never green-washed, and never conflated with the fixed case.

**Independent Test**: `tests/merge/test_reconciliation.py::test_squash_three_way_merge_resolution_is_unattributable`
remains `xfail(strict=True)` with an updated reason; a new tracked issue references it.

**Acceptance Scenarios**:

1. **Given** two approved lanes edit the same product path resolved by stock git to a manual third
   blob, **When** the attribution axis runs, **Then** it still FAILs (unattributable) and the test
   stays a strict-xfail.
2. **Given** the narrowed xfail reason, **When** a future reader inspects it, **Then** it names the
   distinct root (stock-git conflict + manual resolution, not the deterministic union driver) and
   the tracked follow-up issue.

### Edge Cases

- A projected path that is NOT driver-governed (no `.gitattributes merge=` rule) and diverged on
  the target: the driver-replay probe has no registered driver to replay → the proof must fall back
  to fail-closed behavior (REFUSE), never silently PASS.
- The subset where the target did NOT diverge from checkpoint (`target == checkpoint`): the
  projection legitimately carried coord forward and `coord == target` already holds — this subset
  must continue to PASS exactly as today (no regression).
- Idempotent replay: the driver is deterministic; a re-run of the probe yields the same expected
  blob, so `--resume` re-evaluates identically.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Driver-replay attribution proof | As the merge executor, I want the squash projection proof to accept a landed coord-partition blob when it byte-equals the registered merge driver's own replayed output from `(checkpoint, pre-merge-target, coord)`, so a legitimate lossless union is not false-REFUSEd (#5038). | High | Open |
| FR-002 | Fail-closed on non-driver-output | As the merge executor, I want the projection proof to REFUSE when the landed blob is NOT the driver's replayed output, so genuine coord-content loss/tampering is still caught. | High | Open |
| FR-003 | Fail-closed on unevaluable probe | As the merge executor, I want the projection proof to REFUSE (never PASS) when the driver-replay probe cannot be evaluated (missing input blob, no registered driver for a diverged path, or a git/driver probe error). | High | Open |
| FR-004 | Preserve non-diverged PASS path | As the merge executor, I want paths where `target == checkpoint` (coord carried forward, `coord == target`) to keep PASSing exactly as today, so the fix introduces no regression on the common clean case. | High | Open |
| FR-005 | Flip P1 red→green via real CLI | As a maintainer, I want `test_5038_p1` (real `spec-kitty merge` CLI repro) to flip from strict-xfail to PASS by this real fix, per ATDD red-first. | High | Open |
| FR-006 | Re-ground the P2 floor | As a maintainer, I want `test_5038_p2` re-grounded onto a genuinely-lossy scenario (a landed blob the driver replay does not reproduce) so it still REFUSEs, proving the floor bites on real loss rather than on a lossless union. | High | Open |
| FR-007 | Narrow & split #5021-r2 | As a maintainer, I want `test_squash_three_way_merge_resolution_is_unattributable` kept strict-xfail with a narrowed reason distinguishing it from the fixed driver-governed case, and a dedicated tracked issue filed for the residual. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No data-loss floor regression | All 13 Phase-R-identified guardian tests (`test_repro_4945/4977/4981/5001/5018/5022`, the attribution-axis unit guards incl. `test_squash_fails_when_superseded_v1_blob_ships`) stay GREEN — 0 regressions. | Reliability | High | Open |
| NFR-002 | Bounded probe cost | The driver-replay probe runs O(number of post-checkpoint projected paths), each a bounded blob read + one driver invocation; no O(repo-history) scan. Merge wall-clock stays within existing budgets (<2s CLI target for typical projects). | Performance | Medium | Open |
| NFR-003 | Quality gates clean | New/changed code passes `ruff check`, `ruff format --check` (on non-excluded files), and `mypy --strict` with zero new issues and zero new suppressions; cyclomatic complexity ≤ 15 per function. | Maintainability | High | Open |
| NFR-004 | New branches tested | Every new helper/branch introduced by the fix has a focused direct test in the same commit (Sonar new-code gate). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never green-wash the floor | The fix must not make `test_5038_p2` or any genuine data-loss case PASS without a sound proof (charter Standing Order #9 / ADR 2026-07-17-1). Re-grounding P2 is authorized ONLY because its byte-equality premise is disproven for union-driver paths (operator ruling, `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ`), and only onto a genuinely-lossy scenario. | Regulatory | High | Open |
| C-002 | #5021-r2 stays honest xfail | The attribution-axis 3-way product-content case is out of code scope (soundly unfixable); it must not be un-stricted or forced green. | Technical | High | Open |
| C-003 | #4997 out of scope | The staged-deletion / `LOCAL_CHANGES` behind-HEAD window (`--strategy merge`, tracked on PR #5031) is a distinct class and must not be touched or conflated. | Technical | High | Open |
| C-004 | Respect format-exclude asymmetry | `executor.py`, `bookkeeping_projection.py`, and `git_probes.py` are `[tool.ruff.format].exclude` entries — do NOT reformat them (only surgical edits). `reconciliation.py` is normally format-gated. | Technical | High | Open |
| C-005 | Canonical CLI + coord hygiene | Use canonical spec-kitty CLI only; materialize the coord worktree via `CoordinationWorkspace.resolve` (never `doctor coordination --fix`); never `git add` status.json/status.events.jsonl into primary planning commits (TARGET_BRANCH_CONTENT_CONFLICT). | Technical | High | Open |

### Key Entities

- **Projection proof**: the squash content assertion (`_assert_squash_projected_content_landed` in
  `merge/executor.py`) + its byte-comparison helper (`projected_content_matches_target` in
  `merge/bookkeeping_projection.py`). The seam that false-REFUSEs today.
- **Merge driver**: a registered `spec-kitty merge-driver-*` command (e.g. `merge-driver-traces`)
  invoked by git with `%O %A %B` during the squash; deterministic and replayable in-process.
- **Driver-replay probe**: the new proof primitive that reconstructs the expected landed blob by
  replaying the registered driver on `(checkpoint, pre-merge-target, coord)` inputs.
- **Guardian tests**: the 13 data-loss regression repros/units that pin the fail-closed floor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_5038_p1_clean_single_lane_squash_must_not_false_refuse` flips from strict-xfail
  (RED) on the merge-base to PASS on the mission head, via the real `spec-kitty merge` CLI.
- **SC-002**: `test_5038_p2_genuine_projection_failure_still_refuses` (re-grounded) REFUSEs on both
  the merge-base and the mission head — the floor holds.
- **SC-003**: 100% of the 13 guardian data-loss tests stay GREEN (0 regressions) across the change.
- **SC-004**: `test_squash_three_way_merge_resolution_is_unattributable` remains a strict-xfail with
  a narrowed reason, and a dedicated follow-up issue for #5021-r2 exists and is linked.
- **SC-005**: The merge/terminus blast-radius suite (`tests/merge/ tests/terminus/ tests/coordination/`)
  is green modulo the documented honest xfails; ruff/format/mypy clean; the architectural battery and
  foreign-coverage guard pass (baseline recaptured to the measured value if a new real-CLI repro is added).
