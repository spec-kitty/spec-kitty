---
work_package_id: WP07
title: 'Consumer guidance: templates, prompts and checklist describe the grammar'
dependencies:
- WP02
- WP03
- WP05
requirement_refs:
- FR-017
- C-006
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: 606b2ac4a0067cca0deb064ae23f16c3365fa379
created_at: '2026-09-29T11:15:08.244452+00:00'
subtasks:
- T031
- T032
- T033
- T034
phase: Phase 3 - Guidance and evidence
history:
- at: '2026-09-29T06:24:46Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/missions/
create_intent:
- tests/specify_cli/review/test_antipattern_checklist.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- packs/built-in/missions/software-dev/templates/spec-template.md
- packs/built-in/missions/mission-steps/software-dev/specify/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-outline/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-packages/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md
- packs/built-in/missions/mission-steps/software-dev/review/prompt.md
- packs/built-in/missions/software-dev/actions/specify/guidelines.md
- packs/built-in/missions/software-dev/actions/tasks/guidelines.md
- packs/built-in/missions/software-dev/actions/review/guidelines.md
- src/specify_cli/review/antipattern_checklist.py
- tests/specify_cli/review/test_antipattern_checklist.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Consumer guidance: templates, prompts and checklist describe the grammar

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show curator-carla` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## ⛔ HARD RULE: no heavy suites

Never run any of these:
- the whole `tests/architectural/` directory;
- e2e or full-integration suites;
- performance, stress or timing suites;
- `make test-full`;
- whole-repo `pytest`.

Run ONLY the files listed under `## Validation surface`:
- this WP's named test files;
- the owning module's fast tier;
- the named architectural gate files, each by file name.

Always invoke tests as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

FR-017: the shipped consumer guidance must describe what the tools now accept. WP01–WP05 changed the behaviour; this WP changes the words. After this WP, the SOURCE spec template, the specify/tasks/tasks-outline/tasks-packages/tasks-finalize/review prompts, the specify/tasks/review action guidelines and the WP review anti-pattern checklist all state:

1. **The grammar**: the four kinds `FR`, `NFR`, `C`, `SC`; a hyphen; digits (width is significant); an optional single **lowercase** letter suffix (`FR-###a`).
2. **The qualified citation** `<mission-slug>#<ID>` for another mission's ID. It is never counted as this mission's own.
3. **The rejection reasons** `malformed`, `unknown_spec_id` (both fail) and `foreign_qualified` (never fails).
4. **Success criteria are tracked, not gating.**
5. **Refs are never erased or rewritten** by `finalize-tasks`; `map-requirements` is append-only.
6. **A malformed declared ID blocks `setup-plan`** (`SPEC_REQUIREMENT_IDS_INVALID`).

**Done means:**
- only SOURCE files changed (C-006); no generated agent copy under `.claude/`, `.agents/`, `.gemini/`, etc. was touched;
- every file in the Validation surface is green, including the two-sided provenance ratchet (no count moved);
- the spec template's declared-ID set is unchanged;
- ruff (lint and format) and `mypy --strict` are clean on the touched src file and the new test;
- the wording quotes the SHIPPED keys, reasons and codes (verified by grep, Step 0);
- the tracer notes, including the friction note, are in the hand-off's `## Tracer notes` section.

## Context & Constraints

Read these first:
- the charter: `.kittify/charter/charter.md`;
- in `kitty-specs/requirement-id-grammar-01M3NRCA/`:
  - `spec.md`: FR-017, FR-007, FR-009, FR-010, FR-013, FR-019, C-006, and the Edge Cases;
  - `plan.md`: "Behavioural changes by surface" and IC-06;
  - `data-model.md`: RefVerdict and the per-WP rule;
  - `contracts/grammar.md` and `contracts/json-payload-deltas.md` (every key name you will quote);
  - `research.md`: R5 (qualified-citation syntax) and R10 (template and pack constraints).

**Pack facts** (verified on `main` `aedb30cddd`; re-verify line numbers on your lane base):

