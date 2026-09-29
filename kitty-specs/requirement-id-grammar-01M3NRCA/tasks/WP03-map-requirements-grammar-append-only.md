---
work_package_id: WP03
title: map-requirements accepts the grammar, is append-only, explains refusals
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-010
- FR-012
- FR-019
- NFR-002
- NFR-005
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: 463c3566d56f784279cf3ac032a7068482c45b92
created_at: '2026-09-29T09:59:16.571386+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
phase: Phase 2 - Grammar consumers
history:
- at: '2026-09-29T06:12:58Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/tasks_map_requirements.py
- src/specify_cli/cli/commands/agent/tasks_mapping_core.py
- tests/specify_cli/test_cli/test_map_requirements.py
- tests/specify_cli/cli/commands/agent/test_tasks_map_requirements_seam.py
- tests/specify_cli/cli/commands/agent/test_tasks_mapping_core.py
- tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/json/byte_contracts.json
- tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – map-requirements accepts the grammar, is append-only, explains refusals

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show python-pedro` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⛔ HARD RULE: no heavy suites

Never run any of these:
- the whole `tests/architectural/` directory;
- e2e or full-integration suites;
- performance, stress or timing suites;
- `make test-full`;
- whole-repo `pytest`.

Run ONLY:
- the test files named in `## Validation surface`;
- the owning module's fast tier;
- the architectural gate files named there, by file name.

Use `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`. This is charter constraint C-007 and internal doctrine `NO_FULL_HEAVY_SUITES_IN_MISSION`. If a run starts collecting thousands of tests, stop it; you have typed the wrong path.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status`) or the Activity Log below.
- **Address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress:** as you address each item, update the Activity Log with what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``. Use language identifiers in code blocks.

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

`map-requirements` becomes a consumer of the WP01 grammar and stops destroying authored data. When this WP is done:

1. **No erasure (FR-005, #2991).** Mapping new refs onto a WP keeps every existing `requirement_refs` item byte-identical, in its original position. New refs are appended in canonical form and deduplicated by canonical form. An existing `FR-006A` item absorbs a new `FR-006a`, and the stored `FR-006A` is left as written.
2. **Grammar input (FR-006, #3519 part 2).** `--refs SC-001,FR-006a` (and `--batch`) is accepted when the spec declares both IDs. Each ref is written in canonical form: uppercase kind, verbatim digits, lowercase suffix. An undeclared `SC-009` is refused as `unknown_spec_id` on the same fixture; that is the positive control.
3. **One reason vocabulary (FR-010, FR-019).** Every unusable ref carries exactly one reason: `malformed`, `unknown_spec_id` or `foreign_qualified`. `malformed` and `unknown_spec_id` block. `foreign_qualified` (`<mission-slug>#<ID>`) never blocks.
4. **Refusals explain themselves (FR-012).** The pre-write malformed refusal lists `parsed_spec_ids` and a hint that names the grammar. One hint constant replaces the three copies of the `FR-NNN` rule text.
5. **Contracts moved deliberately (NFR-002).** Exactly two `byte_contracts.json` entries are re-pinned, each with a one-line justification. Every other byte contract, `map_requirements_success` included, stays byte-identical.
6. **Red-first proof (NFR-005, defect (b)).** Two issue-pinned repros land RED in the first commit and GREEN after the fix. Both are demoted to focused tests before handoff.

## Context & Constraints

**Read first:**
- `kitty-specs/requirement-id-grammar-01M3NRCA/spec.md`: US1 scenario 3, US2 scenario 2, US3, FR-005/006/010/012/019, NFR-002, NFR-005.
- `plan.md`: "Behavioural changes by surface" (the three map-requirements rows) and IC-03.
- `data-model.md`: the `RefVerdict` table and the per-WP rule.
- `contracts/grammar.md`.
- `contracts/json-payload-deltas.md` § map-requirements. This is the payload contract you implement.
- `research.md` R8 and R9 (operator rulings, Decision Moments `01M3NSKBMEKR60XKRJSYQC41G3` and `01M3NSKHE8T6TBKNFPSJ6BRD2G`).

