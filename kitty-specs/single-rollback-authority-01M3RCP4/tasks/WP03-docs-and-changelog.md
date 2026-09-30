---
work_package_id: WP03
title: Docs and changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-006
- C-005
planning_base_branch: claude/5385-single-rollback-authority-qqt180
merge_target_branch: claude/5385-single-rollback-authority-qqt180
branch_strategy: Planning artifacts for this mission were generated on claude/5385-single-rollback-authority-qqt180. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/5385-single-rollback-authority-qqt180 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-rollback-authority-01M3RCP4
base_commit: e0235952dc5794a1f0a4129183d8d117ba430752
created_at: '2026-09-30T08:39:39.394238+00:00'
subtasks:
- T014
- T015
- T016
phase: Phase 3 - Polish
agent: claude
history:
- at: '2026-09-30T06:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/adr/3.x/
execution_mode: code_change
owned_files:
- docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md
- docs/changelog/CHANGELOG.md
- CLAUDE.md
- AGENTS.md
role: implementer
---

# WP03 — Docs and changelog

## ⚡ Do This First: Load Agent Profile

Load `scribe-sally` (`/ad-hoc-profile-load scribe-sally`); read `.kittify/charter/charter.md` (writing doctrine: plain language, docs mirror shipped behaviour).

## Objective

Record what WP01 and WP02 shipped. Docs mirror the code on the lane head; read the diff (`git diff <base>..HEAD -- src/`) before writing.

## Branch Strategy

Planning base and merge target: `claude/5385-single-rollback-authority-qqt180`; run `spec-kitty agent action implement WP03 --agent claude`.

## Subtasks

### T014 — ADR follow-up

In `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md`, after the 2026-09-29 amendment, add a short dated follow-up (2026-09-30, mission `single-rollback-authority-01M3RCP4`, #5385): every exit between the first mutation and the gate now goes through A3 (one `try` in the driver, including exceptions and interrupts); `_reset_coord_to_checkpoint`, `_revert_coord_done_commit`, `_rollback_to_pre_mutation_checkpoint` and `_revert_orphan_target_bake_commit` are retired (the "Remaining authorities" list shrinks to `_rollback_target_after_failed_reconciliation` and `repair_coord_strand`); the protected-target preflight reuses the transaction's policy gate; the named residuals from the spec. Keep the ADR's `updated:` date current if it has one. Update the references line at the end (#5385 no longer a residual).

### T015 — CLAUDE.md

In the "Refusals and failures roll back through one authority" paragraph of `CLAUDE.md`, replace "the other in-phase exits are residual #5385" with the new behaviour (all post-mutation exits, the preflight, the named residuals) in the same terse style. `AGENTS.md` is a byte-identical regular file (not a symlink): apply the same edit there and keep the two identical. List any other hit of `rg -n "residual #5385" -- *.md docs` in your report.

### T016 — CHANGELOG

`docs/changelog/CHANGELOG.md` `[Unreleased]`: one entry, bold impact-first lead with `(#5385)`, then before -> after, consumer-focused (what an operator running `spec-kitty consolidate` sees). No version bump. Root `CHANGELOG.md` is a symlink to this file; bump the file's `updated:` frontmatter date.

## Validation

`.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (0 errors), `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`, and if a docs index lists ADRs, `scripts/docs/docs_index.py --write` then commit its output.
