# Implementation Plan: Coordination branch remote-existence probe

**Branch**: `issue-4979-coord-branch-remote-probe` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)
**Input**: GitHub issue #4979 — `doctor coordination --fix` flattens a live coord mission from a checkout that cannot see the remote coordination branch.

## Summary

The coord read-path and `doctor coordination --fix` decide "coordination branch never
created / deleted" from a single canonical probe, `_coord_branch_exists`
(`surface_resolver.py`), which today inspects only the local head and already-fetched
`refs/remotes/*` refs (the #2614 residual). On a `git clone --single-branch`, `--depth 1`
CI checkout, or a pruned-origin clone, neither ref exists though the branch lives on origin,
so the probe reports "absent", the doctor flattens the mission (drops `coordination_branch`,
demotes `topology: coord → lanes`), and `implement`'s planning-artifact auto-commit carries
the flattened `meta.json` to the target branch — hiding every teammate's approvals on pull.

**Approach (three-tier defense, fail-closed throughout):**
1. **WP01 (root, closes the class):** extract ONE shared tri-state remote-branch-lookup
   primitive `{HIT, CLEAN_MISS, ERROR}` (iterate configured remotes, bounded timeout, no
   credential prompt, memoized) and teach `_coord_branch_exists` to consult it after the
   local fast paths. A remote HIT ⇒ present; a reachable CLEAN-MISS across all remotes ⇒
   absent; ERROR/TIMEOUT ⇒ fail-closed present; **zero remotes configured ⇒ keep today's
   local-authority "absent"**. Refactor the existing duplicate `_branch_resolvable` onto the
   same primitive (C-001). Because the probe feeds the read-path error, the doctor, and
   backfill, fixing it stops the flatten at source. Rewrite the remote-only guidance to
   "fetch first" and confirm the read path fails closed (`CoordinationWorktreeUnmaterialized`).
2. **WP02 (belt-and-suspenders):** re-verify against the remote at the doctor flatten site
   (`_fix_never_created_branches`) before the destructive `flatten_coordination_metadata`;
   present-on-remote ⇒ skip + actionable message.
3. **WP03 (defense-in-depth):** make `implement`'s planning-artifact staging REFUSE (never
   silently commit) when the uncommitted `meta.json` is a topology demotion.

Each defect lands a `@pytest.mark.regression` reproduction pinned to #4979, RED through the
pre-existing entry point on the mission base and GREEN on the WP's final commit.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `git` subprocess (already required); typer, rich (CLI). No new dependency.
**Testing**: pytest (`@pytest.mark.regression` red-first per ADR 2026-07-17-1); mypy --strict; ruff.
**Target Platform**: Linux / macOS / Windows (cross-platform git).
**Project Type**: single (CLI library).
**Performance Goals**: CLI < 2s typical; remote probe runs only after local fast-path miss, memoized per-process (one round-trip per invocation); bounded `timeout=` (~5s).
**Constraints**: fail-closed-toward-present on any git error; `GIT_TERMINAL_PROMPT=0` + SSH BatchMode (no hang/prompt); single canonical remote-lookup primitive (no third duplicate); complexity ≤15; ≥90% new-code coverage.
**Scale/Scope**: three source files + one shared primitive; ~3 red-first regressions + focused unit tests.

## Constitution / Charter Check

*GATE: must hold before and after design.*

- **Single canonical authority (C-001):** extend the ONE branch-existence authority; extract a shared tri-state remote-lookup primitive consumed by both `_coord_branch_exists` (fail-toward-present) and `_branch_resolvable` (fail-toward-false) — no third parallel probe. **PASS by design.**
- **Preserve write-gate strictness (C-002):** `_coord_branch_is_local_head` and `coord_branch_has_committed_artifact` stay LOCAL-strict; WP01 does not touch them. Confirmed safe by construction (distinct functions; remote-only ⇒ still not-a-local-head ⇒ write refuses self-materialization). **PASS.**
- **ATDD / red-first (C-003, C-011):** each WP's first commit is a failing issue-pinned regression through the pre-existing entry point. **PASS.**
- **Fail-closed reliability (NFR-002):** every new git probe fails toward "present"; bounded timeout + no prompt. **PASS.**
- **Locality of change (DIRECTIVE_024) / smallest-viable-diff:** three distinct files + one shared primitive home; the `_branch_resolvable` refactor is domain-matched (both are remote-branch probes) and closes the parallel-authority class — a justified, proportional extension, not scope creep. **PASS.**
- **Terminology canon (C-004):** Mission/`--mission` only; no forbidden terms. **PASS.**
- **Tiered rigour:** the #4959/#4970 coord-unmaterialized seam is fragile core domain logic — treat with MORE rigour (explicit read-path fail-closed assertion, FR-007). **NOTED.**

## Project Structure

### Source Code (repository root)

