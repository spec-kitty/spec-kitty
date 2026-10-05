---
work_package_id: WP08
title: Documentation, Glossary, Changelog & End-to-End Validation
dependencies:
- WP06
- WP07
requirement_refs:
- C-001
- C-007
- FR-019
tracker_refs: []
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
subtasks:
- T042
- T043
- T044
- T045
- T046
phase: Phase 4 - Polish
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/context/feedback.md
create_intent:
- docs/context/feedback.md
- src/specify_cli/.contextive/feedback.yml
- docs/guides/how-to/collaboration/give-feedback.md
execution_mode: code_change
model: ''
owned_files:
- docs/context/feedback.md
- docs/context/index.md
- src/specify_cli/.contextive/feedback.yml
- docs/guides/how-to/collaboration/give-feedback.md
- docs/guides/how-to/collaboration/index.md
- docs/guides/toc.yml
- docs/api/environment-variables.md
- docs/api/configuration.md
- CHANGELOG.md
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP08 – Documentation, Glossary, Changelog & End-to-End Validation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `cursor`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for documentation and glossary curation.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress**: Update the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- The four canonical terms (**Feedback Survey**, **Feedback Submission**, **Survey Trigger**, **Feedback Endpoint**) are defined in the glossary with "avoid" synonyms (C-001). "Telemetry" is listed as a term to avoid.
- A task-oriented how-to explains, for an ordinary user: when the survey appears, how to skip it or turn it off, how to give feedback on demand, what is sent (and what is never sent), and how to see and override the destination (FR-019, C-007).
- Reference docs list `SPEC_KITTY_FEEDBACK_URL`, the `feedback.json` fields and location, and the packager knob `DistributionProfile.feedback_endpoint` (upstream ships none → dormant).
- `CHANGELOG.md` has one entry under the unreleased section.
- The `quickstart.md` walkthrough runs green end to end on a clean, isolated user profile, with evidence recorded.
- **Vendor-neutral**: no company or product names other than Spec Kitty; example hosts use `example.test` or loopback only.

## Context & Constraints

- Read `spec.md`, `plan.md`, `data-model.md`, `quickstart.md`, and all three `contracts/*.json` in `kitty-specs/in-harness-feedback-survey-01M3PK9W/`. Docs must mirror **shipped** behaviour; read the merged code from WP01–WP07 rather than the plan when they differ, and flag any discrepancy in the Activity Log.
- Charter writing doctrine: name the target persona first (DIRECTIVE_047), one Divio type per page declared in frontmatter, `updated: YYYY-MM-DD` on every page, plain language, descriptive alt text for any image.
- Glossary conventions: `docs/context/glossary-conventions.md`; mirror the table format in `docs/context/planning-and-tracking.md` (Definition / Context / Status / Applicable to / Related terms). New terms start as `candidate`.
- Frontmatter pattern for how-tos: see `docs/guides/how-to/harnesses/amazon-q.md` (`title`, `description`, `doc_status`, `updated`, `type: how-to`, `audience`, `related`).
- The env-var reference must keep the existing machine-global scope warning intact (`tests/docs/test_env_var_scope_warning.py`). `SPEC_KITTY_FEEDBACK_URL` is also machine-global when exported in a shell; say so in the same style.
- Tracer files: append dated entries to `kitty-specs/.../traces/*.md` as the tracer procedure requires. That is an expected small out-of-map edit; note it in the Activity Log.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP08 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T042 – Glossary entries

