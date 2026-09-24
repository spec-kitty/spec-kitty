# Mission Specification: Upgrade idempotency — no divergent per-worktree metadata stamps

**Mission Branch**: `fix/upgrade-idempotent-worktree-metadata`
**Created**: 2026-09-24
**Status**: Draft
**Input**: Fix GitHub issue #4972 — a repeated (idempotent) `spec-kitty upgrade` on an already-current project stamps each live worktree with its own `last_upgraded_at` and auto-commits it per branch, wedging every in-flight coord mission while both runs exit 0 "already up to date".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A repeat upgrade must not wedge an in-flight coord mission (Priority: P1)

An operator has a coordination-topology mission in flight (WP01 `in_progress` in `lane-a` with its worktree, WP02 `planned` depending on WP01; the coordination worktree exists). They upgrade the CLI to the current release and run `spec-kitty upgrade --yes` a second time — a re-run, or a teammate running it once after pulling an already-upgraded `main`. Both runs report `Project is already up to date!` and exit 0. Afterwards the operator must still be able to `implement` the dependent WP and `merge` the mission.

**Why this priority**: This is the whole defect. Today the second (idempotent-looking) run stamps each live worktree's `.kittify/metadata.yaml` with a fresh `last_upgraded_at` and auto-commits it on that worktree's own branch, so `main`, the coordination branch and the lane branch carry three different values on one line from a common base. From there `implement WP02` fails the dependency-lane auto-merge and `merge` refuses the lane as stale — both on `.kittify/metadata.yaml` alone. The mission becomes undrivable with recovery only via manual conflict resolution on a file marked "DO NOT EDIT MANUALLY".

**Independent Test**: Reproduce the issue's trigger arm (`UPGRADES=2`): create an rc-baseline coord mission mid-flight, run `upgrade` twice, then drive `implement WP02` and `merge`. Both must exit 0 and `main` must receive both WPs' code — matching the issue's single-upgrade control arm.

**Acceptance Scenarios**:

1. **Given** an already-current project with live coord + lane worktrees, **When** `spec-kitty upgrade` runs a second time (only version/timestamp bookkeeping would change), **Then** each worktree's `.kittify/metadata.yaml` ends byte-identical to the main checkout's (shared `last_upgraded_at`, not a fresh per-worktree `now_utc()`) and no per-worktree "apply spec-kitty upgrade changes" commit is created.
2. **Given** the same project after that second upgrade, **When** `spec-kitty implement WP02` runs (WP02 depends on WP01 in `lane-a`), **Then** the dependency-lane auto-merge succeeds and the command exits 0.
3. **Given** the same project with both WPs approved, **When** `spec-kitty merge` runs, **Then** no lane is refused as stale on `.kittify/metadata.yaml` and `main` receives every approved WP's code (exit 0).

---

### User Story 2 - A teammate's first upgrade on an already-upgraded main behaves the same (Priority: P1)

A teammate pulls an already-upgraded `main` (so `current_version == target_version`) and runs `spec-kitty upgrade` once. This is the *same* code path as the operator's second run and must be equally safe.

**Why this priority**: The issue notes this path was not directly exercised in the repro but is reached by code (`current_version == target_version` on the first invocation). The fix must key on the substantive no-op condition, not on a naive "is this the second run?" heuristic, so both entries are covered.

**Independent Test**: Set up a project whose main checkout is already at the target version with live worktrees at the prior version, run `upgrade` once, and assert the same no-divergent-stamp outcome as User Story 1.

**Acceptance Scenarios**:

1. **Given** a project whose main checkout already reports the target version and whose worktrees are one version behind only in `version`/`last_upgraded_at`, **When** `spec-kitty upgrade` runs once, **Then** the worktrees are reconciled without minting a fresh per-worktree `last_upgraded_at` that diverges from the target checkout.

---

### Edge Cases