```
src/specify_cli/
├── coordination/
│   └── surface_resolver.py        # WP01: _coord_branch_exists consumes the shared primitive;
│                                   #       remote-only guidance; ordering after local fast paths
├── git/                           # WP01: shared tri-state remote-branch-lookup primitive
│   └── remote_probes.py (new)     #       (canonical home under specify_cli/git/; memoized; timeout; no prompt)
├── cli/commands/
│   ├── mission_type.py            # WP01: _branch_resolvable refactored onto the shared primitive
│   ├── _coordination_doctor.py    # WP02: _fix_never_created_branches remote re-verify guard
│   └── implement.py               # WP03: planning-artifact staging demotion REFUSE guard
├── missions/_read_path_resolver.py  # WP01 (read-only trace): probe_coord_state → CoordState
└── mission_runtime/resolution.py     # WP01 (read-only verify): remote-only read raises Unmaterialized
```
(The exact home of the shared primitive is a WP01 brownfield decision: a new `src/specify_cli/git/remote_probes.py` beside the existing `commit_helpers.py`/`ref_advance.py`/`sparse_checkout.py` is preferred, but WP01 confirms no existing git-helper module already fits before creating one. `_branch_resolvable` already lives in `mission_type.py:1292` and enumerates `git remote` → `git ls-remote --heads <remote> <branch>` — the exact idiom to lift, minus its missing `timeout=`.)

### Documentation (this mission)

```
kitty-specs/coord-branch-remote-probe-01M3F6M7/
├── spec.md              # committed
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── tasks/               # per-WP prompt files
└── tracers/             # approach / design-decisions / tooling-friction (seeded, appended during implement)
```

## Phase 0 — Research / Grounding (complete)

Grounding + a 2-lens opus adversarial squad (correctness/fail-closed + boundary/blast-radius)
ran post-spec; findings folded into `spec.md` and `tracers/design-decisions.md` (D-07..D-15).
Key resolved unknowns:

- **Tri-state ls-remote** discrimination (MATCH / reachable-CLEAN-MISS / ERROR) with the
  zero-remotes-keeps-local-authority carve-out — the load-bearing correctness decision.
- **Probe consumers are exactly three**: `_read_path_resolver.py:~320` (read → CoordState.DELETED),
  `_coordination_doctor.py:~501` (doctor NEVER_CREATED), `backfill_topology.py:~220` (skip-flatten) —
  all benefit from "remote-only ⇒ present"; none is harmed.
- **Existing remote-probe duplicate** `_branch_resolvable` (`mission_type.py:~1292`) — reuse via a
  shared tri-state primitive; also fixes its missing-timeout hang.
- **C-002 safe by construction**; **memoization** needed for CI single-branch read frequency;
  **guidance dead-end** (worktree-add hint fails on single-branch) needs a fetch-first branch.

## Phase 1 — Design & Contracts

**Shared primitive contract** (`remote_branch_lookup(repo_root, branch) -> RemoteLookup`):
- Enumerate `git remote`; for each run `git ls-remote --heads <remote> <branch>` with
  `timeout≈5s`, env `GIT_TERMINAL_PROMPT=0`, `GIT_SSH_COMMAND` BatchMode.
- Any remote MATCH ⇒ `HIT`. All configured remotes reachable + clean-miss ⇒ `CLEAN_MISS`.
  Any error/timeout/OSError (and none matched) ⇒ `ERROR`. Zero remotes configured ⇒ a distinct
  `NO_REMOTE` (callers apply local authority). Memoized per-process by `(repo_root, branch)`.
- `_coord_branch_exists`: after `_roots_own_checkout` + local-head + `refs/remotes/` fast paths,
  map `HIT|ERROR ⇒ present`, `CLEAN_MISS|NO_REMOTE ⇒ absent`.
- `_branch_resolvable`: local-head OR `HIT ⇒ resolvable`; else not.

**Guidance contract (FR-006):** `CoordinationBranchDeleted` / doctor hint branch on
local-head-vs-remote-only; remote-only ⇒ "run `git fetch origin <coord_branch>` (or fix
`remote.origin.fetch`) then re-run", never "flatten".

**WP03 demotion predicate (FR-005):** baseline = `git show HEAD:kitty-specs/<slug>/meta.json`;
demotion iff HEAD `coordination_branch` is non-null AND the working copy drops it to
absent/null (a `topology` coord→lanes demotion corroborates but is not required — legacy HEAD
may lack the field, so `coordination_branch` presence→absence is the primary, robust key).
exit-128 (untracked, no HEAD baseline) ⇒ ALLOW; corrupt/unparseable on either side ⇒ REFUSE.
WP01 exposes a small `meta_json_at_ref` / demotion-predicate helper if one is not already
present; WP03 hooks the staging DECISION seam (`detect_structural_planning_changes` /
`resolve_planning_artifact_staging`), not a parallel commit gate.

## Parallel Work Organization

```
WP01 (surface_resolver + shared git-probe primitive + _branch_resolvable refactor + guidance + read-path verify)
  │  owns: git/remote_probes.py (new), coordination/surface_resolver.py, cli/commands/mission_type.py
  │  root — closes the defect class at source
  ├── WP02 (doctor flatten remote re-verify)      depends on WP01 (consumes the shared primitive)
  │      owns: cli/commands/_coordination_doctor.py
  └── WP03 (implement auto-commit demotion REFUSE) depends on WP01 (consumes routing/primitive helpers)
         owns: cli/commands/implement.py
```

WP02 and WP03 are independent of each other and can run in parallel once WP01 lands. Owned-file
sets are disjoint (no-overlap is the real guard, ownership-map-leeway).

## Complexity Tracking

No new architectural surface; no new dependency. The shared primitive is a small extraction
that *reduces* duplication (two probes → one). Complexity kept ≤15 by extracting the tri-state
lookup and the demotion predicate as pure helpers with focused tests.
