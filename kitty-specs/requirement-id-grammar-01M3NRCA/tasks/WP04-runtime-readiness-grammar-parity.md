---
work_package_id: WP04
title: Runtime readiness uses the injected grammar and the shared verdicts
dependencies:
- WP01
- WP02
requirement_refs:
- FR-016
- FR-019
- C-002
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: e531c8646c4d6377ecf20e801c37d3b6868c3b83
created_at: '2026-09-29T11:14:39.904236+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Consumers adopt the grammar
history:
- at: '2026-09-29T06:13:34Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/test_requirement_grammar_parity.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/runtime_bridge.py
- tests/runtime/test_bridge_cores.py
- tests/next/test_runtime_bridge_unit.py
- tests/specify_cli/next/test_runtime_bridge.py
- tests/runtime/test_requirement_grammar_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Runtime readiness uses the injected grammar and the shared verdicts

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

Always invoke tests as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`. `tests/next/test_runtime_bridge_unit.py` holds one `@pytest.mark.performance` test (`test_parse_requirement_refs_completes_under_budget_on_adversarial_input`). `conftest.py` skips it unless `SPEC_KITTY_RUN_PERFORMANCE=1` is set. Do not set that variable.

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

`spec-kitty next` must pass exactly the requirement-mapping fixtures that `finalize-tasks` passes (US6, SC-007). Today the runtime readiness check has its own requirement-ID pattern (`runtime_bridge_cores.py:93`, `FR|NFR|C` only: no `SC`, no letter suffix). It also applies an all-or-nothing rule (`:266-277`): one unknown ref un-maps every valid ref on that WP. After this WP:

1. The cores have **no** requirement-ID pattern, **no** `.upper()` on IDs and **no** default grammar. They receive the grammar by injection through a `RequirementGrammarLike` Protocol. The grammar is `specify_cli/requirement_mapping/grammar.py`, delivered by WP01.
2. `_evaluate_requirement_mapping` applies per-ref verdicts through the injected `classify` (FR-019):
   - `malformed` and `unknown_spec_id` fail;
   - `foreign_qualified` never fails;
   - an accepted ref always counts, whatever its rejected siblings are;
   - a declared SC that no WP references never fails (FR-016, FR-007).
3. `runtime_bridge.py` supplies the grammar through the lazy `specify_cli.requirement_mapping` import it already has. This adds no new layer-ledger key and raises no baseline (C-002). The one-argument delegate `_parse_requirement_refs_from_tasks_md(tasks_content)` keeps its signature.
4. The runtime finding names each failing ref with its reason from the shared vocabulary (`malformed`, `unknown_spec_id`), per `contracts/json-payload-deltas.md` §Runtime.
5. The transitional `src/runtime/next/runtime_bridge_cores.py` entry is removed from `tests/architectural/requirement_id_pattern_allowlist.yaml`, and the recorded baseline is lowered from 3 to 2 in the same edit. The allowlist shrinks by exactly one entry.
6. A parity test (`tests/runtime/test_requirement_grammar_parity.py`) proves that `finalize-tasks --validate-only` and `_check_requirement_mapping_ready` agree on one shared fixture, including the undeclared-`SC-009` positive control and the malformed and foreign refs, with finalize's per-ref reasons read from WP02's `rejected_requirement_refs`.

**Done means:**
- every file in the Validation surface is green;
- `ruff check`, `ruff format --check` and `mypy --strict` report zero findings on the two touched src files;
- the repro was committed RED first and then demoted;
- the tracer notes are in the hand-off's `## Tracer notes` section.

## Context & Constraints

Read these first:
- the charter: `.kittify/charter/charter.md`;
- in `kitty-specs/requirement-id-grammar-01M3NRCA/`:
  - `spec.md`: US6, FR-016, FR-019, C-002, SC-007, and the Edge Cases;
  - `plan.md`: "Behavioural changes by surface" (runtime readiness row), "Test and gate surface" (runtime row) and IC-04;
  - `data-model.md`: Grammar API, RefVerdict and the per-WP rule;
  - `contracts/grammar.md` and `contracts/json-payload-deltas.md` §Runtime;
  - `research.md`: R3 (injection, not a mirror) and R8 (verdict table).