**Dependency: WP01.**
- Your lane stacks on WP01. Before writing code, read `src/specify_cli/requirement_mapping/grammar.py` and `__init__.py` as they landed.
- This prompt uses the API names from `data-model.md`: `parse`, `canonical`, `classify`, `Accepted`/`Rejected`, `FAILING_REASONS`, `tokenize_refs`, the reason constants `MALFORMED` / `UNKNOWN_SPEC_ID` / `FOREIGN_QUALIFIED`, and `RULE_TEXT`.
- WP01 only rewired `validate_ref_format`, `validate_refs` and `classify_stale_refs` to canonical membership. It added NO `foreign_qualified` bucket: that bucket is yours (T018), and so is the removal of those three helpers (see the out-of-map edits).
- If WP01 landed different names or signatures (for example, what `classify`'s `declared` argument expects), use the landed API and do not invent a parallel one.
- Never compile a requirement-ID regex, and never call `.upper()`/`.lower()` on a requirement ID, in the two owned source files. C-001 applies, and `tests/architectural/test_requirement_id_grammar_single_source.py` enforces it.
- `.upper()` on WP IDs (`wp_id.upper()`, `st.wp.upper()`) is not a requirement ID. Leave it alone.

**Seam facts (verified on `main` `aedb30cddd`; re-locate after WP01's rebase, because the line numbers drift):**

| Seam | Location | Today |
|---|---|---|
| Batch input | `tasks_map_requirements.py:228` | `[ref.upper() for ref in ref_list]` |
| Individual input | `tasks_map_requirements.py:238-239` | comma-split + strip, then `.upper()` |
| Merge base read | `_mr_plan`, `:362,368` | `read_all_wp_requirement_refs`: the NORMALISED reader. It drops SC/suffixed/foreign items and respells the rest. This is the erasure. |
| Merge | `tasks_mapping_core.py:109-128` `_merge_refs` | `sorted(set(base) \| set(new))` |
| Pre-write offenders | `tasks_mapping_core.py:140-146` | `validate_ref_format` + `validate_refs`. A malformed ref lands in BOTH buckets. |
| Pre-write refusal | `_mr_gate_offenders:401-438` | hint literal `:415` `"Refs must match FR-NNN, NFR-NNN, or C-NNN format"` |
| Write | `_mr_write_frontmatter:464-475` | `wp_meta.update(requirement_refs=to_write[wp])`, then `write_frontmatter` |
| Stale gate | `_mr_stale_gate:501-563` | re-uppercase `:522`; `classify_stale_refs` `:538`; hint `:545-551`; console rule text `:558` |
| Success output | `_mr_emit_output:608-660` | `mapped` / `total_mappings` sorted; coverage from `plan.unmapped_fr` |

**Ordering invariant (do not break).** `_do_map_requirements` runs validate → resolve → plan → gate → write → stale gate → commit → emit. The frontmatter write precedes the post-write stale gate, so a stale ref on ANY WP refuses with exit 1 while the write is already on disk. This is the pinned partial-write-on-refusal behaviour (NFR-001 of the earlier tasks-py degod mission). Keep it.

**Seam bridge (do not break).** Phase helpers reach patched symbols through `from specify_cli.cli.commands.agent import tasks as _tasks` and `_tasks.<attr>`. `_mr_plan` must keep calling `_tasks.plan_mapping(...)`, which `test_tasks_map_requirements_seam.py:226` intercepts. New helpers you add are NOT tasks-namespace seams. Call them directly.

**Allowed out-of-map edits (each only if needed):**
- `tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py`, comment only (`:119`, `:173`). The comment says `FR-002a` is "malformed per the FR-NNN format rule", which becomes false. Rationale: stale prose next to a re-pinned fixture. Do not change any code there.
- **Parallel-lane hunk (D4).** A parallel lane also edits `src/specify_cli/requirement_mapping/__init__.py` in a distant hunk (WP02 removes `find_discarded_sc_refs` near `:194-214`; your helper removal is near `:389-450`); keep your hunk minimal and do not reformat the file. The multi-dependency lane merge fails closed on a conflict.
- Helper removal (unconditional). WP03 owns the `foreign_qualified` bucket and the deletion or replacement of `validate_ref_format`, `validate_refs` and `classify_stale_refs`: their only product callers are `tasks_map_requirements.py:512-538` and `tasks_mapping_core.py:43-44,141-142`, both WP03-owned, and T018 replaces those calls with `grammar.classify`. Delete the three functions and their re-exports from `src/specify_cli/requirement_mapping/` (`__init__` and, if present, `grammar`), plus their now-orphaned unit tests in `tests/specify_cli/test_requirement_mapping.py`. Rationale: leaving them breaches the dead-symbol gate and C-001's single-authority intent.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`
- The execution worktree comes from `lanes.json`, via `.venv/bin/spec-kitty agent action implement WP03 --agent claude`. Never choose a base by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually.

## Subtasks & Detailed Guidance

### Subtask T015 – RED-FIRST repros (FIRST commit, test only)

- **Purpose:** prove the two defects exist on the WP01-merged base, through the real entry point, before any fix (NFR-005, charter C-011, ADR 2026-07-17-1).
- **File:** create `tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py`, with `pytestmark = [pytest.mark.unit, pytest.mark.fast]` and `@pytest.mark.regression` on each repro.
- **Harness:** copy the fixture style of `tests/specify_cli/test_cli/test_map_requirements.py:21-70`:
  - the same `@patch` triple on `...agent.tasks.locate_project_root`, `_find_mission_slug` and `_ensure_target_branch_checked_out`;
  - the autouse env fixture (`SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`);
  - `CliRunner().invoke(tasks_app, ["map-requirements", ...])`;
  - read back with `specify_cli.frontmatter.read_frontmatter`.
- **Fixture spec:** declare all of `FR-001`, `FR-002`, `FR-006a`, `NFR-001` and `SC-001` in declared shapes. Use a table for the FRs and `- **SC-001**: …` for the success criterion; that is the template shape, and WP01 makes it declared. Seed the WP files with raw YAML text, so the on-disk bytes are exactly what you wrote.

**Repro (a) `#2991` — map-requirements erases authored refs.**
1. Seed WP01 with `requirement_refs: ["SC-001", "FR-006A"]`. `FR-006A` is included on purpose: it makes the repro RED however WP01 shaped the normalising reader. It either drops SC, or respells `FR-006A` → `FR-006a`, or re-sorts.
2. Invoke `map-requirements --wp WP01 --refs FR-002 --json`.
3. Assert, **in this order**:
   - the on-disk list `== ["SC-001", "FR-006A", "FR-002"]`, i.e. the existing items byte-identical and in place, then the new ref appended;
   - then `exit_code == 0`.

   Asserting the disk first makes the RED failure message show the erasure, not an incidental exit code. The write precedes the stale gate, so the disk state is observable even when the command exits 1.
4. Docstring: `#2991: map-requirements must never erase or respell an authored ref (FR-005).`

**Repro (b) `#3519` — SC and suffixed input refused.**
1. Seed WP02 with `requirement_refs: []`.
2. Invoke `map-requirements --wp WP02 --refs SC-001,FR-006a --json`.
3. Assert:
   - `exit_code == 0`;
   - the on-disk list `== ["SC-001", "FR-006a"]` (canonical, input order);
   - `payload["result"] == "success"`.
4. Docstring: `#3519 part 2: declared SC and letter-suffixed IDs are accepted in canonical form (FR-006).`
5. On pre-WP01 `main` this is refused as malformed. On the WP01 base it is refused as unknown, because `.upper()` yields `FR-006A`, which does not equal the declared `FR-006a`; or it is written uppercased. Every variant is RED.

**How to prove RED.**
1. In the lane worktree, commit ONLY the new test file.
2. Run `PWHEADLESS=1 .venv/bin/python -m pytest -q -m regression tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py`. If the worktree has no `.venv`, use the repo-root `.venv/bin/python` with `PYTHONPATH=<worktree>/src`, so the worktree's code is under test, not the root checkout's.
3. Expect `2 failed`. Paste the two assertion lines into the commit message body and the Activity Log.
4. A repro that is GREEN here is vacuous. Stop and re-derive it; never weaken the assertion to get RED.
5. Commit message: `test(map-requirements): red-first repros for #2991 and #3519 (WP03 T015)`.

### Subtask T016 – Canonical input (FR-006, FR-002)

- **Steps:**
  1. Add one small module-level helper in `tasks_map_requirements.py`, e.g. `_canonical_input_refs(refs: list[str]) -> list[str]`. It returns `grammar.canonical(ref) or ref` for each ref, in input order.
  2. A token `canonical()` rejects is passed through **verbatim**, so the pre-write gate reports exactly what the author typed. Never uppercase it. `bogus` stays `bogus`, and `FR_001` stays `FR_001`.
  3. Use the helper at both sites: batch (`:228`) and individual (`:239`, after the existing strip/split, which is unchanged).
  4. Do not add stripping to the batch arm. That would widen behaviour and is out of scope.
- **Tests (same commit):** focused unit tests of the helper:
  - `fr-006A` → `FR-006a`;
  - `sc-001` → `SC-001`;
  - `other-mission-01KAAAAA#fr-013` → the canonical qualified form WP01 renders;
  - `FR_001` → `FR_001`;
  - `C-007-mission` → unchanged.
- **Notes:** `MappingRequest.new_mappings`'s comment ("already upper-cased by the shell", core `:64-66`) becomes "already canonicalised by the shell (malformed tokens verbatim)". Update it.

### Subtask T017 – Append-only merge (FR-005, operator ruling DM `01M3NSKHE8T6TBKNFPSJ6BRD2G`)

**1. Merge base = raw stored items.**
- In `_mr_plan` (`:362,368`), replace `read_all_wp_requirement_refs` with `read_all_wp_raw_requirement_refs`, the WP01 unified raw reader (the same one WP02's finalize and WP04's runtime classify). It is backed by `grammar.tokenize_refs`.
- For the canonical frontmatter shape, a YAML list of single-ID strings, the tokens ARE the items, byte for byte.
- Two edges need a pinning test each, plus a one-line entry in the `## Tracer notes` section of your hand-off:
  - **Legacy scalar string, or one item holding `"FR-001, FR-002"`.** The typed WP model already splits a scalar string into list items (`status/wp_metadata.py:333-336`), so a list of tokens is the only item form that can reach disk. State this as the defined behaviour.
  - **Synthetic `<NON_STRING:…>` tokens** from the raw reader. They must NEVER be written to disk as strings. Pin what happens today for a WP carrying a non-string item: the typed read in `_mr_write_frontmatter` fails before writing. Keep that behaviour, and assert the file is unchanged.

**2. `_merge_refs` (core `:109-128`) becomes append-only.** Keep it pure; this sketch shows the contract, not a mandatory shape:

```python
def _merge_refs(*, new_refs, existing, tasks_md_fallback, replace) -> list[str]:
    if replace:                             # analysis B7: keep the stored spelling on a canonical match
        return _replace_preserving_spelling(existing, new_refs)
    base = list(existing) or list(tasks_md_fallback)
    merged = list(base)                       # existing items: kept, in order, byte-identical,
    seen = {_dedup_key(item) for item in base}  # including any pre-existing duplicates
    for ref in new_refs:                      # new refs arrive canonical (T016)
        key = _dedup_key(ref)
        if key not in seen:
            seen.add(key)
            merged.append(ref)
    return merged

def _dedup_key(item: str) -> str:
    return grammar.canonical(item) or item   # FR-006A and FR-006a share a key
```

- Existing items are never deduplicated among themselves, never respelled and never reordered. "Never erase" includes an author's own duplicate.
- `--replace` (analysis B7 ruling): it overwrites with the new ref set, deduplicated by `_dedup_key` and sorted as today, BUT when a new ref's canonical form matches a stored item, the stored item's spelling is written (for example a stored `FR-006A` stays `FR-006A`). So `--replace` never respells, and `replaced_refs_removed` lists exactly what vanished. Implement `_replace_preserving_spelling(existing, new_refs)` as a small tested helper. Record this in the `_merge_refs` docstring. Replace is the operator's explicit request to rewrite, and it is the documented recovery path for a stale ref.
- **`--replace` reports what it removed (FR-005, pinned name `replaced_refs_removed`).** `--replace` is the explicit, operator-invoked overwrite, so it must not erase silently. Compute, per replaced WP, the stored raw items (from the raw reader, before the write) that are absent from the written list, compared by `_dedup_key`, in their original on-disk order. Add them to the success payload as `replaced_refs_removed: {WP: [item, …]}` (an empty list when nothing was dropped), **only** when `--replace` was passed, so the default-mode `map_requirements_success` byte contract does not move (`contracts/json-payload-deltas.md` § map-requirements). Keep the computation in a small pure helper (e.g. `_replaced_items_removed(existing, written) -> list[str]`) with focused tests. The human leg prints one `Removed by --replace: WP: a, b` line per non-empty WP.
- The tasks.md fallback (used only when the frontmatter list is empty) seeds the base in its parsed order, and new refs append after it.

**3. Coverage projection (FR-019).** `plan_mapping` projects `{**existing_all_refs, **to_write}` into `compute_coverage` (core `:158-159`). Raw items now reach it. Project only **accepted** refs, as canonical strings, using `grammar.classify` against `spec_all_ids`. Then:
- a foreign `slug#FR-001` or an unknown ref can never cover a declared FR;
- a valid sibling on the same WP always counts.

Extract this as a small pure helper with its own tests.

**4. Update the core module docstring and the `_merge_refs` docstring.** They currently say "sorted(set(...)) exactly as the live loop". Replace that with the append-only contract and cite FR-005 and the Decision Moment.

**5. Existing tests that pin the old order.** Re-pin each one with a one-line comment "FR-005 append-only: order preserved (was sorted)":
- `test_map_requirements.py::test_seeds_from_tasks_md_on_first_migration` (`:430-457`): fallback `FR-002`, then new `FR-001`, now gives `["FR-002", "FR-001"]`.
- The union tests in `test_tasks_mapping_core.py:66-116` keep their expected values. Check each one.
- `test_to_write_values_sorted_and_deduped` (`:119`) uses `replace=True`, so it stays green unchanged. That is your proof that `--replace` is unchanged.

**Parallel?** No. T017 depends on T016, because new refs must arrive canonical.

### Subtask T018 – Reasons and diagnostics (FR-010, FR-012, FR-019)

**1. One hint constant (Sonar S1192).**
- The `FR-NNN, NFR-NNN, or C-NNN` rule text appears at the pre-write hint (`:415`), the stale JSON hint (`:545-551`) and the stale console line (`:558`).
- Define ONE module constant in `tasks_map_requirements.py`, e.g. `_REQUIREMENT_ID_GRAMMAR_HINT`, with the wording from `contracts/json-payload-deltas.md`, composed from `grammar.RULE_TEXT` (never restate the rule). Suggested:
  `f"Requirement IDs must match {grammar.RULE_TEXT} with kind FR, NFR, C or SC (e.g. FR-003, FR-003a, SC-001); cite another mission's ID as <mission-slug>#<ID>."`
- All three sites derive from the constant. The stale hint is the constant plus the reason explanation plus the `--replace` example.
- Make sure the constant's text is not a regex literal the C-001 gate would flag. Run the gate.

**2. Pre-write gate (`_mr_gate_offenders`).**
- Compute the offenders in `plan_mapping` (core `:140-146`) with `grammar.classify` per new ref, replacing `validate_ref_format` + `validate_refs`:
  - `malformed` → `offenders.malformed`, raw input spelling;
  - `unknown_spec_id` → `offenders.unknown_spec_id`, canonical;
  - `foreign_qualified` → **neither**. It never blocks, and it is appended like any accepted ref.
- Each ref lands in exactly one bucket (FR-010). The old double-listing of a malformed ref in the unknown bucket is retired.
- Update `MappingOffenders`' docstring.
- Malformed arm payload, in this key order:
  `{"error": "Invalid requirement ref format", "malformed_refs": [...], "parsed_spec_ids": sorted(st.all_spec_ids), "hint": _REQUIREMENT_ID_GRAMMAR_HINT}`.
  `parsed_spec_ids` is a flat sorted list, exactly as on the stale gate.
- The human (non-JSON) leg also prints the hint and a `Parsed spec IDs: …` line.
- Share one tiny helper for `sorted(st.all_spec_ids)` between both gates.
- The unknown arm stays **byte-identical**. Its hint already lists the declared IDs, and the `map_requirements_unknown_spec_ref_error` contract must not move.

**3. Stale gate (`_mr_stale_gate`).**
- Replace the `:522` re-uppercase, `validate_ref_format`/`validate_refs` and `classify_stale_refs` with `grammar.classify` over every raw token on every WP. `<…>` placeholder tokens classify as `malformed`.
- Extract a pure helper, e.g. `_mr_classify_wp_refs(all_wp_raw, declared) -> dict[wp_id, dict[reason, list[str]]]`, with focused tests. This keeps `_mr_stale_gate` at complexity ≤ 15.
- Verdict table: the gate refuses (exit 1) **iff** any rejected ref's reason is in `FAILING_REASONS`. A WP set whose only rejected refs are `foreign_qualified` passes the stale gate silently. Do not add a success-payload key for it; that is not in the contract.
- When the gate refuses, the payload keeps every existing key, in the same order:
  - `stale_refs[wp]`: every rejected raw token on that WP (all three reasons), sorted, as today;
  - `stale_ref_reasons[wp]`: the exact partition of `stale_refs[wp]` into `{"malformed": [...], "unknown_spec_id": [...], "foreign_qualified": [...]}`, in that key order, each sorted. Every WP present gets all three keys.

  This preserves today's invariant that each offending token is in exactly one bucket. The bucket keys come from `grammar.MALFORMED` / `UNKNOWN_SPEC_ID` / `FOREIGN_QUALIFIED`. Record it in your hand-off's `## Tracer notes`: the contract names the new bucket but not whether `stale_refs` lists foreign refs, so this is the interpretation chosen.
- Kept rejected refs on the mapped WP are now reported. Because T017 no longer erases, a malformed or undeclared item already on the WP you map now survives, and the post-write stale gate reports it and exits 1. Previously the normalising read silently deleted it. This is the intended fix ("reported, not erased"). The recovery is `--replace`, which the hint names. Pin it with a focused test (see T019) and call it out in the PR.
- Console leg: keep the per-WP lines and the `Parsed spec IDs` line, and replace `:558` with the constant.

**3b. Success output (`_mr_emit_output`, `:609-618`, C1).** `total_mappings` reads `read_all_wp_requirement_refs`, the normalising reader, which silently drops a malformed ref from the coverage view. Switch it to `read_all_wp_raw_requirement_refs` (the WP01 unified raw reader) plus `grammar.classify` against `st.all_spec_ids`, through the same pure helper as T017 step 3 or `_mr_classify_wp_refs`. `total_mappings[wp]` lists that WP's **accepted** refs as canonical strings, sorted, exactly as today for plain declared refs, so the `map_requirements_success` byte contract does not move. A rejected ref is never silently dropped: on a failing reason the stale gate has already refused, and a `foreign_qualified` ref is not counted as this mission's mapping. After this edit `_mr_plan` and `_mr_emit_output` no longer import `read_all_wp_requirement_refs`; if nothing else in `src` imports it, record that in `## Tracer notes` (it is WP01's to keep or retire at closeout). Add a focused test: a WP carrying `[FR-001, other-mission-01KAAAAA#FR-013]` shows `total_mappings["WP01"] == ["FR-001"]`; positive control, a plain `[FR-001, FR-002]` WP shows both.

**4. Existing tests to re-pin, with a one-line reason each:**
- `test_map_requirements.py::test_reports_stale_invalid_refs` (`:501-534`): `"FR-NNN" in payload["hint"]` becomes an assertion on the new grammar wording, and the WP02 reasons gain `"foreign_qualified": []`.
- `test_map_requirements.py::test_stale_refs_classify_format_vs_unknown` (`:539-570`): `FR-003a` is now well-formed. The spec there declares only FR-001..003 and NFR-001, so it becomes `unknown_spec_id`. Replace the malformed half with a genuinely malformed token (`FR_003`), so the test still proves both buckets. Update its #2066 docstring.
- `test_tasks_mapping_core.py`:
  - `test_malformed_offender_detected` (`:163`): `FR-1A` is now well-formed. Use `FR_1`, and assert unknown `== ()` (exactly one reason).
  - `test_both_offender_buckets_populated` (`:184`): malformed `("FR_1",)`, unknown `("FR-999",)`.
  - `test_offenders_preserve_input_order_and_case_folding` (`:195`): malformed is now the raw `"bogus"`, never `"BOGUS"`. Rename the test to drop "case_folding".

### Subtask T019 – Contracts and wrap-up (NFR-002)

**1. Re-pin `byte_contracts.json`, by hand, key by key.**
- Never blind-refreeze from actual stdout. Derive every expected value from the contract, then run `test_tasks_json_bytes.py` to confirm.
- The fixture spec declares only `FR-001`, `FR-002` (`test_tasks_json_bytes.py:70-79`).

**a. `map_requirements_malformed_ref_error` (`:91-105`).**
- `FR-001a` is no longer malformed: it is well-formed and undeclared, so it would now hit the *unknown* arm. Change `argv`'s `--refs` value to `FR_001`, a genuinely malformed token.
- Re-pin `expected_stdout` to:
  `{"error": "Invalid requirement ref format", "malformed_refs": ["FR_001"], "parsed_spec_ids": ["FR-001", "FR-002"], "hint": "<the constant>"}` + `\n`.
- Changelog note: *"map-requirements malformed-ref refusal: fixture input `FR-001a` → `FR_001` (a letter suffix is now valid grammar); refusal adds `parsed_spec_ids`; the hint names the grammar; malformed tokens are reported as typed, no longer uppercased."*

**b. `map_requirements_stale_frontmatter_error` (`:123-137`).**
- Same argv. `FR-002a` on WP02 is undeclared, so it moves from `malformed` to `unknown_spec_id` and still blocks.
- Re-pin `stale_ref_reasons` to `{"WP02": {"malformed": [], "unknown_spec_id": ["FR-002a"], "foreign_qualified": []}}`, and re-pin the hint to the composed stale hint.
- `stale_refs` and `parsed_spec_ids` are unchanged.
- Changelog note: *"map-requirements stale gate: `FR-002a` reclassified `malformed` → `unknown_spec_id`; `stale_ref_reasons` gains a `foreign_qualified` bucket; hint re-worded to name the grammar."*

**c. Leave every other entry alone.** Assert `map_requirements_success` and `map_requirements_unknown_spec_ref_error` are untouched. If either goes red, your change leaked. Fix the code, never the fixture.

**2. Changelog notes.**
- Put the one-liners in the Activity Log AND in a `## Changelog notes` section of your hand-off, so the closeout can lift them.
- Also add one more note: *"map-requirements now preserves existing ref order on disk and appends new refs; multi-ref WP files are no longer re-sorted (FR-005)."*
- And: *"map-requirements `--replace` success payload gains an additive `replaced_refs_removed` key listing the stored items the overwrite dropped (FR-005); it is absent on default-mode runs."*
- Do not edit `docs/changelog/CHANGELOG.md`: the orchestrator writes it at closeout, and no WP owns it.

**3. Demote the repros.**
- Remove `@pytest.mark.regression` from both repros.
- Rename them to describe behaviour, e.g. `test_existing_items_survive_byte_identical_in_place` and `test_declared_sc_and_suffixed_refs_accepted_canonical`.
- Keep the issue number in each docstring. None stays marked `regression`.

**4. Add focused tests to the new file (non-vacuity: every refusal or absence assertion has a same-fixture positive control):**
- **Dedup by canonical form.** Existing `["FR-006A"]` plus `--refs FR-006a` gives the on-disk `["FR-006A"]`, unchanged. Positive control: `--refs FR-002` on the same fixture appends.
- **Undeclared SC is refused as `unknown_spec_id`, with no write** (file bytes unchanged). Positive control: declared `SC-001` on the same fixture is accepted (FR-006 pairing).
- **Foreign-qualified input never blocks and never covers.**
  - `--refs other-mission-01KAAAAA#FR-001` gives exit 0, the ref is appended, and `coverage.unmapped_functional` still contains `FR-001`.
  - Positive control: plain `FR-001` covers it.
- **Kept rejected ref on the mapped WP.**
  - Seed WP01 with `["FR_009"]`, then map `FR-001`. Result: exit 1, `stale_ref_reasons["WP01"]["malformed"] == ["FR_009"]`, and the file holds `["FR_009", "FR-001"]` (kept, not erased).
  - Then `--replace` clears it with exit 0. That is the positive control and the documented recovery.
- **Foreign-only stale set passes.** A WP02 carrying only `other-mission-01KAAAAA#FR-013`, while WP01 is mapped, exits 0. Adding a malformed token to WP02 exits 1, and then `stale_ref_reasons["WP02"]["foreign_qualified"]` lists the foreign ref.
- **Pre-write malformed refusal:** `parsed_spec_ids` and the hint are present, and no file is written (mtime and bytes unchanged).
- **`--replace` lists what it removed (FR-005).** Seed WP01 with `["FR_009", "FR-001", "SC-001"]`, run `--wp WP01 --refs FR-001 --replace --json`: exit 0, the file holds `["FR-001"]`, and `payload["replaced_refs_removed"] == {"WP01": ["FR_009", "SC-001"]}` (raw, in original order). Positive control on the same fixture without `--replace`: `"replaced_refs_removed" not in payload` and the existing items survive.
- **`--batch` parity:** `{"WP01": ["sc-001", "FR-006A"]}` is written as `["SC-001", "FR-006a"]`.
- **Pure helpers:** `_canonical_input_refs`, `_dedup_key`/`_merge_refs` (append, dedup, replace-unchanged, fallback), the coverage projection helper, `_mr_classify_wp_refs` and `_replaced_items_removed`.

**5. Run the validation surface, then record commands and pass/fail counts in the Activity Log.**

**6. Tracer notes** (1–3 sentences each, dated) go in the `## Tracer notes` section of your hand-off:
- approach: red-first evidence;
- design decisions: the `stale_refs` interpretation and the item-vs-token edge;
- tooling friction: anything that fought you.

## Commit plan

1. `test(map-requirements): red-first repros for #2991 and #3519 (WP03 T015)`: the test file only, RED (2 failed).
2. *(Optional, tidy-first, behaviour-preserving)*: extract `_mr_classify_wp_refs` / payload builders from `_mr_stale_gate` with today's semantics. Existing tests stay unchanged and green.
3. `fix(map-requirements): canonical input + append-only merge (#2991, #3519; FR-005, FR-006)`: T016 and T017, with helper tests. The repros go GREEN.
4. `feat(map-requirements): grammar verdicts and self-explaining refusals (FR-010, FR-012, FR-019)`: T018, with the test re-pins.
5. `test(map-requirements): re-pin byte contracts; demote repros (NFR-002)`: T019.

## Validation surface

**Test files (run exactly these):**
- `tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py`
- `tests/specify_cli/test_cli/test_map_requirements.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_map_requirements_seam.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_mapping_core.py`
- `tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py`
- `tests/specify_cli/cli/commands/agent/test_map_requirements_spec_path.py`
- `tests/specify_cli/cli/commands/agent/test_map_requirements_commit_result_json.py`
- `tests/specify_cli/cli/commands/agent/test_map_requirements_read_surface.py`
- `tests/specify_cli/cli/commands/agent/test_map_requirements_coord.py`
- Blast-radius additions (they import the touched modules; not owned, so read and run them but do not edit them):
  - `tests/specify_cli/cli/commands/agent/test_tasks_core_backed_orchestration.py`: `_do_map_requirements` / `plan_mapping` routing;
  - `tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py`: a frozen coverage floor over `plan_mapping` / `_do_map_requirements` (`:1225-1238`). If the floor moves, report it; do not edit the floor.
- Package tests (you delete the `validate_*`/`classify_stale_refs` helpers and their orphaned unit tests; the package must stay green):
  - `tests/specify_cli/test_requirement_mapping.py`
  - `tests/specify_cli/test_requirement_mapping_coord_surface.py`
  - `tests/specify_cli/test_bare_prose_false_negative_sample.py`

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/test_requirement_mapping.py \
  tests/specify_cli/test_requirement_mapping_coord_surface.py \
  tests/specify_cli/test_bare_prose_false_negative_sample.py \
  tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py \
  tests/specify_cli/test_cli/test_map_requirements.py \
  tests/specify_cli/cli/commands/agent/test_tasks_map_requirements_seam.py \
  tests/specify_cli/cli/commands/agent/test_tasks_mapping_core.py \
  tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py \
  tests/specify_cli/cli/commands/agent/test_map_requirements_spec_path.py \
  tests/specify_cli/cli/commands/agent/test_map_requirements_commit_result_json.py \
  tests/specify_cli/cli/commands/agent/test_map_requirements_read_surface.py \
  tests/specify_cli/cli/commands/agent/test_map_requirements_coord.py \
  tests/specify_cli/cli/commands/agent/test_tasks_core_backed_orchestration.py \
  tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py
```

**Named architectural gates (by file only):**
- `tests/architectural/test_requirement_id_grammar_single_source.py`: no requirement-ID pattern literal and no ID case change in the two owned source files.
- `tests/architectural/test_no_dead_symbols.py`: WP03 removes the last product callers of `validate_ref_format` / `validate_refs` / `classify_stale_refs`. See the allowed out-of-map edit above.

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/architectural/test_requirement_id_grammar_single_source.py \
  tests/architectural/test_no_dead_symbols.py
```

**Owning-module fast tier:** `make test-fast`.

**Static checks on the touched source files:**

```bash
.venv/bin/ruff check src/specify_cli/cli/commands/agent/tasks_map_requirements.py src/specify_cli/cli/commands/agent/tasks_mapping_core.py tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py
.venv/bin/ruff format --check src/specify_cli/cli/commands/agent/tasks_map_requirements.py src/specify_cli/cli/commands/agent/tasks_mapping_core.py tests/specify_cli/cli/commands/agent/test_map_requirements_grammar.py
.venv/bin/mypy --strict src/specify_cli/cli/commands/agent/tasks_map_requirements.py src/specify_cli/cli/commands/agent/tasks_mapping_core.py
```

**Pre-existing failures:** follow the CLAUDE.md baseline-red gotcha. A failure that is also red on the planning base (run it with `PYTHONPATH=<base-worktree>/src`) is not yours. Report it in the Activity Log; do not fix it and do not hide it.

## Quality bar

- Every function stays at complexity ≤ 15 (ruff C901). `_mr_stale_gate` and `_mr_gate_offenders` must not grow past it; extract instead.
- Every new helper gets a focused test in the same commit (Sonar new-code, diff-cover ≥ 90%).
- A literal used 3+ times in a module is hoisted. The hint constant is the known case. The bucket keys `"malformed"` / `"unknown_spec_id"` / `"foreign_qualified"` are never restated: import `grammar.MALFORMED`, `grammar.UNKNOWN_SPEC_ID` and `grammar.FOREIGN_QUALIFIED`.
- No blanket `noqa` / `type: ignore`.
- Terminology: *Mission*, never "feature", in new prose, identifiers and test names.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Order preservation changes the on-disk output for existing multi-ref mappings: they are no longer sorted. **This is intended** (FR-005). | Re-pin only the tests that asserted sorted order, with a one-line FR-005 comment each. Add a changelog note. Call it out in the PR body. |
| Kept rejected refs on the mapped WP now make map-requirements exit 1 where it used to "succeed" by silently deleting them. | Intended ("reported, not erased"). The hint names `--replace` as the recovery. A focused test proves both the refusal and the recovery. |
| The coord-surface write path breaks (`test_map_requirements_coord.py`, `..._spec_path.py`, `..._read_surface.py`). | Do not touch read-dir resolution, `_map_requirements_feature_dir`, the ports or `_mr_auto_commit`. The change is confined to the input, plan, gate, stale and hint seams. Run all three files. |
| The seam-interception contract breaks (`test_tasks_map_requirements_seam.py`). | Keep `_tasks.plan_mapping`, `_tasks.RealRender`, `_tasks.console` and `_tasks._output_error` call routing verbatim. New helpers are direct calls. |
| Byte-contract drift beyond the two sanctioned entries. | Hand-derive the expected bytes, and verify that `map_requirements_success` and `..._unknown_spec_ref_error` are unchanged. |
| WP01 landed a different API shape. | Adapt to the landed API; record any mismatch with this prompt in your hand-off's `## Tracer notes`. Never add a local pattern or `.upper()` as a stopgap (C-001). |
| Coverage floor in `test_tasks_cli_contract_coord.py` shifts. | The floor is frozen. Report a shift to the reviewer with the measured numbers instead of editing it. |

## Review Guidance

- **Byte-identical, in place.** The #2991 test seeds raw YAML and asserts the exact on-disk list, existing items first and unchanged (`FR-006A` stays uppercase). It asserts the disk before the exit code.
- **Deduplication is by canonical form.** Existing `FR-006A` plus new `FR-006a` gives one item, the original spelling. Existing duplicates are not collapsed. `--replace` is still `sorted(set(canonical new refs))`, and its payload lists the dropped items in `replaced_refs_removed` (absent on default-mode runs).
- **`total_mappings` is built from the raw reader plus `grammar.classify`**, so a malformed ref is never silently dropped from the coverage view.
- **A single hint constant.** `grep -n "FR-NNN" src/specify_cli/cli/commands/agent/tasks_map_requirements.py` returns nothing. All three hint sites derive from one constant, and the constant names FR/NFR/C/SC, the lowercase suffix and `<mission-slug>#`.
- **Byte-contract re-pins are justified one by one.** Exactly two entries changed:
  - the malformed case (`FR-001a` → `FR_001`, added `parsed_spec_ids`, new hint, no uppercasing);
  - the stale case (`FR-002a` → `unknown_spec_id`, added `foreign_qualified: []`, new hint).

  Each has its changelog one-liner. `map_requirements_success` and `map_requirements_unknown_spec_ref_error` are untouched.
- **One reason per ref.** No ref appears in two buckets, either in `MappingOffenders` or in `stale_ref_reasons`. `foreign_qualified` never produces exit 1.
- **No normalised read on the merge base.** `_mr_plan` no longer imports `read_all_wp_requirement_refs`, and coverage is projected from accepted canonical refs only.
- **C-001.** No regex literal or requirement-ID `.upper()` remains in either owned source file, and the single-source gate is green.
- **Red-first evidence.** Commit 1 contains only the test file, and its message or the Activity Log shows `2 failed`. The repros are no longer marked `regression` at handoff.
- The implementer ran `mypy --strict` and `ruff format --check` in addition to pytest, and recorded the commands and counts.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this section.
2. **APPEND the new entry at the END.** Never prepend, and never insert in the middle.
3. Use the exact format `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`.
4. Use the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`).
5. The agent ID identifies who made the change.

**Initial entry**:

- 2026-09-29T06:12:58Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP03 --to <status>` to change WP status.
