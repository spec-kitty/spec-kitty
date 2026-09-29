---
work_package_id: WP02
title: finalize-tasks keeps authored refs, applies per-ref verdicts, reports parsed IDs
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-007
- FR-008
- FR-010
- FR-011
- FR-019
- NFR-002
- NFR-005
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: 61c8ab9d6caaab7722526d6ff3865447c0738edc
created_at: '2026-09-29T09:58:51.936363+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Consumers of the grammar
history:
- at: '2026-09-29T06:12:32Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py
- tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py
- tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – finalize-tasks keeps authored refs, applies per-ref verdicts, reports parsed IDs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show python-pedro` and `.venv/bin/spec-kitty charter context --action implement`.

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

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## ⛔ HARD RULE: no heavy suites

- Never run the whole `tests/architectural/` directory, any e2e or full-integration suite, any performance, stress or timing suite, `make test-full`, or a whole-repo `pytest`. The CI agent owns those (charter `NO_FULL_HEAVY_SUITES_IN_MISSION`, spec C-007).
- Run ONLY the files listed under `## Validation surface`: the named test files, the owning module's fast tier and the two named architectural gate files.
- Command shape: `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.
- **Run pytest from the lane worktree root**, in the same shell command as the `cd`. The repo-root `.venv` has an editable install that points at the repo-root `src/`. `pytest.ini`'s `pythonpath = src` only wins when the rootdir is your lane worktree. Check this once per session: `cd <lane> && .venv/bin/python -c "import specify_cli; print(specify_cli.__file__)"` must print a path under `<lane>/src`. If it does not, prefix `PYTHONPATH=<lane>/src`.
- A failure that is also red on the planning base is not yours. Classify it with the CLAUDE.md "baseline-red gotcha", report it in the Activity Log and the PR, and do not fix it or hide it.

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

Once this WP is done, `spec-kitty agent mission finalize-tasks` behaves as follows:

1. **It never erases or rewrites an authored `requirement_refs` item (FR-004, #2991).** After a real run without `--validate-only`, the WP file's list is item-for-item identical to the list that was seeded. In the same pass, the other finalize fields (`planning_base_branch`, `merge_target_branch`, `branch_strategy`) were written, which proves that the write ran.
2. **It applies per-ref verdicts (FR-019, FR-010).** Every ref is classified by the WP01 grammar as accepted, `malformed`, `unknown_spec_id` or `foreign_qualified`. Accepted refs always count toward coverage, whatever their siblings are. A WP fails when any of its rejected refs has a reason in `FAILING_REASONS`. A WP whose only accepted refs are success criteria counts as having refs.
3. **Suffixed functional requirements are coverage-gated (FR-008, #3519).** A declared `FR-006a` that no WP maps fails `--validate-only`. Once it is mapped, the same fixture passes.
4. **The JSON output explains itself (FR-011, #2066).** It gains three additive keys on success (real and `--validate-only`) and on requirement-mapping failure: `parsed_spec_ids`, `rejected_requirement_refs` and `success_criteria_coverage`, exactly as in `contracts/json-payload-deltas.md`. Every existing key keeps its name and type (NFR-002).
5. **Success criteria are tracked but not gating (FR-007).** An unreferenced declared SC appears under `success_criteria_coverage.unreferenced` and never fails the run. The retired warning "SC … DROPPED, not traced" no longer appears anywhere.
6. **Red-first proof (NFR-005).** Defects (a) #2991-finalize and (d) #2066 each have an issue-pinned repro that is RED through the real CLI before the fix and GREEN after it. Defect (c) #3519's red-first evidence is WP01 T004a (function level and `finalize-tasks` CLI level); WP02 adds a CLI ratchet pin on top of it (T008 (b)).
7. **Quality.** Every touched function has complexity ≤ 15. `finalize_tasks` gets **no new branch**. ruff, `ruff format --check` and `mypy --strict` are clean on the touched files. Each new helper has focused tests in the same commit.

---

## Context & Constraints

### Read first, in full

- `kitty-specs/requirement-id-grammar-01M3NRCA/spec.md`: User Stories 1, 2, 3 and 6; FR-004, FR-007, FR-008, FR-010, FR-011, FR-019; NFR-002, NFR-005; Edge Cases.
- `kitty-specs/requirement-id-grammar-01M3NRCA/plan.md`: "Behavioural changes by surface" (the finalize-tasks rows), "Test and gate surface", IC-00 and IC-02.
- `kitty-specs/requirement-id-grammar-01M3NRCA/data-model.md`: RefVerdict, the per-WP rule, the declared-ID set.
- `kitty-specs/requirement-id-grammar-01M3NRCA/contracts/json-payload-deltas.md`, the finalize-tasks section. This is the binding shape of the new keys.
- `kitty-specs/requirement-id-grammar-01M3NRCA/contracts/grammar.md` and `research.md` R8 (verdicts) and R9 (on-disk form).
- `.kittify/charter/charter.md`: ATDD-First Discipline (C-011), Standing Orders #2 (campsite and tidy-first) and #5 (non-vacuous gates).

### What you consume from WP01 (check it first; do not re-implement it)

WP01 creates `src/specify_cli/requirement_mapping/grammar.py` and turns `requirement_mapping.py` into a package. Import paths do not change. Before you write any code, read the WP01-merged sources on your lane base and confirm these names and shapes (data-model.md, "Grammar API"):

- `classify(raw, declared) -> RefVerdict`. It returns `Accepted(RequirementId)` or `Rejected(raw, reason)`, with `reason ∈ {"malformed", "unknown_spec_id", "foreign_qualified"}`. Matching is by canonical form, so a WP ref `FR-006A` matches the declared `FR-006a`.
- `FAILING_REASONS: frozenset` = `{"malformed", "unknown_spec_id"}`.
- `parse(token) -> RequirementId | None`, with `.kind` in `FR/NFR/C/SC`, a `canonical` string and `is_success_criterion`.
- `tokenize_refs(value) -> list[str]`. It returns the raw items of a list value, or a scalar string split on `[,\s]+`.
- `parse_requirement_ids_from_spec_md(text)` still returns `all` and `functional`. `all` now includes SC and suffixed IDs, and WP01 may add the per-kind groups.
- `read_all_wp_raw_requirement_refs(tasks_dir) -> dict[str, list[str]]`: **the WP01 unified raw reader** (WP01 T001 step 5). Finalize classifies its output (T011), and WP04's runtime classifies the same reader's output, so both gates see the same tokens.
- The reason constants `MALFORMED`, `UNKNOWN_SPEC_ID`, `FOREIGN_QUALIFIED`. Use them rather than restating the strings.

If an API differs materially from the list above, stop. Record the difference in the `## Tracer notes` section of your hand-off and adapt to what WP01 actually shipped. **Never** add a requirement-ID regex, a `.upper()`/`.lower()` on an ID, or a tokenizer to `mission_finalize.py`. The C-001 gate `tests/architectural/test_requirement_id_grammar_single_source.py` will fail on it.