**Seam facts** (verified on `main` `aedb30cddd`). Re-verify the line numbers on your lane base, because WP01 may have shifted neighbours.

| Where | What |
|---|---|
| `runtime_bridge_cores.py:72` | `import re`. It is used ONLY by the `:93` pattern, so remove it once the pattern goes (ruff F401). |
| `runtime_bridge_cores.py:93` | `_REQUIREMENT_REF_PATTERN = re.compile(r"\b(?:FR|NFR|C)-\d+\b", re.IGNORECASE)`: the local second authority. |
| `runtime_bridge_cores.py:174-179` | `_parse_requirement_refs_from_tasks_md(tasks_content)` |
| `runtime_bridge_cores.py:182-202` | `_collect_requirement_refs_for_section(section_content)`: dedup through `dict.fromkeys`. |
| `runtime_bridge_cores.py:205-207` | `_iter_requirement_refs(text)`: `ref_id.upper()` over the local pattern (a C-001 case change). |
| `runtime_bridge_cores.py:221-231` | cores `_is_requirement_heading`. It is NOT the same function as `requirement_mapping`'s `:117`. Do NOT merge the two in this mission. |
| `runtime_bridge_cores.py:240-250` | `RequirementMappingFacts` (frozen dataclass, no defaults today). |
| `runtime_bridge_cores.py:253-299` | `_evaluate_requirement_mapping`, with the all-or-nothing rule at `:265-275`. The message order is missing → unknown → unmapped. |
| `runtime_bridge_cores.py:354` | `_ArtifactPresenceSnapshotLike`: the Protocol idiom to copy. Its members are read-only `@property` getters, so frozen dataclasses satisfy it (see its docstring). |
| `runtime_bridge.py:511-529` | The one-argument delegate. It deliberately calls THIS module's `_parse_wp_sections_from_tasks_md`, so a monkeypatch on `runtime_bridge` takes effect. That behaviour is pinned at `tests/runtime/test_bridge_cores.py:124-142`. |
| `runtime_bridge.py:1022-1098` | `_check_requirement_mapping_ready`. The lazy import is at `:1063-1066`; `spec_ids["all"]` is at `:1070`; the frontmatter reader is at `:1078`; the tasks.md fallback is at `:1080-1086` (only when there is no `wps.yaml`, and only for WPs with empty frontmatter refs); facts are built at `:1091-1097`. |
| `runtime_bridge_io.py:1397` | It consumes `_rb._check_requirement_mapping_ready(planning_dir)` as opaque strings. It needs no change. |

**Boundary facts:**
- `tests/architectural/test_bridge_cores_import_boundary.py` walks the FULL AST of the cores. Any non-stdlib import other than `runtime.next.decision` is flagged, including one inside a function, inside `try`, or under `if TYPE_CHECKING:`. Its self-test at `:173-181` uses `import specify_cli.requirement_mapping` as the planted offender. The cores therefore must not name the grammar module in any form.
- The runtime→`specify_cli` ledger (`tests/architectural/test_layer_rules.py:178-205`) keys on the first-level subpackage. `requirement_mapping` is already admitted (`:195`), so a second `from specify_cli.requirement_mapping import …` statement in `runtime_bridge.py` adds no ledger entry.
- `tests/next/test_runtime_bridge_unit.py:1398-1422` and `tests/specify_cli/test_audit_tail_readers.py:724-739` monkeypatch `specify_cli.requirement_mapping.parse_requirement_ids_from_spec_md` and expect the crash to come out as `"Requirement mapping preflight failed: …"`. Two consequences:
  - keep the `from specify_cli.requirement_mapping import …` attribute-lookup form inside the existing `try`;
  - resolve the grammar inside that same `try`.
- The second file is not owned by this WP. It must stay green without edits.

