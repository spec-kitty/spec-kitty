# Code grounding — #5457: upgrade writes project-global state separately on every branch

> Pre-spec grounding squad (adversarial-squad, pre-spec / brownfield point-cut), 2026-10-04,
> against `origin/main` @ `9adc6880` (CLI `4.0.0rc6` installed editable from this checkout).
> Five profile-loaded, read-only lenses: reproducer (`debugger-debbie`), root-cause tracer
> (`debugger-debbie` + `disciplined-defect-diagnosis`), related-issue researcher
> (`researcher-robbie`), architect (`architect-alphonso`), test-suite (`reviewer-renata`).
> The orchestrator synthesis comes first. Each lens report is reproduced in an appendix.
> Machine-local paths are scrubbed to `<scratch>`.

## 1. Verdict: the defect is live on current main, and it is wider than the issue says

The issue's own reproducers were run against the current-main CLI, with the
released `4.0.0rc4` and `3.2.7` wheels as the pre-upgrade CLIs.

| Path | Pre-upgrade CLI | Shape | Result on current main |
|------|-----------------|-------|------------------------|
| A | 4.0.0rc4 | `lanes`, 2 lanes, both approved | `consolidate` exit 1: `Lane lane-b is stale: overlapping files ['.gitattributes', '.kittify/metadata.yaml']` |
| B | 3.2.7 | `lanes`, 1 lane, target `work` | `consolidate` exit 1: `TARGET_BRANCH_CONTENT_CONFLICT`, `conflicting_path: .kittify/metadata.yaml` (`--resume` repeats it) |
| C | 4.0.0rc4 | `lanes_with_coord`, WP02 `for_review` | `agent action review WP02` exit 1: `LANE_AUTO_REBASE_FAILED: no classifier rule matched …/lane-b/.kittify/metadata.yaml` |

New facts beyond the issue text:

- **`.gitattributes` diverges too.** The rc5/rc6 merge-driver migration
  (`decision_index_merge_driver`) appends the same line in every checkout. Each
  lane branch, and the coordination branch, commits it separately. Git merges
  identical additions cleanly, so neither the squash nor the auto-rebase trips
  on it. The stale-lane check does trip, because it compares only file names.
  A fix that covers only `metadata.yaml` would still leave Path A refused.
- **The coordination branch is upgraded too.** On `lanes_with_coord`, four
  branches each get their own upgrade commit (target, coordination branch,
  lane-a, lane-b).
- Per branch, the upgrade commit touched these files (`git show --stat`):
  - **target:** `.gitattributes`, `.kittify/agent_profiles_manifest.json` and
    `.kittify/metadata.yaml`, with all 8 4.0.0 migrations recorded.
  - **each lane and the coordination branch:** `.gitattributes` and
    `.kittify/metadata.yaml`, with only the subset of migrations that run in
    worktrees recorded.
  - Between lanes, the `metadata.yaml` copies differ only in `last_upgraded_at`
    and every `applied_at`.
  - In these scenarios the upgrade touched no agent command directories, no
    skills manifest and no `.gitignore`.

## 2. Root cause: the wrong decision point

**Primary, at the source.** `MigrationRunner._upgrade_worktrees`
(`src/specify_cli/upgrade/runner.py:374-578`) treats every directory under
`.worktrees/` as a project of its own:

- It runs every `runs_on_worktrees` migration in that directory. That flag
  defaults to `True` (`upgrade/migrations/base.py:99`), and 102 of 121
  migrations keep the default.
- It keeps a separate `ProjectMetadata` record for each worktree, with a fresh
  `applied_at` per record (`:494-503`, `:519-527`).
- It auto-commits the result on the worktree's own branch (`:568-583` →
  `upgrade/autocommit.py::commit_touched_checkout`).

The runner never asks whether the worktree's branch integrates back into the
target branch. Mission branches, lane branches and coordination branches all
do. For a worktree that integrates back, every tracked project-global write is
a future overlap or conflict. Branch-target-routing
(`docs/architecture/branch-target-routing.md:33-56`) says only work packages
write to lane branches.

**What the earlier fixes were protecting:**

- **#2385 / #2392:** "every upgrade write ends in a commit, so no checkout is
  left dirty". If upgrade stops writing in integrating worktrees, this holds
  trivially.
- **#4972 (PR #5016):** aligned `last_upgraded_at` for a version-only bump only.
  It can never make two copies byte-identical, because the per-record
  `applied_at`, the record set and the notes still differ.

**Secondary, in the consumers.** None of the four integration consumers has a
rule for project-global bookkeeping:

1. **Stale-lane check.** `lanes/stale_check.py:31-83` intersects the file names
   changed on the mission branch and on the lane. It applies no path class and
   no content comparison.
2. **Squash content gate.** `lanes/consolidation.py:973-1019` (`_run_squash_merge`,
   tagged at `:386-407`, reached from `consolidation/phase_advance.py:552-563`).
   Its reconcilers handle only `kitty-specs/**` planning files and `status.json`.
