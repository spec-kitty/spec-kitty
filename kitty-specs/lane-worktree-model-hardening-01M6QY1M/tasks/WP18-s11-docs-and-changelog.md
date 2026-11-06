---
work_package_id: WP18
title: S11 docs pages and changelog fragments
dependencies:
- WP17
requirement_refs:
- FR-059
- FR-093
- C-001
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T112
- T113
- T116
phase: Phase 7 - S11 text that follows behaviour
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7277-one-status-read-contract.fixed.md
- docs/changelog/unreleased/7278-for-review-gate-reads-lane-branch.fixed.md
- docs/changelog/unreleased/7279-one-lane-checkout-helper.internal.md
- docs/changelog/unreleased/7280-lane-cleanup-last-step.changed.md
- docs/changelog/unreleased/7281-lane-checkouts-hide-status.changed.md
- docs/changelog/unreleased/7281-lane-checkouts-hide-status.upgrade-notes.md
- docs/changelog/unreleased/7282-topology-settled-at-finalize.changed.md
- docs/changelog/unreleased/7282-topology-settled-at-finalize.upgrade-notes.md
- docs/changelog/unreleased/7283-single-branch-approval-windows.fixed.md
- docs/changelog/unreleased/7283-single-branch-approval-windows.upgrade-notes.md
- docs/changelog/unreleased/7284-worktree-free-coordination-adrs.internal.md
- docs/changelog/unreleased/7285-skills-teach-shipped-model.changed.md
execution_mode: code_change
model: ''
owned_files:
- docs/architecture/execution-lanes.md
- docs/architecture/git-worktrees.md
- docs/context/topology.md
- docs/changelog/unreleased/7277-one-status-read-contract.fixed.md
- docs/changelog/unreleased/7278-for-review-gate-reads-lane-branch.fixed.md
- docs/changelog/unreleased/7279-one-lane-checkout-helper.internal.md
- docs/changelog/unreleased/7280-lane-cleanup-last-step.changed.md
- docs/changelog/unreleased/7281-lane-checkouts-hide-status.changed.md
- docs/changelog/unreleased/7281-lane-checkouts-hide-status.upgrade-notes.md
- docs/changelog/unreleased/7282-topology-settled-at-finalize.changed.md
- docs/changelog/unreleased/7282-topology-settled-at-finalize.upgrade-notes.md
- docs/changelog/unreleased/7283-single-branch-approval-windows.fixed.md
- docs/changelog/unreleased/7283-single-branch-approval-windows.upgrade-notes.md
- docs/changelog/unreleased/7284-worktree-free-coordination-adrs.internal.md
- docs/changelog/unreleased/7285-skills-teach-shipped-model.changed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP18 - S11 docs pages and changelog fragments

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP18 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP18 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

- FR-059 (docs half): `docs/context/topology.md`, `docs/architecture/execution-lanes.md` and `docs/architecture/git-worktrees.md` describe the size default (settled once at the first `finalize-tasks`), the Mission topic branch, that the coordination branch shares the Mission branch's name (`kitty/mission-<slug>-<mid8>`), lanes cut from the topic branch, lane checkouts without status files, the status read door, the for_review gate on the lane branch, and cleanup as the last consolidation step. Never "explicit-only" for the default.
- One changelog fragment set per issue (#7277-#7285), in `docs/changelog/unreleased/` per its README (`<id>.<section>.md`, Before/After/What to do style, US spelling). #7280's pr-mode part is WP16's own fragment; do not describe pr-mode cleanup or the Mission-lane prune backstop here unless WP16 has landed.
- The open-packs doctrine (FR-092) is already applied in spec-kitty-open-packs PR #128 (ready, ungated); WP19 is canceled at implement time and this Mission does not bump the core pack pin. Keep your wording consistent with PR #128.

## Context & Constraints

- Read: spec FR-059, FR-092, FR-093, C-001, C-002; `research.md` R-11; `quickstart.md` (operator-facing wording); `upstream/doctrine-and-write-service-adr-map.md` (31 pack edits over 17 files, the K rows); tracer friction on the open-packs pin (`a79c3631` pinned tree vs research scan at `23686fb`; open-packs push denied, so the patch is a hand-off); WP01/WP02/WP03 ADRs; WP17's skill wording (stay consistent).
- **Rule 8 / FR-093**: every behaviour sentence must trace to a shipped FR. Withhold lease text (C-007) and WP16 behaviour unless it landed.
- C-002: never edit `packs/built-in/` or `packs/internal/` in core; the patch is a file in the Mission dir.
- This WP owns only `docs/` files but runs as `code_change` so it can sit after WP17 in a code lane (the planning lane may not depend on code lanes: a planning WP here would form a lane cycle). It must not change any `kitty-specs/` file.
- Fragment ids: the README asks for the PR number once known; until then `<issue>-<slug>` as listed in `owned_files`. If the operator renames them at PR time, that is expected.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T112 - Docs pages

- `docs/context/topology.md`: the topology lifecycle (spec "Topology Lifecycle" diagram as prose or mermaid), size rule incl. ties, explicit values, the topic branch name and its roles, `topology_source`/`topology_settled`, PRIMARY placement of default Missions (FR-061).
- `docs/architecture/execution-lanes.md`: lanes cut from the topic/coordination branch; the for_review gate on the lane branch; the one lane-checkout helper; status never in lane checkouts; approval windows for `single_branch`; cleanup last.
- `docs/architecture/git-worktrees.md`: worktree vocabulary table; which checkouts are disposable; the read door; the clone-local migration report outcomes.
- Keep each page's frontmatter (`title`, `description` <= 180 chars, `doc_status`, `updated: 2026-11-06` or the actual date) valid.

### Subtask T113 - Changelog fragments [P]

- One entry per file, in the README's style: `- **<what changed>** (#NNNN). **Before:** ... **After:** ... **What to do:** ...`. Upgrade-notes fragments: #7281 (the clone-local migration and its `refused_lane_only_events` outcome), #7282 (default create now mints only a topic branch; settles at finalize), #7283 (in-flight `single_branch` Missions refuse `APPROVAL_STAMP_MISSING`; attest per WP).

### Subtask T116 - Validation

```bash
cd <workspace>
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
git diff --check
```

Run any docs frontmatter/link validator under `scripts/docs/` on the three pages. Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP18] ...**`, naming `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/tooling-friction.md`, `approach.md` or `design-decisions.md`); the orchestrator appends them.

## Risks & Mitigations

- Text ahead of behaviour: check each sentence against merged code; withhold otherwise.

## Review Guidance

- Docs say "settled at first finalize", never "explicit-only" for the default; coordination branch shares the Mission branch name; fragments valid; no lease text.

## Definition of Done

- T112, T113, T116 done; validations green.

## Progress & Status

- `spec-kitty agent tasks mark-status T112 T113 T116 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP18 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
