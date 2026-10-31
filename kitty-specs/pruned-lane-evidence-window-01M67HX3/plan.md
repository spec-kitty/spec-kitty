# Implementation Plan: Evidence survives a pruned lane branch

**Branch**: `issue-6780-pruned-lane-evidence-window` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/pruned-lane-evidence-window-01M67HX3/spec.md`

## Summary

`consolidation/wp_evidence.py` decides whether an approved work package may land
as reviewed (#6715). For a lanes/coord Mission it diffs
`planning_commit_sha..<lane branch>` and turns any git error into
`IMPLEMENTATION_UNREADABLE` for every work package in the lane. A Mission landed
through a pull request never runs `consolidate`, and its lane branches are
normally pruned after the merge, so the lane branch — and with it the whole
evidence window — is gone even though every deliverable is on the target
(reproduced on `main` at `512567eee7`, [research.md](research.md)).

The plan keeps the lane branch as the window's first choice and adds one
opt-in stand-in: when the caller supplies a **verified landing commit** (only
`accept --mode pr --merge-commit` has one, verified by
`consolidation.baseline.verify_pr_merge_evidence` before the gate runs) and the
window's tip does not resolve to a commit, the window becomes
`planning_commit..<landing commit>`. Same base, same per-work-package
`owned_files` match, same bookkeeping exclusion, same independence check: a work
package with no owned-file change between planning and the landing still refuses
`IMPLEMENTATION_MISSING`. If the planning commit is not an ancestor of the
landing commit, or the landing commit cannot be read, the fallback is refused
rather than diffed. When no landing commit is available the refusal stays
fail-closed but now names the absent lane branch and both remedies.

## Technical Context

**Language/Version**: Python 3.11+ (project floor `>=3.11`)
**Primary Dependencies**: stdlib only for this change; existing seams
`specify_cli.lanes._git.ref_exists`, `specify_cli.consolidation.git_probes`
(`changed_paths_in_range`, `sha_reachable_from`), `specify_cli.core.vcs.git.git_merge_base`
**Storage**: reads `kitty-specs/<mission>/lanes.json` (through
`lanes.persistence`), `meta.json` (read-only), the status event log; writes
nothing new
**Testing**: pytest with real git fixtures (the existing
`tests/specify_cli/cli/commands/test_accept_merge_commit.py` shape, extended with
a lane-branch merge + prune) driving the production `accept(...)` entry point;
plus the existing #6715/#5939 modules unmodified
**Target Platform**: Linux/macOS developer hosts and CI (`spec-kitty` CLI)
**Project Type**: single project — CLI package `src/specify_cli/`
**Performance Goals**: no new git probe when the lane branch resolves; at most
one ancestor probe plus one diff per lane with an absent branch ref (NFR-001)
**Constraints**: no skip/xfail/filter, no gate weakened (NFR-002); no new CLI
flag, config key or env var (NFR-004); the fallback exists only where a verified
landing commit is supplied (C-003)
**Scale/Scope**: `consolidation/wp_evidence.py` (window choice, refusal text),
`cli/commands/accept.py` (one argument threaded), `consolidation/no_implementation_attestation.py`
(same argument for the attestation planner), one new focused test module, one
changelog entry, one how-to gotcha

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the landing commit is the one value
  `consolidation.baseline.verify_pr_merge_evidence` already verified in this run;
  the accept request carries it, nothing re-derives it. Ref readability is asked
  through the existing `lanes._git` / `git_probes` seams, branch jump-to-target
  through `core.vcs.git.git_merge_base`. No second reader, no string inspection:
  PASS.
- **Architectural alignment / locality of change** — the window choice stays in
  the module that owns the window (`wp_evidence.py`); the accept edit is the
  keyword argument that carries the verified commit; the attestation planner
  gains the same keyword. No package boundary moves: PASS.
- **ATDD-first / red-first** — the reproduction test drives the real
  `accept(mode="pr", merge_commit=…)` entry point through a real git fixture and
  is run red before the production edit: PASS (see IC-02).
- **Test policy (`NO_FULL_HEAVY_SUITES_IN_MISSION`)** — targeted modules only
  (the accept evidence modules, the #6715 integration module, the wp_evidence unit
  modules): PASS.
- **Pre-existing Failure Reporting Rule** — any red outside this diff is
  classified and cited in the PR's `## Deferred`, never skipped: PASS.
