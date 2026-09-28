---
work_package_id: WP08
title: Changelog and documentation closeout
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T040
- T041
- T042
phase: Phase 4 - Closeout
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/CHANGELOG.md
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/**
- docs/api/**
- docs/development/3-2-docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Changelog and documentation closeout

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`. Apply the writing doctrine (audience-oriented writing, DIRECTIVE_047) and the terminology canon (Mission; "local lane consolidation (`spec-kitty consolidate`)", never bare "merge").

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Record the six user-visible fixes and update docs for every changed documented contract (C-007, NFR-003). Runs after WP01–WP07 are approved, so describe what actually landed (read each WP's Activity Log and diff; don't paraphrase the plan).

Done means:
- One `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it) following the house style: bold impact-first lead naming the issues `(#4919, #4900, #4933, #4940, #4998, #4964)`, then **Before:** / **After:** per issue, mission slug `exit-zero-data-intact-01M3KDAS`, and "Bug-fix; no CLI version bump."
- Docs updated wherever they describe: `doctor decisions` always exiting 0 (now: `--repair` exits 1 when a decision can't be reconciled), `.claude/settings.json` handling by `agent config sync --sync-hooks` / `live-work install` (undecodable file → refused untouched, re-save as UTF-8; non-UTF-8 provable encodings → merged with a byte backup), and `migrate` group flags (forwarded or usage error).
- Docs index/freshness checks pass; terminology guard passes.

## Context & Constraints

- Owned: `docs/changelog/CHANGELOG.md`, `docs/guides/**` (incl. `docs/guides/how-to/harnesses/setup-lint-hooks.md`), `docs/api/**` (`cli-commands.md`, `agent-subcommands.md`), the docs retrieval index. If a doc that needs updating lives elsewhere under `docs/`, edit it and record a one-line rationale in the Activity Log (ownership-map leeway; no other WP touches docs).
- Find affected docs: `grep -rn "doctor decisions\|sync-hooks\|settings.json\|migrate --dry-run\|mission_number" docs --include=*.md | grep -v changelog`.
- Keep the entry factual and short relative to neighbours (see recent entries at the top of `[Unreleased]`).

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. `spec-kitty implement WP08` after WP01–WP07.

## Subtasks & Detailed Guidance

### Subtask T040 – CHANGELOG entry

- One bullet under `[Unreleased]` (Fixed/equivalent section used by neighbours). Lead: "**Six commands no longer exit 0 while losing or mis-recording your data** (mission `exit-zero-data-intact-01M3KDAS`; #4919, #4900, #4933, #4940, #4998, #4964)." Then one Before/After sentence pair per issue, using the real behaviour from the WPs (exit codes, backup naming, anchor rule, UTF-32 correction in `recover()` as a side note).

### Subtask T041 – Docs for changed contracts

- Update each doc found by the grep; add a short troubleshooting note for "settings.json is not valid UTF-8" (how to re-save as UTF-8) where agent config / live-work are documented.

### Subtask T042 – Index, freshness, terminology

```bash
uv run --frozen python scripts/docs/docs_index.py --write   # only if a new doc page was added
uv run --frozen python scripts/docs/check_docs_freshness.py --ci   # errors must be 0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Record commands and results in the Activity Log.

## Review Guidance

- Entry matches what landed (spot-check against WP diffs); issues cited; no "merge" where `consolidate` is meant.
- Docs freshness 0 errors; terminology guard green.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