- **Steps**:
  1. Create `docs/context/feedback.md` (type `explanation` or the type other context files use; check their frontmatter) with a short introduction ("Feedback bounded context: how Spec Kitty asks users for optional, anonymous experience feedback") and one table per term:
     - **Feedback Survey**: the short optional prompt (rating 1–5, "What would you change?", optional email, "Send feedback?"). Avoid: questionnaire, poll, NPS.
     - **Feedback Submission**: the single anonymous payload sent only after "Send feedback". Avoid: telemetry, event, moment, sync.
     - **Survey Trigger**: planning complete, mission end, Op close, on demand. Avoid: hook.
     - **Feedback Endpoint**: the web-service address; env > user override > distribution default > none. Avoid: SaaS, Team Kitty, relay.
     - Link related terms: [Op](./planning-and-tracking.md#op), Mission (`./orchestration.md#mission`).
  2. Add the file to `docs/context/index.md`.
  3. If glossary contexts feed `scripts/generate_contextive_glossaries.py` (see the index text), run it and commit the generated `src/specify_cli/.contextive/feedback.yml` if produced. If the generator produces nothing for a new context, record that and drop the file from the diff.
- **Files**: `docs/context/feedback.md`, `docs/context/index.md`, possibly `src/specify_cli/.contextive/feedback.yml`

### Subtask T043 – How-to guide

- **Steps**: Create `docs/guides/how-to/collaboration/give-feedback.md` for persona `docs/context/audience/external/project-owner.md` (or the closest existing external-user persona). Sections:
  1. When you'll see the survey: the three triggers, at most once a week, never in CI or non-interactive terminals. State the known limitation plainly: Spec Kitty cannot tell whether an agent session has a person watching, so in agent harnesses it relies on the agent to offer the survey only when a human is in the loop (spec Assumptions; research R-11).
  2. Answering, skipping, or turning it off: "Skip", "Don't ask again", and `spec-kitty feedback --prompts off|on`.
  3. Giving feedback any time: `spec-kitty feedback`.
  4. What is sent: the exact field list from the submission contract. What is never sent: repository, mission, branch, user or host identity, credentials. Email only if you type it.
  5. Where it goes: `spec-kitty feedback --status`; overriding with `SPEC_KITTY_FEEDBACK_URL` or `endpoint_override` in `feedback.json`; HTTPS required except loopback; no endpoint means no automatic survey.
  6. If the service is down: nothing happens; your command is never affected.
  - Add the page to `docs/guides/how-to/collaboration/index.md` and `docs/guides/toc.yml`, following existing entries.
- **Files**: the how-to, the collaboration index, `docs/guides/toc.yml`

### Subtask T044 – Reference updates

- **Steps**:
  1. `docs/api/environment-variables.md`: add `SPEC_KITTY_FEEDBACK_URL` (purpose, precedence, validation, machine-global note). Do not disturb the existing sync-scope warning text.
  2. `docs/api/configuration.md`: add a `feedback.json` section: location (per-user config directory, per OS), fields (`schema_version`, `automatic_prompts`, `last_shown_at`, `endpoint_override`), permissions (0600), and "never stored in a project repository".
  3. Packager note: in the same configuration reference (or wherever `DistributionProfile` is documented; search `docs/` for `DistributionProfile` first and extend that page instead if one exists), document `feedback_endpoint`: optional, validated at resolution, stock/upstream value `None` → automatic surveys dormant.
  - If extending a page other than the two listed here, add it to this WP's scope with a one-line rationale in the Activity Log.
- **Files**: `docs/api/environment-variables.md`, `docs/api/configuration.md`

### Subtask T045 – CHANGELOG

- **Steps**: Add one entry under the unreleased section, following the file's existing format: "Added: optional, anonymous Feedback Survey offered after planning, mission consolidation, and Op close (at most weekly, consent on every submission, dormant unless a feedback endpoint is configured); `spec-kitty feedback` command." No version number (charter: no versions in scope). Check whether `scripts/docs/sync_changelog.py` mirrors the changelog into `docs/`; if so, run it and include the output in scope with a rationale.
- **Files**: `CHANGELOG.md`

### Subtask T046 – End-to-end validation + evidence

- **Steps**:
  1. Use an isolated profile: `export XDG_CONFIG_HOME=$(mktemp -d)` (Linux) or the macOS/Windows equivalent the preferences module honours. Reinstall the editable package if you use the `spec-kitty` binary (stale-install gotcha).
  2. Walk `quickstart.md` steps 1–7 exactly; paste the key outputs (status text, received JSON body, agent-check/submit JSON) into the Activity Log.
  3. Run the gates: `tests/architectural/test_no_legacy_terminology.py`, `tests/docs/test_env_var_scope_warning.py`, and the docs freshness/frontmatter checks the repository uses for new pages (for example `scripts/docs/check_docs_freshness.py`; read its usage first).
  4. **Real-harness check (SC-006; analysis finding C1)**: in a scratch project initialised with the merged CLI (`spec-kitty init` + `spec-kitty upgrade` so the generated commands carry the Feedback Survey Check), with a loopback endpoint configured, trigger `tasks-finalize` (or `consolidate`) from at least three harnesses — Claude Code, Cursor, and Codex — plus once from a plain terminal. For each, record: the harness name, whether the survey was presented with the harness's own question UI, whether all four steps plus skip / "don't ask again" were offered, and the received submission's `harness` value. Attach transcript excerpts or screenshots in the Activity Log. If a harness cannot be exercised on the machine, record why and mark SC-006 as partially verified in the PR body.
  5. Grep the whole diff for company names and non-`example.test` hosts; record the command and the zero-hit result.
  6. Append tracer entries (assess step preparation) to `traces/approach.md` and `traces/design-decisions.md`.
- **Files**: none owned (validation); tracer files are an expected out-of-map edit.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_env_var_scope_warning.py -q
uv run --frozen pytest tests/docs -q -m "fast or unit"
make test-fast
```

Record commands, counts, and the quickstart evidence in the Activity Log.

## Risks & Mitigations

- **Docs describe planned rather than shipped behaviour** → verify every command and flag against `spec-kitty feedback --help` from the merged code.
- **Env-var doc gate** → keep existing warning text byte-intact; add the new variable in a separate subsection.

## Review Guidance

- Each new page declares one Divio type and has `updated:`.
- "Telemetry" appears only as a term to avoid.
- No company identity; example hosts are `example.test` or loopback.
- The quickstart evidence is present and matches the contracts.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
- 2026-10-01T09:55:00Z – curator-carla – T042-T045 done. New: `docs/context/feedback.md` (4 terms, `candidate`, avoid-lists; "telemetry" only as an avoid term), `docs/guides/how-to/collaboration/give-feedback.md` (how-to, `updated: 2026-10-01`). Edited: `docs/context/index.md`, collaboration index, `docs/guides/toc.yml`, `docs/api/environment-variables.md` (new `SPEC_KITTY_FEEDBACK_URL` section; existing scope warning byte-intact), `docs/api/configuration.md` (`feedback.json` section + `DistributionProfile.feedback_endpoint`, stock value `None` -> dormant). No `.contextive/feedback.yml`: the generator has no entry for a new context (nothing produced, so dropped).
- 2026-10-01T09:56:00Z – curator-carla – Out-of-map edits, each required by a gate: (a) `docs/changelog/CHANGELOG.md` — the root `CHANGELOG.md` is a symlink to it, so the Unreleased entry (no version) lives there; (b) docs page-inventory and docs-retrieval-index files — +2 pages each, needed for `check_docs_freshness.py` (0 errors afterwards; 3 pre-existing warnings about `moments drain` help-text drift, untouched); (c) `tests/docs/test_check_cli_reference_freshness.py` — visible-CLI-command baseline re-pinned 281 -> 282, band 253..309 -> 254..310, because the new spec-required top-level `feedback` command is the 310th visible path (the repo sat at the 309 ceiling). Minimal +1, rationale in the test docstring, mirroring the 2026-09-05 re-pin precedent.
- 2026-10-01T09:58:00Z – curator-carla – T046(a) quickstart steps 1-7 PASSED on an isolated profile (macOS: config dir follows `HOME`, so a temp `HOME` was used rather than `XDG_CONFIG_HOME`) against a loopback listener (`http://127.0.0.1:8765/feedback`). Evidence: `feedback --status` -> `Destination: http://127.0.0.1:8765/feedback (from SPEC_KITTY_FEEDBACK_URL)`, `Last shown: never`, `Automatic prompts: on`. On-demand submission body received: `trigger: on_demand`, `harness: cli`, no `email` key (email only when typed). Agent protocol: `--agent-check` -> `prompt/eligible`; `--agent-submit` -> `handed_off` (body `trigger: mission_end`, `harness: cursor`); second `--agent-check` -> `none/throttled`. Silent failure: with the listener stopped, the thank-you still printed and exit status was 0. Dormant: `--agent-check` -> `none/no_endpoint`; bare `feedback` printed "No feedback endpoint is configured."
- 2026-10-01T10:00:00Z – curator-carla – T046(b) gates: `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_env_var_scope_warning.py tests/docs -q -m "fast or unit"` -> 1465 passed, 3 failed. After the re-pin: `tests/docs/test_check_cli_reference_freshness.py` 33 passed (the 2 visible-count failures cleared). Remaining 1 failure, `tests/docs/test_docs_query_cli.py::test_human_table_renders_with_no_rich_markup_leak`, is PRE-EXISTING: it fails identically on the primary checkout (not this diff). `scripts/docs/check_docs_freshness.py --link-check none` -> 0 errors.
- 2026-10-01T10:01:00Z – curator-carla – T046(e) neutrality: added lines of the WP08 commits grepped for company/product names and non-`example.test`/loopback hosts -> 0 hits (308 added lines). Whole-mission check: `git diff 9e7c7c2e6..HEAD -U0 -- src tests docs packs CHANGELOG.md docs/changelog | grep -E '^\+' | grep -inE 'acme|regnology|sekrit|disco|juno|reg-?kitty'` -> 0 hits (orchestrator re-run). Pre-existing, non-mission fixtures such as an `acme` entry-point fixture exist in the base tree and were not added by this mission.
- 2026-10-01T10:02:00Z – curator-carla – T046(f) tracers appended to `traces/approach.md` and `traces/design-decisions.md` (spec-commit 02686a0).
- 2026-10-01T10:03:00Z – claude (orchestrator) – T046(d) real-harness check (SC-006) — PARTIALLY VERIFIED. Interactive Claude Code / Cursor / Codex sessions could not be driven from this environment, so the survey was NOT observed in each harness's own question UI. What was verified: a fresh `spec-kitty init` (lane-h CLI) project's generated surfaces carry the Feedback Survey block for Claude (`.claude/skills/spec-kitty/SKILL.md`), Codex (`.agents/skills/spec-kitty`, `spec-kitty.tasks`, `spec-kitty.tasks-finalize`, `spec-kitty.consolidate`), and Cursor (`.agents/skills/spec-kitty/SKILL.md` plus the `.kittify/missions/mission-steps/software-dev/{tasks,tasks-finalize}/prompt.md` pack prompts); the plain-terminal path is covered by quickstart steps 1-7 above. To be stated as "SC-006 partially verified" in the PR body.
- 2026-10-01T10:04:00Z – curator-carla – Shipped-vs-plan notes: `--status` lists fields alphabetically; `mission_type` is `null` outside a mission; the `--agent-*` flags are hidden from `--help`, so the how-to documents only `--status`, `--prompts` and bare `feedback`.
- 2026-10-01T10:05:00Z – reviewer-renata – Cycle 1 rejected solely for missing T046 evidence (review-feedback-1.md B1). Evidence appended above; no code change required.