**C-008 (out of scope):** the two tasks.md fallback readers select lines differently. Finalize reads only `Requirement(s) Refs:` label lines (`mission_parsing.py:96-111`); the runtime also reads a heading plus bullets. Do not reconcile them. Parity fixtures therefore use the label-line form, which both readers accept.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes must merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`
- **Workspace**: run `.venv/bin/spec-kitty agent action implement WP04 --agent claude`. It allocates the lane worktree from `lanes.json` on a base that already contains WP01 and WP02. Never pick a base by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

**Commit sequence (binding):**
1. **T020**: the RED repro, alone.
2. **T021 + T022 + the forced pin updates of T023 + the allowlist removal**: ONE green commit. The injection changes signatures that the pins call, so splitting it would leave a red intermediate commit. Deleting the `:93` pattern also makes the allowlist entry stale, and the C-001 gate fails on a stale entry.
3. **T023 wrap-up**: repro demotion and focused tests.

A campsite refactor is optional. If you make one, it goes in a separate, behaviour-preserving commit BEFORE commit 2, with the existing tests unchanged and green.

### Step 0 – Read the grammar you inject (before T020)

- **Purpose**: WP01 owns the real API. `data-model.md` names it `parse`, `canonical`, `find_all(text, *, spec_scan)`, `tokenize_refs`, `classify(raw, declared) -> Accepted | Rejected(reason)` and `FAILING_REASONS`.
- **Steps**:
  1. Open `src/specify_cli/requirement_mapping/grammar.py` on your lane base and note the exact signatures.
  2. Note which `find_all` mode WP01's `mission_parsing._parse_requirement_refs_from_tasks_md` uses for the tasks.md fallback. The runtime must use the SAME mode, for parity.
  3. Confirm that WP02's finalize (on your base) classifies `read_all_wp_raw_requirement_refs`, the WP01 unified raw reader used by WP02's finalize. The runtime binds to the same reader (T022 step 2).
  4. Confirm the shape of WP02's `rejected_requirement_refs` (`{WP: [{ref, reason}]}`) in `mission_finalize.py`; the parity test reads it.
- **Output**: a 2–3 sentence entry in the hand-off's `## Tracer notes` naming the API you bind to.

### Subtask T020 – RED-FIRST parity repro (US6 / SC-007)

- **Purpose**: Prove, through the pre-existing entry points, that the runtime readiness check disagrees with `finalize-tasks --validate-only` on declared `SC-001` and `FR-006a`.
- **File**: `tests/runtime/test_requirement_grammar_parity.py` (new). This is the FIRST commit of the WP.
- **Markers**: `pytestmark = [pytest.mark.regression, pytest.mark.git_repo]`. The docstring names `#3519` (part 2) and `#2991`, US6, SC-007 and FR-016.
- **Entry points** (production paths only; never call the cores directly in this file):
  - runtime: `from runtime.next.runtime_bridge import _check_requirement_mapping_ready`, called with `feature_dir`. This is the function `runtime_bridge_io.py:1397` calls for `spec-kitty next`.
  - finalize: typer `CliRunner` on `specify_cli.cli.commands.agent.mission.app` with `["finalize-tasks", "--mission", slug, "--json", "--validate-only"]`. Copy the `_run_finalize` pattern from `tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py:153-169`, which patches `locate_project_root` and `run_git_preflight`.
- **Fixture**: build the project once with a local helper modelled on `_scaffold_project` (`tests/next/test_runtime_bridge_unit.py:43-67`). Copy it; do not import it from another test module. `spec.md` declares:
  - `FR-001` and `FR-006a` in the Functional Requirements table;
  - `SC-001` as a template-shaped bold bullet (`- **SC-001**: …`) under `## Success Criteria`.

  Write `tasks/WP01-*.md` and `tasks/WP02-*.md`, plus a `tasks.md` that lists both WPs. Parametrize over two ref sources:
  - **(a) frontmatter**: WP01 `requirement_refs: [FR-001, SC-001]`, WP02 `requirement_refs: [FR-006a]`.
  - **(b) tasks.md fallback**: no `wps.yaml`, empty frontmatter refs, and label lines `Requirement Refs: FR-001, SC-001` / `Requirement Refs: FR-006a` under each WP heading.
