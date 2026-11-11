---
updated: 2026-11-11
---

# Code grounding: the CLI commits its own writes; dirty gates are Mission-scoped

Read-only grounding run for sub-epic #7545 (#7556, #7555, #5938, #3933), done before
specifying. Base: `origin/main` at `2e9ca5599`. Every claim cites the code it was read
from; nothing below was changed by this run.

## 1. Inventory: tracked writes and whether the command commits them

Commit seams, lowest first: `safe_commit` (`git/commit_helpers.py:1802`) → the kind-aware
router `commit_for_mission` (`coordination/commit_router.py:256`, result
`CommitRouterResult.status` ∈ committed / unchanged / no_op_wrong_surface / error, with
`commit_hash`) → `BookkeepingTransaction` (`coordination/transaction.py:500`, which
materializes and stages `status.events.jsonl` + `status.json`) → the status door
`emit_status_transition_transactional` (`coordination/status_transition.py:1599`).

| Command | Tracked files written | Committed? | Seam / JSON |
|---|---|---|---|
| `init` | `.gitignore` (`init.py:1262`), `.gitattributes` (`:559`, `:1454`), `.kittify/AGENTS.md` (`:1477`), `.claudeignore` (`:1484`), `.kittify/metadata.yaml` (`:1505`), `.kittify/config.yaml` (`:1538`, `:1547`, identity `:1299`), `.kittify/canonical-events.jsonl`, migration-ledger seed (`:1529`), agent command/skill dirs | **No.** `init.py:1283`: "No git initialization. init is file-creation-only." | none / none |
| `next` (non-owned) | `kitty-specs/<m>/mission-events.jsonl` via `emit_mission_next_invoked` (`runtime/next/next_invocation_lifecycle.py:337`) into the STATUS_STATE write dir, i.e. the coordination worktree on a coordination topology (`:315-334`); `kitty-ops/lifecycle/<ulid>.json` records | **No** (#5938). Only the owned path commits: `_commit_owned_next_mutations` (`next_cmd.py:521`, safe_commit at `:592`). `--answer` commits `decisions.events.jsonl` (`events/decision_log.py:271-295`). | none / no SHA |
| `implement` / claim | planning-artifact commit (`implement_planning_commit.py:132-245`, BookkeepingTransaction); status claim; `meta.json` `vcs_locked_at` (`lanes/implement_support.py:1145`); WP frontmatter `base_branch`/`base_commit` (`:570-590`) | **Yes** (claim commit `implement_claim.py:317-434`, scoped by `claim_commit_paths` `:253-276`; pre-dirty files stay out with a warning, #5905) | safe_commit / no commit field |
| `move-task` | status pair; `--note` annotation; review-cycle verdict; lane deliverables at `for_review` | **Partial.** The transition always goes through the status door, but a coord-less topology takes the "primary-uncommitted" fallback (`status_transition.py:1622-1629`, contract row 8). `--note` commits only with auto-commit or owned (`tasks_move_task.py:529-539`). The verdict is `local_only` under `--no-auto-commit` (`tasks_verdict_persistence.py:489-500`). | status door / no commit SHA (`tasks_move_task.py:1819-1852`) |
| `mark-status` | subtasks annotation (event log only) | **Partial** (owned, or auto-commit on single_branch; `tasks_mark_status.py:610-626`) | `commit_sha` only in owned mode |
| `spec-commit` | named artifacts | **Yes** (`spec_commit_cmd.py:181-207`); comment on #3933 says decision files were silently left out | commit_for_mission / `committed`, `commit_hash` |
| `setup-plan` | `plan.md` (`mission_setup_plan.py:683`); PlanCompleted event appended to `status.events.jsonl` after the commit (`:823-832`); gap-analysis / generator config (`:932-1012`) | **Partial.** `plan.md` only when substantive (`:820-821`); the PlanCompleted event is left uncommitted (#3933 F-04). | commit_for_mission / `commit_created`, `commit_hash`, `commit_status` (`:1114-1125`) |
| `finalize-tasks` | status pair, `tasks.md`, `wps.yaml`, `meta.json`, `lanes.json` | **Yes** (`mission_finalize.py:356-366`, `mission_finalize_commit.py:413-423`) | `commit_created`, `commit_hash(es)` |
| `record-analysis` | `analysis-report.md` | **Yes**, best-effort (`mission_record_analysis.py:264-300`) | `surfaces` only |
| `accept` | `meta.json` acceptance record; acceptance-matrix, status views | **Yes** (raw `git commit` on an unprotected HEAD, `acceptance/__init__.py:1844-1866`; router on a protected one, `:1880-1940`; residuals `cli/commands/accept.py:560-640`) | `accept_commit`, `commit_created` |
| `materialize()` | `status.json` (`status/reducer.py:435-449`) | **No** when called standalone (`status/views.py:104`, `status/progress.py:231`, `status/bootstrap.py:217`, ...); yes inside BookkeepingTransaction (`transaction.py:1116`) | n/a |

## 2. Dirty-tree gates and their path predicates

| Gate | Probe | Filter | Scope today |
|---|---|---|---|
| `WRITE_CHECKOUT_DIRTY` (claim, single_branch only, skipped on resume): `lanes/implement_support.py:318` | `checkout_occupancy.dirty_paths` (`:338`), repo-default untracked mode | own prefix list `_owned_status_prefixes` (`:121-165`: this Mission's status pair, `meta.json`, `mission-events.jsonl`, `.kittify/`, `.spec-kitty/`, `kitty-ops/`), then any Mission's decisions lock (`:191`) | **whole repo**: another Mission's `kitty-specs/<other>/` files refuse (#7556) |
| `DIRTY_WORKTREE` (record-analysis): `mission_record_analysis.py:165-226` | `status_entries(untracked=None)` | `is_self_bookkeeping_churn`, then `is_coord_residue_churn` on a coordination topology | **whole repo** (#7556; #5938 comment: `kitty-ops/` from `next`) |
| accept `git_dirty`: `acceptance/__init__.py:339-455` | repo default | five filters (own pipeline writes, `.bak`, self-bookkeeping, decision ledger, coordination partition) | whole repo; other Missions refuse |
| `MERGE_UNSAFE_WORKTREE_DIRTY` / `_PRIMARY_DIRTY`: `git/destructive_guard.py:224-279` | `ref_advance._status_for_dirty_check` (`:443`, `--untracked-files=all`) | `ResidueContext.is_disposable` → `_is_disposable_residue` (`coherence.py:570`); another Mission's file is never disposable | whole checkout |
| consolidate porcelain invariant: `consolidation/phase_bookkeeping.py:572-632` | repo default | skips `??`; `is_toolchain_generated_churn`, `is_self_bookkeeping_churn` | tracked changes only |
| review pre-handoff: `review/dirty_classifier.py` | `status_entries(pathspecs=[feature_dir])` | toolchain churn + survivor list (`mission-events.jsonl`, #5669) | **this Mission only** |
| "Planning artifacts not committed": `implement_planning_commit.py:33-64` | `untracked="all"`, pathspec = feature dir | `is_status_state_path`, legacy event log, self-write-only diffs | this Mission only |

There is **no public working-tree-dirty seam yet** (#5101 is open): `ref_advance._dirty_entries`
and friends are private. `coherence._is_other_mission_path` (`coherence.py:551`) is the one
structural "another Mission's path" rule, but it does not recognise a collapsed untracked
Mission directory (`kitty-specs/<other>/`, `len(after) < 2` → `False`), which is exactly
the shape repo-default `git status` reports for a wholly untracked Mission (#7556).

## 3. Invariants that must survive

- **Protected branches.** Only a `GuardCapability` asserted at the call site lands a commit on
  a protected ref (`commit_helpers.py:60-90`, `core/commit_guard.py:74-114`). The per-flow
  allowlist is `tests/architectural/test_guard_capability_call_sites.py:45-63`;
  `UPGRADE_BOOKKEEPING` is held only by `upgrade/autocommit.py`. No new capability holder.
- **#5905: never sweep operator edits.** The claim commit stages only the set it wrote and
  leaves pre-dirty files out with a warning (`implement_claim.py:95-99,253-276`). The upgrade
  committer derives its set from a pre-write baseline (`upgrade/autocommit.py:1-25,401-448`).
  Any new committer here must use one of these shapes, never `git add -A`.
- **#5669 keep-local ruling.** `mission-events.jsonl` has live research-gate readers and must
  stay real dirt for the gates (`cli/commands/accept.py:289-296`). So #5938 is fixed by
  committing it, not by exempting it.
- **Lane `kitty-specs/` guard / status write door.** A status write aimed at a lane checkout
  refuses `STATUS_WRITE_TARGETS_LANE_CHECKOUT`; lane checkouts carry no status files.
- **Placement seam owns surfaces.** Commit targets come from `placement_seam(...).write_target`
  / `resolve_placement_only`, never a checkout-derived ref (`test_no_write_side_rederivation.py`).
  `_commit_status_artifacts_to_coord` (`status_transition.py:352-388`) is the canonical shape
  for "commit an emitted file in the coordination worktree".
- **Destructive guards.** Another Mission's file is never disposable (#5966). Nothing in
  this mission widens `_is_disposable_residue`.
- **ADRs:** `2026-06-24-1` (kind/topology-aware placement), `2026-11-06-2` (one status read
  contract), `2026-11-06-4` (coordination branch written by commit), `2026-11-01-2` (Op
  lifecycle records, one file per record), `2026-10-04-4` (upgrade writes project-global state
  once).

## 4. Architectural gates referencing these files

- `test_exemption_registry_ratchet.py`: lists `mission_record_analysis.py`, `coherence.py`,
  `dirty_classifier.py`, `acceptance/__init__.py`, ... in `CHURN_SURFACE_MODULES` (`:79-127`); a
  module-level frozenset/tuple/regex of **filenames** there is an exemption that needs a
  registry row, and the registry only shrinks. **Keep it green honestly: the new predicate is
  structural (Mission directory segment), not a filename list.** `implement_support.py` is not
  listed.
- `test_git_path_listing_owner.py`: no `status --porcelain` / `ls-files` argv outside
  `src/kernel/git/` (no allowlist). Use `kernel.git.status_entries`.
- `test_safe_commit_import_boundary.py`, `test_commit_scope_owner.py` (commits only through
  `safe_commit`, against a census): new commits go through `safe_commit` / the router.
- `test_guard_capability_call_sites.py`: per-flow capability allowlist (above).
- `test_destructive_op_routing.py`, `test_status_events_writes_gate.py:181`,
  `test_status_read_single_door.py`, `test_no_write_side_rederivation.py`,
  `test_layer_rules.py` (`runtime` may not import `specify_cli` at module level; the
  existing lazy imports are ledgered).

## 5. Test seams and cost

- Claim gate: `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`
  (real git repo, CliRunner, ~seconds). Pins `test_dirty_checkout_refuses`.
- record-analysis: `tests/specify_cli/test_analysis_report.py:572`
  (`test_record_analysis_refuses_dirty_worktree_before_write` pins a root-level `dirty.txt`
  refusing; under #7556 that file is outside the Mission and becomes a warning, so this test
  is re-pinned, not deleted).
- `next`: `tests/next/`, `tests/runtime/` (CliRunner with a real repo is slower, ~10 s).
- init: `tests/specify_cli/cli/commands/test_init*`, `tests/init/` (real filesystem, fast).
- setup-plan: `tests/specify_cli/cli/commands/agent/test_setup_plan*`.

## 6. Interactions

- **PR #7557** (open): makes `kitty-ops/lifecycle/<ULID>.json` self-bookkeeping in
  `is_self_bookkeeping_churn`. That covers the `kitty-ops/` half of the #5938 comment and of
  #7556. This mission does not touch that predicate, so either landing order rebases cleanly.
- **#7544** (coordination closeout) and **#7549** (doctor/lock): sibling cloud runs; no
  shared file is planned here beyond reads of `consolidation/`.
- **#7310** (S5 status read door): status reads go through `resolve_status_read`; this
  mission adds no status read.

## 7. Churn (since 2026-08-13, ~90 days)

| File | Lines | Commits | `fix` commits |
|---|---|---|---|
| `cli/commands/agent/tasks_move_task.py` | 2309 | 86 | 47 |
| `lanes/implement_support.py` | 1146 | 49 | 22 |
| `cli/commands/next_cmd.py` | 1576 | 46 | 27 |
| `cli/commands/init.py` | 1676 | 44 | 20 |
| `git/commit_helpers.py` | 2099 | 35 | 22 |
| `coordination/coherence.py` | 1096 | 26 | 12 |
| `cli/commands/agent/mission_setup_plan.py` | 1478 | 26 | 15 |
| `git/destructive_guard.py` | 1279 | 23 | 13 |
| `cli/commands/agent/mission_record_analysis.py` | 553 | 16 | 8 |
| `runtime/next/next_invocation_lifecycle.py` | 384 | 11 | 4 |
| `review/dirty_classifier.py` | 258 | 3 | 2 |

These are high-churn god-surfaces. Hence: new logic goes into one small new module
(the Mission-scoped dirt predicate) and is called from the gates, rather than growing them.

## 8. Approach this grounding points to

1. Enabler: a public, structural `mission_dirt` predicate in `coordination/` that splits dirty
   paths into this Mission's own, another Mission's, and outside-any-Mission; `coherence`
   reuses it for `_is_other_mission_path` (behaviour-preserving).
2. #7556: record-analysis refuses only on this Mission's own paths (outside-Mission dirt is
   committed by nobody here, so it is a warning); the single_branch claim keeps refusing on
   code dirt (the WP will commit code there) and warns on another Mission's paths.
3. #5938: `next` commits the `mission-events.jsonl` it wrote when the write landed in the
   coordination worktree, with the `_commit_status_artifacts_to_coord` shape.
4. #3933: setup-plan commits the PlanCompleted event with the plan, and reports the hash it
   committed. move-task: verify on this mission (single_branch) what it leaves dirty, then fix.
5. #7555: `init` commits what it wrote through the upgrade committer's baseline shape
   (`commit_touched_checkout`), which already holds the protected-branch capability for
   project-scaffold bookkeeping; `--no-commit` opts out.