### Seam map (verified on `main` `aedb30cddd`; re-check the line numbers on your base)

| Seam | Location in `mission_finalize.py` | Role |
|---|---|---|
| SC-discard import | `:79` `from specify_cli.requirement_mapping import find_discarded_sc_refs` | retire (T013) |
| spec ID read | `_read_spec_requirement_ids:863-894` returns `(all, functional, warnings, spec_content)` | keep the signature (a test at `test_mission_finalize_phases.py:537-543` unpacks 4) |
| ref resolution | `_resolve_dependencies_and_refs:1013`; frontmatter refs at `:1049`; tasks.md fallback at `:1058-1061` | the raw-ref source for classification (T011) |
| all-or-nothing rule | `_classify_wp_requirement_refs:1161-1182`, the rule at `:1176-1180` | per-ref verdicts (T011) |
| failure report | `_emit_requirement_mapping_report:1214` (cx 10), JSON at `:1227-1235` | payload builder (T009), new keys (T012) |
| gate | `_validate_requirement_mapping:1257-1295` | return the diagnostics (T012) |
| ref rewrite | `_apply_bootstrap_fields:1387-1436`, refs at `:1432-1435` | remove the rewrite (T010) |
| bootstrap loop | `_run_bootstrap_loop:1480` (cx 12), refs at `:1539-1540` | extract the per-WP resolution (T009) |
| write | `_flush_frontmatter_writes:1644-1649` dumps the whole `WPMetadata` model | unchanged; the reason a scalar becomes a list (T010) |
| validate-only success JSON | `_emit_validate_only_report:1862`, payload at `~:1925-1940` | new keys (T012) |
| real-run success JSON | `_emit_success_report:2788`, payload at `~:2836-2885` | new keys (T012) |
| acceptance-matrix seed | `_scaffold_acceptance_matrix_if_lane_based:2601`, the seed at `:2632` | now includes suffixed FRs, for new matrices only (C-008) |
| entry point | `finalize_tasks:3217`, `# noqa: C901` at complexity 15; SC splice at `:3408-3411`; gate call at `:3435-3443` | **no new branch**; only branch-free statement edits |

### Out-of-map edits sanctioned for this WP (and no others)

- `src/specify_cli/requirement_mapping/__init__.py` (WP01-owned). Delete `find_discarded_sc_refs` and `_discarded_sc_warning`. Also delete `_SC_REF_FIND_PATTERN` if it still lives there and nothing else uses it. **Rationale:** the only caller is removed in T013, so `test_no_dead_symbols` would flag the orphaned public function, and a leftover pattern literal would trip the C-001 gate. Touch nothing else in that file.
- `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` (WP05-owned): re-pin `_TASKS_SUCCESS_DATA_KEYS` (`:181-204`, asserted at `:671`), adding ONLY `parsed_spec_ids`, `rejected_requirement_refs` and `success_criteria_coverage`, with a one-line comment citing NFR-002 (additive). **Rationale:** the `tasks` verb passes finalize's success payload through, so T012's additive keys red that exact key-set pin. Touch nothing else in that file; WP05 edits `_PLAN_SUCCESS_DATA_KEYS` in its own lane (WP05 T025).
- **Dead-reader removal (C1), only if truly orphaned.** After T011 switches `:1049` to `read_all_wp_raw_requirement_refs`, grep first: `rg -n "_parse_requirement_refs_from_wp_files" src tests`. If the only remaining references are its definition, its re-exports and its own unit tests, remove, in the T011 commit:
  - the function in `src/specify_cli/cli/commands/agent/mission_parsing.py` (WP01-owned; `:114` on the planning base);
  - its re-export in `src/specify_cli/cli/commands/agent/mission.py` (`:137`) and its import in `mission_finalize.py` (`:107`, your own file);
  - its three unit tests in `tests/specify_cli/cli/commands/agent/test_mission_parsing.py` (`:103-125`, WP01-owned);
  - its entry in `tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py`, only if that file pins it (it did not on the planning base; re-check).

  **Rationale:** a dead reader next to the WP01 unified raw reader is a second WP-ref read path and a `test_no_dead_symbols` finding. If any other product caller remains, keep the function and record the caller in `## Tracer notes`. Keep `_parse_requirement_refs_from_tasks_md`; it is still used.
