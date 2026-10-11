# Implementation Plan: Governed ops never destroy or mis-report user content

**Branch**: `fix/5964-5434-4796-govern-user-content` | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/govern-user-content-safety-01M4NWGM/spec.md`

## Summary

Three independent P1 point-fixes in the #3129 ambient-write-boundary class, each a case where a governed/package-owned operation destroys the only copy of operator content or reports a false verdict and still exits 0. The fixes do not share a code seam — only #4796 touches the #6020 residue/pre-mutation-preflight family; #5964 is an upgrade-migration ownership bug and #5434 is a git-exclude-location bug. Each lands with a failing-first acceptance test on real observable state (`git ls-files`, `git status --porcelain`, pre/post refs), then the minimal fix, reusing the single canonical authority that already exists for each surface.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new (stdlib + git; typer/rich/ruamel already present)
**Storage**: filesystem + git (no DB)
**Testing**: pytest; assertions on real git state, not on side-effect files written. `make test-fast` + targeted blast radius per WP; CI owns full/arch/nightly.
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single project (`src/specify_cli`, `src/kernel`, `src/coordination` via specify_cli)
**Performance Goals**: no regression; allocator/migration calls stay well under the <2s CLI budget
**Constraints**: smallest-viable-diff + locality; reuse canonical authorities; no new suppressions; `mypy --strict` clean
**Scale/Scope**: three isolated WPs, ~3 source files touched + 1 new migration + targeted tests; no cross-WP file overlap

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (DIRECTIVE_044): PASS by design. #5964 reuses `skills/command_installer.py` + `skills/manifest.py` ownership (the charter "Proof Trail" surface); #4796 reuses `consolidation/entry_preflight.py::_pre_mutation_safety_preflight`; #5434 reuses `core/git_ops.py::exclude_from_git_index` + the `m_0_13_1` migration shape. No second predicate is introduced; specifically NOT extending `coordination.coherence.is_self_bookkeeping_churn` (operator ruling + grounding: that would widen the data-loss into the consolidate/accept destructive guards).
- **ATDD-first** (C-011): each WP commits a red-first acceptance test before the fix; reviewer verifies red→green.
- **Smallest-viable-diff + Locality** (DIRECTIVE_024/025, RECONCILE_CHANGE_SCOPE_TENSIONS): #5434 removes only the dead per-worktree writer + its two call sites; the larger `core/worktree.py`/`core/vcs` legacy cluster is a separate tracked follow-up. No opportunistic scope growth.
- **Terminology canon**: no new `feature*` identifiers; Mission throughout.
- **Tiered rigour**: all three touch core governed-safety logic → high rigour, direct branch tests on observable state.
- **No full heavy suites in-mission** (NO_FULL_HEAVY_SUITES_IN_MISSION): targeted blast radius only; named arch-gate files where implicated (e.g. dead-symbol allowlist for #5434), never a bare `tests/architectural/` sweep.

Re-check after Phase 1: unchanged — no new authority, no new gate, no terminology risk.

## Project Structure

### Documentation (this mission)

```
kitty-specs/govern-user-content-safety-01M4NWGM/
├── spec.md              # committed
├── plan.md              # this file
├── research.md          # Phase 0 (grounded findings, below + research command)
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── tasks/               # per-WP prompts
```

### Source Code (repository root) — files touched, partitioned by IC (no overlap)

```
# IC-01 (#5964) — upgrade migration ownership scoping
src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py   # scope _untrack_tracked_paths selection
src/specify_cli/upgrade/autocommit.py                                            # (optional) defense-in-depth drop of non-owned .agents/skills from index_deletions
  reuses: src/specify_cli/skills/command_installer.py, src/specify_cli/skills/manifest.py   # ownership authority (read-only reuse)
tests/upgrade/test_gitignore_backfill_untrack.py                                 # + red-first team-skill-survives case
tests/specify_cli/upgrade/migrations/test_m_3_2_5_agents_skills_gitignore.py     # + unit: selection excludes team content
tests/upgrade/test_upgrade_carries_migration_untracks_5443.py                    # + inverse: team skill absent from upgrade commit deletions

