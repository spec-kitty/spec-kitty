---
work_package_id: WP02
title: Footgun and concept pages, plus identity
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-010
- FR-011
planning_base_branch: issue-7522-context-refresh
merge_target_branch: issue-7522-context-refresh
branch_strategy: Planning artifacts for this mission were generated on issue-7522-context-refresh. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7522-context-refresh unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Footgun and concept pages
history:
- at: '2026-11-13T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/context/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/context/orchestration.md
- docs/context/execution.md
- docs/context/topology.md
- docs/context/team-kitty.md
- docs/context/identity.md
- scripts/docs/retired_surface_burndown.yaml
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Footgun and concept pages, plus identity

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP02 --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- The five pages are checked claim by claim against the code and CLI (FR-004); corrections logged with evidence, unverifiable facts flagged (FR-005).
- The `primary`, `merge`, `routing` and `residue` disambiguations stay accurate, and every anchor linked from `CLAUDE.md`, `AGENTS.md` or another doc still resolves (FR-006, C-003).
- `team-kitty.md` describes the #6164 state: hosted surfaces removed from open-core, the Mission Status Read API as what remains (FR-007); fixes D7 (`spec-kitty charter sync` was removed in #5828).
- No page names a retired surface; all 11 `context/` burn-down pairs are drained and `test_retired_surface_gate.burn_down` goes from 81 to 70, each pair with its page fix in the same commit (FR-008).
- Each page names its reader (plan.md Decision 4) and has a verified `updated` (FR-003, FR-010).

## Context & Constraints

- Plan Decisions 4, 5, 6, 8; gap analysis D6 to D8.
- `CLAUDE.md` Terminology Canon and its Team Kitty section are the operator's current statement; they are not themselves sources of truth over the code: where they disagree with the code, flag it (example O1 in `operator-flags.md`).
- Retired set: `scripts/retired_surfaces.py`. The gate's hint: a STALE entry leaves `scripts/docs/retired_surface_burndown.yaml` and `test_retired_surface_gate.burn_down` is lowered to match in the same pull request. `scripts/docs/retired_surface_landing.yaml` stays as is (C-004).
- Commit nothing to this WP after it is approved (C-005).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-7522-context-refresh
- **Merge target branch**: issue-7522-context-refresh

```bash
spec-kitty agent action implement WP02 --agent claude --mission context-docs-refresh-01M7AN3N
```

## Subtasks & Detailed Guidance

### Subtask T008 – Snapshot anchors and baseline

- List every heading slug on the five pages and every inbound link to them:
  `git grep -nE "(orchestration|execution|topology|team-kitty|identity)\.md#" -- . ':!kitty-specs' ':!docs/archive'`.
- Record the gate state (`make docs-lint`, strict link check). Keep the list for the T013 comparison.

### Subtask T009 – `orchestration.md`

- Check each glossary entry's definition, owning module and command against the source (`git grep`, `--help`). Pay special attention to the footgun entries (`#primary-partition`, `#primary-branch`, `#target-ref--commit-target`, `#lane-consolidation`, `#branch-integration--git-merge`, `#publish-to-originmain`, `#routing`, `#residue`).
- Burn-down pairs: `spec-kitty merge` (1), `src/specify_cli/auth` (1), `src/specify_cli/delivery` (1), `src/specify_cli/sync` (2). Describe the retired sense without naming the retired path ("the retired sync transport, removed in #6164 and August 2026"); `spec-kitty merge` → say `spec-kitty consolidate` (the rename is #3080).
- The audit flags `mixed` (How-To headings): keep it an Explanation; move or trim any step-by-step part.

### Subtask T010 – `execution.md` and `topology.md`

- Same check. Anchors linked from `CLAUDE.md`: `execution.md#pack-skill`, `#repository-root-checkout`; `topology.md` from `CLAUDE.md` and three docs (`#started-work-package`, `#topic-branch`, `#lane-work-tip`).
- `topology.md`: verify against `src/specify_cli/lanes/topology_settlement.py` and the create-time default (ADR `2026-11-06-3`).

### Subtask T011 – `team-kitty.md`

- Reflect #6164: the hosted CLI entries, clients and drain posture are removed from open-core (code preserved in `spec-kitty/event-router`); open-core keeps the produce seam (`src/specify_cli/status/adapters.py`) and the Mission Status Read API (ADR `2026-10-01-2`; pinned build in `pins/read-service.source.yaml`).
- Burn-down pairs: `Zeitgeist` (2 identifier lines), `saas_client` (1), `spec-kitty sync` (1), `src/specify_cli/sync` (1). Fix D7.
- Keep the anchors other pages link to; the title may stay "Team Kitty and Zeitgeist" only if the gate's patterns allow the product name in prose (check `scripts/retired_surfaces.py`).

### Subtask T012 – `identity.md`

- Burn-down pairs: `saas_client` (1), `src/specify_cli/egress.py` (1), `src/specify_cli/tracker/saas_client.py` (1).
- Check the `#human-in-charge-hic` entry and the engagement entry whose example quotes a hosted-sync refusal: verify the message still exists in `src/` (`git grep`); if not, the example is historical and must say so or go (logged).

### Subtask T013 – Burn-down, logs, gates, self-review

- Each page commit removes its pairs from `scripts/docs/retired_surface_burndown.yaml` and lowers `test_retired_surface_gate.burn_down` (with the justification-comment convention already in that file).
- Compare heading slugs with the T008 snapshot; any lost linked slug fails the WP.
- Frontmatter (`audience:`, `updated`), corrections log and operator flags.
- Gates (committed state): as WP01 T007, plus `uv run pytest tests/docs/test_glossary_residue_entry.py tests/docs/test_context_glossary_contract_scenario_and_pack_level.py -q`.

## Risks & Mitigations

- The orchestration glossary is long and dense; a "simplification" can change a definition. Change wording only where a claim is wrong or the guidance requires it; log every factual change.

## Review Guidance

- Burn-down count 70; no `context/` entry left.
- Anchor list unchanged (or redirect recorded).
- Every definition change has evidence.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
