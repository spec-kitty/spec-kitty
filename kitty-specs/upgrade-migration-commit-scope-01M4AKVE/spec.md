# Mission Specification: Schema-3 upgrade commits only what it changed

**Mission Branch**: `fix/upgrade-migration-commit-scope`  
**Created**: 2026-10-07  
**Status**: Planned  
**Input**: User description: "Fix #5443 (P0): upgrading a 2.x project commits all uncommitted work — untracked secrets, staged files, unrelated edits — into the schema-v3 migration commit, and a hook that rejects it is bypassed with --no-verify, exit 0." Widened on 2026-10-07 at the maintainer's request (issue comment 6035306299) to the rule, as corrected by the validation squad (2026-10-07, `<operator-local squad notes>`): **an automatic commit records exactly the paths the operation wrote, nothing else. Every automatic commit goes through `safe_commit` with an explicit list of the paths the calling code wrote; only `spec-kitty upgrade` derives its list from its pre-run baseline, because its writers are not known in advance. Merge, revert and squash conclusions, where git refuses a pathspec, go through one canonical merge-conclusion owner; two recorded path-scoped commits that cannot use `safe_commit` are listed in C-005. A gate keeps every sweeping, pathspec-less or hook-bypassing commit route out of `src/`.** — adding #5673, #5229, #4763, the merge-time mission-number commits, the dead sweeping helpers, an architectural gate, shipped skill text, and the safe-commit CLI path bugs #5401, #5671, #4722 (#5393 already fixed).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An upgrade never commits the operator's own work (Priority: P1)

An operator upgrades a project created with Spec Kitty 2.x. Their working tree holds an untracked `secrets.env`, a staged new file and an unstaged edit to a tracked file. The upgrade must commit only the files the upgrade itself changed; the secret stays untracked, the staged file stays staged and uncommitted, and the unstaged edit stays unstaged with its content intact. Today the schema-3 migration stages everything with `git add -A` and commits it all, exit 0.

**Why this priority**: an untracked secret ends up in history silently; once pushed it must be rotated (P0 under the honesty ADR).

**Independent Test**: a real git repository with the legacy (pre-schema-3) layout plus the three kinds of operator work; `spec-kitty upgrade --yes`; inspect HEAD's file list, `git status` and `git diff --cached`.

**Acceptance Scenarios**:

1. **Given** a legacy project with an untracked `secrets.env`, a staged `src/staged.py` and an unstaged edit to tracked `src/app.py`, **When** the operator runs `spec-kitty upgrade --yes`, **Then** the upgrade's commit contains the migrated `.kittify/metadata.yaml` (now at the current schema version) and none of the three operator paths; `secrets.env` is still untracked, `src/staged.py` is still staged, and `src/app.py` still carries the unstaged edit.
2. **Given** the same project with a clean working tree, **When** the operator upgrades, **Then** the upgrade's changes are committed (positive control: the fix must not stop committing upgrade changes). The fixture pins HOME state and the agent configuration, and the scenario holds for both a cold HOME and an empty `agents.available` (where a false manual-review flag suppresses the commit on main today).
3. **Given** an operator file under a path the project ignored before the upgrade (e.g. `.kittify/workspaces/token.json`), **When** the upgrade runs, **Then** that file is never committed, directly or inside a backup copy.
4. **Given** a tracked file the migration un-tracks (`git rm --cached`) and starts ignoring, **When** the upgrade commits, **Then** the removal is part of the commit and the file is no longer both tracked and ignored.
5. **Given** the operator had already edited a file the migration also rewrites (e.g. `.gitignore`), **When** the operator upgrades, **Then** that file is not committed and keeps both the operator's and the migration's content in the working tree.

---

### User Story 2 - Hooks are never bypassed (Priority: P1)

An operator's repository has a pre-commit hook that rejects commits containing secrets. The upgrade must let the hook decide; if the hook rejects the commit, nothing is committed, the tree is left migrated and uncommitted, and the operator sees upgrade's existing "could not auto-commit" warning. Today a rejection triggers a silent retry with `--no-verify`.