| Fact | Consequence |
|---|---|
| `tests/architectural/test_builtin_pack_provenance_ratchet.py:49` counts `#\d{3,5}`, `WP\d\d` and `FR-\d+` per file, and `:48` counts `src/specify_cli`, `src/doctrine`, `tests/architectural`, `kitty-specs/`. It is **two-sided**: growth fails (`:93`) AND a drop fails (`:101`). | Every count must stay EXACTLY equal. `FR-\d+` also matches inside `NFR-001`, so `NFR-` digits count too. New examples use `FR-###`, `NFR-###`, `SC-###`, `C-###`, `FR-###a`, `WP##` placeholders only. Never write an issue number (`#NNNN`), a real `WPnn`, or `kitty-specs/` in new pack text. Do not delete an existing digit token either. |
| Current counts (live = baseline): spec-template provenance 6; specify prompt repo 5 / prov 3; tasks prompt repo 9 / prov 57; tasks-outline repo 4 / prov 18; tasks-packages repo 5 / prov 12; tasks-finalize repo 2; review prompt repo 1; tasks guidelines repo 2; specify and review guidelines 0. | Record the before and after census (T034). |
| `test_substantive_gate_formats.py:780-790` pins the template's declared-ID set. WP01 re-pinned it to `FR-001..003`, `NFR-001..003`, `C-001..003`, `SC-001..SC-004`. | Keep the SC bullets (`spec-template.md:145-148`) byte-identical. Never start a new line (after indentation or a list marker) with an ID-shaped token, and never put one in a first table cell, heading or bold lead. |
| The same file asserts `text.count("summary of tactic") == 1`, `"| FR-EXAMPLE |" in text`, the table headers, the `NFR-001`/`C-001` rows, and each SC bullet's delivery suffix. | Leave `spec-template.md:98` and `:101` untouched. |
| `FR-EXAMPLE` (`spec-template.md:101`) is malformed under the grammar. WP05's lint skips HTML comments, which is the only reason the template passes `setup-plan`. | Keep the row inside the comment. Prove the template lints clean (T031 step 5). |
| `test_command_template_cleanliness.py:128-151` rejects the dev slugs `057-`/`058-`; `:348-376` pins `do **not** run the mutating finalization command`, `do **not** run finalization`, and `--mission` on every `map-requirements --batch` line. | Use `<mission-slug>#<ID>`, never a real slug. Do not touch the pinned sentences. |
| `specify/prompt.md` is snapshotted byte-for-byte: `tests/specify_cli/skills/__snapshots__/codex/specify.SKILL.md`, `tests/specify_cli/regression/_twelve_agent_baseline/claude/specify.md` and `.../gemini/specify.toml`. | Regenerate those three in the same commit (sanctioned out-of-map; see below). |
| The live guidelines are `software-dev/actions/<step>/guidelines.md` (`src/charter/offering/missions/repository.py:510`). `mission-steps/software-dev/<step>/guidelines.md` are unpinned copies: `specify` is byte-identical today; `tasks` and `review` already drift. | Mirror only the `specify` edit (sanctioned out-of-map). Leave the drifted `tasks`/`review` copies alone and record the drift as friction. |
| `antipattern_checklist.py` items 1–8 appear verbatim in `review/prompt.md` §4a (`:201-240`). `tests/agent/test_workflow_review_lane_gate.py:809` and `tests/next/test_prompt_builder_unit.py:356` assert the label `FR coverage`. | Keep the `**FR coverage**` label. Edit item 4 identically in both files, in ONE commit (T033). |