# IC-02 (#5434) — lane worktree .spec-kitty common-dir exclude + migration + dead-writer removal
src/specify_cli/lanes/worktree_allocator.py                                      # call exclude_from_git_index at the choke point (~:1087)
src/specify_cli/upgrade/migrations/m_4_0_0rcX_exclude_spec_kitty.py              # NEW, modeled on m_0_13_1_exclude_worktrees.py
src/specify_cli/core/worktree.py                                                 # DELETE _ensure_spec_kitty_exclude + its 2 call sites
tests/architectural/dead_symbol_allowlist.yaml                                   # drop the now-deleted rows
  reuses: src/specify_cli/core/git_ops.py::exclude_from_git_index               # common-dir writer (reuse)
tests/lanes/test_worktree_allocator.py                                           # + red-first reuse/recovery clean-status cases
tests/upgrade/test_exclude_spec_kitty_migration.py                               # NEW, mirrors test_exclude_worktrees_migration.py
tests/integration/core/test_worktree_exclude_spec_kitty.py                       # remove/replace (pins wrong location)

# IC-03 (#4796) — orchestrator-api pre-mutation preflight parity
src/specify_cli/orchestrator_api/consolidation.py                                # hoist pre-mutation preflight into _execute_lane_merge before :588
  reuses: src/specify_cli/consolidation/entry_preflight.py::_pre_mutation_safety_preflight  # parity target (reuse / extract leg 2)