- **Parallel-lane hunks (D4).** A parallel lane also edits `src/specify_cli/requirement_mapping/__init__.py` in a distant hunk (WP03 removes the `validate_*`/`classify_stale_refs` helpers near `:389-450`; you remove `find_discarded_sc_refs` near `:194-214`); keep your hunk minimal and do not reformat the file. A parallel lane also edits `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` in a distant hunk (WP05 re-pins `_PLAN_SUCCESS_DATA_KEYS` at `:148-179`; you re-pin `_TASKS_SUCCESS_DATA_KEYS` at `:181-204`); keep your hunk minimal and do not reformat the file. The multi-dependency lane merge fails closed on a conflict.
- `tests/agent/test_agent_feature.py` and `tests/missions/test_write_surface_coherence.py`: edit these only if an assertion pins an exact key set or an exact refs list that the additive keys or the kept refs legitimately change. **Rationale:** NFR-002 allows additive keys, and FR-004 changes which refs stay on disk. Re-pin each such assertion narrowly and cite FR-004 or NFR-002 in a comment. Do not weaken an unrelated assertion.

### Architecture guardrails

- `mission_finalize.py` is a consumer. Grammar logic stays in `grammar.py` (C-001). Mapping a `RequirementId.kind` to a JSON bucket name (`FR → functional`, `NFR → non_functional`, `C → constraint`, `SC → success_criteria`) is presentation, and is allowed here as one module constant. Use the WP01 grouping instead if WP01 exposes one.
- `finalize_tasks` is at complexity 15 with a `noqa`. You may change a statement there, for example turn the `_validate_requirement_mapping(...)` call into an assignment or delete the splice at `:3408-3411`. You may not add an `if`, `for`, `while`, `try`, boolean operator or comprehension-with-`if`. Route every new behaviour through the helpers.
- Terminology: say Mission, never "feature", in every new identifier, docstring, comment and test name. (Existing fixtures say `feature_dir`; leave those alone.)

---

## Branch Strategy

- **Strategy**: set by `.venv/bin/spec-kitty agent mission finalize-tasks` in this file's frontmatter.
- **Planning base branch** and **merge target branch**: both `issue-2991-requirement-id-grammar`.
- The execution worktree comes from the lane `lanes.json` computes. Start it with `.venv/bin/spec-kitty agent action implement WP02 --agent claude`. Never pick a base by hand. Your lane base already contains WP01 (dependency).

---

## Subtasks & Detailed Guidance

Commit order: **T008 (red) → T009 (tidy) → T010 → T011 → T012 → T013 → T014.** Each T0xx is one or more commits. Never fold T008 or T009 into a functional commit.

### Subtask T008 – RED-FIRST issue-pinned repros (FIRST commit)

- **Purpose**: Prove each defect through the pre-existing entry point before touching `src/` (ADR 2026-07-17-1, charter C-011, NFR-005).
- **File**: create `tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py`. This commit contains nothing else.
- **Entry point**: the real typer command via `CliRunner`, with `from specify_cli.cli.commands.agent.mission import app` and `runner.invoke(app, ["finalize-tasks", "--mission", <slug>, "--json", "--target-branch", "main", ...])`. Do not call the helper functions directly in these repros.
- **Fixture template (copy the patch set, do not improvise):** `tests/agent/test_agent_feature.py:1242-1325` (`test_uses_wp_frontmatter_requirement_refs_when_tasks_md_missing_refs`). It is the only existing CliRunner real-write finalize test. It patches these names:
  - `mission.locate_project_root`
  - `mission._find_feature_directory`
  - `mission._show_branch_context`
  - `mission_finalize.resolve_checkout_identity`, which injects a `CheckoutIdentity` rooted at `tmp_path`
  - `coordination.commit_router.commit_for_mission`
  - `mission.run_command`

  Also mirror the autouse `SPEC_KITTY_ENABLE_SAAS_SYNC=0` fixture from `test_feature_finalize_bootstrap.py:40-52`. Put the fixture builder in one module-level helper, `_seed_mission(tmp_path, *, spec_md, wp_refs: dict[str, list[str]])`, so all repros share it. Parse JSON the way `test_agent_feature.py:1316-1318` does: take the last line that starts with `{`.