**Terminology:** Mission, never "feature", in every new sentence.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes must merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`
- **Workspace**: run `.venv/bin/spec-kitty agent action implement WP07 --agent claude`. It allocates the lane worktree from `lanes.json` on a base that contains WP02, WP03 and WP05. Never pick a base by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Sanctioned out-of-map edits

Each is allowed only as described:

1. `tests/specify_cli/skills/__snapshots__/codex/specify.SKILL.md`, `tests/specify_cli/regression/_twelve_agent_baseline/claude/specify.md`, `tests/specify_cli/regression/_twelve_agent_baseline/gemini/specify.toml`: regenerated, never hand-edited. Rationale: byte snapshots of `specify/prompt.md`; an intended prose edit forces regeneration.
2. `packs/built-in/missions/mission-steps/software-dev/specify/guidelines.md`: the same one-line edit as its `actions/` source. Rationale: it is byte-identical today; keep it so.
3. *(Now owned, not out-of-map: `tests/specify_cli/review/test_antipattern_checklist.py` is in this WP's `owned_files` and `create_intent`. It holds the checklist tests and the guidance-content test; see the RED commit below.)*
4. `tests/specify_cli/missions/test_substantive_gate_formats.py`: ONLY if the declared-ID set changes unavoidably. It should not; if it does, stop and report instead of re-pinning.
5. `tests/architectural/_builtin_pack_provenance_baseline.yaml`: ONLY to lower a count, and only if an edit had to remove an existing digit token. Prefer rewording so nothing moves.

## Subtasks & Detailed Guidance

**Commit sequence (ATDD: the FIRST commit is RED, charter C-011):**
1. **RED commit, test only**: `tests/specify_cli/review/test_antipattern_checklist.py` with the T033 checklist tests AND the guidance-content test (see "RED commit" below). Run it on the lane base and show it RED; paste the failing test ids and one-line reasons into the commit body and the Activity Log. Do not squash this commit away.
2. **T031**: spec template alone (the template case of the guidance test goes GREEN).
3. **T032**: prompts and guidelines, plus the specify guidelines mirror and the three regenerated snapshots, in one commit (the tasks-outline and tasks-finalize cases go GREEN).
4. **T033**: the checklist and `review/prompt.md` item 4 edited identically (the checklist tests go GREEN). Never leave a red commit at the tip.
5. **T034**: the Activity Log; tracer notes go in the hand-off.

The RED commit is ATDD for new guidance, not a defect repro, so it uses no `@pytest.mark.regression` marker. Nothing may be left marked `regression`.

### RED commit – guidance-content and checklist tests (before T031)

- **File**: `tests/specify_cli/review/test_antipattern_checklist.py`, with `pytestmark = [pytest.mark.unit, pytest.mark.fast]`. Locate pack files from the repo root (`Path(__file__).resolve().parents[3]`).
- **Checklist tests**: tests 1–3 of T033, written now.
- **Guidance-content test** (`test_guidance_names_requirement_id_grammar`, parametrised over three SOURCE files): `packs/built-in/missions/software-dev/templates/spec-template.md`, `packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md` and `packs/built-in/missions/mission-steps/software-dev/tasks-outline/prompt.md`. For each file, assert the text names:
  - the four kinds: `FR`, `NFR`, `C` and `SC` (assert `SC-###` or `SC` next to the other three, as the target wording in T031/T032 writes them);
  - the lowercase suffix: the word `lowercase` together with `FR-###a` or "letter suffix";
  - the qualified citation: `<mission-slug>#`;
  - `tracked, not gating`;
  - the shipped JSON key names, bound in Step 0 (use the shipped names, not this prompt's, if they differ): `parsed_spec_ids`, `rejected_requirement_refs` and `success_criteria_coverage` in tasks-finalize; `foreign_qualified` in tasks-outline. The template carries no JSON key.
- **Positive control on the same read**: each file also contains a string it already holds today (for example `requirement_refs` in both prompts, `| FR-EXAMPLE |` in the template), so a failure means the grammar wording is missing, not that the file was not read.
- **Expected RED on the lane base**: every guidance case fails (no `<mission-slug>#` and no `tracked, not gating` in any of the three files today), and checklist test 1 fails. Checklist test 3 is a green parity ratchet (item 4 is identical in both files today), and checklist test 2 and the positive controls pass.

### Step 0 – Verify the shipped surface (before T031)

WP02, WP03 and WP05 are merged into your base. The guidance must quote what shipped, not what the contracts predicted. Run:

```bash
grep -n '"parsed_spec_ids"\|"rejected_requirement_refs"\|"success_criteria_coverage"\|"missing_requirement_refs_wps"\|"unknown_requirement_refs"\|"unmapped_functional_requirements"' src/specify_cli/cli/commands/agent/mission_finalize.py
grep -n 'parsed_spec_ids\|stale_ref_reasons\|foreign_qualified\|unmapped_functional\|_GRAMMAR_HINT\|--replace' src/specify_cli/cli/commands/agent/tasks_map_requirements.py src/specify_cli/cli/commands/agent/tasks_mapping_core.py
grep -n 'SPEC_REQUIREMENT_IDS_INVALID\|invalid_requirement_ids\|requirement_id_warnings' src/specify_cli/cli/commands/agent/mission_setup_plan.py
grep -n 'FAILING_REASONS\|"malformed"\|"unknown_spec_id"\|"foreign_qualified"' src/specify_cli/requirement_mapping/grammar.py
```

- Note the map-requirements hint constant text (WP03). Reuse its phrasing where a prompt describes the grammar, so the tool and the guidance say the same thing.
- If a name differs from this prompt, use the shipped name and record the difference in your hand-off's `## Tracer notes`.
- Output: a 2–3 sentence entry in the hand-off's `## Tracer notes` listing the keys, codes and reasons you bound to.

### Subtask T031 – `spec-template.md` (SOURCE only, C-006)

- **File**: `packs/built-in/missions/software-dev/templates/spec-template.md` (148 lines).
- **Step 1, the ID rule (`:84`).** Current text, inside the `<!-- ACTION REQUIRED … -->` comment:

  ```text
    2) Use unique IDs per type (FR-###, NFR-###, C-###)
  ```

  Replace it with this (same indentation, still inside the comment; no line starts with an ID token):

  ```text
    2) Use unique IDs per type (FR-###, NFR-###, C-###, and SC-### for success
       criteria). An ID is the kind, a hyphen, digits, and optionally one
       lowercase letter for a sub-requirement (FR-###a). Digit width is part of
       the ID. To cite an ID that another mission owns, write
       <mission-slug>#<ID>; it is never counted as this mission's own.
       setup-plan refuses a malformed ID in a declared position (first table
       cell, heading, list-item lead or bold lead).
  ```

- **Step 2, the `FR-EXAMPLE` note (`:99`).** Leave `:98` untouched (it holds the single `summary of tactic` the pin counts). Replace only `:99`:

  ```text
    does not match the `FR-###` id pattern, so it declares no requirement id):
  ```

  with:

  ```text
    does not match the requirement-ID grammar, so it declares no requirement
    id; it stays inside this comment because setup-plan refuses a malformed
    declared ID):
  ```

  Keep the `| FR-EXAMPLE |` row (`:101`) and the closing `-->` (`:102`) exactly as they are.

- **Step 3, the Success Criteria comment (`:135-138`).** Current:

  ```text
  <!--
    ACTION REQUIRED: Define measurable success criteria.
    These must be technology-agnostic and measurable.
  -->
  ```

  Replace with:

  ```text
  <!--
    ACTION REQUIRED: Define measurable success criteria.
    These must be technology-agnostic and measurable.
    Give each one an SC-### ID in the bold-lead bullet shape below. Success
    criteria are tracked, not gating: finalize-tasks reports which work
    packages reference each one, but an unreferenced success criterion never
    fails it. A work package may list SC-### IDs in its requirement_refs.
  -->
  ```

- **Step 4.** Do NOT touch `:142-148`. The four SC bullets keep their IDs and suffixes; the declared-ID pin depends on them.
- **Step 5, prove it.** Run:
  - `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/missions/test_substantive_gate_formats.py`. The declared-ID set must still equal WP01's pinned set.
  - A one-off lint check through WP05's shipped function (use its real name from `src/specify_cli/requirement_mapping/lint.py`):
    ```bash
    .venv/bin/python -c "from pathlib import Path; from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids as l; r=l(Path('packs/built-in/missions/software-dev/templates/spec-template.md').read_text()); print(r)"
    ```
    Expect zero errors. Also expect zero warnings: the new prose uses only placeholders. Paste the output into the commit body.
  - The provenance census (T034 snippet): spec-template provenance must still be 6.

### Subtask T032 – Prompts and guidelines

Minimal diffs only. Quote nothing you have not verified in Step 0. All paths below are under `packs/built-in/missions/`.

**A. `mission-steps/software-dev/specify/prompt.md`**
- `:263` current: ``- Do not emit requirements without stable IDs (`FR-###`, `NFR-###`, `C-###`).``
  New: ``- Do not emit requirements without stable IDs (`FR-###`, `NFR-###`, `C-###`, `SC-###`, with an optional single lowercase letter suffix such as `FR-###a`). Cite another mission's ID as `<mission-slug>#<ID>`; `setup-plan` refuses a malformed declared ID with `SPEC_REQUIREMENT_IDS_INVALID`.``