tests/orchestrator_api/test_consolidate_mission_premutation_timing.py            # NEW, pins timing (no mutation/push on refusal)
```

## Implementation Concern Map

Three disjoint ICs → one WP each → three lanes with zero file overlap (the no-overlap ownership guard is satisfied without needing an ownership map).

| IC | Issue | Concern | Canonical authority reused | Owns files |
|----|-------|---------|----------------------------|------------|
| IC-01 | #5964 | Upgrade untracks only spec-kitty-projected `.agents/skills/` paths; team content stays tracked and uncommitted-as-deletion | `skills/command_installer.py` (`spec-kitty.*` pattern + `_is_canonical_rel_path`), `skills/manifest.py` (`ManagedFileEntry.installed_path`), `command-skills-manifest.json` | `m_3_2_5_agents_skills_gitignore_backfill.py`, `autocommit.py`, IC-01 tests |
| IC-02 | #5434 | Lane worktrees honour a common-dir `.spec-kitty/` exclude on all allocation routes; backfill migration; remove the dead per-worktree writer | `core/git_ops.py::exclude_from_git_index`, migration shape of `m_0_13_1_exclude_worktrees.py` | `worktree_allocator.py`, new migration, `core/worktree.py`, dead-symbol allowlist, IC-02 tests |
| IC-03 | #4796 | Orchestrator-api merge runs a pre-mutation safety preflight (lane-worktree dirty + on-target) before any mutation/push; refusal truthfully means nothing mutated | `consolidation/entry_preflight.py::_pre_mutation_safety_preflight` (leg 2) | `orchestrator_api/consolidation.py`, IC-03 test |

## Phase 0 — Research (complete; see research.md)

Grounded by a three-agent adversarial grounding squad + codegraph mapping at HEAD `3498b426`:

- **#5964 OPEN** — `m_3_2_5_agents_skills_gitignore_backfill._untrack_tracked_paths` `git rm --cached -r`'s the whole `.agents/skills/` tree consulting neither manifest; `autocommit.migration_index_untracks` → `safe_commit(index_deletions=...)` lands the deletion. Fix = scope the untrack selection to manifest-owned + `spec-kitty.*` paths. The `is_self_bookkeeping_churn` predicate is the WRONG seam (path-pattern for disposable bookkeeping, feeds destructive guards; extending it would widen the bug). Operator-confirmed.
- **#5434 confirmed / independent** — dead `core/worktree.py::_ensure_spec_kitty_exclude` writes the unread per-worktree `info/exclude`; only the common-dir exclude is honoured. Does not touch the residue predicate. Fix = one `exclude_from_git_index(repo_root, [".spec-kitty/"])` at the allocator choke point + migration + delete dead writer.
- **#4796 OPEN** — `orchestrator_api/consolidation.py::_execute_lane_merge` mutates + pushes, first lane-worktree dirty check at cleanup (`:611`→`guarded_worktree_remove`→`destructive_guard.py:280`), enveloped `PREFLIGHT_FAILED`. #6038's snapshot/rollback did not cover this path. Fix = hoist pre-mutation preflight mirroring CLI `_pre_mutation_safety_preflight` leg 2.

## Phase 1 — Design per IC

- **IC-01**: replace the blanket enumeration in `_untrack_tracked_paths` with a filter that keeps a tracked `.agents/skills/` path only if it is spec-kitty-projected — matched by the stable command pattern (`command_installer._is_canonical_rel_path` / `spec-kitty.<command>/`) OR present in `skills-manifest.json` / `command-skills-manifest.json` (`installed_path`). Everything else stays tracked. The `.kittify/skills-manifest.json` file untrack is unchanged. Optional defense-in-depth: `autocommit.migration_index_untracks` drops any `.agents/skills/` deletion that is not projected.
- **IC-02**: at the single code-lane choke point in `allocate_lane_worktree` (`worktree_allocator.py:~1087`, before both `_validate_worktree_clean` calls), call `exclude_from_git_index(repo_root, [".spec-kitty/"])` with `repo_root` asserted to be the main repo. New migration `m_4_0_0rcX_exclude_spec_kitty` modeled 1:1 on `m_0_13_1_exclude_worktrees` with pattern `.spec-kitty/`. Delete `_ensure_spec_kitty_exclude` + its two call sites (both in already-dead functions) and drop the two dead-symbol-allowlist rows; delete/replace the wrong-location integration test.
- **IC-03**: in `_execute_lane_merge`, right after retention resolution (`:566-571`) and before the first `consolidate_lane_into_mission` (`:588`), invoke the shared `_pre_mutation_safety_preflight` (it already takes `lanes_manifest`, `remove_worktree`, `teardown_coordination`) — or extract its lane-worktree leg — gated on the same resolved retention. A raised `DestructiveOpRefused` is still caught at `:859` and enveloped `PREFLIGHT_FAILED`, now truthfully pre-mutation.

## Risks & Mitigations

- **R1 (IC-01)**: two manifests easily conflated (`skills-manifest.json` = pack skills; `command-skills-manifest.json` = command skills). Mitigation: ownership check consults both + the stable `spec-kitty.*` pattern; unit test asserts a pack skill and a command skill are both recognized as projected while team content is not.
- **R2 (IC-01)**: migration determinism — the migration deliberately hardcodes its gitignore entries; reading live manifest state for the untrack decision is a conscious, scoped departure (untrack decision only). Call out in PR.
- **R3 (IC-02)**: `exclude_from_git_index` no-ops if handed a worktree path or if `.git/info/exclude` is absent. Mitigation: pass the asserted main-repo root; migration `can_apply` already guards exclude-file presence.
- **R4 (IC-03)**: standing up a full real-repo orchestrator merge is heavy. Mitigation: model the fixture on `tests/orchestrator_api/test_mission_branch_moved_error_code.py` which already drives the real entrypoint; pin timing via pre/post target ref + done-stamp + push assertions.
- **R5 (dogfood blind spot, IC-02)**: this repo's own `.gitignore` already contains `.spec-kitty/`, masking the bug when dogfooding — tests must construct a consumer-like repo without that tracked entry.

## Out of scope (tracked follow-ups)

- The larger `core/worktree.py` / `core/vcs` legacy dead-code cluster (~1,570 lines) beyond the single dead writer (#5434 scope note).
- Narrowing the `.agents/skills/` `.gitignore` breadth so *future* team additions in a fresh `init` stay trackable (a `GitignoreManager`/`state` change, separate from the untrack+commit data-loss this mission fixes).