**Why this priority**: the bypass defeats the operator's last line of defence against the exposure in User Story 1.

**Independent Test**: install a rejecting pre-commit hook in the repository, upgrade, and check that the hook ran, no commit contains the rejected content, and no second bypassing commit was attempted.

**Acceptance Scenarios**:

1. **Given** a pre-commit hook that rejects the commit, **When** the operator upgrades, **Then** the hook runs, no new commit is created, the migrated files remain in the working tree, and the output contains upgrade's existing skip warning.
2. **Given** the hook accepts, **When** the operator upgrades, **Then** the upgrade commit is created normally.

---

### User Story 2b - A failed upgrade commits nothing (Priority: P1)

When a migration step fails, `spec-kitty upgrade` exits non-zero ("Upgrade failed.") but today still auto-commits the partial state, including the migration's backup folder (and, through it, ignored operator files such as tokens), the rewritten agent shims and the rollback debris.

**Why this priority / Independent Test**: the backup folder carries ignored secrets into history (same exposure as User Story 1); tested through `spec-kitty upgrade` with a forced step failure in WP01 T003 (main checkout and an upgraded worktree).

**Acceptance Scenarios**:

1. **Given** a migration step that fails, **When** the upgrade finishes, **Then** no commit is created, the output says the changes were left uncommitted, and `.kittify/` is left as FR-012 defines.

### User Story 2c - Files are held back for manual review only when the operator customised them (Priority: P1)

A file is "customised" only when it lacks Spec Kitty's version marker. Freshly written agent command files must not be flagged because the global runtime or a global equivalent is absent. When files are genuinely held for review, the rest of the upgrade's changes are still committed and the held files are named. The same holds in every upgraded worktree.

**Why this priority / Independent Test**: a false flag silently skips the whole upgrade commit on a cold HOME; tested through `spec-kitty upgrade` in WP01 T003 (cold/warm HOME, held file, held file in a worktree).

**Acceptance Scenarios**:

1. **Given** a legacy project upgraded in a cold HOME, **When** the upgrade runs, **Then** no file the upgrade wrote is flagged for manual review and the upgrade commit is created.
2. **Given** a command file the operator edited (no version marker), **When** the upgrade runs, **Then** that file is held for review and named, and every other upgrade-written clean path is committed.

### User Story 3 - A failed commit never reports a successful migration it undid (Priority: P2)

**Why this priority**: a false success hides a rolled-back migration; no exposure, so P2.

Today a failure in the migration's own commit step restores the pre-migration backup, so the migration's changes are rolled back, while the schema-3 migration still reports success. After this mission the migration never commits on its own, so its result no longer depends on a commit.

**Independent Test**: run the migration in a directory where committing is impossible and verify the migrated files are present and the migration reports success truthfully.

**Acceptance Scenarios**:

1. **Given** a legacy project, **When** the schema-3 migration runs, **Then** it creates no commit by itself and leaves HEAD and the index exactly as it found them.

### User Story 4 - Claiming a work package never commits the operator's config edit (Priority: P1)

An operator edits `.kittify/config.yaml` and claims a work package with `spec-kitty implement` in a single_branch root checkout. The claim commit must contain only what the claim wrote — the status artifacts, plus `meta.json` only when the claim itself changed it, plus the claimed WP prompt only when workspace allocation stamped it in this claim (`base_branch`, `base_commit`, `created_at`); never `config.yaml` (no implement path writes it), another WP's prompt, an operator edit to the claimed prompt, or `tasks.md`. If `meta.json` was already dirty before the claim, it is left uncommitted and the operator is warned (#5673). The separate implement planning-artifacts commit is out of scope (C-003, follow-up).

**Why this priority / Independent Test**: same exposure class as #5443 on every claim; tested through a real `spec-kitty implement` claim in WP03 T015.

**Acceptance Scenarios**:

1. **Given** a dirty `.kittify/config.yaml`, **When** the operator claims a WP, **Then** the claim commit does not contain `config.yaml` and the file still carries the operator's edit.
2. **Given** a clean config, **When** the operator claims a WP, **Then** the claim commit's content is the same set of claim-written paths (positive control).