- **A real, substantive upgrade (a worktree migration that applied real content, or freshly synthesized metadata)** must still stamp with a real `now_utc()` and commit as today — the aligned-value write applies only when the SOLE driver of the write is the version bookkeeping bump. (Out of scope to change: the migrations-present path is #4893.)
- **Dirty worktree at upgrade time** — the #2385 fix that auto-commits touched worktrees so they no longer block merge must be preserved for genuine changes; the fix must not reintroduce the dirty-worktree-blocks-merge regression. The auto-commit is already churn-gated, so a suppressed/aligned write that yields an empty baseline delta self-cancels without a new special case.
- **A worktree already at the target version** must remain untouched (the existing `version==target` save-gate already suppresses; the single-upgrade control behaves correctly).
- **Worktree line not at the merge base** (a prior partial stamp, synthesized metadata, or a base already at target): bare suppression would leave the line divergent and could still wedge, which is why the fix aligns to the main checkout's shared value rather than merely skipping the write.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Aligned (not fresh) worktree bookkeeping | As an operator, I want a version-only worktree reconciliation to write the **main checkout's stored `last_upgraded_at`** (a shared value), not a fresh `now_utc()`, so `.kittify/metadata.yaml` is byte-identical across `main`, coord, and lane branches and merges cleanly regardless of merge base. | High | Open |
| FR-002 | Suppress no-op worktree autocommit | As an operator, I want no "apply spec-kitty upgrade changes" commit on a worktree's branch when the only change would be `version`/`last_upgraded_at` bookkeeping — relying on the existing churn-gate (`commit_touched_checkout` returns no-op on an empty baseline delta) rather than a new special case. | High | Open |
| FR-003 | Fix at the shared stamp, covering all callers | As a maintainer, I want the fix placed at the single per-worktree mint site (`_upgrade_worktrees`, the `version != target` branch and the `last_upgraded_at` write) so all three callers of `_upgrade_worktrees` inherit it — not in the CLI-only `_run_no_migrations_worktree_stamp` wrapper, which two callers bypass. | High | Open |
| FR-004 | Cover the current_version==target_version entry | As a teammate who pulled an already-upgraded main, I want my single `upgrade` run to be as safe as an operator's second run (same behavior keyed on the substantive no-op condition, not run count). | High | Open |
| FR-005 | Preserve substantive-upgrade behavior | As a maintainer, I want a genuine upgrade (a worktree migration that applied real content, or freshly synthesized metadata) to still stamp with a real `now_utc()` and auto-commit exactly as today — the alignment write applies only when the SOLE driver is the version bookkeeping bump. | High | Open |
| FR-006 | In-flight mission stays drivable | As an operator, I want `implement WP##` and `merge` to succeed after a repeat upgrade, with `main` receiving every approved WP's code. | High | Open |
| FR-007 | Honest exit and messaging preserved | As an operator, I want the repeat upgrade to keep reporting "already up to date" and exit 0 truthfully. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Regression proof | A red-first `@pytest.mark.regression` test pinned to #4972 reproduces the wedge through the real `upgrade`→`implement`/`merge` entry points and is RED before the fix, GREEN after. | Reliability | High | Open |
| NFR-002 | No new lint/type debt | New code passes `ruff check`, `ruff format --check`, and `mypy` with zero new issues; no blanket suppressions. | Maintainability | High | Open |
| NFR-003 | Complexity ceiling | Any touched or added function stays at cyclomatic complexity ≤ 15 (Ruff C901 / Sonar S3776). | Maintainability | Medium | Open |
| NFR-004 | New-code coverage | Every new branch/helper is exercised by a focused test in the same change (Sonar new-code gate). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Prevention-only scope | Fix the divergence at its source (the worktree-stamp path); do NOT change the lane auto-merge / stale-lane bookkeeping-tolerance behavior (the declined defense-in-depth option). | Technical | High | Open |
| C-002 | Preserve #2385 / reconcile with #1838 save-gate | Keep the #2385 dirty-worktree auto-commit for genuine changes; extend the existing #1838 version/timestamp save-gate (`runner.py:531-542`) rather than inventing a second authority. (#1872 governs migration-record writes, a different concern, and does not gate this path.) | Technical | High | Open |
| C-003 | metadata.yaml stays generated | `.kittify/metadata.yaml` remains a generated, "DO NOT EDIT MANUALLY" file; the fix must not require operators to hand-edit it. | Technical | High | Open |
| C-004 | Out-of-scope siblings | The migrations-present upgrade wedge (#4893) and main-checkout timestamp-only churn (#1838) are out of scope except where they inform the shared no-op pattern. | Technical | Medium | Open |

### Key Entities

- **`.kittify/metadata.yaml`**: The generated per-checkout metadata file carrying `version` and `last_upgraded_at`; the single line whose divergence across worktree branches causes the wedge.
- **Live worktree**: A materialized `.worktrees/<slug>-coord` or `.worktrees/<slug>-lane-*` checkout on its own branch that the upgrade path stamps.
- **Upgrade worktree-stamp path**: `_run_no_migrations_worktree_stamp` (`cli/commands/upgrade.py`) → `_upgrade_worktrees` (`upgrade/runner.py`) → `commit_touched_checkout` autocommit — the source of the divergent per-branch commits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `spec-kitty upgrade` N times on an already-current project with live worktrees produces zero new commits on any worktree branch after the first substantive run (0 divergent `last_upgraded_at` values across `main`, coord, and lane branches).
- **SC-002**: After a repeat upgrade, `implement WP##` on a dependent WP and `spec-kitty merge` both exit 0, and `main` contains every approved WP's code — identical to the single-upgrade control.
- **SC-003**: The #4972 regression test is RED on current `main` at the pre-fix entry point and GREEN after the fix; the full targeted upgrade/lanes test suites pass.
- **SC-004**: A genuine (migrations or real-content) upgrade still stamps and auto-commits worktrees, proven by an existing or added test that stays GREEN — no #2385 regression.

## Assumptions

- The fix follows the operator-confirmed **prevention-only** strategy: idempotency at the worktree-stamp source. The lane auto-merge and stale-lane consumers are intentionally left unchanged.
- Implemented as **value alignment, not bare suppression** (post-spec adversarial finding, DM `01M38X487WENDRSAEY24BN841K`): the divergence is minted at the single per-worktree `last_upgraded_at = now_utc()` site in `_upgrade_worktrees`. When the version-only bookkeeping bump is the sole driver, write the main checkout's stored `last_upgraded_at` (shared) so bytes match across branches and merge cleanly regardless of merge base. Bare suppression closes only the literal repro (lane line == merge base) and is not provably general.
- The relevant prior art is the **#1838 save-gate** at `runner.py:531-542` (suppresses when `version==target`), which the fix extends. **#1872** governs migration-record writes inside the worktree migration loop — a different concern that is inert on the no-migrations path — so it is NOT the gate to reuse.
- The fix locus is the shared `_upgrade_worktrees` stamp (all three callers inherit it), not the CLI-only `_run_no_migrations_worktree_stamp` wrapper (two callers bypass it).
- The reproduction and root-cause analysis in issue #4972 (filed against a commit that is an ancestor of current `main`) hold on current `main`; all cited surfaces were confirmed present during grounding.
- "Already current" is detected by the substantive no-op condition (only `version`/`last_upgraded_at` would change), not by counting upgrade runs, so both the operator's second run and a teammate's `current_version == target_version` first run are covered.
