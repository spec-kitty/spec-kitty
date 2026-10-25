---
work_package_id: WP07
title: Red-first guard, ADR amendment, changelog
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-009
- NFR-004
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
- T029
- T030
phase: Phase 4 - Close-out
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/integration/migration/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py
- tests/integration/migration/test_upgrade_residue_identity_6627.py
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- docs/changelog/CHANGELOG.md
- tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Red-first guard, ADR amendment, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py` (from PR #6672, cherry-picked onto this branch):
  - covers all 5 leftover shapes of US1 (tasks WP, event log, status snapshot with and without a log, `tasks/doing/` lane file, `decisions/`), plus two controls in the same project:
    - a real Mission with identity;
    - a **committed legacy Mission**: a tracked `spec.md`, no `meta.json`, and a tracked `tasks/doing/WP01-x.md`. It must still be migrated (identity minted, lane file moved), which proves the git-aware rule did not turn real pre-identity Missions into residue (post-tasks review M9);
  - asserts each residue folder is named in the upgrade output exactly once;
  - **loses its `@pytest.mark.p0_repro(issue=6669)` marker** and passes per PR (FR-009, ADR 2026-07-17-1);
  - its docstring says it was the red-first `p0_repro` and is now a per-PR guard, as the #6627 guard's docstring already does.
- The #6627 guard still passes.
- ADR 2026-10-17-1 gains an Amendment (C-002). It covers:
  - successors that are **new migrations** placed in their predecessor's slot (`# tie:`);
  - the ledger-gated `detect()` using the selection view;
  - the four superseded ids;
  - the accepted residual C-006.
- `docs/changelog/CHANGELOG.md` `[Unreleased]` → `### Fixed` carries an entry for #6669, in impact-first before/after style, naming the accepted cost. `### Added` carries one for #6668 (the doctor finding).
- NFR-001: `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` is empty.
- Requirement refs: FR-009, NFR-004, C-003, C-004, C-005, SC-001..SC-004.

## Context & Constraints

- Every other WP must be merged into this lane first. This WP proves the end-to-end behaviour through the real `spec-kitty upgrade` CLI.
- Each in-process upgrade takes about a minute. Build one project per shape with `pytest.mark.parametrize`, or a single project holding all five residue folders. One upgrade with all five folders is preferred: it also proves the once-per-folder notice collapse (WP04).
- Changelog style: read the top of `docs/changelog/CHANGELOG.md` and the #6627 entry (written by #6662) for tone. The docs-lint and changelog-style CI job checks style.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

```bash
spec-kitty agent action implement WP07 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T027 – Extend the guard and drop the marker

- Remove `@pytest.mark.p0_repro(issue=6669)`.
- Assert:
  - every residue folder is byte-identical (snapshot before and after);
  - nothing under it is tracked;
  - the real Mission keeps its `mission_id`;
  - the upgrade output names each residue folder exactly once;
  - exit code 0.
- Run the test once **without** the fixes to keep the red-first evidence honest: check out `origin/main` source in a scratch worktree, or record the PR #6672 CI evidence in the WP history.

### Subtask T028 – ADR 2026-10-17-1 Amendment

- Append `## Amendment 2026-10-25b (#6669: residue-aware successors)`, following the style of Amendment 2026-10-25. Cover:
  - why a successor is a new migration and not a rewrite;
  - why it sits in its predecessor's slot;
  - the selection-view gate;
  - the accepted residual (C-006);
  - the stale "re-skipped every run" listing in `migrate ledger` for the successor on settled projects.
- If ADR index tooling exists, regenerate it (`uv run python -m scripts.docs.docs_index --write`, then `uv run python -m scripts.docs.check_docs_freshness --ci`). Check `scripts/docs/` for the exact module names.

### Subtask T029 – CHANGELOG

- Under `### Fixed`, describe #6669:
  - **Before:** an upgrade fabricated an identity, wrote status files into Mission-shaped leftovers, and moved or rewrote leftover WP files.
  - **After:** such folders are left untouched and reported once; real Missions are repaired as before.
  - Name the accepted cost (committed tasks-only folders in a tracked project count as residue) and the remedy.
- Under `### Added`, describe the #6668 doctor finding and its remedy, and state that it never deletes.

### Subtask T030 – Validate and record

- **Corpus parity gate**: this mission's own coordination branch is live while the PR is open, so `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` lists it as an unlisted live-coordination skip. Add `"residue-safe-migration-sweep-01M5SS0F"` to `LIVE_COORDINATION_SKIPS`, with the reason "this Mission's coordination branch is live until it is consolidated (#6669)". Removing it is a closeout item for the merge.
- **C-003 / C-004 check**: `git diff --stat origin/main -- src/specify_cli/status/ src/specify_cli/frontmatter.py src/specify_cli/upgrade/feature_meta.py` must show no behaviour change to the status model, the frontmatter writer or `backfill_mission`. `feature_meta.py` may show only the WP06 `baseline_slug_fields` extraction. Record the output in the WP history.
- **Success-criteria trace**: SC-001 and SC-002 are covered by this guard. SC-003 (real Missions repaired as before) is covered by WP03's T015 parity cases and WP02's equivalence test. SC-004 (fabricated identities reported, never deleted) is covered by WP06's T026. Cite the test names in the WP history.

- Walk through `kitty-specs/residue-safe-migration-sweep-01M5SS0F/quickstart.md`.
- Run the NFR-001 command.
- Run the blast-radius suites and record commands with pass/fail counts in the WP history. Classify any red per the AGENTS.md baseline-red rules: `test_mission_corpus_recovery.py` is a shallow-clone environment red, and dirty-tree refusals mean commit first.
- Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py`.

## Test Strategy

```bash
uv run --frozen pytest tests/integration/migration -n 4 --dist loadfile -q
uv run --frozen pytest tests/architectural/test_migration_order_manifest.py tests/architectural/test_migration_walkers_use_mission_predicate.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'
```

## Risks & Mitigations

- **Runtime**: one upgrade per test function, with shared fixtures.
- **Changelog conflicts with parallel PRs** (#6655 edits the same section): union-resolve at rebase.

## Review Guidance

- Confirm the marker is removed, every shape is covered, and the "exactly once" assertion exists.
- Read the ADR amendment against the code that actually landed: selection-view helper name, successor ids, manifest lines.

## Progress & Status

- `spec-kitty agent tasks add-history WP07 --note "..."`, `spec-kitty agent tasks move-task WP07 --to <status>`, `spec-kitty agent tasks status`.