---

### User Story 5 - Merge bookkeeping never commits what the operator staged (Priority: P1)

During consolidation, assigning a mission number commits `meta.json` on the operator's primary checkout with a bare `git commit`, sweeping anything the operator had staged into a `chore(...): assign mission_number` commit (same class as #5442). The commit must contain only `meta.json`.

**Why this priority / Independent Test**: same exposure class at merge time; tested with real-git bake fixtures in WP04 T019.

**Acceptance Scenarios**:

1. **Given** a file the operator staged on the primary checkout, **When** consolidation assigns the mission number there, **Then** the bookkeeping commit contains only the mission's `meta.json` and the operator's file is still staged and uncommitted.
2. **Given** the primary checkout is on another branch or detached, or `meta.json` differs from HEAD, **When** the mission number is assigned, **Then** nothing is committed there and the mission number is reported as not yet baked (today the commit lands on the wrong branch or includes the operator's in-file edit).

---

### User Story 6 - A migrated or rolled-back project has a coherent `.kittify/` (Priority: P2)

The schema-3 migration writes `metadata.yaml` with its own capability list instead of the canonical map and non-atomically (#5229), and a migration rollback copies its backup folders into `.kittify/` (#4763), which the canonical upgrade commit would now record.

**Why this priority / Independent Test**: data loss and debris, not exposure; tested on the final `metadata.yaml` after `spec-kitty upgrade` in WP02 T011 and by the rollback unit tests in WP01 T005.

**Acceptance Scenarios**:

1. **Given** a legacy project, **When** it is upgraded, **Then** `metadata.yaml` carries the canonical schema-capability map (operator keys preserved, a legacy list converted).
2. **Given** a migration that fails and rolls back, **When** the rollback finishes, **Then** `.kittify/` is left as FR-012 defines.

---

### User Story 7 - The class stays closed (Priority: P1)

No production code may stage everything (`git add -A`, `add .`, `--all`, `-u`), commit without naming its paths (including `--amend`), commit with `-a`, or bypass hooks (`commit --no-verify`, `commit -n`, `-c core.hooksPath=`). An architectural gate enforces it across `src/` and **starts empty** (ADR 2026-09-30-1; Decision `01M4B2XJQ0JAHVXGVDNQBMF6XF` supersedes the earlier allowlist decision): merge, revert and squash conclusions in spec-kitty-managed worktrees — where git refuses a pathspec — go through one canonical owner function that asserts an operation is in progress (or a fresh worktree for a squash), and that owner and `safe_commit` are the gate's only exemptions (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`). The unused sweeping helpers are removed, and shipped skill/toolguide text and the two upgrade docs stop teaching `git add -A` / `git add .` / directory adds (Decision `01M4AY23FFY71BJA2JRG39SMB6`).

**Why this priority / Independent Test**: without a gate the class reopens with the next commit site; tested by the planted-form gate in WP05 T023 and the shipped-text check in WP06 T029.

**Acceptance Scenarios**:

1. **Given** a planted `git add -A`, a planted pathspec-less `git commit` and a planted `--no-verify` in a scanned module, **When** the gate runs, **Then** each is reported (non-vacuity); on the real tree it passes with no exemption other than the two canonical owners, and fails on each planted form.

---

### User Story 8 - `safe-commit` commits exactly what it was given (Priority: P2)

With `safe_commit` as the single commit route, its command-line front end must not lose or redirect paths: a staged rename under a directory argument must commit the removal too (#5401); a symlink argument must commit the link, not the file it points to (#5671, also `spec-commit`); a batch with one bad path must name that path and git's reason (#4722). #5393 (non-ASCII paths) is already fixed on main.

**Why this priority / Independent Test**: path loss or redirection inside the single commit route; tested through `spec-kitty safe-commit` / `spec-commit` in WP07 T037–T038.

**Acceptance Scenarios**:

1. **Given** a staged `git mv docs/old.md docs/new.md`, **When** the operator runs `spec-kitty safe-commit docs/`, **Then** the commit records the rename and nothing is left staged.
2. **Given** a tracked or untracked symlink `link.md` → `real.md` with WIP in `real.md`, **When** the operator safe-commits or spec-commits `link.md` (relative or absolute, or a directory containing it), **Then** only the link path is committed and `real.md`'s WIP stays uncommitted; a symlinked directory argument is committed as a link, never expanded; a looping link is refused on every interpreter (#5251 / PR #5252).
3. **Given** a batch with one nonexistent path, **When** safe-commit runs, **Then** the error names that path and git's reason; a lone path unknown both on disk and to git is an error too (a deleted tracked file stays valid).
4. **Given** a rename whose other side lies outside the directory argument, **When** safe-commit runs, **Then** it refuses and names the outside path; nothing is committed.

---

### Edge Cases

- Upgraded worktrees under `.worktrees/` follow the same rules as the main checkout (WP01): a per-worktree baseline taken before writes; a commit only when that worktree's migrations succeeded; only marker-less files held for review and named, the rest committed; one explicit message per no-commit reason. Operator work in them is equally untouched.
- If upgrade's own commit does not happen (`auto_commit: false`, a failed run, a hook rejection), the migration's changes stay uncommitted and an explicit message reports why (FR-023). Files held for manual review never suppress the commit; they stay uncommitted and are named (FR-021).
- A path the operator had dirty that the migration also rewrote stays uncommitted; naming such overlaps in the output is a follow-up, not this mission.
- FR-022 ships with the second PR (WP07 adds index-deletion support to `safe_commit`); it is pre-existing behaviour on main, not part of the P0 secret exposure.
- Renames and deletions made by the migration on paths that were clean before are committed (the canonical commit already handles them).
- **Interaction with #5811:** the upgrade's single commit is taken after migrations and surface repair and before the mission-state repair (`upgrade/finalize.py`), and includes only paths clean at the pre-run baseline. Mission-state repair rewrites are therefore never committed by this mission's commit path, in the same run or later. Event logs rewritten by the schema-3 migration's own state rebuild are written by the upgrade and are committed. #5811/#5812 (draft PR #5856) remove the repair from `upgrade` and do not change this behaviour; if a future change moves the repair before the commit, it must get its own commit authority rather than relying on the baseline.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Untracked work never committed | As an operator, I want an untracked file in my tree to stay untracked after an upgrade so that a secret is never committed. | High | Open | [build] | no — the same fixture commits `secrets.env` today |
| FR-002 | Staged and unstaged work untouched | As an operator, I want my staged and unstaged changes to be neither committed nor altered by the upgrade. | High | Open | [build] | no — asserted on the same fixture (today both are committed) |
| FR-003 | Upgrade changes still committed | As an operator, I want the files the upgrade changed to be committed, including the migrated metadata at the current schema version. | High | Open | [ratchet] | no — the commit must contain `.kittify/metadata.yaml` at the target schema; a "commit nothing" change fails it |
| FR-004 | Overlapping dirty file not committed | As an operator, I want a file I had already modified and the migration also rewrote to stay uncommitted with both changes in the tree. | Medium | Open | [build] | no — today it is committed |
| FR-005 | Hooks always honoured | As an operator, I want my pre-commit hook to decide; a rejection leaves the tree migrated and uncommitted with upgrade's existing skip warning (`UPGRADE_COMMIT_SKIP_WARNING`) and no bypassing retry. | High | Open | [build] | no — today the retry with `--no-verify` commits |
| FR-006 | Migration never commits by itself | As a maintainer, I want the schema-3 migration to leave HEAD and the index unchanged so that the upgrade command's single, baseline-scoped commit is the only commit authority. | High | Open | [build] | no — today it creates its own commit |
| FR-007 | No false success after a failed commit | As an operator, I want the migration's reported result to match what is on disk: no rollback triggered by a commit step, no success reported for changes that were undone. | Medium | Open | [build] | no — today a failed commit rolls back while reporting success |
| FR-008 | Red-first reproduction | As a release owner, I want an issue-pinned real-git reproduction of FR-001/002/004/005 that fails before the fix and passes after, per ADR 2026-07-17-1. | High | Open | [build] | no — committed red before the fix commit |
| FR-009 | Claim commit is claim-written paths only | As an operator, I want a work-package claim to commit only what the claim wrote: status artifacts, `meta.json` only when the claim changed it and it was clean before, and the claimed WP prompt only when workspace allocation stamped it in this claim and it was clean before; never `config.yaml`, another WP's prompt or `tasks.md` (#5673). A claim-written file that was dirty before the claim is left uncommitted with a warning. | High | Open | [build] | no — today the bundle includes config.yaml and an operator-edited meta.json |
| FR-010 | Merge bookkeeping commit is meta.json only | As an operator, I want the mission-number assignment on my checkout to commit only the mission's `meta.json`, on the target branch, through `safe_commit`; off-target, detached, or with my own `meta.json` edit pending it commits nothing and reports the number as unbaked. The temp-worktree commit names its path. | High | Open | [build] | no — today a bare commit sweeps staged files and lands on any branch |
| FR-011 | Canonical schema metadata | As an operator, I want the final `metadata.yaml` after `spec-kitty upgrade` to carry the canonical capability map and keep every key it had (including `project_uuid` and my own keys), written atomically and merge-preserving by every writer — `ProjectMetadata.save()`, `MigrationRunner._stamp_schema_version()`, `backfill_project_uuid()` and the schema-3 migration's `_update_schema_version` (#5229). | Medium | Open | [build] | no — today the final file loses project_uuid, capabilities and operator keys |
| FR-012 | Rollback leaves `.kittify/` as it was | As an operator, I want a rolled-back migration to leave `.kittify/` with exactly the entries the schema-3 migration found at its start — no backup debris and no `.migration-backup` folder — and to remove a `.gitignore` the migration created (#4763). | High | Open | [build] | no — today backup folders are copied in and committed |
| FR-013 | Sweeping commits gated, starting empty | As a maintainer, I want a gate that fails on any `add -A`/`add .`/`--all`/`-u`/`:/`, pathspec-less `commit` or `--amend`, `commit -a`, `commit --no-verify`/`commit -n`/`-c core.hooksPath=` override, or `merge`/`revert`/`cherry-pick` that auto-commits, in `src/`; the only exemptions are the two canonical owners — `safe_commit` and the merge-conclusion owner, through which every such conclusion is routed (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`). | High | Open | [build] | no — planted hits of each form must fail it |
| FR-014 | Sweeping helpers removed | As a maintainer, I want the unused `GitVCS.commit(paths=None)` and `init_git_repo` removed so nothing can route back into a sweeping commit. | Medium | Open | [build] | no — the gate fails while they exist |
| FR-015 | Shipped text teaches path-scoped commits | As an agent operator, I want shipped skills, the built-in git toolguide and the two upgrade docs to stop recommending `git add -A`, `git add .` or directory adds. | Low | Open | [build] | no — a text check fails today |
| FR-016 | `safe-commit` keeps rename sources | As an operator, I want `safe-commit <dir>` to commit a staged rename completely (#5401). | Medium | Open | [build] | no — today the source stays in HEAD |
| FR-017 | `safe-commit` commits the link, not its target | As an operator, I want a symlink argument to commit the link path and never the target's content, in `safe-commit` and `spec-commit` (#5671). | High | Open | [build] | no — today the target's WIP is committed |
| FR-018 | `safe-commit` names a failing path | As an operator, I want a batch failure to name the offending path and git's reason, and a lone unknown path to fail (#4722). | Low | Open | [build] | no — today the error names every path and a lone typo exits 0 |
| FR-019 | No commit after a failed upgrade | As an operator, I want a failed upgrade to commit nothing and say so, in the main checkout and in every upgraded worktree whose migrations failed. | High | Open | [build] | no — today it commits the partial state, backups included |
| FR-020 | Ignored paths never committed by upgrade | As an operator, I want files that were ignored before the upgrade never committed by it, even if the migration changes the ignore rules or copies them into a backup. | High | Open | [build] | no — today un-ignored runtime files and backup copies are committed |
| FR-021 | Manual review only for customised files | As an operator, I want only files lacking Spec Kitty's version marker held for manual review, the rest of the upgrade's changes committed, and the held files named, in the main checkout and in every upgraded worktree. Note: `upgrade --json`'s `commit_policy.project_enabled` no longer turns false for manual review (on `origin/main` it already passed `manual_review=False`, so its value is unchanged; it is not a published contract — not in `docs/`). | High | Open | [build] | no — today freshly written files are flagged and the whole commit is skipped |
| FR-022 | Migration's own removals committed | As an operator, I want a file the migration stops tracking to be removed in the upgrade commit, not left tracked and ignored at once. | Medium | Open | [build] | no — today the staged removal is dropped |
| FR-023 | Every no-commit case is explained | As an operator, I want an explicit message whenever the upgrade leaves its changes uncommitted (baseline unavailable, `metadata.yaml` already dirty, activation or preparation errors, failed run, review holds), in the main checkout and in each upgraded worktree. | Medium | Open | [build] | no — today some cases are silent |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No regression in upgrade suites | The upgrade, migration-runner and safe-commit test modules that pass before the change pass after it; only tests pinning behaviour this mission's FRs change are edited, each listed old→new in the WP Activity Log. | Reliability | High | Open |
| NFR-002 | No sweeping or hook-bypassing git call in the upgrade flow | After the change, no production code path in the upgrade flow stages with `git add -A` or commits with `--no-verify`. | Security | High | Open |
| NFR-003 | Changelog | One `### Fixed` bullet per user-visible change, each under 900 characters (style guard `LENGTH_WARNING_LIMIT`), plus an `### Internal`/`### Changed` bullet for removed public exports; the style guard exits 0. | Documentation | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the canonical commit | Upgrade reuses its existing baseline-scoped commit; other sites pass an explicit written-path list to `safe_commit`. The canonical merge-conclusion owner the gate requires is the only new commit owner. Avoid the files the maintainer's PR #5856 edits (`upgrade/finalize.py`, `upgrade/outcome.py`, `upgrade.py`'s repair step, import block and `finalize_upgrade` kwargs, and its four test files); add new test modules instead. Also untouched (#5856): `tests/upgrade/test_teamspace_consent_scope.py`, `tests/upgrade/test_mission_corpus_recovery.py`, `tests/upgrade/test_yes_consent_exit_honesty.py`, `docs/api/upgrade-lifecycle.md` `:57-63` (this mission edits only its commit block near `:130`), and `docs/changelog/CHANGELOG.md` entries #5856 adds (this mission appends its own bullets only). | Technical | High | Open |
| C-002 | Decisions | Dirty tree: commit only paths the upgrade changed that were clean before (`01M4AKVTD3XMCEAJ9TDYBBAJVT`); hook bypass removed with no flag (`01M4AKVWCWHYNTGTRGXJ0WJ0VM`); scope widened per the maintainer (`01M4AY1QM21535SC7AZ6BC9NXT`); safe-commit CLI bugs included as a parallel WP (`01M4AY1VGXRZYAYGQ0883K7JZQ`); skill text in scope (`01M4AY23FFY71BJA2JRG39SMB6`); the P0 work package ships as its own PR first, the rest in a second PR (`01M4AYQTE5WGNXKW7411AVYP79`); manual review = missing version marker only, commit the rest (`01M4AYQRGFPWSGN39HBBTTBFSR`); gate starts empty with a canonical merge-conclusion owner (`01M4B2XJQ0JAHVXGVDNQBMF6XF`, supersedes `01M4AY1ZK6PCTM1DKHVWTFJV5W`); the gate exempts exactly the two canonical owners by symbol — `safe_commit` and the merge-conclusion owner — with no allowlist (`01M4B6FZNNSTP6DPN2AAEDEQHZ`); the runner-side `_update_schema_version` write (#5229) moves to the second PR's metadata work package (`01M4B6G3J0YNZ57WSHJXDMJS6N`). | Business | High | Open |
| C-003 | Out of scope | Upgrade exit-code policy (#5745, #5746), lane-cwd scoping (#5747), mission-state repair (#5811, own PR #5856), naming overlap paths in the output, implement's planning-artifacts auto-commit of operator edits (follow-up issue), other docs that show `git add .` for brand-new repositories, the acceptance commits' move to `safe_commit` (already path-scoped), the mutation-journal cap, plumbing commits (`commit-tree`/`update-ref`) outside the gate (follow-up issue filed at closeout). The upgraded-worktree commit path is in scope (WP01), not a residual. | Business | Medium | Open |
| C-004 | Red-first discipline | The #5443 reproduction lands in a commit before the fix and is red there through `spec-kitty upgrade`; the fix commit removes the `p0_repro` marker. Every other defect in scope gets a `regression` test that is red before its fix commit. | Regulatory | High | Open |
| C-005 | Commit authority | Every automatic commit this mission touches goes through `safe_commit` with an explicit path list from the code that wrote the files, or — for merge, revert and squash conclusions, which git cannot scope to paths — through the merge-conclusion owner, except two recorded path-scoped commits that cannot use `safe_commit` (detached HEAD / amend): the mission-number commit in a fresh detached temp worktree (`commit --only -- <rel_meta>`) and the restored-bookkeeping amend in a consolidation worktree (`commit --amend --only -- <restored>`). | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After upgrading the issue's fixture, 0 of the 3 operator paths are in the upgrade commit and all 3 keep their pre-upgrade state — [build] · no-op passable: no
- **SC-002**: A rejecting hook results in 0 commits containing the rejected content and 0 bypass retries — [build] · no-op passable: no
- **SC-003**: The upgrade commit on a clean legacy project still contains the migrated metadata — [ratchet] · no-op passable: no
- **SC-004**: The reproduction is red on the pre-fix commit and green on the fix commit, verified by the reviewer — [build] · no-op passable: no
- **SC-005**: The sweeping-commit gate passes on `src/` with no allowlist (only the two canonical owners exempt by symbol) and fails on each planted form — [build] · no-op passable: no
- **SC-006**: A claim, a mission-number assignment and a `safe-commit` call each commit exactly the paths they were responsible for, measured on fixtures with unrelated staged/dirty/untracked operator work — [build] · no-op passable: no
- **SC-007**: A forced migration failure, an ignored operator file and a cold-HOME clean legacy project each produce the expected commit outcome with an explicit message: failure → no commit and `FAILED_RUN_LEFT_UNCOMMITTED_WARNING`; ignored file → excluded from the commit that lands, with the `Auto-committed upgrade changes` line; cold HOME → committed, with the `Auto-committed upgrade changes` line and no "Manual review required" section — [build] · no-op passable: no

## Assumptions

- The upgrade command's baseline is captured before any migration writes, in the main checkout and in each upgraded worktree (grounding: `cli/commands/upgrade.py` baseline capture before the runner; `upgrade/runner.py` per-worktree baseline).
- Whether a hook-rejected upgrade should exit non-zero is the maintainer's open decision (#5745 family); this mission keeps today's warning-level outcome.

## Issue Matrix

- In mission: #5443 (P0), #5673, #5229, #4763, #5401, #5671, #4722; the squad's new findings (failed-upgrade commit, ignored-path commit, false manual-review flag, dropped `git rm --cached`) are folded into FR-019..FR-023 under #5443.
- Related: #3393 / #5473 (the dropped untrack may be a regression of #3393).
- Verified already fixed: #5393.
- Context only: #5251 / PR #5252 (looping-symlink refusal reused by FR-017), #4888 (closed; its `safe_commit --only` fix is the seam reused), #5442 / #5479 (closed; same class as the merge bookkeeping commit), #4915 / #3347 (parent epics), #5745 / #5746 / #5747 / #5811 (out of scope, see C-003).