- **Terminology Canon** — "Mission", "work package", "lane branch", "target
  branch", "landing commit" are the canonical terms; the new refusal text names
  only those: PASS.

No violations; **Complexity Tracking** is intentionally empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pruned-lane-evidence-window-01M67HX3/
├── spec.md              # Mission specification
├── research.md          # Discovery + Phase 0 decisions (D-1 … D-8)
├── plan.md              # This file
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── tasks/               # Work-package task files
```

### Source Code (repository root)

```
src/specify_cli/
├── consolidation/
│   ├── wp_evidence.py                    # EDIT: window stand-in, refusal text, one new keyword
│   ├── git_probes.py                     # READ-ONLY: changed_paths_in_range, sha_reachable_from
│   └── no_implementation_attestation.py  # EDIT: thread the same landing commit into the planner
├── cli/commands/
│   └── accept.py                         # EDIT: pass the verified landing commit to the gate + planner
├── lanes/
│   ├── _git.py                           # READ-ONLY: ref_exists
│   └── compute.py                        # READ-ONLY: lane_created_branch, is_planning_lane
└── consolidation/baseline.py             # READ-ONLY: verify_pr_merge_evidence

tests/
├── specify_cli/cli/commands/
│   ├── test_accept_merge_commit.py       # EDIT: pruned-lane reproduction + control arms
│   └── test_accept_evidence_preflight.py # must stay green, unmodified
└── consolidation/
    └── test_evidence_code_literals.py    # must stay green (pins the code literals)

tests/integration/test_6715_squad_identity_and_evidence.py  # must stay green, unmodified

docs/
├── development/how-to/pr-landing.md      # EDIT: a gotcha for pruned lane branches
└── changelog/CHANGELOG.md                # EDIT: [Unreleased] entry (#6780)
```

**Structure Decision**: single-project CLI layout; the production change is
confined to the evidence axis and the two call sites that already own the
verified landing commit. The fixture extension lives beside the existing
`--merge-commit` tests so the blast-radius run is two directory-scoped commands.

**Interface sketch** (internal, not a public contract):

```python
# consolidation/wp_evidence.py
def mission_evidence_report(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    excluded_canceled_wp_ids: Iterable[str] = (),
    landed_commit: str | None = None,   # NEW: a caller-verified PR landing commit
) -> EvidenceReport: ...

def evaluate_evidence(..., landed_commit: str | None = None) -> EvidenceReport: ...

