# Implementation Plan: Regression-slice test cleanup

**Branch**: `issue-5618-regression-slice-cleanup` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/regression-slice-cleanup-01M42WCF/spec.md`

## Summary

Apply the per-file verdict ledgers of issues #5618–#5621 and fix the root-only failure in
#5622, all inside `tests/`. The work splits cleanly by owning code domain, one concern per
issue, and every concern follows the same order: add any missing seam test first, plant a
break in product code to prove the covering guard, revert, then remove markers or trim the
slow file. The #5620 charter-scope reader unit test is the priority item because it is the
only fix in the slice with no working guard today.

## Technical Context

**Language/Version**: Python 3.11+ (repository `.venv`, `uv sync --frozen --all-extras`)
**Primary Dependencies**: pytest (markers from `pytest.ini`), pytest-xdist; no new dependencies
**Storage**: N/A (test files only)
**Testing**: targeted pytest runs on the named files; planted breaks applied in the lane
worktree's `src/` (pytest's `pythonpath = src` makes the worktree's `src/` win for in-process
tests; subprocess tests need `PYTHONPATH=<worktree>/src`); `make test-fast`; named
architectural gates `tests/architectural/test_marker_job_completeness.py` and
`tests/architectural/test_ci_collection_completeness.py`, `tests/architectural/test_fast_tier_marker_completeness.py`
**Target Platform**: Linux (CI runs non-root; the cloud container runs as root — #5622)
**Project Type**: single (CLI + library); this mission touches `tests/` only
**Performance Goals**: NFR-001 — summed per-PR runtime of touched files drops by ≥50% of the
ledger estimates; NFR-002 — each new seam test < 1 s
**Constraints**: C-001 test-only; C-002 no heavy sweeps; C-003 no `p0_repro` work;
C-004 marker routing complete; C-005 planted breaks never committed
**Scale/Scope**: ~70 test files across ~20 test directories; ~25 files edited, a handful
retired or trimmed

### Marker routing facts (verified at plan time)

- Module CI shards select `-m "not performance and not stress"`
  (`scripts/ci/shard_select.py::MODULE_SELECTION_MARKER_EXPR`), so `regression` tests run
  per-PR in their module shard; removing the marker does not de-route a test.
- `make test-fast` deselects `regression` (`Makefile` `FAST_TIER_MARKERS`), so unmarking a
  `fast`/`unit` test moves it into the local fast tier — the intended shift-left.
- A test left with no tier marker after unmarking gets the tier marker its siblings use.

## Charter Check

- **Single canonical authority** — no new test helpers duplicate existing fixtures; seam
  tests reuse each module's conftest. PASS.
- **ATDD-first / red-first** — every new seam test and every tightened oracle is shown red on
  a planted break before the slower test is trimmed (Standing Order #4, DIRECTIVE_041). PASS.
- **Test remediation discipline** — "judge the test": RETIRE only with a named guard proven
  red (procedure `test-suite-quality-assessment` step "Verify each proposed fix or retirement
  with a planted break"). PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — only named files and named architectural gates. PASS.
- **Pre-existing failure reporting rule** — baseline reds found on `origin/main` get an issue
  before being treated as baseline. Planned.
- **Tracker ticket assignment rule** — assign #5618–#5622 to the operator with a claim
  comment naming this mission. Planned.
- **Branch naming** — charter says `issue-<n>-<slug>`; the operator brief said
  `fix/regression-slice-cleanup`. The charter wins: `issue-5618-regression-slice-cleanup`.

## Project Structure

### Documentation (this mission)

```
kitty-specs/regression-slice-cleanup-01M42WCF/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── traces/            # tooling-friction, approach, design-decisions (Standing Order #3)
└── tasks.md, tasks/   # /spec-kitty.tasks output
```

### Source Code (repository root)

```
tests/
├── charter/, next/, coordination/, core/, integration/, characterization/,
│   specify_cli/next/                                  # #5620 concern
├── specify_cli/ (audit, migration, upgrade), unit/migration/, policy/, regressions/,
│   migrate/                                            # #5621 concern
├── cli/, specify_cli/cli/                              # #5619 concern
├── terminus/, lanes/, consolidation/, orchestrator_api/, specify_cli/lanes/  # #5618 concern
└── charter/test_pack_manager.py, cli/commands/test_charter_io.py            # #5622 concern
```

**Structure Decision**: no new directories; new seam tests land in the existing test file
that owns the seam's module (or a new sibling file in that directory when none exists).

## Implementation Concern Map

- **IC-01 Charter scope & status/runtime ledger (#5620)** — new unit test for
  `charter.activation.scope._load_charter_scope_config` (priority, proved red); unmark/retire
  the 4600 CLI replay; RETIRE the #5513 file; FIX+unmark #5440; SHIFT-LEFT #4642 via
  `next_cmd._dispatch_query_mode` / `_dispatch_advancing_mode` stubs; SPLIT-BY-KIND the
  single-branch write-checkout e2e; unmark `TestIsReviewRejectionEdge`.
- **IC-02 Migration/upgrade/charter ledger (#5621)** — four SPLIT-BY-KIND files, two
  MARKER-ONLY, port #4962 case 3 then retire the file, retire T030.
- **IC-03 CLI ledger (#5619)** — MARKER-ONLY batch; SPLIT-BY-KIND files; seam units for
  `workflow._partition_paths_by_primary_kind` and `_slugify_feature_input` before trimming the
  4905 and non-ASCII e2e; tighten the 2745 oracle.
- **IC-04 Consolidation/terminus/lanes ledger (#5618)** — MARKER-ONLY and SPLIT-BY-KIND files;
  #5569 deleted-branch REFUSE + approved-dependency PASS units first; trim SHIFT-LEFT files to
  one smoke per family after re-proving B1–B9.
- **IC-05 Root-independent permission tests (#5622)** — skip under euid 0 with a reason (or
  inject at the I/O seam) for the two named tests and any other chmod-unreadable test found.

Concerns touch disjoint files, so they can run in parallel lanes.

## Complexity Tracking

No charter violations to justify.
