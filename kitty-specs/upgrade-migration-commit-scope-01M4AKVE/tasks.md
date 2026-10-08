# Tasks: Schema-3 upgrade commits only what it changed

**Mission**: `upgrade-migration-commit-scope-01M4AKVE` · **Issues**: #5443 (P0), #5673, #5229, #4763, #5401, #5671, #4722
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md); evidence `<operator-local squad notes>`
**Code reference**: `origin/main` 5ee323802 · **Landing**: WP01 ships alone as PR 1, with the #5443 changelog bullet written by the orchestrator as a landing fold when PR 1 is cut (WP08 does not write it); WP02–WP08 land as PR 2, WP08 authoring PR 2's bullets only (Decision `01M4AYQTE5WGNXKW7411AVYP79`).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Shared hermetic real-git legacy-project fixture: allowlisted env (exactly four `GIT_` keys), pinned cold/warm HOME and agent config, `git init --template= -b work` with empty-hooks assertion, `sys.executable -m specify_cli` with `PYTHONPATH=<lane>/src` (`packs/` beside it), hook installer with call counter | WP01 | |
| T002 | Red-first `p0_repro(issue=5443)` reproduction: untracked secret, staged file, unstaged edit, operator-staged deletion, overlapping `.gitignore`, rejecting hook; accepting-hook positive control without `p0_repro` | WP01 | |
| T003 | Red-first `p0_repro` outcomes: forced migration failure × {no `.gitignore`, tracked `.gitignore`} (no commit, backup gone, created `.gitignore` removed, no rollback debris, token in no history), ignored token, cold/warm-HOME clean commits, held customised file; upgraded worktree (failed migration → no commit there; held file → rest committed) | WP01 | |
| T004 | Remove runner step 10 (`git add -A` + `--no-verify`) and the dead success-on-commit-failure branch; git-free runner tests (HEAD/index unchanged); fix `test_upgrade_git_paths.py` collection | WP01 | |
| T005 | Rollback hygiene: skip sibling backup entries, `.gitignore` absent-sentinel, `_restore_backup` → bool and clean `.migration-backup` only after a full restore, shims after step 9, keep obsolete ignore lines | WP01 | |
| T007 | Globalize migrations: manual review only for a missing version marker; generated files kept without a review flag | WP01 | |
| T008 | Autocommit: ignored-at-baseline exclusion (`untracked="normal"` probe), index-deletion exclusion (keep the migration's untracks), reason constants; `commit_touched_checkout(None)` contract kept | WP01 | |
| T009 | `upgrade.py`: commit gated on run success at the commit decision; manual review no longer suppresses the commit; #5856 regions untouched. `upgrade/runner.py` worktree commit (`:554-555`/`:609-612`): commit only when that worktree's migrations succeeded, hold only marker-less files and commit the rest, explicit message per no-commit reason | WP01 | |
| T045 | `upgrade.py`: held-file warning worded by commit outcome (keeps `Skipped auto-commit` when nothing committed) and exactly one explicit no-commit reason (`_no_commit_reason`) | WP01 | |
| T010 | Verification: remove `p0_repro` markers in the fix commit, targeted suites + protected files unchanged, ruff/mypy, changelog draft for WP08 | WP01 | |
| T011 | Red-first `regression` tests on the final `metadata.yaml` after `spec-kitty upgrade` (legacy and fresh-init shapes) plus writer unit tests | WP02 | [P] |
| T012 | `ProjectMetadata.save()` merge-preserving and atomic; `backfill_project_uuid` atomic | WP02 | [P] |
| T013 | `_stamp_schema_version` (recorded out-of-map edit of WP01's `upgrade/runner.py` after WP01) writes the canonical capability map from `CURRENT_SCHEMA_CAPABILITIES`; legacy list converted, operator map kept | WP02 | [P] |
| T006 | Runner `_update_schema_version` (moved from WP01, Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`; recorded out-of-map edit of `migration/runner.py` after WP01): derive from `CURRENT_SCHEMA_*`, map shape, merge-preserving, atomic; delete `_TARGET_SCHEMA_*` | WP02 | [P] |
| T014 | Verification: targeted suites, ruff/mypy, protected-file diff check, changelog draft | WP02 | [P] |
| T015 | Red-first `regression` tests: real `spec-kitty implement` with dirty `config.yaml`, clean positive control, in-process pre-dirty `meta.json`, WP prompt/`tasks.md` | WP03 | [P] |
| T016 | `_ensure_vcs_in_meta` returns a changed flag; claim records whether `meta.json` was dirty before; facts threaded to `commit_claim` | WP03 | [P] |
| T017 | `claim_commit_paths` becomes the explicit written-path list; warning when `meta.json` was already dirty; empty bundle skips the commit | WP03 | [P] |
| T018 | Verification: targeted suites, listing-owner gate, ruff/mypy, changelog draft | WP03 | [P] |
| T019 | Red-first `regression` real-git tests for both bake commits: operator staged file, off-target branch, detached HEAD, operator `meta.json` edit, temp-worktree argv | WP04 | [P] |
| T020 | Primary-checkout bake through `commit_merge_bookkeeping(destination_ref_override=target_branch)`; check before write; refused → bytes restored, number reported unbaked | WP04 | [P] |
| T021 | Temp-worktree commit becomes `commit --only -m … -- <rel_meta>`; `target_branch` threaded; seam tests updated | WP04 | [P] |
| T022 | Verification: targeted tests and ratchets, ruff/mypy, evidence for WP05's gate, changelog draft | WP04 | [P] |
| T023 | Red-first gate: `_commit_scope_census.py` + `test_commit_scope_owner.py` with planted forms (incl. varargs `run_git(cwd, *args)`), negative controls, scanned-file floor, exactly two canonical owners exempt by symbol (`safe_commit`, merge-conclusion owner); real tree red listing the merge-conclusion sites | WP05 | |
| T024 | Canonical merge-conclusion owner `specify_cli.git.merge_conclusion` (runner refusing bypass flags, in-progress/fresh-worktree conclusion) with unit and real-git tests | WP05 | |
| T025 | Route `auto_rebase.py` and `consolidation.py` sites through the owner; `:844` becomes `--amend --only -- <restored>` | WP05 | |
| T026 | Route `worktree_allocator.py`, `coherence.py:736` and `agent/workflow.py:661`; gate green with no allowlist (two canonical owners exempt by symbol) | WP05 | |
| T027 | Behaviour-preservation tests (no `regression` marker) on routed entry points (messages, parents, staged operator files, signing) | WP05 | |
| T028 | Verification: targeted suites, ruff/mypy, self-mutation spot checks, no baseline entry, tracer entries | WP05 | |
| T029 | Red-first `regression` text check over shipped skills, the git toolguide and the two upgrade docs (non-vacuity, floor) | WP06 | [P] |
| T030 | Red-first removal tests: `GitVCS.commit`, `VCSProtocol.commit`, `init_git_repo` gone (incl. `__all__`) | WP06 | [P] |
| T031 | Delete the sweeping helpers and rewrite/delete their tests | WP06 | [P] |
| T032 | Rewrite shipped skill/toolguide text to path-scoped commits; bump toolguide YAML; regenerate the pack manifest | WP06 | [P] |
| T033 | Rewrite the two upgrade docs' commit blocks; docs-freshness and markdownlint gates; verification | WP06 | [P] |
| T034 | `kernel.resolution.resolve_commit_path`: parents resolved, leaf never followed, loop refused, dangling allowed | WP07 | [P] |
| T035 | Core `safe_commit` normalisation (`preflight_commit`, expected-parent bytes) via the helper; `SafeCommitPathLoopRefused` | WP07 | [P] |
| T036 | `_stage_requested_files` names the failing path and git's reason; `RuntimeError` + prefix kept (#4722) | WP07 | [P] |
| T037 | safe-commit CLI: rename sources kept (#5401), symlinked dir = link, cross-boundary rename refused, lone unknown path error | WP07 | [P] |
| T038 | spec-commit and `OwnedCheckout.files` keep the link (#5671) | WP07 | [P] |
| T039 | Commit router symlink sites use the leaf-preserving helper | WP07 | [P] |
| T044 | `safe_commit(index_deletions=...)` via a HEAD-seeded temp index (hooks honoured, real index reset only for committed paths); upgrade carries migration untracks (one out-of-map call site in `upgrade/autocommit.py` after WP01) | WP07 | |
| T040 | Verification: loop refusal on every surface, targeted suites, ruff/mypy, `.resolve()` audit, changelog draft | WP07 | [P] |
| T041 | Red (documentation-WP exemption): style guard + in-scope issue check on the planning base recorded; confirm the orchestrator's #5443 PR 1 bullet is on the rebased base (never written or edited here) | WP08 | |
| T042 | One `### Fixed` bullet per remaining user-visible change (#5673, bake, #5229, #4763, #5401, #5671, #4722, shipped text) plus an unconditional bullet for the removed public exports | WP08 | |
| T043 | Style guard, docs freshness, terminology gate, Activity Log with SHAs and character counts | WP08 | |

## Dependency graph

```
WP01 ──┬──────────────> WP02 ──────────────┐
       ├──────────────> WP07 ──┐           │
       └───────────────────────┼─> WP05 ──┼──> WP08
WP04 ──────────────────────────┤           │
WP06 ──────────────────────────┘           │
WP03 ──────────────────────────────────────┘
(WP01, WP04, WP06, WP07 also feed WP08 directly)
```

WP01, WP03, WP04 and WP06 can start in parallel (disjoint `owned_files`). WP02 starts after WP01 (T006 and T013 are recorded out-of-map edits of WP01's `migration/runner.py` and `upgrade/runner.py`, Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`; T011–T012 could start earlier but ship in PR 2 anyway). WP07 starts after WP01 (T044 edits one call site in WP01's `autocommit.py` and builds on its baseline seams). WP05 waits for WP01, WP04 and WP06 (they remove `src/` sweeping sites so its gate can start empty) and for WP07 (its gate exempts `safe_commit` by symbol, including WP07's temp-index commit; Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`). WP08 waits for WP01–WP07 and writes PR 2's bullets only; the #5443 bullet is the orchestrator's PR 1 landing fold.

**Recorded out-of-map edits** (the only files touched by two WPs): `src/specify_cli/migration/runner.py` (WP01 owns; WP02 T006 edits `_update_schema_version` + `_TARGET_SCHEMA_*` after WP01), `src/specify_cli/upgrade/runner.py` (WP01 owns the worktree commit block; WP02 T013 edits `_stamp_schema_version` after WP01) and `src/specify_cli/upgrade/autocommit.py` (WP01 owns; WP07 T044 edits one call site after WP01).

## WP01 — "Upgrade commits only what it wrote (P0 #5443)" (IC-01)

**Prompt**: [tasks/WP01-upgrade-commits-only-what-it-wrote.md](tasks/WP01-upgrade-commits-only-what-it-wrote.md) · ~330 lines (dense)
**Goal**: `spec-kitty upgrade` on a 2.x project commits only paths it wrote that were clean before the run; never ignored-at-baseline paths, never after a failed run, never bypassing hooks; holds back only marker-less files and names them; explains every no-commit case — in the main checkout and in every upgraded worktree (`upgrade/runner.py`). **Priority**: P0 (release blocker, ships alone as PR 1).
**Independent test**: `SPEC_KITTY_RUN_P0_REPRO=1 pytest tests/upgrade/test_upgrade_commit_scope_5443.py tests/upgrade/test_upgrade_commit_outcomes_5443.py` is red on the planning base and green (markers removed) at the WP's final commit.

T001 Hermetic real-git legacy-project fixture (WP01)
T002 Red-first `p0_repro` reproduction: operator work and hooks (WP01)
T003 Red-first `p0_repro` outcomes: failure, ignored, cold HOME, held, upgraded worktree (WP01)
T004 Remove the runner's commit step and dead branch; git-free runner tests (WP01)
T005 Rollback and backup hygiene (#4763) (WP01)
T007 Manual review only for missing version marker (WP01)
T008 Autocommit: ignored and index-deletion exclusions, reasons (WP01)
T009 Commit decision gated on success, holds never suppress — main checkout and upgraded worktrees (WP01)
T045 `upgrade.py` held-file warning and one explicit no-commit reason (WP01)
T010 Verification and marker removal (WP01)

**Implementation sketch**: T001–T003 are the red commit (through `spec-kitty upgrade`); T004 removes the sweeping commit; T005 and T007 fix the runner rollback and migrations; T008–T009 make the baseline commit honour ignores, the migration's untracks, holds and failures; T045 says why when it does not commit and names held files; T010 removes the markers in the green commit. The runner-side schema stamp (#5229) is WP02's T006 (PR 2).
**Parallel opportunities**: none inside the WP; T005 and T007 touch different files and can be authored in any order.
**Dependencies**: none. **Risks**: PR #5856 adjacency (no edits to `finalize.py`, `outcome.py`, `upgrade.py`'s import block/repair step/`finalize_upgrade` kwargs/help text, or its four test files; new names reached as `autocommit.X`); environment-sensitive fixtures (cold vs warm HOME, `agents.available`).

## WP02 — Metadata writers keep keys and stamp the canonical map (IC-02, #5229)

**Prompt**: [tasks/WP02-metadata-writers-canonical-map.md](tasks/WP02-metadata-writers-canonical-map.md) · ~215 lines (dense)
**Goal**: the final `.kittify/metadata.yaml` after `spec-kitty upgrade` keeps `project_uuid` and operator keys and carries the canonical capability map, written atomically by every writer. **Priority**: P1.
**Independent test**: `pytest tests/upgrade/test_metadata_final_file_5229.py` (real `spec-kitty upgrade`, `regression`) is red on the planning base and green at the end.

T011 Red-first `regression` tests on the final file plus writer unit tests (WP02)
T012 Merge-preserving atomic `ProjectMetadata.save()`; atomic `backfill_project_uuid` (WP02)
T013 `_stamp_schema_version` writes the canonical map (WP02)
T006 Runner `_update_schema_version` canonical, merge-preserving, atomic — moved from WP01, out-of-map edit of `migration/runner.py` (WP02)
T014 Verification (WP02)

**Implementation sketch**: the final file is written by `ProjectMetadata.save()` after each migration (`upgrade/runner.py:703-721`) and `_stamp_schema_version` (`save()` owned here; `_stamp_schema_version` a recorded out-of-map edit of WP01's `upgrade/runner.py`), so the test goes green through T012/T013; T006 makes the runner-side `_update_schema_version` write the same canonical shape atomically (moved from WP01 by Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`; its tests in a new module so WP01's `test_runner.py` stays untouched).
**Dependencies**: WP01 (T006 and T013 edit WP01's `migration/runner.py` and `upgrade/runner.py` after it lands). **Risks**: legacy list → map conversion; header/comment preservation; `schema_version=None` must neither forge nor erase; import cycle `migration.runner` → `upgrade.metadata` (function-local import).

## WP03 — Claim commit contains only claim-written paths (IC-03, #5673)

**Prompt**: [tasks/WP03-claim-commit-written-paths.md](tasks/WP03-claim-commit-written-paths.md) · ~195 lines (dense)
**Goal**: a work-package claim commits the status artifacts, plus `meta.json` only when the claim changed it and it was clean before; never `config.yaml`, the WP prompt or `tasks.md`. **Priority**: P1.
**Independent test**: `pytest tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py` red on the base, green at the end; the claim commit's file set is asserted exactly.

T015 Red-first `regression` tests (real claim + in-process seams) (WP03)
T016 Changed-flag and dirty-before facts threaded to the claim commit (WP03)
T017 Explicit written-path list and warning (WP03)
T018 Verification (WP03)

**Dependencies**: none. **Risks**: topology variants (single_branch, lanes, coord); the planning-artifacts auto-commit (`implement_planning_commit.py:228`) is out of scope (C-003) and runs first, so the pre-dirty `meta.json` case is tested in-process.

## WP04 — Merge bookkeeping commits only `meta.json` (IC-04)

**Prompt**: [tasks/WP04-merge-bookkeeping-meta-only.md](tasks/WP04-merge-bookkeeping-meta-only.md) · ~200 lines (dense)
**Goal**: the mission-number assignment commits only the Mission's `meta.json`, on the target branch, through the bookkeeping `safe_commit` seam; off-target, detached or with an operator `meta.json` edit pending it commits nothing and reports the number as not yet baked; the temp-worktree commit names its path. **Priority**: P1.
**Independent test**: `pytest tests/consolidation/test_bake_commit_scope_meta_only.py` red on the base, green at the end.

T019 Red-first `regression` real-git tests for both bake commits (WP04)
T020 Primary-checkout bake through `commit_merge_bookkeeping` with pre-write checks (WP04)
T021 Temp-worktree `commit --only -- <rel_meta>`; seam tests updated (WP04)
T022 Verification (WP04)

**Dependencies**: none. **Risks**: `MERGE_BOOKKEEPING` may only be asserted in `commit_guard.py`/`bookkeeping_commit.py` (`test_guard_capability_call_sites.py`), hence `commit_merge_bookkeeping` instead of a direct `safe_commit`; `target_branch` must be threaded; protected-branch guard; fake-subprocess tests in `test_ordering_bake_seam.py`.

## WP05 — Merge-conclusion owner and an empty commit-scope gate (IC-05)

**Prompt**: [tasks/WP05-merge-conclusion-owner-and-gate.md](tasks/WP05-merge-conclusion-owner-and-gate.md) · ~275 lines (dense)
**Goal**: every merge/revert/squash conclusion in `src/` goes through one owner; a `src/` gate that starts empty (no allowlist) and exempts exactly two canonical owners by symbol — `safe_commit` and the merge-conclusion owner (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`) — fails on every sweeping, pathspec-less or hook-bypassing commit route. **Priority**: P1.
**Independent test**: `pytest tests/architectural/test_commit_scope_owner.py` — planted forms each reported, real tree red at the red commit (listing the conclusion sites) and green at the end with no allowlist entry.

T023 Red-first gate with planted forms and floor (WP05)
T024 Canonical owner `specify_cli.git.merge_conclusion` (WP05)
T025 Route `auto_rebase.py` and `consolidation.py` sites (WP05)
T026 Route `worktree_allocator.py`, `coherence.py`, `agent/workflow.py` (WP05)
T027 Behaviour-preservation regression tests (WP05)
T028 Verification (WP05)

**Dependencies**: WP01, WP04, WP06 (their `src/` sites must be gone before the gate can start empty) and WP07 (`safe_commit`'s temp-index commit must exist and sit in the exempt symbol scope). **Risks**: behaviour-preserving routing in hot merge paths (hooks, signing, messages unchanged); documented AST blind spots (plumbing `commit-tree`/`update-ref` out of the gate; follow-up issue filed at closeout); `agent/workflow.py:661` was missed by the squad and is owned here (re-confirmed by the post-tasks rescan).

## WP06 — Remove sweeping helpers and shipped `git add -A` text (IC-06)

**Prompt**: [tasks/WP06-remove-sweeping-helpers-and-text.md](tasks/WP06-remove-sweeping-helpers-and-text.md) · ~245 lines (dense)
**Goal**: `GitVCS.commit(paths=None)`, `VCSProtocol.commit` and `init_git_repo` are gone; shipped skills, the built-in git toolguide and the two upgrade docs teach path-scoped commits; the pack manifest is regenerated. **Priority**: P2.
**Independent test**: `pytest tests/architectural/test_shipped_text_path_scoped_commits.py tests/git_ops/test_sweeping_helpers_removed.py` red on the base, green at the end.

T029 Red-first shipped-text check (WP06)
T030 Red-first helper-removal tests (WP06)
T031 Delete the helpers and their tests (WP06)
T032 Rewrite skill/toolguide text; regenerate the pack manifest (WP06)
T033 Rewrite the two upgrade docs; docs gates; verification (WP06)

**Dependencies**: none. **Risks**: pack-manifest freshness (content hash covers the toolguide YAML, so bump it); docs freshness and markdownlint budgets; three extra directory adds found in other shipped skills are in scope.

## WP07 — `safe-commit` / `spec-commit` commit exactly the given paths (IC-07, #5401 #5671 #4722)

**Prompt**: [tasks/WP07-safe-commit-path-normalisation.md](tasks/WP07-safe-commit-path-normalisation.md) · ~300 lines (dense)
**Goal**: a staged rename under a directory argument is committed whole; a symlink argument (tracked or untracked, relative or absolute, or inside a directory argument) commits the link, never its target; a symlinked directory is a link; looping links refused; cross-boundary renames refused naming the outside path; a failing batch names its path and git's reason; a lone unknown path is an error; `safe_commit` gains `index_deletions` so the upgrade can commit the migration's own `git rm --cached` untracks (FR-022) without moving any file. **Priority**: P2.
**Independent test**: `pytest tests/specify_cli/cli/commands/test_safe_commit_paths_5401_5671_4722.py tests/specify_cli/cli/commands/test_spec_commit_symlink_5671.py tests/kernel/test_resolve_commit_path.py` red on the base, green at the end.

T034 `resolve_commit_path` helper (WP07)
T035 Core normalisation and loop refusal (WP07)
T036 Failing-path detail (#4722) (WP07)
T037 safe-commit CLI fixes (#5401, links, cross-boundary, lone path) (WP07)
T038 spec-commit and owned checkout (#5671) (WP07)
T039 Commit router sites (WP07)
T044 Commit index deletions without re-adding; upgrade carries migration untracks (WP07)
T040 Verification (WP07)

**Dependencies**: WP01. **Risks**: exception-type contracts (`RuntimeError` + prefix kept); 3.12 vs 3.13 `Path.resolve` loop behaviour; Windows symlink skips; temp-index commit must stay inside `safe_commit`'s exempt symbol scope (WP05) and leave the real index clean for committed paths; `index.lock` contention on the post-commit reset.

## WP08 — Changelog entries (IC-08)

**Prompt**: [tasks/WP08-changelog-entries.md](tasks/WP08-changelog-entries.md) · ~150 lines
**Goal**: PR 2's changelog bullets (NFR-003): one `### Fixed` bullet per remaining user-visible change in the house style, each under 900 characters, plus an unconditional bullet for the removed public exports. WP08 does NOT write the #5443 bullet — the orchestrator writes it as a landing fold when PR 1 is cut. `execution_mode: code_change` (normal lane); documentation-WP exemption from a red test module, its red being the style guard and in-scope issue check run on the planning base. **Priority**: P1 (release notes).
**Independent test**: `PYTHONPATH=. python -m scripts.docs.check_changelog_style` exits 0; each of #5673, #5229, #4763, #5401, #5671, #4722 appears in exactly one new bullet; the #5443 bullet is unchanged by WP08's diff.

T041 Red on the planning base; #5443 bullet present, untouched (WP08)
T042 Remaining bullets (WP08)
T043 Gates and closeout (WP08)

**Dependencies**: WP01–WP07. **Risks**: describing the plan instead of what shipped; overlap between the #5443 and #4763 bullets; over-long bullets.