- **Assertions**:
  1. **Accepting case**: finalize `--validate-only` succeeds, `_check_requirement_mapping_ready(feature_dir) == []`, and both verdicts are equal.
  2. **Positive control**: on the same fixture, add `SC-009` (undeclared) to WP02's refs. Assert that:
     - finalize fails, and `{"ref": "SC-009", "reason": "unknown_spec_id"}` is in its `rejected_requirement_refs["WP02"]`;
     - the runtime findings are non-empty, and one finding contains both `SC-009` and `unknown_spec_id`;
     - both gates fail.
  3. **Malformed parity** (frontmatter variant): WP01 refs `[FR-001, SC-001, C-007-mission]`. Finalize fails with `{"ref": "C-007-mission", "reason": "malformed"}` in `rejected_requirement_refs["WP01"]`; the runtime fails with a finding naming `C-007-mission (malformed)`; `FR-001` is unmapped in neither gate (the valid sibling counts).
  4. **Foreign parity** (frontmatter variant): WP01 refs `[FR-001, SC-001, other-mission-01KAAAAA#FR-013]`. Both gates pass; finalize reports the citation as `foreign_qualified` in `rejected_requirement_refs`, and the runtime findings are `[]`.
  5. **Foreign-only WP** (frontmatter variant; Decision Moment `01M3NYFZ1P6QBD2DX4DVDA323W`): WP02 refs `[other-mission-01KAAAAA#FR-013]`, with `FR-006a` moved to WP01. Both gates fail on "missing refs" for WP02, and neither lists the citation as a failing reason.

  Each case asserts the same pass/fail verdict from both gates and, for every rejected ref, the same reason. Finalize's reasons come from WP02's `rejected_requirement_refs`, which is on your base.
- **Proving RED on the WP01+WP02 base**:
  1. After commit 1, the lane HEAD is the base plus the test only. Run `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/runtime/test_requirement_grammar_parity.py`.
  2. Expected RED:
     - variant (b) fails, because the cores pattern `:93` cannot see `SC-001` or `FR-006a`. The runtime reports `unmapped FRs: FR-006a` and/or `missing refs`, while finalize accepts;
     - the positive control and the malformed case fail in both variants where the runtime is involved, because today's finding says `unknown refs: …` and carries no reason;
     - the foreign case fails if the runtime's all-or-nothing rule or its reader drops or rejects the citation.
  3. A case that is already green on the base is recorded honestly; do not force it red.
  4. Paste the failing test ids and the key assertion lines into the commit body and the hand-off's `## Tracer notes`.
- **Before writing assertions, check finalize on the base.** Run finalize `--validate-only` once on each fixture. If finalize itself does NOT give the verdict the data-model rule predicts (WP02 is on your base, so it should):
  - STOP and record the fact in the hand-off's `## Tracer notes`;
  - pin the runtime half against the expected verdict from `spec.md` US6 AS1/AS2 and `data-model.md`;
  - report the gap in your hand-off.

  Never edit finalize (WP02-owned) to make parity hold, and never mark anything `xfail`.

### Subtask T021 – Cores injection (`runtime_bridge_cores.py`)