- `:733` current: `      - [ ] IDs are unique across FR-###, NFR-###, and C-### entries`
  New: ``      - [ ] IDs are unique across FR-###, NFR-###, C-### and SC-### entries, and match the requirement-ID grammar (optional lowercase letter suffix; `<mission-slug>#<ID>` only for another mission's ID)``
- Leave `:101`, `:232`, `:701` and the brief-intake lines (`:323-377`) alone: they are correct and not about the grammar.
- Regenerate the three snapshots (sanctioned edit 1):
  ```bash
  PYTEST_UPDATE_SNAPSHOTS=1 PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/skills/test_command_renderer.py tests/specify_cli/regression/test_twelve_agent_parity.py
  PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/skills/test_command_renderer.py tests/specify_cli/regression/test_twelve_agent_parity.py
  git diff --stat -- tests/specify_cli/skills/__snapshots__ tests/specify_cli/regression/_twelve_agent_baseline
  ```
  The diff must touch exactly the three specify files, and only the two edited lines in each. Anything else means the regeneration picked up unrelated drift: stop and report it.

**B. `software-dev/actions/specify/guidelines.md:27`** (and its byte-identical mirror, sanctioned edit 2): the same replacement as A `:263`. Afterwards, `cmp` the two files; it must report no difference.

**C. `mission-steps/software-dev/tasks-outline/prompt.md`**
- `:96` current: ``- Every WP must include a `requirement_refs` list referencing IDs from `spec.md` (FR/NFR/C)``
  New: ``- Every WP must include a `requirement_refs` list referencing IDs declared in `spec.md` (FR/NFR/C/SC, with an optional lowercase letter suffix such as `FR-###a`)``
