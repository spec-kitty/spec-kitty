---
work_package_id: WP01
title: Audience profiles
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-010
- FR-011
planning_base_branch: issue-7522-context-refresh
merge_target_branch: issue-7522-context-refresh
branch_strategy: Planning artifacts for this mission were generated on issue-7522-context-refresh. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7522-context-refresh unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Audience profiles
history:
- at: '2026-11-13T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/context/audience/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/context/audience/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Audience profiles

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
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- The ten audience profiles under `docs/context/audience/{external,internal}/` describe readers of Spec Kitty 4.x: goals, vocabulary and the questions each reader brings match the current CLI and concepts (FR-001).
- The three hubs (`docs/context/audience/README.md`, `external/README.md`, `internal/README.md`) list every profile, say how a page names its reader in `audience:` frontmatter, and drop the dead journey references (FR-002; gap-analysis D2 to D4).
- All 13 pages name their reader (FR-003; plan.md Decision 2: `internal/maintainer` and `internal/ai-collaboration-agent`).
- Every factual change has a row in `corrections-log.md`; anything unverifiable, and any profile add/remove or template idea, goes to `operator-flags.md` (FR-004, FR-005, C-002).
- `updated` is bumped to `'2026-11-13T00:00:00Z'` only on pages actually checked (FR-010).
- Writing guidance applied and cited in the self-review (FR-011).

## Context & Constraints

- Spec: `kitty-specs/context-docs-refresh-01M7AN3N/spec.md`; plan: `plan.md` (Decisions 1, 2, 3, 8); gap analysis: `gap-analysis.md` (D1 to D6).
- Charter: `.kittify/charter/charter.md`, "Writing, Communication & Diagramming Doctrine" and Terminology Canon.
- Persona template (canonical, keep its shape): `src/charter/offering/templates/architecture/stakeholder-persona-template.md`.
- Do not add or remove a profile (C-002). Do not touch `packs/`, ADRs, `plans/`, `archive/`, `docs-retrieval-index.yaml`, `page-inventory.yaml` (C-001).
- Commit nothing to this WP after it is approved (C-005).
- Commits are signed, use conventional-commit subjects, and end with the three trailer lines the operator gave.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-7522-context-refresh
- **Merge target branch**: issue-7522-context-refresh

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start the work with:

```bash
spec-kitty agent action implement WP01 --agent claude --mission context-docs-refresh-01M7AN3N
```

## Subtasks & Detailed Guidance

### Subtask T001 – Load the writer profile and doctrine; record the gate baseline

- **Purpose**: Write under `comms-cleo` with the #3891 guidance in hand, and know which gate results predate the WP.
- **Steps**:
  1. Load `comms-cleo` (`packs/built-in/agent_profiles/comms-cleo.agent.yaml`) with `/spk-charter-profile-load`. Its rules bind: name the persona, minimal edits with a reason each, no new or changed fact without author approval.
  2. Load with `spec-kitty charter context --include <kind>:<id>`: `directive:047-audience-oriented-writing`, `tactic:writing-audience-catalog`, `styleguide:report-writing` (internal pack: anti-AI-prose patterns), `styleguide:plain-language`, `styleguide:professional-communications`, `styleguide:common-docs`, `directive:042-common-docs`, `styleguide:divio-type-discipline`, `styleguide:docs-accessibility`, `styleguide:docs-freshness-sla`, `styleguide:publication-authority`, `tactic:documentation-curation-audit`, `tactic:usage-examples-sync`.
  3. Run `make docs-lint` and the strict link check (commands in T007) on the unchanged tree and note the counts.
- **Files**: none changed.

### Subtask T002 – External profiles and hub

- **Purpose**: Evaluators and owners judge Spec Kitty from these profiles; their vocabulary must be 4.x.
- **Files**: `external/project-owner.md`, `external/tech-lead-evaluator.md`, `external/architect-evaluator.md`, `external/product-manager-evaluator.md`, `external/README.md`.
- **Steps** (each change logged with evidence):
  1. `Domain / Context`: "Spec Kitty architecture 2.x" → "Spec Kitty 4.x" (D1; evidence `pyproject.toml` `version`, charter "4.x — Current active line"). `Created / Updated`: keep the created date, add the check date.
  2. Terminology Canon (D5): where "feature" names the unit of Spec Kitty work, write Mission ("first accepted Mission spec", "pilot Missions"). Leave "feature" where it means a capability of the reader's own product.
  3. Overloaded terms (D6): "branch routing" → name the sense (which branch a change lands on: branch-target routing, `orchestration.md#routing`).
  4. Ground the questions each reader brings in today's workflow: specify (discovery interview), plan, tasks, implement, review, accept, `consolidate`; `spec-kitty next`; work packages and lanes; the charter interview and activation; review gates. Check each named command with `spec-kitty <cmd> --help`.
  5. Journeys: "user journeys" are archived 2.x snapshots (`docs/plans/user_journey/README.md`); a desideratum that asks for "journey artifacts" names the 4.x artefacts that play that role (spec and plan), stated as a need, not as a feature claim.
  6. `external/README.md`: replace the "Linked Journeys" column (D2) with a column that helps authors choose the profile, and fix link text.
