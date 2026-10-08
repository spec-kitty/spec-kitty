---
work_package_id: WP08
title: Changelog entries for every user-visible fix
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- C-003
- SC-004
- NFR-003
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T20:30:16.196130+00:00'
subtasks:
- T041
- T042
- T043
phase: Phase 3 - Release notes
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5443'
- '#5673'
- '#5229'
- '#4763'
- '#5401'
- '#5671'
- '#4722'
---

# Work Package Prompt: WP08 – Changelog entries for every user-visible fix

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission upgrade-migration-commit-scope-01M4AKVE`). Address every feedback item before completing.

---

## Objectives & Success Criteria

- NFR-003: one `### Fixed` bullet under `## [Unreleased] - 4.0.0rc6` per user-visible change PR 2 ships (IC-08), each under 900 characters (the style guard's `LENGTH_WARNING_LIMIT`, `scripts/docs/check_changelog_style.py:61`; error at 1200, `:60`).
- Each bullet matches the house style of the existing Fixed bullets (`docs/changelog/CHANGELOG.md:56-…` on `origin/main`): a bold, impact-first headline naming what the operator sees, then `(#issue)`, then `**Before:**` … `**After:**` in plain language, each contrast part at most two sentences / 300 characters (`_CONTRAST_MAX_SENTENCES`, `_CONTRAST_MAX_CHARS`, `:58-59`), no internal tokens (WP ids, function names that operators never see, decision ULIDs).
- This WP authors PR 2's bullets only. It does **NOT** write the #5443 bullet: the orchestrator writes that bullet as a landing fold when PR 1 is cut (plan "Landing plan" step 1, Decision `01M4AYQTE5WGNXKW7411AVYP79`), so it is already on the base this WP rebases onto. WP08 keeps its dependencies on WP01–WP07 (it describes what they shipped).
- NFR-003: one bullet (under `### Internal`, or `### Changed` if the style guard requires it) for the removed public exports `GitVCS.commit`, `VCSProtocol.commit` and `init_git_repo` (also dropped from `specify_cli.core.__all__`) — unconditional.
- `python -m scripts.docs.check_changelog_style` exits 0; docs freshness errors = 0.

## Context & Constraints

- Inputs: spec US1–US8 and FR table; each implementing WP's Activity Log holds a drafted bullet (WP01 T010 step 6 drafts the #5443 text for the orchestrator's PR 1 landing fold — not for this WP; WP02–WP07 hand theirs over the same way). Read the merged code/tests of WP01–WP07 for exact operator-visible strings — quote only strings the code actually prints (the no-commit warnings live in `src/specify_cli/upgrade/autocommit.py` after WP01).
- Edit `docs/changelog/CHANGELOG.md` only (the root `CHANGELOG.md` is a symlink to it — never edit the link). PR #5856 also edits this file (C-001, review NOTE 2): append this mission's bullets only, never touch or reflow bullets #5856 adds, and rebase onto the latest base before the PR so a conflict shows up as an add/add hunk, not an edit of #5856's text. Do not touch other sections' existing bullets; do not reorder sections; keep the `<!-- markdownlint-disable MD024 -->` header intact.
- Terminology canon: "Mission", "work package"; never "feature" for a Mission; avoid the phrases the terminology ratchet bans in `docs/` ("lane merge", "lane-merge", "merge the lanes", "merging lanes" — `tests/architectural/test_no_legacy_terminology.py`).
- `execution_mode: code_change` so this WP gets a normal lane and lands with PR 2's code (not the planning lane). Profile `scribe-sally` (or `comms-cleo` if the orchestrator prefers); the work is editorial, no code.
- **Documentation-WP exemption (charter ATDD-first, C-004)**: this WP adds no test module. Its red is recorded in the Activity Log BEFORE the first edit, on the planning base (rebased): `PYTHONPATH=. .venv/bin/python -m scripts.docs.check_changelog_style` output plus an in-scope issue check — for each of #5673, #5229, #4763, #5401, #5671, #4722, `grep -c` on the `## [Unreleased]` section of `docs/changelog/CHANGELOG.md` returns 0 (red: the release notes miss these fixes). Green is the same two checks after the edit (style guard exit 0, each issue in exactly one new bullet).
- If a WP's behaviour changed during review (e.g. WP04's seam, WP07's owned-checkout decision), the code wins over the plan text: describe what shipped.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP08 --agent claude`. One commit (`docs(changelog): commit-scope fixes for PR 2`) holding PR 2's bullets; it never adds, edits or moves the #5443 bullet.