- **Purpose**: Remove the second requirement-ID authority from the stdlib-only cores, and decide per ref.
- **Steps**:
  1. **Protocol.** Next to the requirement-mapping cluster, define `RequirementGrammarLike(Protocol)` in the `_ArtifactPresenceSnapshotLike` idiom:
     - a docstring stating that it is satisfied structurally by `specify_cli.requirement_mapping.grammar` without the cores importing it;
     - read-only `@property` getters for any constant (such as the failing-reason set);
     - methods for what the cores call: a ref finder for tasks.md text, and `classify`.

     Declare only the members the cores use. If a return type is a grammar class (a `RequirementId`, or an `Accepted`/`Rejected` verdict), describe the fields the cores read with a second small Protocol, for example `_RefVerdictLike` with read-only properties. Never import the class.
  2. **Required, no default.** Recommended placement, which keeps signatures sane and complexity low:
     - **Decision tail**: `RequirementMappingFacts` gains `grammar: RequirementGrammarLike` with no default and no `default_factory`, as the plan says ("carried in `RequirementMappingFacts`").
     - **Parse family**: this family has no facts object, so `_parse_requirement_refs_from_tasks_md`, `_collect_requirement_refs_for_section` and `_iter_requirement_refs` each take a required keyword-only `*, grammar: RequirementGrammarLike`.

     Deviate from this placement only with a recorded reason (in the hand-off's `## Tracer notes`) AND a gate test that pins the placement you chose (the no-default test below, adapted to it).
  3. **Delete the local authority.** Remove `_REQUIREMENT_REF_PATTERN` (`:93`), the now-unused `import re` (`:72`) and the `.upper()` in `_iter_requirement_refs`. `_iter_requirement_refs` returns the canonical strings the injected finder yields, in the SAME `find_all` mode that finalize's tasks.md fallback uses (Step 0). Keep the `dict.fromkeys` dedup in `_collect_requirement_refs_for_section`. The existing pins expect `nfr-002` → `NFR-002` and dedup; the grammar's canonical form (kind uppercase) preserves both.
  4. **Per-ref verdicts** replace the all-or-nothing rule (`:265-275`). Extract a small pure helper, for example `_classify_wp_refs(refs, *, grammar, declared) -> tuple[list[str], list[tuple[str, str]]]` (accepted canonical ids, and rejected `(raw, reason)` pairs), so that `_evaluate_requirement_mapping` stays at complexity ≤ 15. For each WP:
     - its accepted ids always feed `mapped_requirement_ids`;
     - its rejected refs whose reason is in the injected failing set are reported;
     - `foreign_qualified` refs are neither reported nor counted.
  5. **Unmapped.** Keep `unmapped = functional_requirement_ids - mapped`. `functional` holds FR ids only, suffixed ones included. A declared SC is never part of the gate, so an unreferenced SC produces no finding.
  6. **"Missing" semantics (Decision Moment `01M3NYFZ1P6QBD2DX4DVDA323W`, shared with WP02).** A WP is *missing* requirement refs when it has **no accepted ref**. A declared SC is an accepted ref, so a WP with only SC refs is not missing (`data-model.md`). A WP whose only refs are `foreign_qualified` citations IS missing: a citation of another mission's ID does not trace this WP to any requirement of this mission. A WP whose refs are all rejected for failing reasons (`malformed`, `unknown_spec_id`) fails for those reasons AND is reported missing.

     This is the same rule WP02's finalize uses. Pin the foreign-only-WP case (missing) and the SC-only case (not missing) in a cores unit test; the parity test (T020 case 5) pins it across both gates.
  7. **Finding text.** Keep the prefix `"Requirement mapping incomplete before finalize-tasks: "`, the bucket order and the `--mission <name> --json` suffix byte-identical. Replace the `unknown refs: WP02: FR-999` bucket with a reason-bearing bucket in the same position, for example `rejected refs: WP02: FR-999 (unknown_spec_id)`. Sort by WP id, then by ref. The FR-010 shared vocabulary forces this change; it is the only intended wording change.
- **Must NOT**:
  - add a default grammar, a fallback pattern or a `try: import …` anywhere in the cores. A default-pattern fallback is a silent second authority (research R3);
  - add any import to the cores beyond stdlib;
  - touch `_is_requirement_heading`, `_requirement_inline_refs_suffix`, `_extract_wp_heading` or the guard/decision clusters.

### Subtask T022 – Supplier (`runtime_bridge.py`)

- **Purpose**: The only caller supplies the grammar through the edge it already has (C-002).
- **Steps**:
  1. **`_check_requirement_mapping_ready` (`:1022-1098`).** Extend the existing lazy import at `:1063-1066` to bring in the grammar module alongside `parse_requirement_ids_from_spec_md` and the reader. It stays inside the same `try`, so an import or resolution failure still becomes `"Requirement mapping preflight failed: …"`. Then:
     - pass the grammar into `RequirementMappingFacts(grammar=…)`;
     - keep `parse_requirement_ids_from_spec_md(spec_content)["all"]` as the declared set (after WP01 it includes SC and suffixed IDs) and `["functional"]` as the gated set.
  2. **The WP ref reader (binding).** The runtime must classify the same token list finalize classifies. Switch `:1078` from `read_all_wp_requirement_refs` to `read_all_wp_raw_requirement_refs`, the WP01 unified raw reader used by WP02's finalize. Otherwise a malformed ref passes the runtime while finalize fails it. No other test monkeypatches either reader (checked: only a docstring mentions it), so the switch is safe.
  3. **The one-argument delegate (`:511-529`).** Keep the signature `_parse_requirement_refs_from_tasks_md(tasks_content: str) -> dict[str, list[str]]`. Resolve the grammar lazily with a function-local `from specify_cli.requirement_mapping import grammar` (same ledger key, no new edge), and pass it as `grammar=` to `_cores._collect_requirement_refs_for_section`. Keep the composition through THIS module's `_parse_wp_sections_from_tasks_md` so the monkeypatch pin at `tests/runtime/test_bridge_cores.py:124-142` stays meaningful.
  4. **Adapter, only if needed.** If the grammar module does not satisfy `RequirementGrammarLike` structurally under `mypy --strict`, for example because an upper-case module constant does not match a `@property`, add a tiny frozen adapter in `runtime_bridge.py` that only binds the grammar's callables and constants. The adapter must hold no pattern, no case change and no logic, and it gets its own focused test in commit 2. Prefer passing the module when mypy accepts it.
- **Must NOT**: add a top-level `specify_cli` import to `runtime_bridge.py`, touch `runtime_bridge_io.py`, or change `_check_bare_prose_requirements_ready`.

### Subtask T023 – Pins, allowlist and wrap-up

- **Pin updates** (in commit 2). Change ONLY what the injection or FR-010 forces:
  - `tests/runtime/test_bridge_cores.py`:
    - `:58-70`: the parse-family existence check keeps its names. `_iter_requirement_refs` still exists with a new signature; adjust only if you renamed a helper.
    - `:118-120`: the cores call now passes `grammar=`. Pass the REAL grammar module, `from specify_cli.requirement_mapping import grammar`, so the pin exercises the single authority. Test modules are not bound by the cores boundary gate.
    - `:150-222`: every `RequirementMappingFacts(...)` gains `grammar=`. At `:175` and `:181`, the `unknown refs` substring becomes the new reason-bearing bucket. Keep every other assertion unchanged: the missing/unmapped strings, the order, the `--mission … --json` suffix, and both #3394 negative-space pins returning `[]`.
  - `tests/next/test_runtime_bridge_unit.py:715-748` and `tests/specify_cli/next/test_runtime_bridge.py:260-288` call the one-argument delegate. They should pass UNCHANGED, because the delegate kept its signature and canonical output. If one needs an edit, explain why in the commit body.
  - Keep the live-lookup pin (`tests/runtime/test_bridge_cores.py:124-142`) unchanged.
- **New focused cores tests** (commit 2, in `tests/runtime/test_bridge_cores.py`, pure and in-memory with the real grammar unless noted). Each refusal is paired with a same-fixture positive control:
  - Per-ref verdict (FR-019): WP refs `("FR-001", "FR-999")` with `FR-001` declared. The finding lists `FR-999 (unknown_spec_id)` and does NOT list `FR-001` as unmapped; the valid sibling counts.
  - A malformed sibling: `("FR-001", "C-007-mission")` gives a `malformed` finding, and `FR-001` still counts.
  - A foreign sibling: `("FR-001", "other-mission-01KAAAAA#FR-013")` gives `[]`, while the same WP with an undeclared bare `FR-013` fails.
  - An unreferenced declared SC gives `[]`, while an unmapped FR on the same facts fails.
  - Uppercase-suffix tolerance (US2 AS4): the ref `FR-006A` matches the declared `FR-006a` and gives `[]`.
  - The foreign-only-WP "missing" rule from T021 step 6.
  - Injection is load-bearing: a stub grammar whose `classify` rejects everything as `unknown_spec_id` makes a normally clean facts bundle fail. This proves the verdict flows only through the injected object, with no hidden local rule.
  - No default: assert that for the `grammar` field in `dataclasses.fields(cores.RequirementMappingFacts)`, both `default` and `default_factory` are `dataclasses.MISSING`. If you chose kw-only args, assert that `inspect.signature` of each parse-family function has a `grammar` parameter with no default.
  - The tasks.md parse family, with the real grammar: `Requirement Refs: SC-001, FR-006a, fr-002` yields `["SC-001", "FR-006a", "FR-002"]`.
- **Allowlist** (commit 2, **sanctioned out-of-map edit**): in `tests/architectural/requirement_id_pattern_allowlist.yaml`, remove exactly the `src/runtime/next/runtime_bridge_cores.py` entry AND lower the recorded baseline from 3 to 2, in the same edit. That file is owned by WP01. Rationale: "shrink-only ratchet: the transitional entry this WP retires". Touch nothing else in that file. The C-001 gate (`test_requirement_id_grammar_single_source.py`) checks the count two-sided, so it must then pass with the cores containing no requirement-ID literal, the entry gone and the baseline at 2 (the two frozen entries remain).
- **Demote the repro** (commit 3):
  - remove `pytest.mark.regression` from `tests/runtime/test_requirement_grammar_parity.py` (keep `git_repo`);
  - rewrite the docstring as the standing SC-007 parity test that keeps the issue references;
  - keep both variants and the positive control.

  After this commit, no test in this WP is marked `regression`.
- **Run** the full Validation surface and record each command with its passed/failed/skipped counts in the Activity Log and the hand-off.
- **Changelog notes (NFR-002).** `docs/changelog/CHANGELOG.md` is written by the orchestrator at closeout; this WP does not edit it. Put one line in a `## Changelog notes` section of your hand-off for the runtime finding-wording change, for example: *"`spec-kitty next` requirement-mapping finding: the `unknown refs: WP: ref` bucket is replaced, in the same position, by `rejected refs: WP: ref (<reason>)` naming the shared reason (`malformed` or `unknown_spec_id`); a `foreign_qualified` ref is no longer reported, and a valid ref beside a rejected sibling now counts (FR-010, FR-016, FR-019)."*
- **Tracer notes** (1–3 dated sentences each, in the `## Tracer notes` section of your hand-off):
  - approach: the Step-0 API binding, and the RED evidence;
  - design decisions: field vs argument placement, the reader switch, the "missing" rule, the finding wording;
  - tooling friction: anything that slowed you, such as a finalize-on-base surprise or mypy friction with module-as-Protocol.

## Validation surface

Run only these, as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.

**Test files:**
- `tests/runtime/test_requirement_grammar_parity.py`
- `tests/runtime/test_bridge_cores.py`
- `tests/next/test_runtime_bridge_unit.py`
- `tests/specify_cli/next/test_runtime_bridge.py`
- `tests/next/test_runtime_bridge_blocked_paths.py`

**Not owned, but must stay green without edits** (monkeypatch contract on the lazy import):
- `tests/specify_cli/test_audit_tail_readers.py`

**Named architectural gates** (by file name only):
- `tests/architectural/test_bridge_cores_import_boundary.py`
- `tests/architectural/test_layer_rules.py`
- `tests/architectural/test_ratchet_baselines.py`
- `tests/architectural/test_runtime_charter_doctrine_boundary.py`
- `tests/architectural/test_requirement_id_grammar_single_source.py`

**Static checks** (zero findings):
- `.venv/bin/ruff check src/runtime/next/runtime_bridge_cores.py src/runtime/next/runtime_bridge.py tests/runtime/test_requirement_grammar_parity.py tests/runtime/test_bridge_cores.py`
- `.venv/bin/ruff format --check src/runtime/next/runtime_bridge_cores.py src/runtime/next/runtime_bridge.py tests/runtime/test_requirement_grammar_parity.py tests/runtime/test_bridge_cores.py tests/next/test_runtime_bridge_unit.py tests/specify_cli/next/test_runtime_bridge.py`
- `.venv/bin/mypy --strict src/runtime/next/runtime_bridge_cores.py src/runtime/next/runtime_bridge.py`

**Baseline-red gotcha:** a failure that is also red on the lane base (before your commit 1) is not yours. Classify it per CLAUDE.md, report it in the hand-off, and do not fix or hide it.

## Test Strategy

- **ATDD / red-first** (ADR 2026-07-17-1, charter C-011): T020 is the issue-pinned `regression` repro through the production entry points, committed alone and shown RED. Commit 2 turns it green, and commit 3 demotes it.
- **Non-vacuity**:
  - every refusal assertion has a same-fixture positive control;
  - the compound fix is proven half by half: the parity test proves grammar injection (SC and suffix visibility) and cross-gate agreement on malformed, unknown and foreign refs, and the cores unit tests prove the per-ref verdicts (sibling counts, foreign never fails);
  - the stub-grammar test proves the injection is the only decision source.
- **Sonar**:
  - every new helper (`_classify_wp_refs`, and the adapter if you add one) is tested in the same commit;
  - hoist any literal used 3+ times, such as a reason label or the bucket prefix, to a module constant;
  - complexity ≤ 15 everywhere; check it with `.venv/bin/ruff check --select C901`.
- **Typing**: `mypy --strict` is part of the gate. A passing test run does not replace it.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| A default grammar or fallback pattern becomes a silent second authority | Forbidden outright. The no-default test pins it. The C-001 gate plus the allowlist removal prove that no literal remains in the cores. |
| A layer-ledger edge or ratchet baseline grows (C-002) | Use only the admitted `specify_cli.requirement_mapping` key. Run `test_layer_rules.py` and `test_ratchet_baselines.py`. Never edit `_baselines.yaml` or the ledger. |
| The cores gain a grammar import, even under `TYPE_CHECKING` | The boundary gate walks the full AST. Use structural Protocols only. |
| Tests call the one-argument delegate directly | The signature is unchanged; the grammar is resolved lazily inside it. The pins at `test_runtime_bridge_unit.py:715-748` and `test_runtime_bridge.py:260-288` run unchanged. |
| The monkeypatched `parse_requirement_ids_from_spec_md` crash stops folding into the generic message | Keep the attribute-lookup import and the grammar resolution inside the existing `try`. `test_audit_tail_readers.py` guards this. |
| Parity holds only vacuously | WP02 is on this lane's base, so the parity test asserts per-ref reasons from `rejected_requirement_refs` for malformed, unknown and foreign refs, not only pass/fail. WP06 T038 adds the three-gate check (with map-requirements) after all lanes merge. |
| The runtime reader silently drops malformed refs while finalize fails them | Both gates read the WP01 unified raw reader (T022 step 2); the malformed parity case pins it. |
| The "missing" rule for a foreign-only WP diverges from WP02 | DM `01M3NYFZ1P6QBD2DX4DVDA323W`; pinned in the cores unit tests and in parity case 5. |

## Review Guidance

- The cores contain **no** default grammar anywhere: no default on the field or on any argument, no fallback pattern, no `import re`, no `.upper()`, and no non-stdlib import. `test_bridge_cores_import_boundary.py` is green.
- `git diff` of `tests/architectural/requirement_id_pattern_allowlist.yaml` removes exactly one line group, the `runtime_bridge_cores.py` entry, and changes the baseline from 3 to 2. `test_requirement_id_grammar_single_source.py` is green.
- On the shared fixture, parity holds in both ref-source variants, including the undeclared `SC-009` positive control, whose runtime finding carries `unknown_spec_id`; the malformed, foreign and foreign-only cases give the same verdict and reason in both gates.
- A valid ref counts even beside a failing sibling; `foreign_qualified` never fails; an unreferenced declared SC never fails.
- The one-argument delegate's signature is unchanged, and the live-lookup pin is untouched.
- Commit 1 is the RED repro alone, with evidence in its body. No test is left marked `regression`.
- `mypy --strict` and ruff (lint and format) are clean on both src files, and every function is at complexity ≤ 15.
- No new ledger entry and no baseline change. The two `_is_requirement_heading` helpers were not merged.

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

- 2026-09-29T06:13:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP04 --to <status>` to change WP status.
