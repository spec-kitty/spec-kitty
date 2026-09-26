---
work_package_id: WP08
title: ADR, living docs, CHANGELOG
dependencies:
- WP07
requirement_refs:
- FR-001
- FR-002
- FR-011
- FR-014
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T056
- T057
- T058
- T059
- T060
phase: Phase 5 - Living documentation (wave 5)
task_type: implement
execution_mode: code_change
owned_files:
- docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md
- docs/architecture/execution-lanes.md
- docs/architecture/git-worktrees.md
- docs/migrations/mission-id-canonical-identity.md
- docs/migrations/legacy-to-coordination.md
- CHANGELOG.md
- CLAUDE.md
- AGENTS.md
authoritative_surface: docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md
create_intent:
- docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md
agent_profile: architect-alphonso
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP08 – ADR, living docs, CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Living Documentation Sync (DIRECTIVE_037) and Decision Documentation (DIRECTIVE_003). The observable naming behaviour changed, so every artifact that describes it changes in this mission (PD-15):

1. **ADR** `docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md` records:
   - the decision: lane branch and worktree names are keyed on the creation input (slug + lane id), the creation-side placement authority is extended, and nothing new is introduced (C-001);
   - the reversal of the #1899 premise ("keyed on (slug, mission_id)");
   - the rejected alternatives: persisting per-lane names in `lanes.json` (C-002), moving naming into a lower layer, keeping a private identity-aware composer, and read-time probing (C-004 / ADR `2026-07-01-1`);
   - the PD-3 golden re-pin reading of NFR-001;
   - FR-011 Mission-branch preservation;
   - the FR-005 upgrade behaviour (a resume from an older release refuses; the remedy is `merge --abort` plus a fresh merge);
   - the tension with the pre-3.2.x legacy retirement (C-007, see #2463), recorded and not decided.

   Its file name uses the `-2` suffix because `2026-09-26-1-ci-coverage-honesty.md` already exists (tasks.md deviation 4). WP07's gate docstring already cites this path.
2. **Architecture docs**:
   - `docs/architecture/execution-lanes.md` §Naming: today it says lanes are `kitty/mission-<human-slug>-<mid8>-lane-a`. Rewrite it to "mid8 appears in a lane name only when the Mission slug embeds it; lane names never derive from the identity".
   - `docs/architecture/git-worktrees.md`: the "Naming note (mission 083+)" and the examples.
3. **Migration docs**:
   - `docs/migrations/mission-id-canonical-identity.md`: backfill does **not** rename lanes or the recorded Mission branch, and re-finalize preserves it.
   - `docs/migrations/legacy-to-coordination.md` (≈L107): the worktree layout sentence.
4. **`CLAUDE.md` / `AGENTS.md`**: the Mission Identity Model "**Naming:**" line (≈L500 in both) is corrected. Keep the two files in sync; they are mirrors.
5. **CHANGELOG** `[Unreleased]` entries under the canonical headings:
   - **Changed / breaking**: the `mission_id` keyword was removed from `lane_branch_name` / `worktree_dir_name` / `worktree_path`.
   - **Fixed**:
     - #5108: divergent Missions now merge, cleanup leaves no orphans, and the resume guard is armed;
     - re-finalize keeps the recorded Mission branch;
     - #5113: decisions on a fresh coordination Mission, plus the truthful `doctor coordination --fix` remedy.
   - **Upgrade note**: a merge interrupted under an older release refuses `--resume`; use `merge --abort` and merge again.

## Context & Constraints

- **Spec**: the Intent Summary (architecture decision Option A), Domain Language, FR-001, FR-002, FR-005, FR-011, FR-013 and FR-014, and C-001, C-002, C-004 and C-007.
- **Plan**: PD-15 (the doc list), PD-3, PD-4, PD-6, PD-9, PD-10, PD-13 and PD-14.
- **Research**: the ADJ-1..7 table (adjudications worth citing in the ADR), and Part A §1.3 (alternatives).
- **Charter**: Common Docs standard (DIRECTIVE_042: in-file frontmatter with `title`, `description`, `doc_status`/`status`, `updated`/`date`, following the neighbouring ADRs), audience-oriented writing (DIRECTIVE_047), and the terminology canon (**Mission**, never "feature"). Run `tests/architectural/test_no_legacy_terminology.py`.
- **Execution mode**: `code_change`, because `CHANGELOG.md`, `CLAUDE.md` and `AGENTS.md` are outside `kitty-specs/` and `docs/`. The finalizer may warn that this WP owns no `src/`/`tests/` path; that warning is expected.
- **Source of truth**: describe what WP01–WP07, WP09 and WP10 actually shipped. Read the merged code and the WP Activity Logs. Do not transcribe the plan.

**Implementation command**: `spec-kitty agent action implement WP08 --agent <name>`. It depends on WP07.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T056 – ADR `2026-09-26-2-lane-naming-keyed-on-creation-input.md`

- **Template**: follow the canonical ADR template resolved through doctrine (DIRECTIVE_044). Check `docs/adr/3.x/README.md` for the house structure. The recent ADRs in `docs/adr/3.x/` (for example `2026-09-26-1-ci-coverage-honesty.md`) use frontmatter with `title`, `description`, `status`, `date` and MADR-style sections. Use the template, not a copy of an older ADR.
- **Audience**: maintainers who will touch lane naming, merge, or the gate. They know git and spec-kitty lanes; they do not know this mission.
- **Content outline**:
  1. *Context and Problem Statement*: #5108. Creation names lanes from the slug alone, while six read sites re-derived names with the identity. List the four divergent shapes, and the refusal "no approved lane resolved any commits".
  2. *Decision Drivers*: single canonical authority, no probing (ADR `2026-07-01-1`), no schema change, layer direction, and closing the class by construction.
  3. *Considered Options*:
     - A: extend the creation-side authority (chosen);
     - B: persist per-lane branch names in `lanes.json`;
     - C: move naming into a lower layer;
     - D: keep a private identity-aware composer (violates FR-002 and C-004);
     - E: probe candidates at read time.
  4. *Decision Outcome*:
     - the signatures (no `mission_id` on the lane surface);
     - `predict_lane_worktree` as the placement decision;
     - the parsers and the single `_LANE_ID_RE`;
     - the extended gate (four legs, shrink-only allow-list).
  5. *Consequences*:
     - the golden re-pin (PD-3), with the list of re-pinned rows taken from WP07's Activity Log;
     - Mission-branch preservation on re-finalize;
     - the H5 resume refusal on coordination topology, and the upgrade behaviour;
     - the reversal of the #1899 premise.
  6. *Residuals / follow-ups*: the recovery enumeration prefix over-match, the review-workspace second creation path, the `mission_state` rebuild, the lane-id grammar past 26 lanes, and the #2463 tension (C-007).
  7. *Links*: spec, plan, and the #5108 / #5113 issues.
- **Validation**: `tests/docs/test_adr_content_invariance.py`, `tests/docs/test_adr_readme_prose.py` and `tests/docs/test_description_length_gate.py` are green. If an ADR index (`docs/adr/3.x/index.md` / `README.md`) must list new ADRs, check how `2026-09-26-1` is registered. If registration is required and the index is not in `owned_files`, add it as a logged out-of-map edit.

### Subtask T057 – Architecture docs

- `docs/architecture/execution-lanes.md` §Naming (≈L47–60). State:
  - Mission branch: `kitty/mission-<human-slug>-<mid8>`. This is unchanged: Mission and coordination names still use the identity.
  - Lane branch: `kitty/mission-<slug-body>-<lane-id>`, where `<slug-body>` is the recorded Mission slug with a stale `NNN-` dropped only when the slug embeds a mid8.
  - Lane worktree: `.worktrees/<slug>-<lane-id>/`, verbatim.
  - A worked example for a modern Mission (the slug embeds mid8, so the name looks identical to before) and one for a legacy `057-foo` Mission.
  - A sentence: "the Mission identity is never an input to lane naming".
- `docs/architecture/git-worktrees.md`: fix the "Naming note (mission 083+)" and the example commands, for example `git checkout -b kitty/mission-my-feature-01J6XW9K-lane-a`. Keep it valid when the slug embeds the mid8, and say so.
- Keep the frontmatter `updated:` current.

### Subtask T058 – Migration docs

- `docs/migrations/mission-id-canonical-identity.md`: add a short section, "What backfill does not change". Lane branches and worktrees keep their created names, and `lanes.json` `mission_branch` is preserved across re-finalize (FR-011). Link the ADR.
- `docs/migrations/legacy-to-coordination.md` (≈L100–110): the legacy lane worktree layout is `.worktrees/<slug>-lane-<id>/` (or `<slug>-<mid8>-lane-<id>` when the slug embeds a mid8).
- Keep the frontmatter `updated:` current.

### Subtask T059 – `CLAUDE.md` / `AGENTS.md` naming line

- Replace **Naming:** `Branch: kitty/mission-<slug>-<mid8>-lane-<id> | Worktree: .worktrees/<slug>-<mid8>-lane-<id>` with something like: `**Naming:** Lane branch/worktree are keyed on the recorded Mission slug + lane id only (the mid8 appears when the slug embeds it): Branch kitty/mission-<slug>-lane-<id> | Worktree .worktrees/<slug>-lane-<id>. Mission/coordination branches keep kitty/mission-<human-slug>-<mid8>.`
- Make the **same** edit in both files, and diff them afterwards to confirm the mirrored section is identical.
- CLAUDE.md says that when it and the charter disagree, the charter wins. Check `.kittify/charter/charter.md` for a naming statement. If it disagrees, **flag the drift in the Activity Log**; do not edit the charter.

### Subtask T060 – CHANGELOG + doc validation

- `CHANGELOG.md` `[Unreleased]`: add entries under `### Changed` and `### Fixed`, matching the file's bold-lead, **Before:/After:** style. Cite #5108 and #5113, and the ADR path. Include the upgrade note for interrupted merges and the API keyword removal.
- Frontmatter `updated:` stays current.
- Run the doc checks and the terminology guard (Test Strategy). Record the commands and counts.

## Test Strategy

This WP has no code, so red-first does not apply. Validation is by the docs gates:

```bash
.venv/bin/python -m pytest tests/docs/ -q
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py tests/architectural/test_no_dead_src_path_literals.py -q
diff <(sed -n '/Mission Identity Model/,/^---$/p' CLAUDE.md) <(sed -n '/Mission Identity Model/,/^---$/p' AGENTS.md)
make test-fast
```

- Every code identifier cited in the docs must exist in the merged code: `grep -rn "<identifier>" src/`.

## Definition of Done

- [ ] The ADR exists, with frontmatter, options, decision, consequences and residuals, and the WP07 gate docstring link resolves to it.
- [ ] The architecture and migration docs describe the shipped naming. No doc claims that lanes derive from the identity.
- [ ] `CLAUDE.md` and `AGENTS.md` are updated identically.
- [ ] The CHANGELOG has Changed, Fixed and the upgrade note.
- [ ] The docs tests and terminology guard are green.

## Risks & Mitigations

- **Docs drifting from the shipped code**: cite functions by name and verify each one with grep.
- **Over-long descriptions** failing `test_description_length_gate.py`: keep frontmatter descriptions short.
- **The CLAUDE.md/AGENTS.md mirror drifting**: diff after editing.

## Review Guidance

- Read the ADR as a newcomer would: is the reversal of the #1899 premise explicit?
- Spot-check three doc claims against the code.
- Mission, never "feature".

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