# the window the module actually judges, per lane
def _lane_window_for_landing(
    repo_root: Path, window: tuple[str, str], landed_commit: str | None
) -> tuple[tuple[str, str], str | None]:   # (window, absent-tip ref or None)
```

`landed_commit=None` keeps every existing caller byte-identical.

## Complexity Tracking

*No Charter Check violations — intentionally empty.*

## Implementation Concern Map

### IC-01 — The window stand-in (core)

- **Purpose**: judge an approved/done work package's evidence against the
  verified landing commit when its lane branch ref is gone, without changing the
  window's base or its pass criteria.
- **Relevant requirements**: FR-001, FR-002, FR-006, NFR-001, NFR-002, C-001,
  C-003.
- **Affected surfaces**: `src/specify_cli/consolidation/wp_evidence.py`
  (`_scan_lane`, `_dependency_evidence_windows`, `widened_lane_paths`,
  `evaluate_evidence`, `mission_evidence_report`); read-only imports of
  `lanes._git.ref_exists`, `git_probes.sha_reachable_from`.
- **Sequencing/depends-on**: none.
- **Risks**: (a) widening the tip could let another mission's change to the same
  path satisfy the gate — mitigated by keeping the planning base, the owned-glob
  match and the disjoint-owner assumption unchanged, and by restricting the
  stand-in to a *caller-verified* landing commit; (b) the dependency widening
  computes `merge-base(<dependency branch>, <lane branch>)`, which would itself
  raise on the pruned ref — the effective tip is therefore threaded through
  `widened_lane_paths`; (c) `ref_exists` must be asked with a full revspec so a
  tag or remote ref cannot masquerade as the lane branch (local-only
  `branch_exists` is the wrong probe for a tip that is a target branch on a
  planning lane).

### IC-02 — Red-first reproduction and the sum-of-arms control

- **Purpose**: prove the reported shape fails on pre-fix code and passes after,
  that the gate still refuses a hollow work package, and that a readable lane
  branch keeps using the lane window — on one shared fixture.
- **Relevant requirements**: FR-001, FR-002, FR-003, SC-001, SC-002, SC-003,
  SC-005.
- **Affected surfaces**: `tests/specify_cli/cli/commands/test_accept_merge_commit.py`
  (fixture extension + new test functions).
- **Sequencing/depends-on**: IC-01 (the test is authored first and run red).
- **Risks**: a fixture that leaves the lane branch in place never reproduces the
  bug (the existing module already covers that path); the fixture must merge the
  lane branch into the mission branch *before* the landing merge, otherwise the
  owned file is not on the target and the assertion would be vacuous. The
  "hollow" arm must use a work package that is approved but never implemented, so
  it proves the gate still fires.

### IC-03 — The honest refusal (text, both lanes)

- **Purpose**: when no stand-in is available, name the absent lane branch and
  both remedies instead of a blanket "could not be diffed"/"restore or fetch".
- **Relevant requirements**: FR-004, NFR-003.
- **Affected surfaces**: `src/specify_cli/consolidation/wp_evidence.py`
  (`_RECOVERY[IMPLEMENTATION_UNREADABLE]`, the per-work-package line built in
  `_scan_lane`); the accept rendering surfaces are unchanged (they print the
  `EvidenceReport`).
- **Sequencing/depends-on**: IC-01 (same function).
- **Risks**: an operator could read the new text as an instruction to pass
  `--merge-commit` blindly; the text says the commit must be the verified PR
  landing, and `verify_pr_merge_evidence` still refuses a wrong SHA before the
  gate.

### IC-04 — One window for the attestation planner

- **Purpose**: `accept --attest-no-implementation` must not contradict the gate
  that runs immediately after it on a pruned-lane Mission.
- **Relevant requirements**: FR-005, NFR-003.
- **Affected surfaces**: `src/specify_cli/consolidation/no_implementation_attestation.py`
  (`plan_no_implementation_attestations`, one keyword), `src/specify_cli/cli/commands/accept.py`
  (`_record_no_implementation_attestations` passes the same commit).
- **Sequencing/depends-on**: IC-01.
- **Risks**: an attestation must still be refused for a genuinely unreadable
  window (a `--merge-commit` that is not supplied, or a base/landing mismatch);
  the `_UNLIFTABLE_VERDICTS` rule is untouched.

### IC-05 — Operator-facing record

- **Purpose**: an operator who prunes lane branches after a PR merge (or who is
  refused without `--merge-commit`) must find the documented remedy.
- **Relevant requirements**: FR-004, NFR-003.
- **Affected surfaces**: `docs/development/how-to/pr-landing.md` (Gotchas),
  `docs/changelog/CHANGELOG.md` ([Unreleased]).
- **Sequencing/depends-on**: IC-01, IC-03.
- **Risks**: `docs/api/cli-commands.md` is a generated surface; the change adds
  no CLI option, so no regeneration is required — confirm with
  `uv run python -m scripts.docs.check_docs_freshness --ci`.
