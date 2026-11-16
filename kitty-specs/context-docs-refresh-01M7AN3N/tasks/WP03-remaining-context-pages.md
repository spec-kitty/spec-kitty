---
work_package_id: WP03
title: Remaining context pages
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-009
- FR-010
- FR-011
planning_base_branch: issue-7522-context-refresh
merge_target_branch: issue-7522-context-refresh
branch_strategy: Planning artifacts for this mission were generated on issue-7522-context-refresh. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7522-context-refresh unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Remaining context pages
history:
- at: '2026-11-13T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/context/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/context/README.md
- docs/context/charter.md
- docs/context/charter-overview.md
- docs/context/governance.md
- docs/context/governance-files.md
- docs/context/identity-fields.md
- docs/context/configuration-project-structure.md
- docs/context/dossier.md
- docs/context/system-events.md
- docs/context/contextive-glossaries.md
- docs/context/glossary-conventions.md
- docs/context/lexical.md
- docs/context/historical-terms.md
- docs/context/spec-driven.md
- docs/context/practices-principles.md
- docs/context/testing-taxonomy.md
- docs/context/technology-foundations.md
- docs/context/naming-decision-tool-vs-agent.md
- docs/context/product-lines.md
- docs/context/ops-vs-missions.md
- docs/context/mission-types.md
- docs/context/planning-and-tracking.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Remaining context pages

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
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP03 --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- The 22 pages are checked claim by claim against the code and CLI (FR-004), corrections logged, unverifiable facts flagged (FR-005).
- Each page names its reader per plan.md Decision 4 (FR-003); pages that already name one keep it unless it is wrong.
- `contextive-glossaries.md` loses its text-drawn diagram for Mermaid with `%% title:` and `%% description:` (FR-009, D12).
- Dead references fixed: `spec-driven.md` (D10), `testing-taxonomy.md` (D11); `context/README.md` no longer presents the hosted flow as live (D9).
- Mixed Divio types resolved on `charter.md`, `identity-fields.md`, `mission-types.md` (FR-011, `divio-type-discipline`).
- `updated` bumped only where checked (FR-010).

## Context & Constraints

- Plan Decisions 1, 4, 7, 8; gap analysis D9 to D12. This WP owns no burn-down entry (WP02 does).
- No retired surface may be introduced: `make docs-lint` fails on a new pair.
- Commit nothing to this WP after it is approved (C-005).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-7522-context-refresh
- **Merge target branch**: issue-7522-context-refresh

```bash
spec-kitty agent action implement WP03 --agent claude --mission context-docs-refresh-01M7AN3N
```

## Subtasks & Detailed Guidance

Each subtask: read the page; verify every command (`--help`), flag, path (`git ls-files`), module and behaviour claim (source); fix what the code disproves; log each fix; name the reader; one commit per subtask.

### Subtask T014 – Governance and charter pages

- `charter.md` (827 lines, mixed How-To/Reference headings), `charter-overview.md`, `governance.md`, `governance-files.md`.
- Verify the activation ledger, cascade and kind vocabulary against `src/charter/activation/` and the `CLAUDE.md` "Charter Activation and Doctrine Integrity Model" section; `spec-kitty charter` subcommands against `--help` (no `sync`, removed in #5828).

### Subtask T015 – Identity fields, configuration and records

- `identity-fields.md` (mixed Reference) against `meta.json` fields and `src/specify_cli/mission_metadata.py`; `configuration-project-structure.md` against `.kittify/` layout; `dossier.md` against `src/specify_cli/dossier/`; `system-events.md` against `spec_kitty_events` usage and `src/specify_cli/status/`.

### Subtask T016 – Glossary tooling

- `contextive-glossaries.md`: convert the text diagram to Mermaid (`mermaid-diagramming` toolguide); `src/specify_cli/my_new_package` is an illustrative placeholder in an example (keep, note in self-review). Verify the generator command and `.kittify/traceability/contextive-map.yaml`.
- `glossary-conventions.md`, `lexical.md`, `historical-terms.md`.

### Subtask T017 – Method pages

- `spec-driven.md` (621 lines): `scripts/bash/validate-task-workflow.sh` does not exist (D10); find what replaced it (`git log --diff-filter=D`) and say so, or remove the reference with a log row.
- `testing-taxonomy.md`: `tests/architectural/test_pytest_marker_convention.py` does not exist (D11); same treatment. Verify markers against `pytest.ini`/`pyproject.toml`.
- `practices-principles.md`, `technology-foundations.md`, `naming-decision-tool-vs-agent.md`.

### Subtask T018 – Product and work model

- `product-lines.md` (keep consistent with WP02's `team-kitty.md`), `ops-vs-missions.md` (verify `spec-kitty dispatch`, `profile-invocation complete`), `mission-types.md` (verify against `spec-kitty mission list --json`; the four built-in types), `planning-and-tracking.md`.

### Subtask T019 – Section index

- `context/README.md`: D9 (the Team Kitty blurb), every listed page still exists, link text matches targets after #6939.

### Subtask T020 – Logs, audit, gates, self-review

- Regenerate the `context/` rows with the staleness audit's per-page record and confirm SC-001 and SC-003.
- Gates as WP01 T007.

## Risks & Mitigations

- Size: if one subtask grows past one session, stop and ask to split the WP rather than skimming.

## Review Guidance

- Every changed claim has evidence; every page names a reader; no text diagram left.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