- **Fixture spec.** Include every declared shape the grammar admits:
  - a Functional Requirements table with `| FR-001 |` and `| FR-006a |`;
  - a Success Criteria section with the template's bold-bullet shape, `- **SC-001**: …` and `- **SC-002b**: …`.
- **Mark** each test `@pytest.mark.regression`. Name the issue in its docstring (`#2991`, `#3519`, `#2066`). Also add the module-level `pytestmark = [pytest.mark.fast]` so the fast tier collects the file.

**(a) #2991: a real run erases authored refs.**
- WP01 refs, in this order, and nothing else: `[FR-001, SC-001, SC-002b, FR-006A]`.
  - `FR-006A` is an uppercase-suffix spelling of the declared `FR-006a`.
  - Every item is valid after the fix, so the real write must run. Keep this so the test is non-vacuous. **Do not** add a malformed token here, because a malformed ref makes finalize fail before the write. The qualified-citation retention case lives in T011, not here.
- Run without `--validate-only`. Assert all three:
  - (i) `exit_code == 0`;
  - (ii) the WP file read back with `read_wp_frontmatter` has `requirement_refs` equal to the seeded list, item for item and in order;
  - (iii) **non-vacuity**: `planning_base_branch == "main"` and `branch_strategy` contains `"Planning artifacts"` in the same file.
- Why it is RED on the WP01 base: WP01's `normalize_requirement_refs_value` respells `FR-006A` → `FR-006a`, and finalize still writes the normalised list, so (ii) fails. It goes GREEN after T010. The SC and suffix drops are the historical #2991 shape on the pre-WP01 base.

**(b) #3519: a declared, unmapped `FR-006a` makes `--validate-only` fail.**
- The WP refs map `FR-001` only. Run `--validate-only`. Assert `exit_code == 1` and `"FR-006a" in payload["unmapped_functional_requirements"]`.
- **Positive control, on the same fixture:** add `FR-006a` to a WP's refs, re-run `--validate-only`, and assert `exit_code == 0`.
- **Red-first evidence lives in WP01.** WP01's rewire closes the #3519 hole, and WP01 T004a carries both the function-level and the `finalize-tasks --validate-only` CLI-level red-first repros. So (b) is expected to be GREEN on your WP01 base: keep it as a CLI ratchet pin, say so in the Activity Log, and cite WP01 T004a as the NFR-005(c) red-first evidence. Never contort the fixture to manufacture a red.

**(c) #2066: the failure JSON has no parsed spec-ID set.**
- Seed an unmapped `FR-006a` (as in (b)) plus one WP ref `SC-009`, which is an undeclared success criterion. Run `--validate-only`.
- Assert, in this order:
  - `"parsed_spec_ids" in payload`, first, so the RED failure names the missing key rather than a `KeyError`;
  - `exit_code == 1`;
  - `payload["parsed_spec_ids"] == {"functional": ["FR-001", "FR-006a"], "non_functional": [], "constraint": [], "success_criteria": ["SC-001", "SC-002b"]}`;
  - `{"ref": "SC-009", "reason": "unknown_spec_id"} in payload["rejected_requirement_refs"]["WP0x"]`.
- On the base it is RED because the keys are absent.
- **Prove RED:** after this first commit, run `cd <lane> && PWHEADLESS=1 .venv/bin/python -m pytest -q tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py`. Paste the failing test IDs and the one-line reasons into the Activity Log. (a) and (c) must fail on assertions, not on fixture errors. If one fails for a fixture reason, fix the fixture and re-prove it. (b) is expected green (the ratchet above).

### Subtask T009 – Tidy-first extractions (separate, behaviour-preserving commit)