- `:178` current: ``- `requirement_refs`: Requirement IDs from `spec.md` (FR/NFR/C) addressed by this WP.``
  New: ``- `requirement_refs`: Requirement IDs declared in `spec.md` (kinds FR/NFR/C/SC, digits, an optional single lowercase letter suffix) addressed by this WP. Success criteria are tracked, not gating. A `<mission-slug>#<ID>` citation of another mission's ID is kept and reported as `foreign_qualified`, but never counts as this mission's coverage. Items are kept exactly as written.``
- Leave the `FR-001`…`NFR-001` example refs (`:128-163`) untouched; they are counted.

**D. `mission-steps/software-dev/tasks-packages/prompt.md`**
- `:203` current: `requirement_refs: ["FR-001", "NFR-001"]  # From wps.yaml requirement_refs`
  New: `requirement_refs: ["FR-001", "NFR-001"]  # Copied verbatim from wps.yaml requirement_refs`
- Insert one paragraph right after that frontmatter block's closing fence, before the `**Note**: plan_concern_refs…` line:
  ``Copy `requirement_refs` from `wps.yaml` exactly as written, including `SC-###`, letter-suffixed (`FR-###a`) and `<mission-slug>#<ID>` items. `finalize-tasks` never erases or rewrites them; a ref it cannot use is reported with a reason (`malformed`, `unknown_spec_id` or `foreign_qualified`) instead.``
- Do not touch the `plan_concern_refs` warning; `tests/contract/test_tasks_packages_prompt_guards.py` pins it.