## Subtasks & Detailed Guidance

### Subtask T041 – Red on the planning base; the #5443 bullet is the orchestrator's

- **Purpose**: the documentation-WP red (see Context) and a guard against duplicating PR 1's release note.
- **Steps**:
  1. Rebase onto the latest base. Run the style guard and the in-scope issue check (Context, "Documentation-WP exemption"); record both outputs in the Activity Log as the red.
  2. Confirm the #5443 bullet (written by the orchestrator as a landing fold when PR 1 was cut) is present under `### Fixed`. Do NOT write, edit, reflow or move it. If it is present, leave it byte-identical; if it is absent (PR 1 not yet merged into the base), add nothing for #5443 and note that in the Activity Log — the orchestrator merges `origin/main` into `fix/upgrade-migration-commit-scope` after PR 1 lands, before WP08 starts.
  3. Read it so PR 2's bullets do not overlap it (#5443 = commit behaviour; #4763 = on-disk debris).
- **Validation**: Activity Log shows the red outputs; `git diff` of this WP leaves the #5443 bullet byte-identical.

### Subtask T042 – One bullet per remaining user-visible change

- **Purpose**: every user-visible change is discoverable (IC-08).
- **Steps** (one bullet each, same style, each < 900 chars, issue refs in the headline parentheses):
  1. **Work-package claim commit** (#5673, WP03): claiming a work package no longer commits your edit to `.kittify/config.yaml` or a `meta.json` you had already edited; Before/After as in spec US4. Mention the warning the operator now sees when `meta.json` was dirty (quote WP03's message).
  2. **Mission-number bookkeeping during consolidation** (WP04; cite #5443 as the umbrella if no dedicated issue exists — check WP04's tracker_refs and Activity Log): the `assign mission_number` commit contains only the Mission's `meta.json`; off the target branch, detached, or with your own `meta.json` edit pending, nothing is committed and the number is reported as not yet recorded.
  3. **`metadata.yaml` keeps its keys** (#5229, WP02 incl. T006): after `spec-kitty upgrade` the file keeps `project_uuid` and your own keys and carries the capability map; written atomically.
  4. **Rollback leaves `.kittify/` clean** (#4763, WP01 T005): a failed schema migration no longer copies its backup folders into `.kittify/` or leaves `.kittify/.migration-backup` and a `.gitignore` it created. (If the #5443 bullet — the orchestrator's PR 1 fold — already says "commits nothing when it fails", this bullet is about the on-disk debris; keep them non-overlapping.)
  5. **`safe-commit` path fixes** (#5401, #5671, #4722, WP07): either one bullet per issue or one combined bullet if under 900 chars — prefer one per issue when each has a distinct Before/After: a directory argument now commits a staged rename completely; a symlink argument commits the link (also `spec-commit`), never the file it points to; a batch failure names the failing path and git's reason, and a lone path unknown to disk and git is an error.
  6. **Removed sweeping helpers and shipped text** (WP06): the shipped skills/toolguide/upgrade docs no longer recommend `git add -A`/`git add .`; that is user-visible to agents reading skills → one short bullet under `### Fixed` (or `### Changed` if the guard requires the Changed contrast — check which section the existing "shipped skills name real config keys" bullet used: Fixed). **Unconditionally** (NFR-003) add one bullet for the removed public exports `GitVCS.commit`, `VCSProtocol.commit` and `init_git_repo` (dropped from `specify_cli.core.__all__`; no product callers) under `### Internal` (or `### Changed` if the guard requires it; read `:105-127` for the section's form).
  7. **Merge-conclusion owner and gate** (WP05): internal; add a one-line `### Internal` bullet only if the section's convention covers architectural gates (it lists such items on `origin/main` — read it and match).
  8. Place each bullet at the top of its section (newest first is the file's convention — confirm by reading the section order) and never between an existing bullet and its continuation.
- **Validation**: style guard exit 0; no warning for length on the new bullets.

### Subtask T043 – Gates and closeout

- **Steps**:
  1. `PYTHONPATH=. .venv/bin/python -m scripts.docs.check_changelog_style` → exit 0, no warnings on new bullets.
  2. `PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci` → errors = 0 (bump the front-matter `updated:` date of `CHANGELOG.md` to the landing day if the freshness check or house convention asks for it — it reads `updated: '2026-10-06'` on `origin/main`).
  3. `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
  4. Spelling check if the repo runs one on the changelog (grep `scripts/docs/` for `check_spelling` and run it on the file).
  5. Activity Log: list each bullet's headline, character count and commit SHA, and the green rerun of T041's two checks; mark T041–T043 done.

## Test Strategy

```bash
PYTHONPATH=. .venv/bin/python -m scripts.docs.check_changelog_style
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Risks & Mitigations

- **Duplicating or editing the #5443 bullet** → it is the orchestrator's PR 1 landing fold; T041 step 2 checks it is present and Review Guidance checks it is byte-identical.
- **Describing the plan instead of what shipped** → read each WP's final diff and Activity Log; quote only printed strings.
- **Over-long bullets** → measure; split per issue rather than exceed 900.
- **Overlap between the #5443 and #4763 bullets** → #5443 = commit behaviour, #4763 = on-disk debris.

## Review Guidance

- WP08's diff changes only `docs/changelog/CHANGELOG.md`, adds PR 2's bullets, and leaves the orchestrator's #5443 bullet byte-identical.
- The Activity Log records the red (T041 step 1) before the first edit and the green rerun at the end (documentation-WP exemption).
- Every in-scope issue (#5673, #5229, #4763, #5401, #5671, #4722) appears in exactly one new bullet's parentheses (#5443 only in the orchestrator's bullet, or as the umbrella of the bake bullet); the removed-exports bullet is present; no bullet references WP ids, decision ULIDs or private function names.
- Each new bullet < 900 characters; style guard exit 0.

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Post-tasks review NOTE 2 folded: `docs/changelog/CHANGELOG.md` is also a #5856 file (C-001 updated in spec); append-only, never edit #5856's bullets. Note for T041: after WP01's review fold the held-file warnings are "Held for manual review (not committed): …" / "Skipped auto-commit of N file(s) held for manual review: …"; quote only what merged code prints.
- 2026-10-07 – planner-priti – Analysis fold: AN-INC-001 (orchestrator resolution) — WP08 authors only PR 2's bullets and does NOT write the #5443 bullet (the orchestrator's landing fold when PR 1 is cut); the first-commit cherry-pick instruction is removed; T041 repurposed (red + presence check), dependencies on WP01–WP07 kept. AN-INC-009 — `execution_mode: code_change` (normal lane). AN-CHR-001 — documentation-WP exemption recorded, red = style guard + in-scope issue check on the planning base. AN-CHR-002 — removed-exports bullet unconditional. AN-COV-001 — NFR-003 added to `requirement_refs`.
- 2026-10-07 – orchestrator (recording implementer evidence) – Lane-h: b37820a6f merges origin/main 6d45d8fcc (PR #5873, #5856, #5759). Conflicts resolved in upgrade.py (main's surface-repair gate, #5856 rename, #5759 step kept) and migration/runner.py (WP02 T006 imports kept). d8c810e28 writes the changelog (8 Fixed, 2 Internal, the #5443 bullet's staged-removal sentence edited for FR-022). 36ff1d9f4 (orchestrator) narrows the #5673 bullet to the `--no-auto-commit` limit. Style: 0 errors, warnings 15 before and after. Gates after the merge: upgrade+migration 1459 passed (46 preview failures identical on origin/main); git_ops/lanes/consolidation/coordination/kernel 4810 passed; cli/commands 5769 passed / 9 failed (8 identical on origin/main, plus 1 stale WP03 test logged as a required PR 2 fold); architectural 4332 passed; ruff, format, mypy clean.
- 2026-10-08 – orchestrator – Review cycle 1 rework: 239a3f1d0 applies the reviewer's three corrected bullets. #5673 (707 chars): with `--no-auto-commit`, an operator edit refuses the claim; with auto-commit, the planning-artifacts commit records it. Merge-conclusion gate (775 chars): limited to literal argument lists, with its blind spots named. Removed helpers (427 chars). Style: 0 errors, 15 warnings (same set as main).
- 2026-10-08 – orchestrator – Decisions on the reviewer's deviations: (1) the edit to the existing #5443 bullet's last sentence (FR-022 now carries the untracks) was requested by the orchestrator, because the PR 1 text became false after WP07; (2) the shipped-skills bullet and both Internal bullets keep (#5443) as their umbrella issue, because they describe parts of the #5443 rule.