3. **Lane auto-rebase.** `lanes/auto_rebase.py:435-473` manages only
   `kitty-specs/<mission>/**`. Every other path falls through to
   `consolidation/conflict_classifier.py:556-570` (`R-DEFAULT-MANUAL`, "no
   classifier rule matched"). It is reached from `lanes/lifecycle_sync.py`
   (`sync_lane_after_coordination_commit`) on every coordination lifecycle
   commit, which is why review and implement-resume die on coord missions.
4. **Dependency-lane merge during implement.** `lanes/worktree_allocator.py:1529`.
   It goes through the same classifier.

**Why the printed stale remedy is a no-op.** Consolidate merges lane-a into the
mission branch, finds lane-b stale against that new tip, refuses, and then
`rollback_to_snapshot` (`consolidation/executor.py:422`) puts the mission
branch back to its pre-run tip. Lane-b already contains that tip, so the
printed `git merge kitty/mission-<slug>` reports "Already up to date" and the
next run hits the same overlap. The remedy text is built in
`lanes/stale_check.py::_stale_remediation`.

## 3. Owning authority: which seam owns "project-global, primary-owned"

The lenses disagreed, and I settled it from the source:

- **The root-cause lens proposed `state/contract.py` `STATE_SURFACES`.** It is
  the declarative registry of durable state surfaces. It already lists
  `.kittify/metadata.yaml` (`project_metadata`, `PROJECT`, `AUTHORITATIVE`,
  `TRACKED`, owner `init/upgrade`) and `.kittify/config.yaml`. It already drives
  one derived consumer (`get_runtime_gitignore_entries` → `gitignore_manager`).
- **The architect proposed `coordination/coherence.py`.** That module owns a
  different fact: which *dirty churn* a gate may ignore. Its predicates answer
  "may this uncommitted change be disregarded". They do not answer "which branch
  owns this tracked path".

**Decision for the spec.** The *fact* belongs in `STATE_SURFACES`: a new
declared attribute saying the surface is owned by the primary branch, so a
lane, coordination or mission branch never authors it. One predicate is derived
from the registry. The predicate is exported for consumers, and no
module-level filename list is added to `lanes/` or `consolidation/`, which
`tests/architectural/test_exemption_registry_ratchet.py` forbids.

**The auto-rebase leg is a closed-list classifier rule.** ADR `2026-05-14-1`
already has a non-text-merge precedent: `R-UVLOCK-REGENERATE` handles a
generated file by regenerating it rather than merging text. A new rule
`R-PRIMARY-OWNED-BOOKKEEPING` takes its file pattern from the state-contract
predicate and resolves to the integrating side's copy. It is inserted before
`R-DEFAULT-MANUAL`, and the ADR gets an amendment.

**Scope of the classified set.** Only fully generated, "do not edit" surfaces
belong in it. Initially that is `.kittify/metadata.yaml`.

- `.gitattributes`, `.gitignore` and `.kittify/config.yaml` are
  operator-editable. A work package may legitimately change them, so a
  "target wins" rule there would silently drop real work. This is the #4933 /
  #4978 lesson: basename exemptions lost data.
- The already-diverged `.gitattributes` copies get a content-based,
  path-agnostic rule in the stale check instead. An overlap where the lane's
  blob equals the mission branch's blob cannot conflict and carries no semantic
  difference, so it is not staleness.

## 4. Structural fix shape (input to the spec; the plan decides the details)

1. **Write placement (source; removes the defect class).** Upgrade does not
   write, stamp or commit anything in a worktree whose checked-out branch
   integrates back into the primary branch, whether it is a mission, lane or
   coordination branch. Recognition goes through the branch-naming authority,
   `lanes/branch_naming.py::parse_mission_slug_from_branch`. Project-global
   state reaches those branches through integration from the repository root
   checkout, where upgrade writes it exactly once.
   - Commands run inside a worktree already resolve `.kittify` from the
     repository root checkout: `core/paths.py:197 locate_project_root`, the
     startup schema gate (`__init__.py:165-179`) and the compat planner
     (`planner.py:559-580`). A lane keeping its pre-upgrade copy is therefore
     harmless at runtime.
   - `--no-worktrees` already exists as a supported mode, so skipping
     worktrees is not new behaviour.
   - Worktrees on branches that do not integrate back keep today's behaviour.
   - Per the C6 guidance relayed by the operator, the runner change stays
     seam-shaped: worktree selection plus write placement. How upgrade
     computes and reports its result is not restructured.
2. **Classification (consumers; defence in depth plus recovery).** The four
   consumers above all consult the one state-contract predicate:
   - the stale check drops primary-owned paths and content-identical overlaps;
   - the squash gate restores the target's copy for primary-owned paths;
   - the auto-rebase classifier rule takes the integrating side's copy;
   - the dependency-lane merge goes through the same classifier.
3. **Recovery.** A project already in the broken state (per-branch
   `metadata.yaml` / `.gitattributes` commits from a pre-fix upgrade) heals on
   the next `consolidate` or lane sync, with no history rewrite and no
   destructive command. This gets a documented how-to plus a CHANGELOG entry.
   The stale-lane remedy must no longer print a no-op for this case.
4. **ADR work:**
   - a new ADR: upgrade writes project-global state once, and integrating
     branches never carry upgrade bookkeeping;
   - amend ADR `2026-07-07-1` (§Decision item 3: lane gitignore protection now
     arrives through integration, with the residual exposure window
     documented);
   - amend ADR `2026-05-14-1` to add the new rule.

## 5. Related set: dispositions

| Issue | Disposition | Reason |
|-------|-------------|--------|
| #5457 | **Fix (Closes)** | All three paths. |
| #4972 (closed; PR #5016) | Regression arm | Its tests are re-pinned. Its "version-only bump stays aligned" invariant survives for non-integrating worktrees. |
| #2385 / #2392 (closed) | Invariant preserved | No checkout is left dirty by upgrade, because integrating worktrees are no longer written at all. |
| #4892 (closed) | Preserved | The squash conflict gate is not weakened. The new allowance is anchored on exact registry paths, never `-X theirs`. |
| #5473 (closed NOT_PLANNED, QA) | **Refs** | It shares the source mechanism (the per-worktree upgrade commit). The write-placement fix removes it for future upgrades, including its `.gitignore`, `config.yaml` and `skills-manifest.json` legs. Recovery for an already-broken project with its modify/delete `skills-manifest.json` conflict is not covered, because that surface is not primary-owned bookkeeping. |
| #5673 | Cross-ref | It is about `implement` staging `.kittify/config.yaml` into the claim commit, with no upgrade involved. It shares only the theme. It should reuse the new predicate later, and it collides on `implement.py` with #5635. |
| #4925 / #4893 (C6) | Cross-ref | Exit status of upgrade. C6 is running separately. The shared file is `upgrade/runner.py`, but the cause is not shared: C6 is about result derivation, and this mission is about worktree write placement. |
| #702, epic #4807 | Out of scope | Codex skills manifest versus ignored payload; tool-surface projection honesty. Not observed being written into lanes in these scenarios. |
| #5229 | Cross-ref | `metadata.yaml` has two writers. Keep `ProjectMetadata.save()` as the single owner, and add no third writer. |
| #5539 | Cross-ref | Same `LANE_AUTO_REBASE_FAILED` call chain, but the cause is a missing lane branch. |
| #5443, #5151, #5292, #5434, #1838, #2491 | Cross-ref | Neighbouring seams (autocommit scope, the bookkeeping-dirt handoff, the meta.json merge driver, lane excludes, no-op timestamp churn, a third #2392 instance). |
| #5635 / #5634 / #5573 | Avoid | Sibling missions on `implement.py`, `mission_creation.py` and finalize lane computation. This mission does not touch those files. |
| Stale remedy after in-run rollback (general case) | **Follow-up** | For a genuine user-file overlap between two lanes, the printed `git merge kitty/mission-<slug>` is equally a no-op after the rollback. This mission removes the upgrade-induced trigger. The general remedy wording is a separate defect, and an issue will be filed for it. |

## 6. Test-suite findings (what missed it, and the remediation)

**Why the existing tests missed it:**

- Every upgrade-worktree test calls the private
  `MigrationRunner._upgrade_worktrees(v, [], …)` with an empty migration list
  on a fixture whose main is pre-stamped. So "main applies a migration and the
  worktree applies or skips it" is never exercised.
- `tests/upgrade/test_upgrade_worktree_commit.py:157-219`
  (`test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned`,
  assertion at `:211`) **pins the defect**. It asserts that the worktree stamp
  differs from main's.
- The per-worktree "spec-kitty upgrade" commit assertions
  (`test_upgrade_worktree_commit.py:91`, and around L176 in the #4972 test)
  pin the per-branch commit design.
- The consumer tests (`tests/lanes/test_merge.py`,
  `tests/integration/test_lane_lifecycle_sync.py`,
  `tests/consolidation/test_conflict_classifier.py`) never see
  `.kittify/metadata.yaml` or `.gitattributes`.
- The only real-CLI upgrade test (`tests/e2e/test_upgrade_post_state.py`) has no
  worktrees.

**Baseline:** 190 passed on the relevant files, with no pre-existing reds.

**Remediation:**

- Re-pin the two defect-pinning tests to the new invariant. Do not delete them.
- Add red-first tests for paths A, B and C through the real CLI (`run_cli`
  subprocess). Build the pre-upgrade state faithfully: commit an older
  `metadata.yaml` version so that real registered migrations detect and apply,
  and create real lane and coordination worktrees with git.
- Add focused unit tests for the predicate, the classifier rule, the stale
  rule and the squash reconciler.
- There is no old-CLI version-hop harness, and none will be built (see §7).

**Architectural gate files this implicates** (run these specifically, never the
whole directory):

- `test_exemption_registry_ratchet.py`
- `test_guard_capability_call_sites.py`
- `test_no_op_stable_writes.py`
- `test_no_dead_symbols.py`
- `test_migration_chain_integrity.py`
- `test_layer_rules.py`
- `test_merge_reconciliation_class_guard.py`, if any reconciler class is added

## 7. Assumptions and open points for the spec

- **The red tests use a simulated pre-upgrade state, not installed old CLIs.**
  An installed-CLI e2e test needs network access to PyPI in CI and a pinned old
  wheel. The faithful simulation reaches the same decision points through the
  same entry points: `spec-kitty upgrade`, `spec-kitty consolidate` and
  `spec-kitty agent action review`. The issue's verbatim shell reproducers were
  run against the real old wheels during grounding, as live evidence, and will
  be re-run against the fixed CLI before the PR.
- **Residual: lane gitignore exposure.** A lane worktree created before an
  upgrade does not see new `.gitignore` entries until it integrates. Lanes are
  short-lived, and the previous mechanism committed those entries on the lane
  (which caused this defect). The residual is documented in the ADR amendment
  rather than projected through `$GIT_COMMON_DIR/info/exclude`.

---

## Appendix A — reproducer lens

### Reproducer lens: #5457 (origin/main, new CLI 4.0.0rc6)
Profile: debugger-debbie loaded via `spec-kitty agent profile show`; charter context loaded (read-only, no repo edits, scratchpad only).
Venvs: repro/rc4 (4.0.0rc4), repro/v327 (3.2.7). Scripts (issue reproducers extracted verbatim): repro/pathA.sh, repro/pathB.sh; repro/pathC.sh (A variant, WP02 left at for_review, then probes review/implement).
Run: QA_WORK=<dir> bash pathA.sh <new> <old> [topology]; bash pathB.sh <new> <3.2.7>; bash pathC.sh <new> <rc4> lanes_with_coord

#### Verdict: REPRODUCES on all three paths.

##### Path A (rc4 -> rc6, lanes, 2 lanes): consolidate exit 1
last_upgraded_at: main ...47.138722, lane-a ...47.214485, lane-b ...48.464064 (each branch has own "chore: apply spec-kitty upgrade changes (4.0.0rc4 -> 4.0.0rc6)" commit)
Error: `Lane lane-b is stale: overlapping files ['.gitattributes', '.kittify/metadata.yaml']` (NOTE: .gitattributes too, not only metadata.yaml). Rollback follows; no work lost.

##### Path B (3.2.7 -> rc6, 1 lane, target work): consolidate exit 1
`TARGET_BRANCH_CONTENT_CONFLICT conflicting_path: .kittify/metadata.yaml` (lane merged into mission branch OK, squash into `work` refused); --resume repeats. (pathB.sh prints INCONCLUSIVE only because it greps skills-manifest; log shows the defect.)

##### Path C (lanes_with_coord, WP01 approved, WP02 for_review at upgrade): 
`agent action review WP02` => `Error: LANE_AUTO_REBASE_FAILED: no classifier rule matched .../.worktrees/uq-01M444WX-lane-b/.kittify/metadata.yaml` (lane_id lane-b, coordination_branch kitty/mission-uq-01M444WX). Commit "Start WP02 review": main [ok], coord branch [refused].
`agent action implement WP02` resume: blocked first by unrelated analysis_report_required gate (script did not record analysis); not separately verified. Consolidate on lanes_with_coord also refuses: lane-a stale on ['.gitattributes', '.kittify/metadata.yaml'].
Also: plain `lanes` topology has NO coord branch; lanes_with_coord adds a 4th upgraded branch (the coord branch kitty/mission-<slug>).

#### Files touched by the upgrade commit per branch (git show --stat)
- main (repo root): `.gitattributes` (+1: `kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index`), `.kittify/agent_profiles_manifest.json` (24 lines), `.kittify/metadata.yaml` (47 lines; all 8 4.0.0 migrations recorded). 3 files.
- each lane branch (lane-a, lane-b) AND the coord branch: only `.gitattributes` (+1, identical line) and `.kittify/metadata.yaml` (25 lines: own last_upgraded_at, own applied_at per migration, only subset of migrations recorded). 2 files each.
- Path B (3.2.7): work upgrade commit: .gitattributes, .kittify/metadata.yaml (51 lines); lane: .gitattributes, .kittify/metadata.yaml (25 lines). No agent command dirs/skills manifest/.gitignore touched in these scenarios.
- Diff lane-a vs lane-b metadata.yaml: only last_upgraded_at and every applied_at differ (plus notes identical). .gitattributes lines identical but both are add-of-same-line => file-overlap stale check trips (git itself would merge them cleanly).
- Mission branch (lanes topology, non-coord) was not upgraded (last commit "Add tasks...").

## Appendix B — root-cause lens

### Root-cause trace — #5457 (upgrade writes per-branch .kittify/metadata.yaml in live worktrees)

Lens: ROOT-CAUSE TRACER. Profile loaded: `debugger-debbie` (investigator; Five-Whys + Matrix-Maker paradigms
applied single-handed, no patch). Procedure applied: `procedure:disciplined-defect-diagnosis` (ranked,
falsifiable hypotheses; the issue's reproducer is the feedback loop, not re-run here: READ-ONLY).
Charter: `charter context --action implement` (single canonical authority, DIRECTIVE_024 locality, canonical sources).
Code: origin/main at HEAD (shallow history: 50 commits, so `git log -S` only finds the squash commit 2ad12729;
the provenance below comes from CHANGELOG.md and the code docstrings).

#### 1. Upgrade → worktrees: how and why

[HIGH] src/specify_cli/upgrade/runner.py:218-219 - `upgrade()` always fans out to `_upgrade_worktrees(...)` when
  `include_worktrees` (CLI default: `not no_worktrees`, cli/commands/upgrade.py:1838-1839), with
  `auto_commit=should_auto_commit_for_worktree(...)`. No-migrations path does the same at runner.py:158-159
  and cli/commands/upgrade.py:830-834 (`upgrade_worktrees_only`).

[HIGH] src/specify_cli/upgrade/runner.py:402,427 - WRONG DECISION POINT #1 (scope). Worktrees are enumerated by a raw
  filesystem scan of `.worktrees/*` (`sorted(worktrees_dir.iterdir())`), with no notion of topology, lane vs coord,
  or which branch the checkout holds. Every lane/coord checkout is treated as an independent *project* that owns
  its own copy of project-global state. Gate is only `has_upgradeable_state` (:431-434: `.kittify/` exists, or
  `kitty-specs/`/.specify exists).

[HIGH] src/specify_cli/upgrade/migrations/base.py:99 - `runs_on_worktrees: bool = True` is the DEFAULT. 102 of 121
  migration modules do not opt out. runner.py:397 filters `worktree_migrations`; :399 returns early only when there
  are migrations and none is worktree-eligible. rc5 has worktree-eligible ones (`m_4_0_0rc5_decision_index_merge_driver`,
  `m_4_0_0rc5_retire_bundled_dashboard`, `m_4_0_0rc5_retire_single_owner_doctrine_ids`), so every rc4→rc5 or
  3.2.7→rc5 upgrade visits every live worktree.

[HIGH] src/specify_cli/upgrade/runner.py:443-448 - each worktree loads ITS OWN `ProjectMetadata` from
  `<wt>/.kittify/metadata.yaml` (or synthesizes a fresh one with `initialized_at=now_utc()`), then:
  - :494-503 not-applicable → `_record_migration_result(..., "skipped", "Not applicable")` → new record, `dirty=True`;
  - :519-527 success → new record, `dirty=True`;
  - metadata.py:298 `record_migration(...)` stamps `applied_at=now_utc()` PER RECORD PER CHECKOUT, and
    `_record_migration_result` (runner.py ~:700) saves immediately.
  Effect: the migration-record SET differs (main runs all applicable migrations; the worktree runs only the
  `runs_on_worktrees` subset, and `detect()` can differ per checkout: "target lists eight, lane two"), and every
  `applied_at` differs. Timestamp alignment alone can never make the copies byte-identical.

[HIGH] src/specify_cli/upgrade/runner.py:618-625 (`_reconcile_worktree_bookkeeping`) - #4972 fix: aligns
  `last_upgraded_at` to main's value ONLY when `bookkeeping_only_bump` (`not worktree_metadata_dirty`). Any record
  written above makes it dirty → `now_utc()` fresh per worktree (:625). The docstring calls this "#2385
  preservation". It is a partial patch on one field of a file whose whole content diverges.

[HIGH] src/specify_cli/upgrade/runner.py:552-557,564-565 - saves the worktree metadata and stamps `schema_version`
  into the worktree copy (`_stamp_schema_version(wt_kittify, ...)`).

[HIGH] src/specify_cli/upgrade/runner.py:570-583 → upgrade/autocommit.py:351 `commit_touched_checkout(worktree, ...)` -
  WRONG DECISION POINT #2 (commit placement). Commits the worktree's churn ON THAT WORKTREE'S BRANCH (lane branch,
  coordination branch), as an independent "chore: apply spec-kitty upgrade changes" commit. The main checkout gets
  its own separate commit through the CLI finalizer (cli/commands/upgrade.py:1853 `should_auto_commit`). The result
  is N divergent commits of the same project-global path on N branches that consolidate later merges together.

##### Why upgrade touches worktrees (the invariant it is trying to keep)
- CHANGELOG.md:5088-5110 (#2392 epic, closes #2385/#1873): worktree migration churn was left UNCOMMITTED. A dirty
  coord/lane worktree tripped the `spec-kitty merge` worktree-dirty guard (#1826/NFR-002). The fix was to commit
  each worktree's churn on its own branch. autocommit.py:1-24 states the invariant: "every path an upgrade run writes
  or migrates, in every checkout it touches, must end in exactly one auto-commit".
- #1873/#1857: freshly synthesized worktree metadata must be persisted (self-healing when a worktree lacks it).
- CHANGELOG.md:362 (#4972): the second upgrade with an already-current CLI minted a fresh `last_upgraded_at` per
  worktree. Fixed only for the version-only bump.
- The premise "worktrees need migrating" predates lane worktrees being plain checkouts of tracked branches. The
  #2385 fix treated the SYMPTOM (dirty tree) by committing. It did not question whether project-global, tracked,
  primary-owned files should be written in lane/coord checkouts at all. Five-whys: consolidate refuses → branches
  carry divergent metadata.yaml → each worktree was upgraded and committed independently → the runner models a
  worktree as a project (`runs_on_worktrees=True` default + per-checkout ProjectMetadata) → there is no canonical
  "project-global / primary-owned path" classification that upgrade, the lane allocator or the merge gates consult.

#### 2. Consumer refusals: predicate and classification

[HIGH] src/specify_cli/lanes/stale_check.py:62-81 - predicate: `overlap = (git diff --name-only mb..mission) ∩
  (git diff --name-only mb..lane)`; non-empty → stale. Pure path intersection, no exemption list at all.
  `.kittify/metadata.yaml` changed on both sides (lane-a's upgrade commit, now on the mission branch; lane-b's own
  upgrade commit) → stale. Called from lanes/consolidation.py:294, which first tries
  `_try_auto_rebase_if_stale` (:209-228, :295) → auto-rebase (below) → Manual → stays stale → :303-310 error.

[HIGH] src/specify_cli/lanes/auto_rebase.py:435-473 `_resolve_managed_artifact_conflicts` - the only "managed"
  classes: `_is_status_events_path` (:183), `_is_status_json_path` (:192), `_is_coordination_owned_artifact` (:201-226:
  `is_coord_residue_churn` + `kind_for_mission_file` ∈ `_AUTO_REBASE_MANAGED_LAYOUT_KINDS`). All are
  `kitty-specs/<mission>/**`-scoped. `.kittify/metadata.yaml` falls to `remaining` → `classify()` (:760) →
  consolidation/conflict_classifier.py:556-565 `r_default_manual` "no classifier rule matched". The rules (:576 RULES)
  are pyproject deps, `__init__` imports, urls list, uv.lock, default-manual. No project-global rule.

[HIGH] src/specify_cli/lanes/lifecycle_sync.py:76-170 `sync_lane_after_coordination_commit` - merges the
  COORDINATION branch into the lane (`attempt_auto_rebase(mission_branch=coordination_branch)`, :155-161) at
  claims (cli/commands/agent/workflow.py:621-626, workflow_executor.py:327). On lanes_with_coord the coord worktree got
  its own upgrade commit → conflict on metadata.yaml → `LaneAutoRebaseSyncError` (:163-170). This also blocks
  implement/review, not just consolidate.

[HIGH] src/specify_cli/lanes/consolidation.py:973-1019 `_run_squash_merge` (called via `integrate_mission_into_target`
  :329-424, from consolidation/phase_advance.py:552-563; rendering :458-480). The executor.py:~1187 cited in the
  issue moved here. Predicate: `git merge --squash` leaves unmerged paths → `_resolve_planning_conflicts` (:908-971,
  `planning_recency.target_newer_primary_artifacts`, `kitty-specs/**` PRIMARY planning kinds only) →
  `reconcile_derived_status_snapshot_conflicts` (status.json only) → anything left → `_SquashMergeConflict` →
  `TARGET_BRANCH_CONTENT_CONFLICT` (consolidation/_constants.py:29). Since #4892 removed `-X theirs`, main's
  metadata.yaml commit vs the mission branch's (via the lane) is a hard refusal.

[MED] src/specify_cli/lanes/consolidation.py:61-133 `_MERGE_DRIVERS` - the canonical merge-driver registry covers only
  `kitty-specs/**` bookkeeping (status.events.jsonl, decisions.events.jsonl, meta.json, traces, acceptance-matrix,
  issue-matrix, review-cycle, decisions/index.json). No `.kittify/**` entry. The repo `.gitattributes` only marks
  `.kittify/workspaces/**`, `.kittify/migrations/**` linguist-generated/-diff.

[MED] src/specify_cli/consolidation/bookkeeping_projection.py:47-120 and coordination/coherence.py:161
  (`is_coord_residue_churn`) - both are mission-scoped (status files, coord residue kinds). Nothing classifies
  project-global paths.

[HIGH] src/specify_cli/state/contract.py:118-137 `STATE_SURFACES` - the CLOSEST CANONICAL LIST that exists:
  `project_config` `.kittify/config.yaml` and `project_metadata` `.kittify/metadata.yaml`, both
  `root=StateRoot.PROJECT, authority=AUTHORITATIVE, git_class=TRACKED, owner_module="init/upgrade"`. It has
  no axis for "primary-owned / must not diverge across lane branches", and none of the consumers (stale check, auto-
  rebase, squash gate, merge drivers) nor upgrade consult it. This is the natural single authority to extend, rather
  than adding a fifth hand-kept path list. CHANGELOG.md:778 shows the hand-kept-list drift history (#2491/#3686).

#### 3. The printed stale remedy (`git merge kitty/mission-<slug>`) and why it is a no-op

[HIGH] src/specify_cli/lanes/stale_check.py:84-120 `_stale_remediation` - assumes the overlap is real content the
  lane is missing from the mission branch, and that merging the mission branch into the lane advances the merge-base.
[HIGH] src/specify_cli/consolidation/phase_advance.py:238-249 + executor.py:422 - the overlap only exists against a
  TRANSIENT mission tip. In the same consolidate run, lane-a was merged into the mission branch (:238), then lane-b
  was found stale, and `raise typer.Exit(1)` (:249) → `rollback_to_snapshot` (executor.py:422; the #5385 single
  rollback door) restores the mission branch to its pre-run tip. That tip is an ancestor of lane-b (lane-b was cut
  from it), so the operator's `git merge kitty/mission-<slug>` prints "Already up to date". The next consolidate
  re-merges lane-a, re-creates the same overlap, and loops forever. The remedy text never names lane-a's
  contribution, and a mid-run, rolled-back state is not something the operator can act on.
[LOW] stale_check.py:117-120 - `cd .worktrees/*-{lane_id}` glob is ambiguous when several missions have a lane
  with the same id (side note, not the #5457 cause).

#### 4. Is `.kittify/metadata.yaml` meant to be on lane branches?

[HIGH] src/specify_cli/coordination/workspace.py:395-423 `lane_sparse_checkout_patterns` - lane sparse checkout is
  `/*` minus only `kitty-specs/<mission>/status.events.jsonl` and `status.json`. And it is registered only for
  coord topologies (lanes/worktree_allocator.py:1664-1687). So lane worktrees materialize the full tree, including
  `.kittify/metadata.yaml`, `.kittify/config.yaml`, `.kittify/charter/**`, `.gitignore`, `.gitattributes`, agent dirs.
[MED] src/specify_cli/core/worktree.py:592 - `info/exclude` only `.kittify/memory`, `.kittify/AGENTS.md` (legacy
  symlink guard, #79). Nothing excludes metadata.yaml.
=> It is tracked (state/contract.py: TRACKED) and inherited on every branch at its fork point, but nothing in the
  lane model ever has a reason to MODIFY it on a lane. The only writer on a lane branch is upgrade's worktree fan-out.
  It is de facto primary-owned project state that happens to be visible in lane checkouts.

#### Set of project-global paths upgrade can write (and commit) inside lane/coord worktrees
Always (runner itself): `.kittify/metadata.yaml` (version, last_upgraded_at, migrations[].applied_at/result, and
  `spec_kitty.schema_version` stamp; also `initialized_at` when synthesized).
Via worktree-eligible migrations (runs_on_worktrees default True; examples):
- `.gitignore`: gitignore backfills (m_3_2_3, m_3_2_4 x2, m_3_2_5, m_3_2_6rc3 x2, m_3_2_0rc35_sync_state_gitignore)
- `.gitattributes` (+ shared local git config): merge-driver migrations (m_3_1_1_event_log, m_3_2_6_* drivers,
  m_3_2_7_review_cycle, m_4_0_0rc5_decision_index_merge_driver, m_3_2_0rc28_github_diff_attributes)
- `.kittify/config.yaml`, `.kittify/charter/**`: m_3_2_0rc35_{charter_bundle_v2, default_charter_pack,
  strip_selection_config, activate_builtin_mission_types, charter_manifest_defaults_repair}, m_unify_charter_activation,
  m_3_2_6_retire_rtk_search_tooling, m_4_0_0rc5_retire_single_owner_doctrine_ids, m_3_1_1_charter_rename
- agent command dirs / `.agents/skills/**` / `.kittify/command-skills-manifest.json`: m_3_0_2/m_3_1_1/m_3_1_2/
  m_3_2_0a4 command globalization, m_3_2_0rc35_{codex_to_skills, spk_skill_pack, pi_letta_backfill,
  kittify_profile_handoff}, m_3_2_0rc43/rc45 retirements, m_4_0_0rc5_retire_bundled_dashboard (also deletes
  `.kittify/.dashboard`, `.kittify/preflight-warning.json`)
- `.kittify/templates`/mission templates: m_3_2_0rc35_update_planning_templates, m_3_0_0_canonical_context
NOT in worktrees: surface repair / manifest repair (cli/commands/upgrade.py:398-485 run on project_path only) and all
  modules with `runs_on_worktrees = False` (19, e.g. provision_kitty_env, session_presence, lane_tip_recorder).
Only metadata.yaml is GUARANTEED to diverge (per-checkout timestamps + records). The others diverge when the
  migration's output depends on the checkout state or ordering. Identical edits merge cleanly but still trip the
  path-intersection stale check if git sees both sides changed with different content.

#### Wrong decision points (summary)
1. runner.py:397/402-427 + base.py:99: upgrade treats each lane/coord worktree as an independently-upgradable
   project (`runs_on_worktrees=True` default, fs scan, no topology/ownership filter).
2. runner.py:443-565: per-worktree ProjectMetadata is recorded with per-checkout `applied_at`/records/`last_upgraded_at`
   (only the version-only bump is aligned by #4972, runner.py:618-625).
3. runner.py:570-583 / autocommit.py:351: the churn is committed on the lane/coord branch instead of being kept
   off lane branches (primary-owned path), or made byte-identical to main's committed copy.
4. Consumers (stale_check.py:62-81, auto_rebase.py:435-473 → conflict_classifier.py:556, consolidation.py:973-1019,
   _MERGE_DRIVERS :61) have no classification for project-global/primary-owned paths. state/contract.py:118-137 is the
   only registry of those paths and nothing consults it for merge/stale decisions.
5. stale_check.py:84-120: the remediation is computed against a mid-run mission tip that rollback (phase_advance.py:249
   → executor.py:422) erases, so it is unactionable ("Already up to date").

## Appendix C — related-issue lens

### Related-issue grounding for #5457 (read-only; GitHub MCP, spec-kitty/spec-kitty; 2026-10-04)

Profile applied: researcher-robbie (investigate, synthesize, no decisions/no production code). Charter context for `specify` loaded (output truncated at head -80; not re-quoted). No GitHub writes made.

#### Core mechanism (from #5457 body + 4 comments)
`upgrade` runs the migration runner per live worktree (`upgrade/runner.py::_upgrade_worktrees`), then auto-commits every touched checkout on ITS OWN branch (`upgrade/autocommit.py::commit_touched_checkout`). Project-global, generated, "do not edit" files (.kittify/metadata.yaml: last_upgraded_at, applied_at, migration set; also .gitignore, config.yaml, skills-manifest.json for 3.1.x) therefore diverge per branch. Consumers that then refuse: stale-lane check (lanes/consolidation.py:293 / stale_check.py), #4892 squash gate (consolidation/executor.py:1187), lane auto-merge of dependency lanes in implement, and (round-22 comment) lane sync after coord lifecycle commits -> lanes/auto_rebase.py:445-458 -> consolidation/conflict_classifier.py:556-566 "no classifier rule matched" => LANE_AUTO_REBASE_FAILED. Verified workaround: `git checkout main -- .kittify/metadata.yaml` + commit in coord and each lane.
Prior fixes were symptom/partial: #2385/#2392 (add per-worktree commit; PR #2387), #4972 (PR #5016: align last_upgraded_at to main only when worktree write is version-bump-only; "downstream consumers deliberately untouched"). #5016's own premise (prevent at mint site) is exactly what #5457 shows is insufficient: any non-applicable migration `skipped` record (runner.py:494-503) or success record re-dirties the worktree with its own applied_at.

#### Classification table

| # | Title (short) | State | Mechanism (one line) | Class | Reason |
|---|---|---|---|---|---|
| 5457 | upgrade writes metadata.yaml per branch; consolidate refuses | OPEN P1 | per-worktree migration pass + per-branch autocommit of project-global metadata.yaml | SUBJECT | + round-22 widening: LANE_AUTO_REBASE_FAILED on coord missions |
| 3347 | Epic: upgrade/migration atomicity & recoverability | OPEN | parent epic of #5457, #5473, #4925, #4893, #5229 | CROSS-REF (parent) | Mission should link as child; not itself fixable |
| 2392 | Epic: upgrade-worktree coherence (canonical seam) | CLOSED | invariant: every path upgrade writes, in every checkout, ends in exactly one commit | CROSS-REF (invariant source) | #5457 violates the spirit: N commits of the same generated file with N values. Its "fix-once at the seam" discipline applies: do not add a 3rd point-patch |
| 2385 | upgrade leaves sibling worktrees dirty | CLOSED (PR #2387) | no commit step in worktrees -> dirty -> merge refuses | CROSS-REF (regression guard) | Fix created the per-branch commit that #5457 now trips on. Any new design must keep worktrees clean (do not regress #2385) |
| 4972 | second upgrade stamps each worktree with own last_upgraded_at | CLOSED (PR #5016) | same file, same consumers (implement dependency-lane auto-merge, stale-lane) | FOLD IN (as regression arm) | Direct predecessor; fix only covers version-only path. Reuse its regression test file `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py` and `test_upgrade_worktree_commit.py`; extend, don't duplicate. 4972 comment also records the "teammate pulls upgraded main" variant (current_version==target) which must stay covered |
| 4892 | squash `-X theirs` silently reverts target | CLOSED (PR #4942) | merge squash resolved conflicts in favor of mission | CROSS-REF | Correct fix; it is WHY path B now hard-refuses (TARGET_BRANCH_CONTENT_CONFLICT). Do NOT weaken it to unblock #5457; fix the divergence source. Possible secondary option (treat generated bookkeeping as take-target in the gate) must be bookkeeping-path-allowlisted only |
| 5473 | 3.1.x upgrade untracks skills-manifest.json on target, commits it on lane | OPEN P2 | `m_3_2_5_agents_skills_gitignore_backfill._untrack_tracked_paths` does `git rm --cached` on main; lane pass re-writes + autocommits the file as tracked; 4 conflicting paths (.gitignore, config.yaml, metadata.yaml, skills-manifest.json) | **FOLD IN (decision)** | Same root cause: per-lane migration pass + per-branch autocommit of project-global files. Its issue text already assigns the metadata.yaml part to #5457. A structural fix (do not run project-global migrations / do not commit project-global paths in lane worktrees; sync lane to target state instead) closes all four paths. A metadata.yaml-only merge driver or classifier rule would NOT (modify/delete on skills-manifest.json cannot be union-merged). Make the 3.1.10->rc5 repro (`repro_upgrade_31x_merge_skills_manifest_conflict.sh`, 3.1.10 legacy binary) an acceptance arm; if the design must be limited, then downgrade to CROSS-REF and say explicitly that fix must be path-generic. Note it is a different *trigger* (a migration that untracks) so keep it as a separate test arm |
| 5673 | implement (single_branch root) claim commit sweeps operator's uncommitted .kittify/config.yaml | OPEN P1 | `_commit_wp_claim_status` (implement.py:1695,1715) unconditionally stages config.yaml; `_owned_status_prefixes` (implement_support.py:55-72) exempts whole `.kittify/` from dirty scan | **CROSS-REF (not fold)** | Different mechanism: no upgrade, no lane/coord worktree, no divergent branch copies; it is "claim commit stages a project-global file" (user-data-preservation epic #4915). Shares only the theme "project-global .kittify state in a lane/claim commit". Also lives in implement.py/implement_support.py which sibling #5635 is refactoring -> high merge-conflict risk if folded. Route to its own mission after/with #5635. Worth one design note: if #5457's fix introduces a "project-global path set" constant, #5673 should consume it (single canonical list), so land the constant first |
| 5001 | Epic: merge/coord integrity | OPEN | umbrella for terminus failures | CROSS-REF (parent of 4972/4892) | #5457 is parented under #3347 (not #5001) but its consumers are #5001 territory |
| 4893 | upgrade from 3.2.0 reports "Upgrade failed." (finalizer fingerprint vs own provisioning write) | OPEN P1 | upgrade finalizer fingerprints config.yaml, then its own provisioning step writes it; round-5 comment noted divergent per-checkout upgrade commits wedging implement on 3.2.0->rc5 "not filed separately" | CROSS-REF | Different primary defect (in-checkout write ordering). Only its round-5 comment overlaps (.gitignore, lanes.json, status.json divergence per checkout) = same family as #5457; verify structural fix also covers those paths, but do not fold |
| 4925 | `upgrade --yes` exits 1 on no-op | OPEN P1 | exit code not tied to outcome | OUT OF SCOPE | Exit-code honesty; no worktree/branch component. Same epic only |
| 702 | Codex .agents/skills drift vs manifests/docs | OPEN P3 | tracked manifest lists files under ignored .agents/ | OUT OF SCOPE | Manifest-vs-ignored-payload policy question, not lane divergence. (Adjacent to #5473 only through the "tracked skills manifest whose payload is ignored" policy; no action) |
| 4807 | Epic: tool-surface projection honesty | OPEN P2 | repair/projection reports success without converging; split authority (orientation refresh x3) | OUT OF SCOPE | Same "one authority per surface" philosophy but no lane component. Sibling #5215 (orientation split-brain) likewise out of scope |
| 5635 | Refactor cli/commands/implement.py hotspot (2,304 LOC) | OPEN P1, assignee stijn | investigate+refactor implement.py: workspace resolution, lane allocation, implement_support, claim, auto-rebase | CROSS-REF (file collision) | Touches implement.py + lanes/implement_support.py + auto-rebase phase. #5457 round-22 consumer path (workflow_executor.py:890/1075/1794 -> lifecycle_sync -> auto_rebase) is adjacent. Keep #5457 fix OUT of implement.py; fix at upgrade/ + lanes/auto_rebase.py / conflict_classifier.py level to avoid conflicts. Coordinate sequencing with operator |
| 5634 | Refactor core/mission_creation.py hotspot | OPEN P1, assignee stijn | topology/protected mint/retention/scaffold | OUT OF SCOPE (no file overlap) | #5457 never touches mission_creation.py. Only note: tests that create missions via this seam should not be edited by #5457 |
| 5573 | finalize-tasks re-run moves in-progress WP to another lane; exit 0 | OPEN P1 | `_assign_stable_lane_ids` (lanes/compute.py:505-560) tie-break; mission_finalize.py:3329/1690; worktree_allocator.py:435-525 | OUT OF SCOPE | Lane-identity under re-finalize, no upgrade/project-global-file angle. File overlap with #5457 limited to lanes/worktree_allocator.py (only if #5457 touches allocation; it should not). Parent #1795 |
| 5539 | agent action implement LANE_AUTO_REBASE_FAILED for first WP of re-finalize-minted lane | OPEN P2 | lifecycle_sync runs `git worktree add <lane_branch>` for a never-allocated lane | CROSS-REF | Same error code and same call chain (`sync_lane_after_coordination_commit` -> auto_rebase) as #5457's round-22 widening but different cause (missing lane branch). Test fixtures for LANE_AUTO_REBASE_FAILED can share helpers; fix is independent. Beware the same function (lanes/lifecycle_sync.py) if #5457 adds an upgrade-bookkeeping skip there |
| 5443 | upgrade of 2.x project commits ALL uncommitted work into schema-v3 migration commit | OPEN P1 | upgrade autocommit sweeps non-upgrade paths | CROSS-REF | Same seam (`upgrade/autocommit.py::prepare_upgrade_commit_files` / `commit_touched_checkout`) but opposite defect: commits too much on main. If #5457 changes the commit-set computation, make sure it moves toward "only paths the run changed" (derived from actual writes), which also serves #5443. Do not fold (different trigger, main checkout) |
| 5472 | 3.0.x upgrade ignores per-WP branches; lanes rebuilt from slug only | OPEN P1 | migration/mission_state.py `_rebuild_lanes_if_wedged` | OUT OF SCOPE | Legacy-branch carry-over; distinct. Also needs #5470/#5471 workarounds first |
| 5470 | 3.0/3.1 upgrade creates a charter.yaml the project never had | OPEN P1 | upgrade manufactures charter file; implement then fails | OUT OF SCOPE | Not branch-divergence. (Noted in #5473 as not affecting that flow) |
| 5434 | Lane worktrees never get .spec-kitty/ exclude (per-worktree info/exclude not read by git) | OPEN P1 | exclude writer targets wrong info/exclude; leftover review-lock dirties lane | CROSS-REF | Related to "project-global/generated state appears in lane worktrees"; includes proposed migration writing common-dir exclude. If #5457 touches how upgrade treats lane worktrees, avoid conflicting changes in `lanes/worktree_allocator.py` |
| 5229 | metadata.yaml has two uncoordinated writers (migration/runner._update_schema_version vs ProjectMetadata.save) | OPEN P2 | non-atomic, shape-divergent writers of the same file | CROSS-REF (strong) | Same FILE; if #5457's fix funnels metadata.yaml writes through one place, #5229's single-owner/atomic-write intent should be respected (and could be closed by the same change if scope allows). Do not fold: different symptom (schema_version/capabilities), main checkout only |
| 5292 | Align .gitattributes meta.json merge-driver glob (#4933) | OPEN P2 | merge-driver glob vs anchor | CROSS-REF | Establishes the merge-driver pattern. Issue #5457 notes "No merge driver covers .kittify/metadata.yaml" -- a merge driver is one candidate fix; weigh vs. not diverging at all. Merge driver cannot cover modify/delete (skills-manifest) |
| 5151 | move-task refuses lane handoffs after planning branch moves; one dirty repo-root file blocks every WP | OPEN P1 | claim-time kitty-specs merge drift / dirty repo-root file | CROSS-REF (weak) | "generated/bookkeeping dirt blocks lifecycle" family; planning-branch drift, not upgrade. PR #5326 (draft) targets it |
| 4933/4978 | merge destroys uncommitted meta.json / kitty-specs bookkeeping (dirty preflight exemptions) | CLOSED | preflight exempts bookkeeping basenames then reset --hard | OUT OF SCOPE | Cautionary precedent: classifying by basename/"is bookkeeping" has bitten. If #5457 adds a "generated bookkeeping" allowlist for classifier/stale check, anchor by exact path (.kittify/metadata.yaml), never basename |
| 2491 | upgrade auto-commit runs before surface repair, leaving post-commit writes dirty (breach of #2392) | CLOSED | commit ordering in finalizer | CROSS-REF | Third prior instance of the #2392 invariant breaking; supports "fix at seam, add invariant test" |
| 1838 | timestamp-only churn on no-op upgrades | OPEN (per #4972) | no-op save gate | CROSS-REF | #5016 extended this gate; a clean fix likely extends it again (don't bump last_upgraded_at / don't record skipped rows in worktrees) |
| 2412, 4888, 3398, 1063, 4619 | skills symlink/skills-manifest hygiene; safe_commit stash; abs paths in committed reports; clutter | CLOSED | assorted generated-file hygiene | OUT OF SCOPE | Swept; no shared mechanism with lane-branch divergence |
| 5016 (PR) | #4972 fix | MERGED 2026-09-25 | see above | CROSS-REF | 22 files; runner.py helpers `_reconcile_worktree_bookkeeping`, `_aligned_worktree_timestamp` are the code to generalize |
| 5326, 5694 (open PRs) | #5151 handoff provenance (draft); #5193 pack skills slices 0+1 | OPEN | | OUT OF SCOPE | Only open PRs matching upgrade/metadata/implement/finalize queries; 5694 adds skill kind projected into project skill roots -- could add new project-global writes the upgrade/lane pass must treat the same way (watch only) |

#### Direct decisions requested
- **#5673: CROSS-REF, not fold.** Different trigger (implement claim, single_branch, no upgrade, no divergent copies). Collides on implement.py/implement_support.py with #5635. Only shared artefact worth coordinating: a single canonical "project-global .kittify paths" constant, if #5457 introduces one.
- **#5473: FOLD IN as a second acceptance arm**, conditional on the fix being structural/path-generic (lane worktrees must not own committed copies of project-global files the upgrade changes). It is a child of the same epic (#3347), carries the same two code sites (runner._upgrade_worktrees + autocommit.commit_touched_checkout), and its remaining non-metadata conflicts (.gitignore, config.yaml, skills-manifest.json modify/delete) are unreachable by any metadata.yaml-specific fix. If the chosen design is metadata.yaml-specific, keep #5473 open as CROSS-REF and say so in the spec.

#### Sibling-mission file footprint (collision map)
- #5635: src/specify_cli/cli/commands/implement.py, lanes/implement_support.py, workspace/context.py (resolve_workspace_for_wp), lane allocation, claim, auto-rebase phase (assignee stijn-dejongh, P1, 4.0.0 scope).
- #5634: src/specify_cli/core/mission_creation.py (+ tests monkeypatching it).
- #5573: lanes/compute.py (_assign_stable_lane_ids), cli/commands/agent/mission_finalize.py (:3329, :1690), lanes/worktree_allocator.py (:435-525).
- #5673 (not requested but relevant): implement.py:1695/1715, lanes/implement_support.py:55-72.
- #5457 likely footprint: upgrade/runner.py (:374,:494-527,:570-583,:618-625), upgrade/autocommit.py (:301-375), possibly lanes/auto_rebase.py:445-458, consolidation/conflict_classifier.py:556-566, lanes/stale_check.py / lanes/consolidation.py:293, lanes/lifecycle_sync.py, consolidation/executor.py:1187-1195 (reading only). Overlap risk: lanes/worktree_allocator.py (5573, 5434), lanes/lifecycle_sync.py (5539), implement chain (5635).

#### Gaps / caveats
- Issue #5457 original (pre-rewrite) body not read (edit history unavailable via MCP). `gh` CLI returned non-JSON (auth/proxy), MCP used instead.
- PR #5016 file list (22 files) was too large to read; touched files inferred from description.
- Semantic search results were noisy (labels dominate); reviewed titles/labels for ~60 hits, opened bodies only for the issues above. Did not open #5443, #5151, #5539 comments, #5575/#5574 (closed upgrade exit/consent bugs: out of scope on title).

## Appendix D — architect lens

### #5457 — Architect lens (architect-alphonso), pre-spec grounding

Repo: spec-kitty @ 9adc6880 (origin/main; history is grafted to 50 commits, so
`git log -S` cannot reach #2385/#2392/#4972 — provenance below is taken from in-code
citations and the regression tests that pin them). READ-ONLY.

#### Doctrine applied
- `spec-kitty agent profile show architect-alphonso`: design/boundaries/ADRs, no implementation.
- `spec-kitty charter context --action plan`: DIRECTIVE_001 (architectural integrity / separation of
  concerns), DIRECTIVE_003 (decision documentation → ADR), DIRECTIVE_024 (locality of change),
  DIRECTIVE_031/032 (context-aware design, conceptual alignment: name the sense of "primary"),
  DIRECTIVE_037 (living docs sync).
- Charter §Governing Principles, "Single canonical authority" (.kittify/charter/charter.md:46-50):
  extend/reference the existing owner rather than add a second authority; prefer
  require-canonical + migration over fallback branches.
- Glossary senses used precisely: **repository root checkout** (docs/context/execution.md:258, Sense C),
  **lane** / lane worktree (orchestration.md:162), **coordination worktree/branch**,
  **PRIMARY partition** (orchestration.md:541, Sense A — NOT relevant here: `.kittify/metadata.yaml`
  is not a mission artifact kind at all), **target branch**, **lane consolidation** (orchestration.md:567)
  vs **branch integration** (squash mission→target).

#### Defect mechanics (confirmed in code)
- Worktree pass: `MigrationRunner._upgrade_worktrees` (src/specify_cli/upgrade/runner.py:374-578)
  iterates every `.worktrees/*` dir (:427), loads/synthesizes a **per-worktree** `ProjectMetadata`
  ledger (:443-450), runs every migration with `runs_on_worktrees` (default **True**,
  src/specify_cli/upgrade/migrations/base.py:99 — ~101 of 121 migrations inherit it; only one
  sets it explicitly True: m_3_3_0_op_record_schema_v2.py:240), saves the worktree's
  `.kittify/metadata.yaml` (:556), stamps schema_version (:563), then
  `autocommit.commit_touched_checkout(worktree, ...)` commits it **on that worktree's own branch**
  (:568-578). Called from both CLI paths (src/specify_cli/cli/commands/upgrade.py:815-833 no-migrations
  path; :1828-1840 migrations path) with `auto_commit=should_auto_commit_for_worktree(...)`.
- `metadata.yaml` is tracked (`git ls-files .kittify` lists it) and is structurally guaranteed to
  diverge bytewise per checkout: per-record `applied_at` timestamps, `notes`, `environment.platform*`
  (see the repo's own .kittify/metadata.yaml), a worktree-only ledger of skipped/failed records.
  #4972's `_reconcile_worktree_bookkeeping`/`_aligned_worktree_timestamp` (runner.py:581-647) only
  aligns `last_upgraded_at`; it cannot make the copies byte-identical, and it cannot help the
  stale-lane check at all because that check intersects **file names**, not content.
- Consumers that refuse (four, not three):
  1. Stale-lane check — `check_lane_staleness` (src/specify_cli/lanes/stale_check.py:31-83): pure
     `git diff --name-only` intersection, no path-class filter whatsoever. Called in
     `consolidate_lane_into_mission` (src/specify_cli/lanes/consolidation.py:294-309) after
     `_try_auto_rebase_if_stale` (:209-228).
  2. Squash TARGET_BRANCH_CONTENT_CONFLICT — not in executor.py: raised by `_run_squash_merge`
     (lanes/consolidation.py:973-1019) → `_SquashMergeConflict` → `integrate_mission_into_target`
     (:386-407) tags `TARGET_BRANCH_CONTENT_CONFLICT`; rendered by
     consolidation/phase_advance.py:465-479; forecast by consolidation/forecast.py:205-217 via
     `preview_mission_target_integration` (lanes/consolidation.py:1022). The only pre-conflict
     reconcilers are `_resolve_planning_conflicts` (:908-970, PRIMARY planning recency) and
     `reconcile_derived_status_snapshot_conflicts` (:855) — neither knows `.kittify/`.
  3. Lane auto-rebase — `attempt_auto_rebase` (lanes/auto_rebase.py:931): managed-artifact pre-pass
     `_resolve_managed_artifact_conflicts` (:435-473) only covers status files and
     `_is_coordination_owned_artifact` (:201-226, mission-kind based via `kind_for_mission_file`, so
     `kitty-specs/**` only); everything else falls to `conflict_classifier.classify` →
     `r_default_manual` "no classifier rule matched" (consolidation/conflict_classifier.py:556-583).
  4. (Not in the issue, same root cause) implement's dependency-lane tip merge
     `_merge_dependency_lane_tips` (lanes/worktree_allocator.py:1529, fail-closed on conflict, #1915);
     the #4972 test docstring already names "implement's dependency-lane auto-merge conflict".

#### Q1 — Which authority should own "project-global upgrade bookkeeping"?

**Existing, fragmented `.kittify/` classifications (evidence of drift, not candidates to add to):**
| Site | Shape | Purpose |
|---|---|---|
| coordination/coherence.py:56 `is_self_bookkeeping_churn` | function-local regexes: `.kittify/meta.json`, `.kittify/encoding-provenance/global.jsonl`, `.kittify/mission-state-audit`, kitty-ops, mission meta.json | dirty-state "ignore" — declared THE owner |
| coordination/coherence.py:278 `is_toolchain_generated_churn` | union of the above + coord residue | "single definition (FR-012)", "adding a ninth per-gate list is the regression C9 refuses" |
| consolidation/reconciliation.py:1166-1243 `_is_bookkeeping` | whole repo-root `.kittify/` prefix (:1241) | squash blob-attribution axis; deliberately does NOT delegate to coherence (docstring :1170-1185) |
| consolidation/conflict_resolver.py:66-110 `classify_conflict` | `.kittify/*.json` → OWNED_METADATA; `.kittify/derived|runtime` → UNEXPECTED_DERIVED | legacy T040 resolver |
| lanes/for_review_gate.py:127 `_KITTIFY_PREFIX` | `.kittify/` | for_review status-only exclusion |
| lanes/implement_support.py:75 | `.kittify/` | single_branch dirty scan |
| cli/commands/agent/tasks_shared.py:114 `_RUNTIME_STATE_DENY_LIST` | `.kittify/`, `.spec-kitty/` | runtime-state deny list |
| mission_runtime `kind_for_mission_file` / placement seam | `kitty-specs/<slug>/…` only | has NO notion of `.kittify/`; artifact-placement-seam.md is mission-scoped |
| lanes/consolidation.py:61 `_MERGE_DRIVERS` | `kitty-specs/**` patterns | git merge drivers; ephemeral in squash only, deliberately NOT active in auto-rebase (:512-560) |

**Recommendation:** extend the declared owner, `specify_cli.coordination.coherence`, with ONE
new, repo-root-anchored, depth-exact predicate — e.g. `is_project_global_upgrade_bookkeeping(path)`
matching exactly `^\.kittify/metadata\.yaml$` (and any other file an upgrade run itself rewrites as
ledger, decided in spec — NOT the blanket `.kittify/` prefix: `.kittify/config.yaml`,
`.kittify/charter/**`, doctrine overlays are tracked operator/WP-authorable content and a charter
or doctrine WP may legitimately change them). Compose it into `is_self_bookkeeping_churn` (so dirty
gates inherit it) and expose it standalone for merge-side consumers. Reasons:
- coherence.py is already THE owner for "spec-kitty's own bookkeeping files" and already carries
  three `.kittify/` legs; the R-014/anti-ninth ratchet
  (tests/architectural/test_exemption_registry_ratchet.py:1-40, scanned surfaces :100-117 include
  `lanes/consolidation.py` and `lanes/auto_rebase.py`) will RED any new module-level filename
  frozenset/tuple/regex placed in those consumers and names `is_toolchain_generated_churn` as the
  supported route. Follow coherence's function-local-literal pattern (coherence.py:108-113).
- Not mission_runtime/placement seam: that seam classifies `MissionArtifactKind`s under
  `kitty-specs/<slug>/`; metadata.yaml is project-scoped, not a mission artifact. Not kernel/paths:
  kernel holds path primitives, not toolchain-ownership policy.
- Not conflict_classifier RULES: that module is a pure content-merge rule set governed by ADR
  2026-05-14-1 (pyproject/`__init__`/urls/uv.lock). A path-ownership verdict belongs in the
  orchestrator's managed-artifact pre-pass, which is exactly where status/coord-owned artifacts
  are already handled (auto_rebase.py:435-473).

**One rule, one resolution policy, four consumers.** The classification is "owned by the repository
root checkout; a lane/coordination/mission branch's change to it is never WP content". Merge policy
falls out of the direction of integration: **the integration-target side wins** (the side closer to
the repository root checkout):
1. stale_check: drop classified paths from `overlap` before deciding staleness (stale_check.py:72).
2. squash (`_run_squash_merge`/preview): restore classified paths to the **target** blob — both on
   conflict and unconditionally (mirrors `_preserve_target_newer_planning_artifacts`,
   lanes/consolidation.py:752) so lane-born bookkeeping never lands on target.
3. auto-rebase (merge mission → lane): take-theirs arm in `_resolve_managed_artifact_conflicts`
   (extend `_is_coordination_owned_artifact` or add a sibling arm calling the owner predicate).
4. dependency-lane tip merge / lane→mission merge: same take-target-side resolution.
A small resolution helper ("restore owner-classified paths to <ref>") should be shared by 2-4 so the
policy is not re-implemented three times.

#### Q2 — Where the structural fix belongs

**Upgrade should write project-global bookkeeping exactly once, on the repository root checkout.**
Doctrinal anchor: docs/architecture/branch-target-routing.md:33-56 — "Work-package code stays in an
isolated lane branch… Only the work packages assigned to that lane write code here"; the
coordination branch holds coordination-owned bookkeeping; "Everything else … resolves to the
mission's target branch". The worktree pass makes a non-WP actor commit project-global state onto
lane and coordination branches — a branch-target-routing violation.

What #2385/#2392/#4972 protected:
- #2392 invariant (src/specify_cli/upgrade/autocommit.py:1-23): every path an upgrade run writes,
  in every checkout it touches, ends in exactly one auto-commit, so the merge worktree-dirty guard
  (#1826/NFR-002) never trips. It is a *consequence-of-writing* invariant: if upgrade stops writing
  into worktrees, it holds vacuously. Pinned by tests/upgrade/test_upgrade_worktree_commit.py and
  tests/architectural/test_guard_capability_call_sites.py:54-58 (UPGRADE_BOOKKEEPING allowed only
  from autocommit.py — unaffected).
- #1873/#1857: self-healing synthesized worktree metadata (runner.py:452-455) — only needed because
  a per-worktree ledger exists.
- #4972 (tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py:1-17): alignment of
  `last_upgraded_at` across main/coord/lane to stop exactly this wedge — a mitigation of the
  per-copy design, insufficient by construction (name-intersection stale check; per-record
  `applied_at`/environment divergence).
- ADR 2026-07-07-1 (ignored-surface backfill, :45-66,110) deliberately keeps `runs_on_worktrees=True`
  for gitignore backfills so lane worktrees get the same ignore protection. This is the one real
  in-checkout benefit to preserve (see Option B).

What breaks if lanes keep stale metadata.yaml — essentially nothing at runtime:
- Worktree-run commands resolve the project to the **repository root checkout**:
  `locate_project_root` "Locate the MAIN spec-kitty project root directory, even from within
  worktrees" (src/specify_cli/core/paths.py:197-237); the startup schema gate uses it
  (src/specify_cli/__init__.py:165-179 → migration/gate.check_schema_version); compat planner reads
  `project_root/.kittify/metadata.yaml` from the same resolver (src/specify_cli/compat/planner.py:559-580,
  :778). `get_project_version` (core/version_checker.py:69) is reached only via
  `cli/helpers.check_version_compatibility` (cli/helpers.py:486), which has no in-tree caller.
- Only readers keyed on a worktree path are inside the upgrade package itself (runner.py:443-446
  per-worktree ledger; upgrade/compat.py:24-40 `uses_centralized_runtime`, which already handles
  "metadata-less worktrees"). So stale lane copies are inert; and because the lane never changed
  those paths, lane consolidation / branch integration three-way-merge cleanly to the target's
  version.
- Real residual risk of not migrating worktrees: in-checkout behaviour of tracked generated files a
  migration rewrites (e.g. `.gitignore` backfills per ADR 2026-07-07-1; agent command copies —
  largely moot after the global-commands ADRs 2026-04-07-1 / 2026-04-08-6). These are content, not
  ledger: if upgrade still writes them in a lane, the lane commit + target commit produce the same
  name-intersection staleness. So "migrate worktrees" and "consolidation-safe" are in tension for
  *every* tracked path, not just metadata.yaml.

#### Q3 — Governing ADRs / architecture pages
- docs/adr/3.x/2026-05-14-1-stale-lane-auto-rebase-classifier-policy.md — classifier rule set +
  fail-safe Manual; an "upgrade bookkeeping is take-integration-side" arm is a policy addition →
  **amend** (or note it lives in the managed-artifact pre-pass, outside RULES).
- docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md — mandates
  `runs_on_worktrees=True` for gitignore backfills → **amend** if worktree writes stop or become
  uncommitted.
- docs/architecture/branch-target-routing.md (categories → landing branch) — add "project-global
  upgrade bookkeeping → target branch via the repository root checkout only".
- docs/architecture/git-worktrees.md / execution-lanes.md — no upgrade/metadata coverage today; add
  a short "upgrade and live worktrees" note (DIRECTIVE_037).
- docs/adr/3.x/2026-04-08-1-global-kittify-machine-level-runtime.md — background on project vs
  machine `.kittify`.
- **New ADR warranted** (DIRECTIVE_003): "Upgrade writes project-global state once, on the repository
  root checkout; lane/coordination branches never carry upgrade bookkeeping; consolidation resolves
  any legacy copy to the integration-target side." It reverses the #2385 design choice (commit-per-
  worktree) and changes the migration contract default, so it is a decision, not a bugfix.

#### Q4 — Architectural gates the fix implicates (run these specific files)
- tests/architectural/test_exemption_registry_ratchet.py — R-014/anti-ninth; any filename literal in
  lanes/consolidation.py / auto_rebase.py / coherence.py is scanned. Primary gate.
- tests/architectural/test_guard_capability_call_sites.py — UPGRADE_BOOKKEEPING call-site set
  (:54-58) if autocommit callers change.
- tests/architectural/test_merge_reconciliation_class_guard.py — driver-registry sync/completeness
  (only if a merge driver for metadata.yaml is chosen; it currently enumerates kitty-specs kinds).
- tests/architectural/test_no_op_stable_writes.py (:44, upgrade metadata dirty-flag #1872).
- tests/architectural/test_mission_runtime_surface.py (:177-185, churn-owner location assertions).
- tests/architectural/test_destructive_op_routing.py (:371 auto_rebase `_abort_with_failure`) if the
  auto-rebase abort path is touched.
- tests/architectural/test_layer_rules.py — lanes/consolidation → coordination imports already exist
  (lanes/consolidation.py:27); stays within specify_cli.
- tests/architectural/test_no_dead_symbols.py + dead_symbol_allowlist.yaml — if
  `_reconcile_worktree_bookkeeping` / `_aligned_worktree_timestamp` / `upgrade_worktrees_only` are
  retired.
- tests/architectural/test_migration_chain_integrity.py — if `BaseMigration.runs_on_worktrees`
  default changes.
- tests/architectural/test_no_legacy_terminology.py — prose touches.
Module tests in blast radius: tests/upgrade/{test_upgrade_worktree_commit,test_issue_4972_idempotent_worktree_metadata,
test_worktree_stamp_guard,test_exclude_worktrees_migration,test_upgrade_auto_commit_unit,test_commit_decision}.py,
tests/lanes/{test_stale_check,test_auto_rebase_managed_artifact_recognition,test_lane_lifecycle_characterization}.py,
tests/consolidation/test_conflict_classifier.py, tests/coordination/test_ledger_topology_less_callers.py,
plus the ~8 tests/specify_cli/upgrade/migrations/test_m_*_gitignore.py that exercise include_worktrees.

#### Q5 — Options

**A. Classification only (consumer-side).** Add the owner predicate in coherence.py; stale_check
filters it; squash/preview, auto-rebase pre-pass and dependency-tip merge resolve it to the
integration-target side. Upgrade unchanged.
+ Self-heals already-broken projects with zero history rewriting; smallest diff.
− Keeps N divergent copies and N commits per upgrade; does not cover other migrated tracked files
  (gitignore backfills, agent copies) which hit the same name-intersection wall; treats symptom.

**B. Write-once at source + owner classification as legacy heal (RECOMMENDED).**
1. Upgrade's worktree pass stops writing/committing `.kittify/metadata.yaml` (no per-worktree
   ledger; retire `_reconcile_worktree_bookkeeping`/`_aligned_worktree_timestamp`, the #1873
   synthesis, and the worktree `schema_version` stamp). The repository root checkout's ledger is the
   single authority (consistent with how every worktree-run command already resolves `.kittify`).
2. Flip the migration contract: `runs_on_worktrees` default → False (opt-in), and for the opt-in set
   (gitignore backfills per ADR 2026-07-07-1, op-record v2) either (i) write but **do not commit**
   in lane/coord worktrees is NOT acceptable (#2392 dirty guard) — so prefer (ii) leave lanes alone
   and rely on consolidation bringing the target's version, or (iii) for gitignore protection,
   seed `$GIT_COMMON_DIR/info/exclude` (shared by all worktrees, untracked, no branch commit).
   Spec must pick; (ii)+(iii) is the cleanest.
3. Ship Option A's owner predicate + target-side resolution as the recovery path for projects that
   already have per-branch metadata.yaml commits (and as defence in depth for any future
   upgrade-ledger path).
+ Satisfies branch-target routing and single canonical authority at the source; #2392 invariant
  holds vacuously; removes #4972's mitigation code.
− Needs a new ADR + amendments to ADR 2026-07-07-1 and 2026-05-14-1; larger test churn in
  tests/upgrade.

**C. Refuse/defer upgrade while lane/coord worktrees are live + repair command.** Upgrade preflight
refuses (or auto-implies `--no-worktrees`, flag already exists: cli/commands/upgrade.py `no_worktrees`)
when `.worktrees/*` exist; a `spec-kitty doctor upgrade-bookkeeping --fix` writes one forward commit
per lane/coord branch restoring `.kittify/metadata.yaml` to the merge-base/mission-branch blob.
+ No consolidation-policy change. − Operator burden; still needs the repair for broken state; does not
  fix the stale-check blindness for the next project-global file.

**Non-destructive recovery for already-broken projects (all options):** never rewrite lane history.
Preferred: Option A's resolution at consolidation time — stale_check ignores the classified path;
lane→mission / auto-rebase / dependency merges take the integration-target side; squash restores the
target blob — so existing per-branch commits are neutralised in the merge result and the lane's
history is untouched. Fallback/manual (no code change): in each lane/coord worktree restore the
path to the lane's **merge-base** blob and make one forward commit
(`git checkout $(git merge-base HEAD <mission-branch>) -- .kittify/metadata.yaml && git commit`).
The net lane diff for that path then becomes empty, so the name-intersection stale check and the
squash no longer see it. Restoring to the mission tip instead would still leave a net diff vs the
merge-base and keep the lane stale.

**Where the remedy text lives (to update with the new path class/hint):**
- Stale lane: `_stale_remediation` lanes/stale_check.py:85-118; message assembled at
  lanes/consolidation.py:303-309 (`"Lane {lane_id} is stale: overlapping files … {remediation}"`).
- Squash: `TARGET_BRANCH_CONTENT_CONFLICT_HEADER` / `_REMEDIATION_UPDATE`
  consolidation/_constants.py:34-35, rendered consolidation/phase_advance.py:465-479 and
  consolidation/forecast.py:205-217.
- Auto-rebase halt: `r_default_manual` reason consolidation/conflict_classifier.py:556-570 and the
  ADR §Operator-visible behavior (2026-05-14-1:135-175).

#### Open questions for spec
1. Exact membership of "upgrade bookkeeping": metadata.yaml only, or every path an upgrade *ledger*
   write produces (mission-state-audit is already a coherence leg)? Exclude operator-authorable
   `.kittify/config.yaml`, charter, doctrine.
2. `runs_on_worktrees` default flip vs. keeping worktree content migrations uncommitted-free via
   info/exclude — needs a decision moment with the ADR 2026-07-07-1 owner.
3. Should the squash restore-to-target run unconditionally (lane-born bookkeeping never lands) or only
   on conflict? Recommend unconditional (target is the single authority).
4. Coordination-topology missions: the coordination branch also received metadata.yaml commits; the
   coord teardown/projection (`bookkeeping_projection.project_post_checkpoint_commits_to_target`) only
   projects `kitty-specs/<slug>` paths (bookkeeping_projection.py:407) — confirm no coord→target
   projection of `.kittify/` is needed.

## Appendix E — test-suite lens

### Test-suite lens: #5457 (upgrade writes .kittify/metadata.yaml per live worktree)
Applied: reviewer-renata (quality gate, no implementing); charter review context (DIRECTIVE_025 Boy Scout, _024 Locality, _030 test gate, _034 test-first, _036 black-box integration testing).

#### 1. Existing coverage (paths + tests)
Upgrade worktree handling:
- tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py: test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now, test_repeat_upgrade_is_a_true_no_op_once_worktree_has_caught_up, test_sibling_worktrees_share_one_fallback_timestamp_when_main_is_unstamped, test_two_worktrees_aligned_to_stamped_main_are_byte_identical
- tests/upgrade/test_upgrade_worktree_commit.py (#2385/#2392/#1873): test_worktree_upgrade_churn_is_committed_on_its_own_branch (L91), test_preexisting_uncommitted_work..., test_synthesized_worktree_metadata_is_saved..., test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned (L157), test_current_equals_target_worktree_catchup_ends_byte_identical_to_main (L222), test_dry_run_writes_and_commits_nothing_in_worktrees, test_upgrade_invariant_every_touched_checkout_ends_clean, + ~10 rename/sweep/journal tests
- tests/upgrade/test_upgrade_auto_commit_unit.py (1463 lines): git-status parsing, eligibility, test_upgrade_no_migrations_stamps_existing_worktree_schema_version, ..._keeps_current_worktree_metadata_clean, test_upgrade_worktrees_only_delegates_to_private_impl (L1396, mock), ..._passes_auto_commit (L1440, mock)
- tests/e2e/test_upgrade_post_state.py::test_upgrade_then_branch_context_does_not_gate (only real-CLI upgrade test; no worktrees)
Stale-lane / squash gate: tests/lanes/test_merge.py (test_stale_lane_blocked L114, test_stale_planning_lane_blocked_with_repo_root_remediation L181, test_squash_conflict_carries_structured_paths_and_code L~290); tests/consolidation/test_executor_coverage.py L406-466 (renders TARGET_BRANCH_CONTENT_CONFLICT from a hand-built result), tests/consolidation/test_forecast_seam.py
Auto-rebase / classifier: tests/lanes/test_auto_rebase_additive.py (1828 lines), tests/consolidation/test_conflict_classifier.py (rules: pyproject deps, __init__ imports, urls.py, uv.lock, default manual)
lifecycle_sync: tests/integration/test_lane_lifecycle_sync.py (clean_rebase, recreates_missing_worktree, conflict_refuses_and_preserves_lane_state -> LANE_AUTO_REBASE_FAILED), tests/lanes/test_lane_consumers_divergent.py

#### 2. Why each missed the defect
- Every upgrade-worktree test calls the private `MigrationRunner(root)._upgrade_worktrees(version, [], ...)` directly (4972:155,226,255; wt_commit:97,120,150,271,288) with an EMPTY migrations list. No test runs `upgrade()`/CLI with a real migration over both main and worktrees, so "main applies, worktree skips/applies" divergence is never exercised. Fixtures hard-code `migrations.applied: []` (4972:54,70,87).
- Vacuous equality: 4972 test L170 `assert wt_data == main_data` / wt_commit:279 only holds because main was PRE-STAMPED in the fixture to the target (comment L36-40) and the run is bookkeeping-only. Never covers the case where main gains `migrations.applied` records.
- Pins the defect: test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned asserts `wt_stamp != old_main_stamp` (wt_commit:211) -> codifies a per-worktree distinct metadata.yaml. Must be RE-PINNED when the fix lands. Also the module docstring of test_upgrade_worktree_commit.py (#2385 "commits each worktree on own branch") pins the per-branch-commit design; the 4972 test asserts `_git_out(wt,"log")` contains "spec-kitty upgrade" (4972:~176) and that main did NOT get it - also pins the design.
- Consumers never see .kittify/metadata.yaml: grep of tests/lanes, tests/consolidation, tests/integration/test_lane_lifecycle_sync.py for `metadata.yaml` finds ZERO hits. Stale-lane/squash tests use src/views.py conflicts (test_merge.py:119-130, ~300) on repos built by `_make_repo` with just README. No .kittify, no upgrade commit, so the divergent-metadata scenario is missing.
- Classifier tests (test_conflict_classifier.py) only cover pyproject/__init__/urls/uv.lock/default; no rule or test for `.kittify/metadata.yaml`, so default manual classification on it is untested (the Path C failure).
- test_lane_lifecycle_sync conflict test conflicts on src/shared.txt (L173-209) - correct code path, wrong file; no coord-vs-lane metadata divergence.
- Mocking: tests/integration/test_merge_lane_worktree_safety.py patches _enforce_git_preflight, done_bookkeeping, commit_merge_bookkeeping (L170-184, L37 MagicMock) - consolidation is half-faked; test_executor_coverage.py builds results by hand. test_upgrade_auto_commit_unit.py L1396/1440 are pure delegation mocks.
- Only e2e upgrade test (test_upgrade_post_state.py) uses a no-worktree project and asserts schema_version only.

#### 3. Reusable harness
- tests/conftest.py: `run_cli` (L1339; subprocess `python -m specify_cli.__init__` in cached test venv, isolated env, 60s timeout), `isolated_env`, `temp_repo`, `feature_repo`, `installed_wheel_venv` (L1262, builds current wheel only), session `test_venv`.
- tests/e2e/conftest.py: `e2e_project` (L231; copies real .kittify, git init, status branch), `fresh_e2e_project`.
- tests/integration/coord_topology_fixture.py (`coord_topology_mission`, real git, no patched resolver), tests/integration/conftest.py (`make_owned_checkouts`, `_write_mission`, `_write_single_lane_manifest`), tests/integration/test_lane_lifecycle_sync.py `_init_repo` (L55; lanes.json + real lane worktree + coord branch - best base for Path C), tests/lanes/test_merge.py `_make_repo/_make_manifest` (Path B base, in-process consolidate_lane_into_mission / integrate_mission_into_target), tests/upgrade/test_issue_4972...py `_init_repo/_add_lagging_worktree` (upgrade+worktree base), tests/lanes helpers `write_single_lane_manifest`.
- Old-CLI hop harness: NONE. grep for `spec-kitty-cli==` finds only mocked command-string assertions (tests/readiness/test_upgrade_ux.py:768, compat tests); tests/VENV_ISOLATION.md only suggests manual pip install. Do not build one; simulate pre-upgrade state instead.

#### 4. Baseline (.venv/bin/python -m pytest -q -x -p no:cacheprovider)
- Set A: tests/upgrade/test_issue_4972..., test_upgrade_worktree_commit.py, test_upgrade_auto_commit_unit.py, tests/lanes/test_merge.py, tests/integration/test_lane_lifecycle_sync.py, tests/consolidation/test_conflict_classifier.py, tests/e2e/test_upgrade_post_state.py: 153 passed (159s; first e2e/setup ~25s venv).
- Set B: tests/lanes/test_auto_rebase_additive.py, tests/lanes/test_lane_consumers_divergent.py, tests/integration/test_merge_lane_worktree_safety.py: 37 passed.
- No reds; nothing pre-existing to attribute.

#### 5. Remediation recommendations
Re-pin/strengthen (only in files fix touches):
- RE-PIN test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned (wt_commit:157-219): invert to assert worktree metadata.yaml content is NOT diverged from what the target branch will see (or absent/untracked, depending on chosen design); drop the `!=` assertion.
- RE-PIN 4972 test + wt_commit L91 asserts that every worktree gets its own "spec-kitty upgrade" commit touching .kittify/metadata.yaml; keep the clean-tree/baseline protections (#2385 pre-existing dirty work).
- STRENGTHEN: replace hard-coded `applied: []` fixtures with a real registered migration applied on main (use MigrationRegistry stub as at wt_commit:185) and assert main-vs-worktree `migrations.applied` parity.
- Keep: dry-run no-write, baseline/sweep tests, test_upgrade_worktrees_only_* (adjust if signature changes).
- DELETE nothing; test_upgrade_worktrees_only_* mocks are low-value, boy-scout optional.
New red-first tests via real CLI (subprocess `run_cli` or CliRunner on typer app), real git, no mocking of preflight/gates:
 Shared builder (new helper, e.g. tests/upgrade/_lane_project.py): git repo with committed .kittify/metadata.yaml version 'OLD' (< target_version of a registered/real migration; e.g. write rc4-era version, applied: [], no schema_version/last_upgraded_at), kitty-specs mission + lanes.json (reuse test_lane_lifecycle_sync._init_repo + write_single_lane_manifest), N lane worktrees via `git worktree add` each branched from mission branch, with real commits per lane. This faithfully simulates "before upgrade" without old CLIs: older version in metadata.yaml makes migrations detect/apply (runner compares metadata.version vs migration target_version; runs_on_worktrees defaults True, base.py:99).
 Path A: two lanes + `run_cli(repo,"upgrade","--yes")` (auto-commit on), then `consolidate` (or consolidate_lane_into_mission) -> assert NOT refused as stale; assert no divergent .kittify/metadata.yaml blob across main/coord/lane tips (`git show <br>:.kittify/metadata.yaml` equal or untouched on lane branches). RED today.
 Path B: single lane, upgrade, lane edits real file, main (target) also moved by upgrade commit; `consolidate --strategy squash` -> assert exit 0 / no TARGET_BRANCH_CONTENT_CONFLICT with conflicting_paths excluding .kittify/metadata.yaml. Unit-level companion in tests/lanes/test_merge.py using integrate_mission_into_target with diverged metadata.yaml on both sides.
 Path C: coord worktree + lane; upgrade; then sync_lane_after_coordination_commit / `implement` dependency auto-rebase -> assert no LANE_AUTO_REBASE_FAILED; plus classifier unit test: classify(Path(".kittify/metadata.yaml"), hunk) is the intended verdict (rule or documented manual), in test_conflict_classifier.py.
 Also: idempotent re-run `upgrade` twice leaves zero new commits (extends 4972:181), and a mixed case: worktree already had migration skipped vs applied on main.
Gate before PR: ruff check, ruff format --check --force-exclude on touched files, mypy; run the Set A/B files + tests/upgrade/, tests/lanes/, tests/consolidation/ (owning subsystems) + test-fast; specific architectural gate files only (no bare tests/architectural).
