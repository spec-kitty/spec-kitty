---
work_package_id: WP05
title: Docs, ADR and changelog
dependencies:
- WP03
- WP04
- WP06
requirement_refs:
- C-001
- C-002
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T15:29:02.258690+00:00'
subtasks:
- T019
- T020
- T021
phase: Phase 3 - Docs
history:
- at: '2026-10-05T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/3.x/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
- CLAUDE.md
- docs/changelog/CHANGELOG.md
- docs/guides/how-to/recovery/troubleshoot-merge.md
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Docs, ADR and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show scribe-sally`) to load the agent profile in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Document what WP01–WP04 shipped. Describe the code as it is now; read the merged diff on `issue-5686-rollback-anchor` first.

## Subtasks & Detailed Guidance

### Subtask T019 – ADR follow-up

Append a dated "Follow-up 2026-10-05 (#5686 / #5666)" section to `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`, in the style of the existing follow-ups. Cover:
- the retirement of `_rollback_target_after_failed_reconciliation`, so a FAIL/REFUSE restores only through the door, and the widened AST pin;
- per-branch unsettled marks: an orderly exit does not settle a branch. Explain how this supersedes the A2 "keep an operator change between attempts" rule, which now applies only to settled branches;
- advance-intent chains, and adoption only with an expected base;
- the recorder taint (FR-011);
- `UNEXPLAINED_BRANCH_MOVE` and `RELEASE_BRANCH_INVALID`, and `--abort --release-branch`;
- the restore over a lagging checkout;
- the remaining residuals:
  - the same-phase foreign commit;
  - no tool-mediated undo of an unprovable landing (follow-up issue);
  - resume recovery's checkout reset before the refusal;
  - #5372, #5667, #5638, #5048(a);
  - the remaining second restore path, `repair_coord_strand`.

Update the ADR's `updated:` front-matter date if present.

### Subtask T020 – CLAUDE.md

In the "Consolidation & Preflight Patterns" section, in the paragraph about refusals and failures rolling back through one authority:
- Change "Remaining second restore paths: `_rollback_target_after_failed_reconciliation` and `repair_coord_strand`" so it names only the paths that remain.
- Add one or two sentences on unsettled marks, advance intents, `UNEXPLAINED_BRANCH_MOVE` and `--abort --release-branch`. Keep the dense style of the surrounding text, and do not restate the ADR.

### Subtask T021 – Changelog and operator docs

`CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`, so edit the real file. Also document `--abort --release-branch/--release-reason`, `UNEXPLAINED_BRANCH_MOVE` and `RELEASE_BRANCH_INVALID` in `docs/guides/how-to/recovery/troubleshoot-merge.md` and `docs/api/cli-commands.md`, keeping each page's front-matter `updated:` date fresh.

ADR residuals to record: the in-span moves that report no intent (`bake.py:389` plain commit, the plain `safe_commit` path), as listed in WP03's activity log.


Under `## [Unreleased] - 4.0.0rc6`, add a `### Fixed` entry in the **Before/After** style the file uses, naming #5686 and #5666 (and the #5687 deadlock part). If the abort option is listed under Added in this file's convention, add the `--release-branch` option there too. Bump the front-matter `updated:` date.

## Carried from the WP04 review

- Document in `troubleshoot-merge.md`: a release saved by an `--abort` that then fails on another branch stays in the record. A later plain `--abort` still honours it while the released branch sits at the bound SHA, and the report shows it as `kept`.

## Carried from the WP03 review: ADR residuals

- If the only unexplained branch is the coordination branch named by a `pending_coord_reconcile` marker, the pre-check skips it. A requested `--attest-canceled-superseded` status commit can then land before the claim refuses with `UNEXPLAINED_BRANCH_MOVE`.
- A kill after the PASS anchor is saved but before the squash projection proof leaves an anchor that turns off the pre-check. That is no worse than today: `rollback_to_snapshot` refuses while the PASS holds (FR-011), and the resume re-runs the projection proof.
- After a PASS, this run's own coordination-branch commits outside the span (teardown bookkeeping) are not recorded. A resume after the target moves off the anchor refuses with `UNEXPLAINED_BRANCH_MOVE`.
- A killed run's global merge lock is not reclaimed (unchanged behaviour).
- The PASS-anchor exemption (option (a)): while the live target equals the PASS anchor, the unexplained-move refusal is skipped. Rationale: FR-011 forbids any rollback, and teardown deletes are compare-and-swap protected.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/docs -q -k "adr or changelog or freshness" -n auto --dist loadfile
```

Also run any docs index regeneration the repository requires for ADR edits. Check `docs/adr/README.md`; `git log` shows "re-derive the ADR index" commits.

## Activity Log

- 2026-10-05T12:00:00Z – system – Prompt created.
- 2026-10-05T16:30:00Z – claude – WP05 c76592dc (lane-e): ADR 2026-09-19-1 follow-up 2026-10-05 (+References line, updated: 2026-10-05); CLAUDE.md paragraph (only repair_coord_strand + resume recovery resets remain; one dense sentence each on #5666 and the #5686 authority); CHANGELOG Added (--release-branch/--release-reason) + Fixed #5666 and #5686 (+#5687 deadlock part), updated bumped; troubleshoot-merge.md (Quick Reference rows, --abort report kinds, new "Keep a branch that cannot be restored" incl. the WP04 sticky-release note, new "A branch moved without a record"); cli-commands.md (RELEASE_BRANCH_INVALID + UNEXPLAINED_BRANCH_MOVE rows, --release-branch bullet, consolidate help block refreshed from live `consolidate --help` via build_cli_reference.capture_help, only that block).
- 2026-10-05T16:30:05Z – claude – Leeway edits: AGENTS.md (CLAUDE.md is a symlink to it in this repo; the guard flags it as outside owned_files); docs/development/docs-retrieval-index.yaml re-derived with `scripts/docs/docs_index.py --write` (3 new heading anchors; page-inventory lockfile: no drift).
- 2026-10-05T16:30:10Z – claude – Tests: pytest tests/architectural/test_no_legacy_terminology.py + tests/docs/{test_docs_spelling_live,test_docs_structural_lint,test_touched_set_gates,test_description_length_gate,test_adr_content_invariance,test_published_pages,test_docs_index_freshness,test_changelog_style,test_adr_readme_prose,test_architecture_docs_consistency,test_rulers_blocking,test_sync_changelog,test_build_cli_reference}.py -> 526 passed (first run 2 failed in test_changelog_style: banned token FAIL + entry >1200 chars; fixed). check_changelog_style: 0 errors (two new entries carry the 900-char soft warning, as do 12 existing ones). check_cli_reference_freshness: no consolidate finding; --strict-mode red only on pre-existing materialize/moments HELP-DRIFT.