- **Purpose**: Make room for T010–T012 without breaching complexity 15 and without touching `finalize_tasks` (plan IC-00, charter Standing Order #2).
- **Extraction 1: `_run_bootstrap_loop` (`:1480`, cx 12).** Move the per-WP input resolution into one helper, for example `_resolve_wp_bootstrap_inputs(wp_id, wp_meta, dep_resolution, wps_manifest, state) -> tuple[list[str], list[str]]`. It covers the dependency preservation at `:1531-1537`, the refs lookup at `:1539` and the `state.work_packages.append(...)` at `:1540`. The loop calls it. Behaviour is identical, including `state.preserved_wps` bookkeeping.
- **Extraction 2: `_emit_requirement_mapping_report` (`:1214`, cx 10).** Move the payload dict into a pure `_build_requirement_mapping_failure_payload(...) -> dict[str, object]`. The emitter keeps only the JSON/console branching.
- **Tests (same commit):** add focused tests for both new helpers in `test_mission_finalize_phases.py`:
  - the helper's dependency preservation for both the `wps_manifest is None` and not-None cases;
  - the payload builder returning exactly the current 7 keys.

  **Every existing test stays unchanged and green.** This includes `test_emit_requirement_mapping_report_json:370-389`, which pins exact equality.
- **Check**: `.venv/bin/ruff check --select C901` on the file reports nothing new. Run the whole validation surface before committing.

### Subtask T010 – finalize-tasks never rewrites authored refs (FR-004)

- **Change.** Stop feeding authored refs back into the builder:
  - Remove the `requirement_refs` comparison and `bld.set(requirement_refs=...)` for any WP whose frontmatter already carries items (`_apply_bootstrap_fields:1432-1435`, reached via `:1539` and `:1548-1549`).
  - The model then keeps the items exactly as `WPMetadata` read them.
  - `_flush_frontmatter_writes` still dumps the whole model, so the list goes back out unchanged.
- **The tasks.md fallback: populate-when-empty (mandatory).**
  - Today a WP with **no** authored refs gets them populated from the tasks.md fallback (`:1058-1061`) through this same `bld.set`.
  - Populating an empty list erases nothing. Removing it would regress legacy pre-`wps.yaml` Missions, whose WP frontmatter would then stay empty for map-requirements and the dossier.
  - Keep exactly one narrow write: set `requirement_refs` only when `wp_meta.requirement_refs` is empty and the resolved refs are non-empty. Pin both halves with tests:
    - (1) an authored list is never touched, even when tasks.md lists different refs;
    - (2) an empty WP is populated from tasks.md.
  - `_apply_bootstrap_fields` must stay at cx ≤ 15. Update its docstring (it lists "requirement_refs" among the always-evaluated fields).
- **Legacy scalar-string `requirement_refs`** (for example `requirement_refs: "FR-001, SC-001"`):
  - `WPMetadata._normalize_legacy_fields` (`status/wp_metadata.py:333-336`, rewired to `grammar.tokenize_refs` by WP01) coerces it to a list.
  - `_flush_frontmatter_writes` then re-serialises it as a YAML list whenever any other field changes.
  - Keeping the scalar form would need a raw-frontmatter read and a substitution at flush time: a second raw-dict path for one legacy shape.
  - **Mandatory:** the list form is the one allowed rewrite (the items keep their order and spelling; only the container changes). This matches the #3941 precedent for string-form `dependencies`. Pin it with a test: a scalar `"FR-001, SC-002b"` becomes `["FR-001", "SC-002b"]` after a real run, with the same items.
  - List it as an NFR-002 changelog note in your hand-off's `## Changelog notes` (for example: "finalize-tasks re-serialises a legacy scalar-string `requirement_refs` as a YAML list; items, order and spelling unchanged"), and name it in the PR body as an on-disk change.
- **Existing tests to re-pin** (all in owned files):
  - `test_apply_bootstrap_fields_marks_changes:577`
  - `..._keeps_planning_and_final_targets_distinct:597`
  - `..._noop_when_already_set:622`
  - `..._normalizes_string_form_even_when_values_equal:687`

  They pass `requirement_refs=` and `has_requirement_refs_line=`. If you change the signature, update the calls and add one assertion per test that `"requirement_refs" not in fields` for an authored list. This is a deliberate FR-004 re-pin (DIRECTIVE_041); say so in each test's docstring.
- **Expected GREEN after T010:** repro (a).

### Subtask T011 – Per-ref verdicts (FR-019, FR-010, FR-008)

- **Raw-ref source (binding).** Classification needs the authored tokens, not a pre-filtered list, or a malformed token silently vanishes and is never reported.
  - Switch `:1049` to `read_all_wp_raw_requirement_refs(tasks_dir)` from `specify_cli.requirement_mapping`: the WP01 unified raw reader. WP04's runtime classifies the same reader, which is what makes the two gates agree on malformed and foreign refs.
  - Do not edit `mission_parsing.py` (it is WP01's) beyond the sanctioned dead-reader removal (see "Out-of-map edits"), and do not add a second local reader.
  - Name the reader in `_resolve_dependencies_and_refs`'s docstring. The tasks.md fallback keeps its WP01 behaviour.
- **Replace the all-or-nothing rule at `:1176-1180`.** For each WP, call `grammar.classify(raw, declared)` per ref:
  - accepted refs are added to `mapped` by **canonical** string;
  - rejected refs are recorded as `{"ref": raw, "reason": reason}`.
- **Bucket semantics.** Existing keys keep their names and types:
  - `missing_requirement_refs_wps`: WPs with **no accepted ref** (Decision Moment `01M3NYFZ1P6QBD2DX4DVDA323W`; `data-model.md` per-WP rule). A WP whose only accepted refs are SC counts as having refs. A WP with only rejected refs is missing **and** is listed with its rejections; that includes a foreign-only WP, which fails through this missing rule even though `foreign_qualified` itself never fails.
  - `unknown_requirement_refs[wp]`: the sorted raw refs whose reason is in `FAILING_REASONS`. Put a `foreign_qualified` ref here **never**. The existing gate condition (`unknown_requirement_refs` non-empty → fail) then implements "a WP fails if any rejected ref's reason is failing" with no new branch in `_validate_requirement_mapping`.
  - A new per-WP rejection map (every reason, including `foreign_qualified`) feeds `rejected_requirement_refs` in T012.
- **Coverage.** `unmapped_functional_requirements = sorted(functional - mapped)`, compared by canonical form. A declared `FR-006a` is therefore gated (FR-008), and `FR-006A` on a WP satisfies it.
- **Return shape.** Keep `_classify_wp_requirement_refs`'s first three return values compatible with `test_mission_finalize_phases.py:341-362`. Add the rejection map as a fourth element or return a small frozen dataclass, and update those two tests if you change the shape. Stay at cx ≤ 15; extract `_classify_one_wp(...)` if needed.
- **Prove the compound fix half by half.** Write focused tests through the CLI (`--validate-only`) on one shared fixture:
  - **Half 1: valid refs still count while a sibling fails.** WP01 = `[FR-001, SC-009]`, where SC-009 is undeclared.
    - Exit 1, with `unknown_requirement_refs == {"WP01": ["SC-009"]}`.
    - **Positive control on the same fixture:** `FR-001` is **not** in `unmapped_functional_requirements`, because it counted.
  - **Half 2: a non-failing rejection does not fail.** WP01 = `[FR-001, other-mission-01KAAAAA#FR-013]`.
    - Exit 0, and the citation is reported `foreign_qualified`.
  - **Qualified citation kept on disk (FR-004 + FR-009; a real run, not `--validate-only`).** On the Half 2 fixture, run without `--validate-only`. Assert exit 0, then read the WP file back with `read_wp_frontmatter`: `requirement_refs == ["FR-001", "other-mission-01KAAAAA#FR-013"]`, item for item. Non-vacuity: `planning_base_branch == "main"` in the same file, which proves the write ran.
  - **SC-only WP.** WP02 = `[SC-001]`, with every FR mapped elsewhere. WP02 is **not** in `missing_requirement_refs_wps`, and the run passes.
  - **Foreign-only WP (DM `01M3NYFZ1P6QBD2DX4DVDA323W`).** WP02 = `[other-mission-01KAAAAA#FR-013]`, with every FR mapped elsewhere. Exit 1, WP02 is in `missing_requirement_refs_wps`, and `unknown_requirement_refs` does NOT list the citation (it is `foreign_qualified`). The SC-only case above is the positive control.
  - **Malformed kept on disk (US1 AC2).** WP01 = `[FR-001, C-007-mission]`, real run.
    - Exit 1 with `C-007-mission` reported `malformed`.
    - The WP file is byte-identical to the seeded text, because the run failed before the write.
    - **Control:** `FR-001` is not in `unmapped_functional_requirements`.
- **Expected GREEN after T011:** repro (b) (if it was not already green) and the verdict tests.

### Subtask T012 – Additive JSON keys (FR-011, FR-007, FR-008; NFR-002)

- **Shape:** exactly `contracts/json-payload-deltas.md` §finalize-tasks.
  - `parsed_spec_ids: {functional, non_functional, constraint, success_criteria}`, each a sorted list of canonical IDs. Group them by `RequirementId.kind`, and always include all four keys.
  - `rejected_requirement_refs: {WP: [{ref, reason}]}`. Include only WPs that have rejections, in the order the authored refs appear.
  - `success_criteria_coverage: {referenced: {SC: [WP…]}, unreferenced: [SC…]}`. It is informational and **never** fails the run. A Mission with no Success Criteria section gets `{"referenced": {}, "unreferenced": []}`.
  - **Named focused test (spec Edge Case "no success-criteria section"):** `test_mission_without_success_criteria_section_finalizes_unchanged`, through the CLI (`--validate-only --json`) on a spec with FR/NFR/C tables and **no** Success Criteria section, every FR mapped. Assert `success_criteria_coverage == {"referenced": {}, "unreferenced": []}`, `parsed_spec_ids["success_criteria"] == []`, exit 0, and that every pre-existing key (`requirement_refs_parsed`, `unknown_requirement_refs`, `missing_requirement_refs_wps`, `unmapped_functional_requirements`, `bare_prose_requirement_ids`, `dependencies_parsed`, `requirement_extraction_warnings`) has the same value it has with the grammar keys ignored. Positive control on the same fixture: leave one FR unmapped and assert exit 1 naming it, so the "unchanged" pass is not vacuous.
- **One builder, three emitters.**
  - Build all three keys once in a pure helper, `_build_requirement_diagnostics(...) -> dict[str, object]`, with focused tests.
  - `_validate_requirement_mapping` returns the diagnostics on success, and passes them into the failure payload builder from T009.
  - Carry them to the two success reports without new branches in `finalize_tasks`:
    - (1) make the call at `:3435` an assignment into a new `_DependencyResolution` field, for example `dep_resolution.requirement_diagnostics = _validate_requirement_mapping(...)`;
    - (2) copy that field onto a new `_BootstrapState` field inside `_run_bootstrap_loop` (or the T009 helper);
    - (3) spread it into the payloads of `_emit_validate_only_report` and `_emit_success_report`.
  - Existing callers that ignore the return value (`test_mission_finalize_phases.py:289-333, 467-529`) keep working.
- **Keep** every existing key with the same type: `requirement_refs_parsed`, `unknown_requirement_refs`, `missing_requirement_refs_wps`, `unmapped_functional_requirements`, `bare_prose_requirement_ids`, `dependencies_parsed` and `requirement_extraction_warnings`.
  - `test_emit_requirement_mapping_report_json:370-389` pins exact equality. Re-pin it to the 7 old keys **plus** the 3 new ones, with a docstring line citing NFR-002 (additive).
  - Grep `rg -n "requirement_refs_parsed|unknown_requirement_refs|missing_requirement_refs_wps" tests` for other exact-set pins. Known hits: `tests/agent/test_agent_feature.py:1320`, `tests/missions/test_write_surface_coherence.py:267` and `test_feature_finalize_bootstrap.py:365-455`.
  - `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py`: re-pin `_TASKS_SUCCESS_DATA_KEYS` (`:181-204`, asserted at `:671`) in this commit, adding only the three new keys (sanctioned out-of-map edit, citing NFR-002).
  - `tests/next/test_runtime_bridge_unit.py` is not yours; if it pins a finalize payload exactly, report it rather than editing.
- **Console output** (non-JSON): add a short "Rejected requirement refs" block (`WP: ref (reason)`) to the failure console path, and test it the way `test_emit_requirement_mapping_report_console:392` does.
- **Expected GREEN after T012:** repro (c).

### Subtask T013 – Retire the SC discard warning (FR-007)

- **Remove:**
  - the import at `:79`;
  - the splice at `:3408-3411`. Leave `requirement_extraction_warnings` bound to `_read_spec_requirement_ids`'s third element. This deletes statements and adds no branch;
  - in `src/specify_cli/requirement_mapping/__init__.py` (a sanctioned out-of-map edit, rationale above): `find_discarded_sc_refs`, `_discarded_sc_warning` and an orphaned `_SC_REF_FIND_PATTERN`.
- **Re-pin `test_discarded_sc_refs_warning_names_dropped_token` (`test_mission_finalize_phases.py:754-770`).** Replace it with a CLI-level test on one fixture:
  - the spec declares `SC-008` **and** has a Functional Requirements section that writes an undeclared token in prose, so `_find_undeclared_requirement_citations` emits its warning;
  - WP01 refs are `[FR-001, SC-008]`;
  - run `--validate-only --json`.
- **Assert:**
  - (i) no entry of `requirement_extraction_warnings` contains `"DROPPED, not traced"` or `"Success-Criteria token"`. This is the retirement check;
  - (ii) **positive control:** `requirement_extraction_warnings` is non-empty and contains the undeclared-citation warning. The key is alive and still carries the other warnings, so (i) is not vacuous;
  - (iii) `success_criteria_coverage.referenced == {"SC-008": ["WP01"]}`.

  Name the test for the behaviour, for example `test_referenced_sc_is_traced_and_the_discard_warning_is_retired`.
- Run `tests/architectural/test_no_dead_symbols.py` and `tests/specify_cli/test_requirement_mapping.py` right after this commit.

### Subtask T014 – Wrap-up

- **Demote the T008 repros.** Remove `@pytest.mark.regression` from every test in `test_finalize_requirement_id_grammar.py` and keep them there as focused functional tests (`pytestmark = [pytest.mark.fast]`). No test in the file may remain marked `regression` (charter C-011). Keep each docstring's issue number.
- **Complexity check:** `.venv/bin/ruff check --select C901 src/specify_cli/cli/commands/agent/mission_finalize.py`. Compare `finalize_tasks` before and after with `git diff`: the only changes allowed there are the assignment at the gate call and the deleted splice.
- Run the whole `## Validation surface`. Record every command with its passed/failed/skipped counts in the Activity Log and in the PR's *Tests run* section.
- **Tracer notes.** Add dated entries of 1–3 sentences to the `## Tracer notes` section of your hand-off:
  - approach: the red→green evidence, and the (b) ratchet note;
  - design decisions: the populate-when-empty write, the scalar-to-list rewrite, and the missing-vs-foreign-only rule (DM `01M3NYFZ1P6QBD2DX4DVDA323W`);
  - tooling friction: any WP01 API mismatch or harness friction.
- **Changelog notes (NFR-002).** `docs/changelog/CHANGELOG.md` is written by the orchestrator at closeout; this WP does not edit it. Put one-liners in a `## Changelog notes` section of your hand-off: the three additive finalize keys; authored refs are never rewritten (FR-004); the retired SC discard warning (FR-007); the scalar-to-list rewrite; and that the dossier parity hash (`dossier/hasher.py:194`) changes for WPs whose refs were previously erased (expected, spec Assumptions).

---

## Validation surface

Run all of these from the lane worktree root (see the HARD RULE). Nothing else.

**Test files** (`PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`):

- `tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py`
- `tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py`
- `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_finalize_validation.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_finalize_seam.py`
- `tests/specify_cli/cli/commands/agent/test_mission_parsing.py`
- `tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py`
- `tests/agent/test_agent_feature.py`
- `tests/missions/test_write_surface_coherence.py`
- `tests/specify_cli/test_requirement_mapping.py`
- `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` (the `_TASKS_SUCCESS_DATA_KEYS` re-pin; at least `-k success_data_key_shape`)

**Owning module fast tier:** `PWHEADLESS=1 .venv/bin/python -m pytest -q -m "fast or unit" tests/specify_cli/cli/commands/agent/`

**Named architectural gates (by file, never the directory):**

- `tests/architectural/test_no_dead_symbols.py`
- `tests/architectural/test_requirement_id_grammar_single_source.py`

**Static checks, on the touched src files:**

- `.venv/bin/ruff check src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/requirement_mapping/__init__.py tests/specify_cli/cli/commands/agent/test_finalize_requirement_id_grammar.py tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py`
- `.venv/bin/ruff format --check` on the same files
- `.venv/bin/mypy --strict src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/requirement_mapping/__init__.py`
- `.venv/bin/ruff check --select C901 src/specify_cli/cli/commands/agent/mission_finalize.py` (no new finding)

---

## Test Strategy

- **ATDD order:** the T008 repros come first, RED. T009 is behaviour-neutral, and the existing suite stays green unchanged. T010–T013 each turn specific tests green. T014 demotes the repros.
- **Entry point:** every defect repro, and every verdict or retirement test that asserts an observable outcome, goes through `runner.invoke(app, ["finalize-tasks", ...])`. Pure helpers (`_build_requirement_diagnostics`, the payload builder, `_resolve_wp_bootstrap_inputs`, `_classify_wp_requirement_refs`) also get direct unit tests in `test_mission_finalize_phases.py` for Sonar new-code coverage (≥ 90% diff coverage, NFR-004).
- **Non-vacuity checklist** (tactic `acceptance-criteria-non-vacuity`). Each of these must be true:
  - The byte-identity assertion runs on a **real** write, proven by `planning_base_branch` being set in the same file.
  - Every "absent" or "does not fail" assertion has a same-fixture positive control:
    - the retired warning has a live `requirement_extraction_warnings` entry;
    - a `foreign_qualified` pass has an `unknown_spec_id` failure on the sibling fixture;
    - an unreferenced-SC pass has an unmapped-FR failure (FR-007's own control: add an unmapped `FR-00x` to the SC-unreferenced fixture and assert exit 1 naming it).
  - The compound FR-019 fix is proven half by half (T011).
- **Fixture discipline:** one `_seed_mission` builder. Spec text uses the canonical declared shapes. Do not copy structure from older missions in `kitty-specs/`.
- **Typecheck:** `mypy --strict` on the touched src files is part of the gate. Passing tests does not replace it.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Dossier parity hash (`dossier/hasher.py:194`) changes for WPs whose refs were previously erased | Expected (spec Assumptions). Note it in the Activity Log, the PR body and the hand-off's `## Changelog notes`; the orchestrator writes the changelog at closeout |
| The acceptance-matrix seed at `:2632` now includes suffixed FRs | Only for **new** matrices (C-008). Existing matrices are not re-seeded. Mention it in the PR |
| Other tests pin exact JSON key sets | Grep before T012 (commands above). Re-pin only owned or sanctioned files; report anything else |
| `finalize_tasks` creeps past complexity 15 | All logic lives in helpers. Only branch-free statement edits in `finalize_tasks`; the C901 check in T014 |
| WP01's API differs from data-model.md | Read the WP01 sources first; adapt, never re-implement; log it in the hand-off's `## Tracer notes` |
| The (b) repro is already green on the WP01 base | Expected: WP01 T004a holds the red-first evidence; keep (b) as a ratchet (T008) |
| The tests run against the repo-root `src/` instead of the lane's | Run pytest from the lane root; verify `specify_cli.__file__` once (HARD RULE) |
| Legacy tasks.md-only Missions lose their frontmatter refs | The mandatory populate-when-empty write, pinned both ways (T010) |
| A foreign-only WP is reported "missing" | Intended: Decision Moment `01M3NYFZ1P6QBD2DX4DVDA323W` and the data-model per-WP rule. Pinned in T011; WP04's runtime applies the same rule (SC-007) |

---

## Review Guidance

1. **Red→green on the base.** Check the first commit on the lane: it holds only `test_finalize_requirement_id_grammar.py`. The Activity Log shows (a) and (c) failing on **assertions** at that commit, and passing at the head. (b) is a ratchet pin that cites WP01 T004a as its red-first evidence.
2. **Byte identity on a REAL write.** Repro (a) runs without `--validate-only`, asserts the item list in order, **and** asserts `planning_base_branch`/`branch_strategy` in the same file. Reject a version that proves identity only under `--validate-only`.
3. **No new branch in `finalize_tasks`.** Diff `finalize_tasks` (`:3217`): only the assignment at the gate call and the deleted SC splice. `.venv/bin/ruff check --select C901` reports nothing new, and the `noqa` is unchanged.
4. **The retirement assertion has a positive control.** The re-pinned T013 test asserts the discard warning is absent **and** that `requirement_extraction_warnings` still carries another warning on the same fixture.
5. **Per-ref verdicts proven half by half.** A valid sibling counts while a failing ref fails. A `foreign_qualified` ref never fails. An SC-only WP has refs.
6. **Tidy-first.** The T009 commit changes no existing test and no behaviour.
7. **NFR-002.** All 7 failure keys and every success key are still present with the same types. The three new keys appear on failure, on validate-only success and on real-run success.
8. **Out-of-map edits.** Only the sanctioned ones, each with its rationale in the commit message.
9. **Quality gates.** ruff, the format check, `mypy --strict`, the named arch gates, no `regression` marker left, and no blanket `noqa` or `type: ignore`.

---

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

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-29T06:12:32Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