- **Parallel?**: Yes, with T003 and T004.

### Subtask T003 – Human internal profiles

- **Files**: `internal/system-architect.md`, `internal/lead-developer.md`, `internal/maintainer.md`.
- **Steps**: as T002 steps 1 to 4. Specific checks:
  - `lead-developer`: "Active feature streams", "across features" (D5); "doctrine curation flow, charter activation path" — check against `spec-kitty charter activate|deactivate|context|list --help`. Keep "doctrine" (the Charter Pack rename is #3732, out of scope).
  - `maintainer`: the charter's Collaboration Strategy says the operator merges and the modular CI plus in-session reviewers own review; check the profile's "Final governance approval" wording against it.
  - `system-architect`: ADRs are filed by era under `docs/adr/` (`docs/adr/4.x/` for new ones); C4 per `USE_C4_MODEL_TECHNIQUES`.

### Subtask T004 – Agent and system profiles, internal hub

- **Files**: `internal/ai-collaboration-agent.md`, `internal/spec-kitty-cli-runtime.md`, `internal/project-codebase.md`, `internal/README.md`.
- **Steps**: as T002 steps 1 to 4. Specific checks:
  - `ai-collaboration-agent`: Human-in-Charge links to `../../identity.md#human-in-charge-hic`; agents work through slash commands or command skills, load agent profiles (`spec-kitty profiles`), and open governed Ops with `spec-kitty dispatch`. Verify each.
  - `spec-kitty-cli-runtime`: "routes mission flows" (D6) → advances Missions step by step (`spec-kitty next`); the status model is the append-only `status.events.jsonl` with the nine-lane state machine (`src/specify_cli/status/`); "optional external integrations" checked against `spec-kitty tracker --help` (local trackers) and the #6164 removal of hosted surfaces.
  - `project-codebase`: Domain update only unless a claim is wrong.
  - `internal/README.md`: replace the "Linked Journeys" column (D2).

### Subtask T005 – Audience hub

- **File**: `docs/context/audience/README.md`.
- **Steps**:
  1. Say what the profiles are for today: every page names its reader in `audience:` frontmatter (`- profile: internal/maintainer` + `guidance_text`), checked by `scripts/docs/audience_resolver.py`; the `writing-audience-catalog` tactic and directive 047 say to pick from the catalog.
  2. List all ten profiles with a one-line "name it when the page is for…" guide.
  3. Fix D3 (journeys) and D4 (link text `internal/index.md` → the real targets).
  4. Keep the existing title and anchors unless a heading is wrong; no linked anchor may disappear (`git grep "audience/README.md#"`).

### Subtask T006 – Frontmatter and logs

- **Steps**:
  1. Add to all 13 pages:
     ```yaml
     audience:
     - profile: internal/maintainer
       guidance_text: <one line, what this reader uses the page for>
     - profile: internal/ai-collaboration-agent
       guidance_text: <one line>
     ```
  2. Set `updated: '2026-11-13T00:00:00Z'` on every page you checked.
  3. Append WP01 rows to `kitty-specs/context-docs-refresh-01M7AN3N/corrections-log.md` (Was / Now / Evidence) and `operator-flags.md` (unverifiable claims, proposals). Out-of-map edit: shared mission logs.

### Subtask T007 – Gates and self-review

- **Commands** (on committed state):
  ```bash
  make docs-lint
  uv run python -m scripts.docs.site_link_gates check-links -- pnpm --dir site exec dockitty-check-links ../docs --strict --astro-config astro.config.mjs
  uv run pytest tests/docs/test_dockitty_frontmatter_shape.py tests/docs/test_audience_resolves.py tests/docs/test_related_validator.py tests/docs/test_section_index_basename.py tests/docs/test_one_index_per_folder.py tests/docs/test_retired_surface_gate.py -q
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  uv run python -m scripts.docs.audience_resolver --strict
  ```
  Plus the site build if feasible (no Docker daemon: PlantUML rendering cannot run; say so).
- **Self-review**: cite each guidance artefact from T001 with one line on how it was applied; run the `report-writing` anti-AI-prose checklist over every changed paragraph.

## Risks & Mitigations

- Persona drift into a different document → minimal edits; template sections unchanged.
- An unverifiable persona claim (they are design statements, not code facts) → keep it, flag only if it names a product behaviour that cannot be found.

## Review Guidance

- Every row in `corrections-log.md` for WP01 has evidence a reviewer can rerun.
- No "feature" for a Mission; no bare "routing".
- Each profile's questions map to a current command or concept.
- No profile added or removed; template sections intact.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
