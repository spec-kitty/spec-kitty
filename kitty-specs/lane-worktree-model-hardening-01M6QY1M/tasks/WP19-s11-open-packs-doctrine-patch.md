---
work_package_id: WP19
title: S11 open-packs doctrine patch and hand-off
dependencies: []
requirement_refs:
- FR-092
- FR-093
- C-002
- SC-011
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T114
- T115
- T117
phase: Phase 7 - S11 text that follows behaviour
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/
create_intent:
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/open-packs-doctrine.patch
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/open-packs-handoff.md
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/open-packs-doctrine.patch
- kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/open-packs-handoff.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP19 - S11 open-packs doctrine patch and hand-off

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP19 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP19 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Why this WP has no dependencies

It is a planning-artifact WP (every owned file is under `kitty-specs/`), so `finalize-tasks` places it in the planning lane, and the planning lane may not depend on a code lane (that formed a lane cycle when the patch sat in the docs WP). The patch is a **hand-off file**: it reaches agents only after the operator lands it in `spec-kitty-open-packs` and bumps the core pin, which happens after this Mission's PR merges. Rule 8 / FR-093 therefore holds as long as the patch carries only rows whose behaviour this Mission ships. **Hand-off gate**: the orchestrator must not hand the patch to the open-packs maintainer until WP07, WP08, WP10, WP12, WP14 and WP15 are approved; rows for WP16 behaviour (pr-mode cleanup, Mission-lane prune backstop) are withheld unless WP16 has landed. Re-run T117 at hand-off time.

## Objectives & Success Criteria

- FR-092: a patch against the pinned `spec-kitty-open-packs` tree, delivered as `upstream/open-packs-doctrine.patch`, carrying: the status-surface rule, the worktree vocabulary and glossary terms (lane branch, lane checkout, harness isolation worktree, coordination worktree, write checkout, Mission topic branch, provisional/settled topology, approval window, kept vs retained lane), the `consolidate` wording, a `lane-recovery` tactic, and only the rows whose behaviour this Mission ships.
- `upstream/open-packs-handoff.md` with the hand-off steps and the withheld rows.
- SC-011 (pack half): `git apply --check` succeeds on the pinned tree.

## Context & Constraints

- Read: spec FR-092, FR-093, C-001, C-002, C-007; `research.md` R-11; `upstream/doctrine-and-write-service-adr-map.md` (31 pack edits over 17 files); tracer friction on the open-packs pin (pinned tree `a79c3631` vs research scan `23686fb`; open-packs push denied, so the patch is a hand-off; review of open-packs PR #128 found core follow-ups); spec "Domain Language" table (glossary wording); WP01/WP02/WP03 ADRs.
- C-002: never edit `packs/built-in/` or `packs/internal/` in core.
- No lease text (C-007).
- Find the pinned tree: `cat packs/built-in.source.yaml` (repo, ref sha, subtree); the cache after `make sync-packs` is `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<sha>/<subtree>`; a read-only clone may exist at `/home/user/spec-kitty-open-packs` (use a temporary `git worktree` at the pinned sha; never push).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T114 - Open-packs patch

- In a temporary checkout of the pinned open-packs tree make the edits listed in the ADR map, row by row, each tagged in the patch's commit-message header (or the hand-off note) with the FR that delivers its behaviour. Then `git diff > <mission>/upstream/open-packs-doctrine.patch`. Paths are relative to the open-packs repository root (`packs/built-in/...`).
- Glossary terms use the spec's Domain Language definitions verbatim where possible; name the sense of "primary", "merge", "routing" and "residue".
- `lane-recovery` tactic: `DESTROYED_LANE` and `LANE_WORK_TIP_UNKNOWN` -> follow the command the CLI prints; stale lane -> `spec-kitty agent action implement <WP>`; never `cd .worktrees/` + `git merge`.

### Subtask T115 - Hand-off note

- `upstream/open-packs-handoff.md`: what the patch carries (row list with FR refs), the pinned sha it applies to, the hand-off gate above, steps: open a PR in `spec-kitty-open-packs`; after it merges, in core `spec-kitty charter pack vendor --pack built-in --ref <sha>`, `make sync-packs`, `spec-kitty charter pack regenerate-graph`; withheld rows and why (lease; WP16 behaviour if not landed).

### Subtask T117 - Validation

```bash
git -C <pinned open-packs checkout> apply --check <abs path>/kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/open-packs-doctrine.patch
cd /home/user/spec-kitty && uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Tracer files

Append to `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/{tooling-friction,approach,design-decisions}.md` (`- **[YYYY-MM-DD][implement WP19] ...**`); if your workspace must not change those files, return the lines in your completion summary.

## Risks & Mitigations

- Pin drift: always diff against the pinned sha.
- Text ahead of behaviour: the hand-off gate and the FR tag per row.

## Review Guidance

- Patch applies cleanly; every row traces to a shipped FR; no lease text; hand-off steps complete.

## Definition of Done

- T114, T115, T117 done; `git apply --check` green.

## Progress & Status

- `spec-kitty agent tasks mark-status T114 T115 T117 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP19 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