**E. `mission-steps/software-dev/tasks-finalize/prompt.md`**
- `:42-45` current:
  ```text
  - Validate requirement mapping:
    - Every WP has at least one requirement reference
    - Referenced requirement IDs exist in spec.md
    - Every FR-### in spec.md is mapped to at least one WP
  ```
  New:
  ```text
  - Validate requirement mapping:
    - Every WP has at least one accepted requirement reference (a declared FR, NFR, C or SC; a `<mission-slug>#<ID>` citation does not count)
    - Every ref gets one verdict: `malformed` and `unknown_spec_id` fail; `foreign_qualified` (another mission's ID) never fails; valid refs always count
    - Every functional requirement declared in spec.md (`FR-###`, including one with a lowercase letter suffix such as `FR-###a`) is mapped to at least one WP
    - Declared success criteria (`SC-###`) are tracked, not gating: they appear in `success_criteria_coverage` but never fail validation
  - Keep every authored `requirement_refs` item: finalize never erases or rewrites refs
  ```
- `:49-52` (keep the pinned `do **not** run finalization` sentence at `:47-48` intact). Current:
  ```text
  (`missing_requirement_refs_wps`, `unknown_requirement_refs`, and
  `unmapped_functional_requirements`), then fix mappings with
  ```
  New:
  ```text
  (`missing_requirement_refs_wps`, `unknown_requirement_refs`,
  `unmapped_functional_requirements`, and `rejected_requirement_refs` with each
  ref's reason), compare them with `parsed_spec_ids` (the IDs finalize read from
  spec.md, grouped by kind), then fix mappings with
  ```
- `:109` current: ``- Validation details when checks fail (`missing_requirement_refs_wps`, `unknown_requirement_refs`, `unmapped_functional_requirements`)``
  New: add the three new keys after `:107`, then keep `:109` extended:
  ```text
  - `"parsed_spec_ids"` — requirement IDs parsed from spec.md, grouped as `functional`, `non_functional`, `constraint`, `success_criteria`
  - `"rejected_requirement_refs"` — per WP, each unusable ref with one reason: `malformed`, `unknown_spec_id` or `foreign_qualified`
  - `"success_criteria_coverage"` — informational: `referenced` (SC → WPs) and `unreferenced`; never fails the run
  ```
  and `:109` becomes ``- Validation details when checks fail (`missing_requirement_refs_wps`, `unknown_requirement_refs`, `unmapped_functional_requirements`, `rejected_requirement_refs`)``.

**F. `mission-steps/software-dev/tasks/prompt.md`** (the umbrella prompt; `:239` and the `map-requirements --batch` line are pinned).
- `:242-246` current:
  ```text
     do **not** run the mutating finalization command. Report
     `missing_requirement_refs_wps`, `unknown_requirement_refs`, and
     `unmapped_functional_requirements`, then fix mappings with
  ```
  New (keep the first line byte-identical):
  ```text
     do **not** run the mutating finalization command. Report
     `missing_requirement_refs_wps`, `unknown_requirement_refs`,
     `unmapped_functional_requirements`, and `rejected_requirement_refs` (each
     ref's reason), checked against `parsed_spec_ids`, then fix mappings with
  ```
- `:315-317` current: ``The CLI validates each ref against spec.md and writes `requirement_refs` directly into each``
  New: ``The CLI validates each ref against the requirement-ID grammar (FR, NFR, C or SC, digits, an optional lowercase letter suffix) and the IDs spec.md declares, and writes `requirement_refs` directly into each``
- `:328-330` current:
  ```text
  The response includes a coverage summary showing which FRs are still unmapped. Keep calling
  until `unmapped_functional` is empty. Default mode unions new refs with existing ones in
  frontmatter. Use `--replace` to overwrite a WP's refs (e.g., to correct a bad mapping).
  ```
  New:
  ```text
  The response includes a coverage summary showing which FRs are still unmapped. Keep calling
  until `unmapped_functional` is empty. Default mode is append-only: existing items stay exactly
  as written and in order, and new refs are appended in canonical form (kind uppercase, suffix
  lowercase). A refusal lists `parsed_spec_ids` and gives each rejected ref one reason
  (`malformed`, `unknown_spec_id` or `foreign_qualified`). Cite another mission's ID as
  `<mission-slug>#<ID>`; it never blocks and never counts as coverage. Use `--replace` to
  overwrite a WP's refs (e.g., to correct a bad mapping).
  ```
- Do NOT touch the batch/individual examples (`:320`, `:325`): their `WP01`/`FR-001` tokens are counted and the `--mission` pin reads them.
- Do NOT fix the umbrella's `tasks.md` hand-writing instruction (`:178`). Record it as friction (T034).

**G. `software-dev/actions/tasks/guidelines.md:18`**
- Current fragment: ``every task must trace back to a requirement (`FR-###`, `NFR-###`, `C-###`) or a locked plan decision``
- New fragment: ``every task must trace back to a requirement (`FR-###`, `NFR-###`, `C-###` or `SC-###`, with an optional lowercase letter suffix) or a locked plan decision``
- Keep the repo-root-relative sentence at `:9` untouched (`test_wp_authoring_contract_roundtrip.py` pins it).

**H. `software-dev/actions/review/guidelines.md`** (no ID wording today). Append ONE bullet at the end of `## Review Intent` (after `:21`):
  ``- Read each rejected requirement ref's reason: `malformed` and `unknown_spec_id` block approval; a `foreign_qualified` ref (`<mission-slug>#<ID>`) cites another mission and never blocks. Success criteria (`SC-###`) are tracked, not gating.``

**I. `mission-steps/software-dev/review/prompt.md:217-219`**: edited in T033, identically to the checklist.

### Subtask T033 – `antipattern_checklist.py` item 4 and its test

- **Tests, written in the RED commit 1** (owned file `tests/specify_cli/review/test_antipattern_checklist.py`). Call the production function `render_wp_review_antipattern_checklist()` directly. Tests:
  1. Item 4 names the grammar: the text contains `**FR coverage**`, `FR-###a`, `SC-###` together with "tracked, not gated", and `<mission-slug>#<ID>`.
  2. Positive control on the same render: all eight labels are present (`Dead code` … `Production fragility`) and the heading line is unchanged. This proves the probe reads the real checklist, so test 1 is not vacuous.
  3. Parity: every numbered item block of the render (split on blank lines, items `1.`–`8.`) appears verbatim in `packs/built-in/missions/mission-steps/software-dev/review/prompt.md`. Locate the file from the repo root (`Path(__file__).resolve().parents[3]`). This pins the two copies together.

  Test 1 (and the guidance-content cases) are RED in commit 1 and go GREEN with this edit. Test 3 (the parity check) is a GREEN ratchet from commit 1 onward, because item 4 is identical in both files today (analysis F11). Record it as a ratchet; never contort it to fake a red.
- **Edit** item 4 at `antipattern_checklist.py:30-32` AND at `review/prompt.md:217-219`, identically. Current (both files):
  ```text
  4. **FR coverage**: every FR in `requirement_refs` has at least one test
     assertion that references the behavior it names, not just a comment or
     frontmatter entry.
  ```
  New (both files):
  ```text
  4. **FR coverage**: every functional requirement in `requirement_refs`
     (`FR-###`, including a letter-suffixed `FR-###a`) has at least one test
     assertion that references the behavior it names, not just a comment or
     frontmatter entry. `SC-###` refs are tracked, not gated, and a
     `<mission-slug>#<ID>` ref cites another mission, so neither needs a test
     here.
  ```
- Keep the label `**FR coverage**`: two render tests outside this WP assert it.
- No new function, constant or branch in the `.py`; it stays one string literal. Complexity is unchanged.

### Subtask T034 – Gates and wrap-up

1. **Provenance census**, run before T031 and again after T033. The two outputs must be identical:
   ```bash
   .venv/bin/python -c "import sys; sys.path.insert(0,'.'); from tests.architectural.test_builtin_pack_provenance_ratchet import census; c=census(); [print(k, c.get(k)) for k in sorted(c) if k.startswith('missions/software-dev/') or k.startswith('missions/mission-steps/software-dev/')]"
   ```
   The ratchet test itself is two-sided, so its passing also proves no count moved.
2. **Run the full Validation surface** and record each command with its passed/failed/skipped counts in the Activity Log and the hand-off.
3. **Tracer notes** (1–3 dated sentences each, in the `## Tracer notes` section of your hand-off):
   - approach: the Step-0 binding, and the snapshot regeneration evidence;
   - design decisions: keeping the `FR coverage` label; placing the review-guideline bullet under Review Intent; any shipped-name difference from the contracts;
   - tooling friction, **mandatory**. Record both, and do NOT fix either (out of scope):
     - The umbrella `mission-steps/software-dev/tasks/prompt.md` (`:178`, "Write `tasks.md`") still instructs hand-writing `tasks.md`, while the canonical split flow (`tasks-outline/prompt.md:14-15,117`) forbids it and generates `tasks.md` from `wps.yaml`. Candidate upstream gap.
     - The software-dev `mission-steps/<step>/guidelines.md` copies are unpinned duplicates of `actions/<step>/guidelines.md` (`test_referential_integrity.py` pins only the documentation/research/plan copies); `tasks` and `review` already drift. Also note the snapshot regeneration tax on `specify/prompt.md`.

## Validation surface

Run only these, as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.

**Test files (template, prompts, checklist):**
- `tests/specify_cli/missions/test_substantive_gate_formats.py` (template declared-ID set and content pins)
- `tests/specify_cli/test_command_template_cleanliness.py`
- `tests/specify_cli/review/test_antipattern_checklist.py` (new)
- `tests/specify_cli/skills/test_command_renderer.py` (codex specify snapshot)
- `tests/specify_cli/regression/test_twelve_agent_parity.py` (claude/gemini specify baseline)
- `tests/specify_cli/skills/test_crlf_skill_render_4998.py` (renders specify)
- `tests/specify_cli/cli/commands/test_init_llxprt.py` (renders specify)
- `tests/missions/test_specify_creates_requirements_checklist.py` (specify)
- `tests/doctrine/missions/test_specify_commit_example_subject.py` (specify)
- `tests/doctrine/test_spk_show_me_skill.py` (specify)
- `tests/prompts/test_prompt_fragment_rendering.py` (specify, tasks)
- `tests/prompts/test_tasks_prompt_ownership_metadata.py` (tasks, tasks-outline, tasks-packages)
- `tests/contract/test_tasks_packages_prompt_guards.py` (tasks-packages)
- `tests/specify_cli/core/test_subtask_rows_snapshot.py` (tasks)
- `tests/doctrine/test_wp_authoring_contract_roundtrip.py` (tasks guidelines, both copies)
- `tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py` (review prompt)
- `tests/doctrine/missions/test_referential_integrity.py` (guidelines copies)
- `tests/doctrine/missions/test_repository.py` (guidelines loading)
- `tests/next/test_prompt_builder_unit.py -k antipattern` (renders the checklist)
- `tests/agent/test_workflow_review_lane_gate.py -k antipattern_checklist` (renders the checklist through `agent workflow review`)

`tasks-finalize/prompt.md` has no content pin beyond the cleanliness file and the provenance ratchet (grep of `tests/` found only those plus the path-only `tests/doctrine/fixtures/content-manifest.json`).

**Not owned, must stay green without edits** (they read the spec template through the template set):
- `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py`

**Owning module fast tier:** `tests/specify_cli/review/`.

**Named architectural gates** (by file name only):
- `tests/architectural/test_builtin_pack_provenance_ratchet.py`
- `tests/architectural/test_no_legacy_terminology.py`
- `tests/architectural/test_lifted_reviews.py` (reads `review/prompt.md`)
- `tests/architectural/test_requirement_id_grammar_single_source.py` (a src file changed; the new string must not read as a requirement-ID pattern literal)

**Static checks** (zero findings):
- `.venv/bin/ruff check src/specify_cli/review/antipattern_checklist.py tests/specify_cli/review/test_antipattern_checklist.py`
- `.venv/bin/ruff format --check src/specify_cli/review/antipattern_checklist.py tests/specify_cli/review/test_antipattern_checklist.py`
- `.venv/bin/mypy --strict src/specify_cli/review/antipattern_checklist.py`

**Baseline-red gotcha:** a failure that is also red on the lane base is not yours. Classify it per CLAUDE.md, report it in the hand-off, and do not fix or hide it. A stale-venv import error means `uv sync --frozen --all-extras` first.

## Test Strategy

- **Wording is verified against shipped behaviour** (Step 0), not against the contracts.
- **Non-vacuity**:
  - the checklist grammar assertion is paired with the eight-label positive control on the same render;
  - the parity test proves the prompt and the checklist cannot drift apart silently;
  - the template's declared-ID pin shows that the new comment text declares nothing, and its `FR-EXAMPLE` presence assertion shows that the probe reads the live file;
  - the lint one-off shows the template passes the new `setup-plan` check.
- **Sonar**: the only `.py` change is one string literal, and it gets a focused test in the same commit.
- **Typing**: `mypy --strict` on the touched src file is part of the gate.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Provenance baseline growth (a new `FR-`/`NFR-` digit, `WPnn`, `#NNNN` or `kitty-specs/` in pack text) | Placeholders only (`FR-###`, `SC-###`, `FR-###a`, `WP##`). Before/after census; the two-sided ratchet catches a drop as well as growth. |
| Template pin drift: a new comment line parses as a declaration | No line starts with an ID token; the SC bullets stay untouched; the declared-ID pin and the lint one-off prove it. Re-pinning is sanctioned only if unavoidable, and should never be needed. |
| Generated agent copies edited | C-006: they are untracked, and `spec-kitty upgrade` regenerates them. `git status` must show only SOURCE files, the three regenerated test snapshots, the mirrored specify guidelines and the new test. |
| The guidance promises a key or reason that did not ship | Step 0 greps the merged code. Quote the shipped names, and record any difference. |
| Snapshot regeneration hides unrelated drift | `git diff --stat` must show exactly three files, with only the edited lines changed. |
| The `FR coverage` label changes and breaks the two non-owned render tests | The label is kept verbatim; only the body changes. |
| Prose sprawl | Only the cited lines change; no unrelated prose is rewritten. |

## Review Guidance

- Only SOURCE files changed (`packs/built-in/…` and the one `.py`), plus the listed sanctioned test/snapshot edits. No `.claude/`, `.agents/` or other generated copy is in the diff.
- No new digit `FR-`/`NFR-` example, `WPnn`, `#NNNN` or `kitty-specs/` in pack text. `test_builtin_pack_provenance_ratchet.py` is green and the baseline YAML is unchanged.
- The spec template's SC bullets and `FR-EXAMPLE` row are unchanged; the declared-ID pin is green without a re-pin.
- Every key, reason and code quoted in the prompts matches the merged WP02/WP03/WP05 code: `parsed_spec_ids`, `rejected_requirement_refs`, `success_criteria_coverage`, `stale_ref_reasons`, `malformed`/`unknown_spec_id`/`foreign_qualified`, `SPEC_REQUIREMENT_IDS_INVALID`.
- Checklist item 4 is identical in the `.py` and in `review/prompt.md`, and the parity test pins it.
- The diffs are minimal; the pinned sentences (`do **not** run …`, the `--batch --mission` line, the repo-root-relative guideline) are untouched.
- The friction note about the umbrella `tasks/prompt.md` is recorded, not fixed.
- The implementer ran `mypy --strict` and ruff (lint and format) in addition to the tests.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-29T06:24:46Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP07 --to <status>` to change WP status.
