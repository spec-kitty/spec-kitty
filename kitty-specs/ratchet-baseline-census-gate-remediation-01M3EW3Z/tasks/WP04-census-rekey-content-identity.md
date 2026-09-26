---
work_package_id: WP04
title: Census re-key (all 80) on _content_identity + composite key
dependencies:
- WP02
requirement_refs:
- C-004
- FR-006
- NFR-001
- NFR-005
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
- T021
- T022
- T023
- T024
- T025
- T026
phase: Phase 2 - Census re-key
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_destructive_op_census.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/_destructive_op_census.py
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/test_overwrite_ownership_routing.py
- tests/architectural/test_mutation_ownership_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Census re-key (all 80) on _content_identity + composite key

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load `spec-kitty charter context --action implement --json`. Binding here: DIRECTIVE_044 and C-004 (one identity mechanism: delete the census helper's second qualname algorithm; one matcher, `_content_identity.partition_findings`), DIRECTIVE_041/DIR-041 (content anchoring), DIRECTIVE_043 / Standing Order #5 (non-vacuity), Standing Order #4 (red-first), Standing Order #7 (git discipline: three reviewable commit stages).

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

The three census gates key their allowlists as `"<rel>:<lineno>:<op>"` strings: destructive-op **22**, mutation **56**, overwrite **2** = **80** line-pinned entries (spec FR-006; research erratum 1 fixes the swapped counts). Every unrelated line shift re-pins them. This WP re-keys all 80 to content identity and unifies the census helper onto the canonical substrate.

Done means:

1. `CensusKey(rel, qualname, token_line, op, op_ordinal)` (plan D-OP-1; `op_ordinal` is the 0-based ordinal among live findings sharing `(rel, qualname, token_line, op)`, ordered by line) replaces every string key. `(qualname, token_line)` comes from `_ratchet_keys.composite_key(source, lineno)`. Exactly 3 of the 80 need `op_ordinal=1`.
2. The census helper's own tree-based `enclosing_qualname` is deleted; `_ratchet_keys.enclosing_qualname(source, lineno)` is the only qualname algorithm (C-004).
3. `diff_against_allowlist` delegates to `_content_identity.partition_findings` (D-OP-9: one matcher, two stale policies). Census stale policy stays **WARN** (D-OP-8, the documented "legitimate cleanup must never be blocked" contract).
4. Drift tolerance (NFR-001): `test_destructive_census_survives_line_drift` (15 files), `test_overwrite_census_survives_line_drift` (2 files), `test_mutation_census_survives_line_drift` (21 files); file sets derived from the allowlists with the count asserted equal to the derived set (never hard-coded; Debbie corrected research's 17/23 to 15/21). RED on the planning base, GREEN at the end.
5. Non-widening proofs (Renata HIGH): a second identical op in an exempted function FAILS; a changed argument on an exempted op FAILS and warns stale.
6. Equivalence proof: the exempted site set on the planning base (`3717c7ea`) equals the set blessed by the new keys at WP head, as a bijection with identical rationale hashes, **80/80**, recorded in the PR and tracer.
7. `len(test_mutation_ownership_routing._ALLOWLIST) == 56` still holds; `_ALLOWLIST` stays a sized mapping (it feeds `destructive_op_allowlist: 56` in `_baselines.yaml` via `test_ratchet_baselines.py:464-467 / 626-629`).

## Context & Constraints

- **Depends on WP02** (`tests/architectural/_content_identity.py`: `partition_findings`, `with_blank_line_at_top`, `with_probe_above_statement`). Rebase onto it before starting.
- **Read**: `spec.md` (FR-006, FR-007 census half, C-004, edge case "census key collisions"), `plan.md` rev 2 (D-OP-1, D-OP-8, D-OP-9; Coordination points: this WP is the **merged** census WP because the `enclosing_qualname` signature change would break another lane), `research.md` §C1–§C3, §B5, `data-model.md` ("CensusKey"), `research/postplan-paula.md` Q1 MEDIUM (partitioner unification), Q2 HIGH (mutation-file coupling), `research/postplan-priti.md` (WP05 LOW: `_RESEARCH_PY_ALLOWLIST_PREFIX`; WP05↔WP06 coupling), `research/postplan-debbie.md` (15/21/2 files; 3 of 80 need ordinal 1; argv-only token lines), `research/postspec-renata.md` (FR-006 HIGH).
- **Forbidden**: do not touch `tests/architectural/_baselines.yaml` or `tests/architectural/test_ratchet_baselines.py` (WP06 owns them). Do not change the container type or size of the mutation `_ALLOWLIST`. No `src/` edit (C-005): `src/` must stay byte-identical to the planning base so `(rel, lineno)` is a valid cross-SHA site identity for the equivalence proof.
- **Formatting**: none of the four owned files is format-excluded; all must pass `ruff format --check`.
- **Mission artefacts (out-of-map, not in `owned_files`)**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/census-rekey-map.csv` and `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py`. A `code_change` WP may not own `kitty-specs/` paths, so write them on the mission's planning surface (the primary partition, from the repository-root checkout), not in the lane commits. The research script is excluded from ruff by `ruff.toml` `extend-exclude = ["kitty-specs/*/research/**"]` and is **not** a committed test (a test would have to hold the 80 old line keys, which the widened ban forbids). A prototype exists only in the planning session's scratchpad (`squad/census-rekey-map.csv`, `squad/census_rekey.py`); regenerate from live code rather than depending on it.
- **WP01 interaction**: WP01's interim rows for the 80 census strings become finding-less after this WP and only warn. Do not edit the ban file. Your `CensusKey(...)` literals must not trip the widened ban: `op_ordinal=` is not a line keyword, `rel="src/…py"` has no `:<int>`, and `lineno` must never appear in an allowlist literal.
- **Known, accepted weakness** (record in the tracer): tokens strip strings, so 8 of the 22 destructive keys have argv-only token lines such as `[ , , ] ,`; an argument swap inside the same op is blessed silently. Deleting an earlier same-key op shifts ordinals so a rationale can re-attach to its twin; both were exempted anyway and census stays warn-on-stale.
- **C-006**: commit in your lane; never push or merge.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

Commit plan (plan rev 2: "split commits: helper → destructive+overwrite → mutation"):

| Commit | Subtasks | State after commit |
|---|---|---|
| 1 (RED) | T017 | drift tests and changed-argument tests RED on all three gates; everything else green |
| 2 (helper) | T018, T019 | helper unified; all pre-existing census tests green; drift tests still RED |
| 3 (destructive + overwrite) | T021, T022 | destructive and overwrite drift tests GREEN |
| 4 (mutation) | T023, T024 | all GREEN |

T020 (artefact tooling) and T025 (equivalence proof) produce mission artefacts outside the lane; T026 is validation.

### Subtask T017 – Red-first acceptance tests (commit 1, RED)

- **Purpose**: C-001. Show, through each gate's own detection and matching path, that line-keyed census allowlists do not survive drift; pin the non-widening behaviour before the re-key so it provably survives it.
- **Steps**:
  1. In each gate module, extract a behaviour-preserving seam `_census_partition(sources: Mapping[str, str]) -> tuple[set[K], set[K]]` returning `(unexpected, suppressed)` using today's `_flatten` + `diff_against_allowlist`. It runs the gate's **real** finder on each source: the finders take a `Path` (`_find_destructive_literals`, L121-133; `_find_destructive_ops`, mutation L202-215; `_find_overwrite_ops`, overwrite L213-226), so write each (possibly mutated) source to a `tmp_path` copy and key the hits with the **original** repo-relative path.
  2. Add `test_destructive_census_survives_line_drift`, `test_overwrite_census_survives_line_drift` and `test_mutation_census_survives_line_drift`, each parametrized over the distinct files referenced by the gate's `_ALLOWLIST` (derived; add a companion test asserting the parameter set equals the derived set). For each file: mutation (i) a blank line at the top; mutation (ii) a probe statement above every exempted site in that file. Assert `(unexpected, suppressed)` for the mutated tree equals the unmutated run. RED on base for every file (line keys shift). Use WP02's `with_blank_line_at_top` / `with_probe_above_statement`.
  3. Add, per gate where the op family allows it, `test_second_identical_op_in_exempted_function_fails` (duplicate an exempted op statement in memory inside its function → the seam reports it as unexpected) and `test_changed_argument_on_exempted_op_fails` (edit an exempted op's arguments in memory so its **token line** changes, e.g. add a name argument or an extra non-string element; changing only a string literal does not change tokens because `composite_key` strips strings → the new site is unexpected and the old entry appears in the stale set). Be precise about their base state (#5068: red for the intended reason): the second-identical-op test is **green on base** (a new line already yields a new line key) and must stay green after the re-key, so it is the non-widening guard; the changed-argument test is **RED on base** (a line key silently keeps blessing a changed argument on the same line) and turns green with the re-key, so it is a second red driver. State this in each docstring.
  4. Run the drift and changed-argument tests, capture the RED failure text, record it: `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category approach --actor <you> --entry "WP04 RED: ..."`. Commit alone.
- **Files**: the three gate modules.
- **Notes**: the gate test functions themselves (`test_destructive_commands_only_at_allowlisted_or_guard_sites` L259-279, `test_every_destructive_literal_is_allowlisted` mutation L505-523, `test_every_overwrite_literal_is_allowlisted` overwrite L338-354) must call the seam, so the drift test and the gate share one path.

### Subtask T018 – Unify the qualname algorithm and add `CensusKey` (commit 2, part A)

- **Purpose**: C-004. Two qualname algorithms for one concept is the defect; the re-key needs one canonical key builder.
- **Steps** (in `_destructive_op_census.py`):
  1. Delete the tree-based `enclosing_qualname(tree, lineno)` (L148-180). Re-export `enclosing_qualname` from `tests.architectural._ratchet_keys` (signature `(source, lineno)`). Research and Debbie witnessed that all 80 census sites and all 10 dirty-predicate sites resolve identically under both algorithms on HEAD. Latent divergence exists only for class-body statements (`<module>` vs `K`) and nested classes in methods; no live site is affected. Do **not** keep a tree-accepting shim (that would be the second algorithm C-004 forbids).
  2. Add `parse_with_source(path) -> tuple[str, ast.Module] | None` next to `parse` (L48-53, kept).
  3. Add `class CensusKey(NamedTuple)` with fields `rel: str`, `qualname: str`, `token_line: str`, `op: str`, `op_ordinal: int`, and `census_keys(rel: str, source: str, hits: Iterable[tuple[int, str]]) -> dict[CensusKey, int]` (key → lineno for diagnostics). Group hits by `(rel, qualname, token_line, op)`, order each group by lineno, assign `op_ordinal` 0, 1, … Add a `render_census_key(key, lineno) -> str` diagnostic formatter producing `rel::qualname::op#ordinal (line N) tokens=<token_line>`; the line number is diagnostic only.
  4. Update every `enclosing_qualname` caller in the **same commit** so the lane stays green: `test_destructive_op_routing.py::_status_porcelain_hits` (L349-362, via `parse_with_source`; `_KNOWN_DIRTY_PREDICATES` unchanged), `test_mutation_ownership_routing.py::test_enclosing_qualname_is_available_for_diagnostics` (L771-779) and `test_overwrite_ownership_routing.py::test_enclosing_qualname_is_available_for_diagnostics` (L612-620). This is the sequenced edit Paula flagged; it is why the three census gates live in one WP.
  5. Add focused tests for `census_keys` (ordinal assignment across a same-key pair; distinct keys across files; distinct keys across ops) in the census gate module that best fits, or as a small block in `test_destructive_op_routing.py`.
- **Files**: `_destructive_op_census.py`; call sites in the three gate modules.

### Subtask T019 – Delegate the partitioner (commit 2, part B)

- **Purpose**: D-OP-9 / Paula Q1 MEDIUM. `CensusKey.op_ordinal` makes census keys unique, so `partition_findings` degenerates exactly to today's set difference; keep one matcher.
- **Steps**:
  1. Rewrite `diff_against_allowlist` (L189-199) over a `TypeVar K` (bound `Hashable`) as a thin call: `unexpected_list, unused = partition_findings(((k, k) for k in live), Counter(allowlist.keys()))`; return `(set(unexpected_list), set(unused))`. Keep the `(unexpected, stale)` contract and the WARN-on-stale docstring (L14-18, L192-197) unchanged, and add one sentence: content keys make warn-on-stale safe because a dead content key cannot re-bind to a new site.
  2. Generalise `drop_one_entry` (L214-221) over `K`. The drop-one-entry non-vacuity tests in all three gates (destructive L458-474, mutation L732-747, overwrite L543-558) must keep passing for every key type.
  3. Update the module docstring (L1-21) to name `_ratchet_keys` (identity) and `_content_identity` (matching) as the single authorities it builds on. Commit T018 + T019 together; run the full census blast radius; the only red tests are T017's drift tests.
- **Files**: `_destructive_op_census.py`.

### Subtask T020 – Re-key tooling and the mapping artefact (mission artefact, out-of-map)

- **Purpose**: FR-006 requires an old→new mapping proving the exempted site set is identical; generating the 80 literals by hand is error-prone.
- **Steps**:
  1. Write `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py` (runs from the repo root with `.venv/bin/python`; stdlib + repo imports only). Modes:
     - `--emit-map`: for each gate, read the **base** `_ALLOWLIST` via `git show <base>:<gate file>` and `ast.literal_eval` of the dict node; for each old key `rel:lineno:op`, read the live source, compute `census_keys` over the gate's live hits, find the new key whose lineno equals the old lineno and whose op matches; write `census-rekey-map.csv` with columns `gate, old_key, rel, qualname, token_line, op, op_ordinal, rationale_sha256` (80 rows; `rationale_sha256` is SHA-256 of the rationale text). data-model.md names the ordinal column `occurrence`; use `op_ordinal` per plan D-OP-1 and note the rename in the CSV header comment or tracer.
     - `--emit-literals <gate>`: print the new `_ALLOWLIST` literal for that gate in keyword form `CensusKey(rel="…", qualname="…", token_line="…", op="…", op_ordinal=0): "<rationale verbatim>",` preserving the original section comments' grouping and order.
     - `--base <sha>` (default `3717c7ea`): the equivalence check of T025.
  2. Generate the CSV. Sanity-check: 80 rows; per-gate 22 / 56 / 2; exactly 3 rows with `op_ordinal=1` (destructive `src/specify_cli/lanes/merge.py::_merge_branch_into` `merge_abort`; mutation `src/specify_cli/upgrade/migrations/m_0_10_8_fix_memory_structure.py::FixMemoryStructureMigration.apply` `Path.unlink` ×2); 0 duplicate `CensusKey`s; distinct `rel` per gate 15 / 21 / 2.
- **Files**: the two mission artefacts only (written on the planning surface, not in the lane).
- **Parallel?**: Can start after T018 exists locally.

### Subtask T021 – Re-key the destructive-op gate: 22 keys (commit 3, part A)

- **Purpose**: FR-006 for `test_destructive_op_routing.py`.
- **Steps**:
  1. Replace `_flatten` (L146-147) with a key builder over `census_keys` (read each file's source once via `parse_with_source`), returning `dict[CensusKey, int]`.
  2. Replace `_ALLOWLIST: dict[str, str]` (L158-256) with `dict[CensusKey, str]` using the literals from `--emit-literals destructive`. Rationale text must be **byte-identical** (T025 checks the hashes; prose such as `ordering.py:329` inside a rationale stays as is).
  3. The gate (L259-279) uses the seam from T017 on the new keys; the failure message lists each unexpected key via `render_census_key` so the author sees `rel::qualname::op#ordinal (line N) tokens=…` and can paste a `CensusKey(...)` literal. Stale keys still `warnings.warn`.
  4. `test_allowlisted_files_exist` (L282-289): replace `key.rsplit(":", 2)[0]` (L286) with `{key.rel for key in _ALLOWLIST}`.
  5. Rewrite the allowlist comment block (L149-157) to describe content identity; it currently says "verified present, at the line shown".
- **Files**: `tests/architectural/test_destructive_op_routing.py`.
- **Validation**: `test_destructive_census_survives_line_drift` (15 files) GREEN; the planted-op tests (L396-456) and dirty-predicate tests (L375-523) unchanged and green.

### Subtask T022 – Re-key the overwrite gate: 2 keys (commit 3, part B)

- **Purpose**: FR-006 for `test_overwrite_ownership_routing.py`.
- **Steps**:
  1. `_flatten` (L255-256) → `census_keys`-based builder; `_ALLOWLIST` (L267-283) → `dict[CensusKey, str]` (2 entries: `intake/brief_writer.py` `os.replace`, `cli/commands/research.py` `shutil.copy2`), rationales verbatim (the `research.py:80` prose stays).
  2. `test_allowlisted_files_exist` (L357-368): `rsplit` at L360 → `key.rel`.
  3. `test_each_routed_module_routes_and_is_allowlist_clean` (L422-443): the literal re-builder at L436 (`{f"{repo_rel}:{lineno}:{op}" ...}`) → `census_keys(repo_rel, source, _find_overwrite_ops(path)).keys()`.
  4. Update the allowlist comment (L258-266: "keyed `\"{path}:{lineno}:{op}\"`").
  5. Commit T021 + T022 (commit 3). Run the blast radius.
- **Files**: `tests/architectural/test_overwrite_ownership_routing.py`.
- **Validation**: `test_overwrite_census_survives_line_drift` (2 files) GREEN; the guard-call deletion tests (L567-610) green.

### Subtask T023 – Re-key the mutation gate: 56 keys (commit 4, part A)

- **Purpose**: FR-006 for `test_mutation_ownership_routing.py`, the largest block (L238-442).
- **Steps**:
  1. `_flatten` (L227-228) → `census_keys`-based builder; `_ALLOWLIST` → `dict[CensusKey, str]`, 56 entries, rationales verbatim, section comments kept. It must remain a sized mapping of exactly 56 (WP06's `_SIZE_RATCHETS` row reads `len(_ALLOWLIST)`).
  2. `_RESEARCH_PY_ALLOWLIST_PREFIX = "…/research.py:"` (L103) relies on the string key shape. Replace it with a repo-relative path constant for `research.py` and make `test_research_py_removal_literals_are_never_allowlisted` (L526-545) check `key.rel == <that path>`; keep its fail-closed intent and message.
  3. `test_allowlisted_files_exist` (L548-560): `rsplit` at L552 → `key.rel`.
  4. `test_each_routed_module_routes_and_is_allowlist_clean` (L628-651): the re-builder at L641 → `census_keys(repo_rel, source, _find_destructive_ops(path)).keys()`.
  5. Update the allowlist header comment and any docstring that describes `path:line:op` keys.
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`.
- **Validation**: `test_mutation_census_survives_line_drift` (21 files) GREEN; `test_removing_an_allowlist_entry_reproduces_a_gate_failure` (L732-747), `test_reverting_a_routed_call_to_a_raw_literal_is_caught` (L750-768) and the planted-op tests green.

### Subtask T024 – Non-widening, diagnostics and cross-gate checks (commit 4, part B)

- **Purpose**: Prove the re-key is not a widening and that failure output stays actionable.
- **Steps**:
  1. Confirm the T017 non-widening tests (second identical op → FAIL; changed argument → FAIL + stale warning) pass on the new keys in every gate. Add one explicit real-data ordinal test: in memory, duplicate the `lanes/merge.py::_merge_branch_into` `merge_abort` statement and assert a third key with `op_ordinal=2` is reported as unexpected.
  2. Add a test that renders an unexpected key and asserts the message contains `rel::qualname::op#ordinal`, the diagnostic line and the token line.
  3. Commit T023 + T024 (commit 4).
  4. Run `.venv/bin/python -m pytest tests/architectural/test_ratchet_baselines.py -q` to confirm `destructive_op_allowlist: 56` still matches (the #1979-class coupling Priti flagged).
- **Files**: the three gate modules.

### Subtask T025 – Equivalence proof, 80/80 (mission artefact)

- **Purpose**: FR-006's "exempted site set identical before and after", Renata HIGH (no laundering of coincidental blessings).
- **Steps**:
  1. Run `.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea` at your lane head. It must: (a) load the old `_ALLOWLIST`s via `git show 3717c7ea:<file>` and compute the old site set `{(gate, rel, lineno, op)}`; (b) import the new gate modules, resolve every `CensusKey` through `census_keys` over live source to `(rel, lineno)`; (c) assert the two site sets are equal, the old→new mapping is a bijection, and `rationale_sha256` matches per site; (d) print per-gate counts (22 / 56 / 2 = 80) and exit non-zero on any mismatch.
  2. Confirm `git diff 3717c7ea -- src/` is empty (C-005 makes `(rel, lineno)` a valid shared identity).
  3. Paste the command and output into the PR and record it with `spec-kitty agent tracer-append ... --category design-decisions`, together with the accepted weakness from "Context & Constraints" and the D-OP-8 warn-on-stale ruling.
- **Files**: mission artefacts only.

### Subtask T026 – Validation and quality gates

- **Purpose**: The helper is shared across `tests/architectural/`, so the full architectural suite is in the blast radius.
- **Steps**:
  1. Run the commands in "Test Strategy" in order; all green.
  2. Confirm with the WP01 ban on your base (if present) that no line pin remains in the three gates (`tests/architectural/test_ratchet_positional_anchor_ban.py`; WP01 rows for these sites only warn).
  3. Campsite (FR-020): clean #2972 findings (S5778 / S5779 / S8997) only in the four owned files; record before/after, zero is acceptable.
  4. Update the Activity Log with the four commit SHAs and the equivalence output summary.

## Test Strategy

Tests are required.

```bash
.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_content_identity.py -q
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q      # shared helper: full architectural run
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea
make test-fast
uv run --frozen ruff check tests/architectural/_destructive_op_census.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py
uv run --frozen ruff format --check tests/architectural/_destructive_op_census.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py
uv run --frozen mypy tests/architectural/_destructive_op_census.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py
```

Pre-existing failure rule: classify any red that is also red on the planning base; if pre-existing, file (or find) a GitHub issue before continuing and cite it in the PR's *Tests run* section.

## Risks & Mitigations

- **Widening by the new key** (Renata HIGH): `op_ordinal` plus `token_line` keeps a second identical op and an argument change visible; the T017 guards prove it before and after.
- **Laundering a coincidental blessing**: the equivalence script compares the base site set, not whatever is live at head; any mismatch fails it.
- **Rationale drift**: generated literals copy rationales verbatim; hashes are checked per site.
- **Lane red between stages**: expected only for the drift tests between commits 1 and 3/4. Every other test must be green at every commit; the `enclosing_qualname` callers are updated in the same commit as the signature change.
- **Baseline coupling**: `_ALLOWLIST` must stay a 56-entry mapping; run `test_ratchet_baselines.py` after commit 4. Never edit `_baselines.yaml`.
- **Size (L)**: keep literals generated, keep commits staged as in the table, and use `git diff --stat` per commit so review stays tractable.
- **Dirty-predicate scan**: `_scan_dirty_predicates()` must still equal `_KNOWN_DIRTY_PREDICATES` after the qualname unification (the existing gate at L375 checks this).

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`):

- Commit 1 contains only the RED drift tests (plus behaviour-preserving seam extraction) and the non-widening guards; its failure text shows the drift mismatches for 15 / 2 / 21 files and the changed-argument blessing.
- Drift tests derive their file set from the allowlist and assert the count; they use both mutations and compare full `(unexpected, suppressed)` sets through the gate's real finder and partition.
- The second-identical-op test exists in every gate and passes before and after the re-key; the changed-argument test is RED at commit 1 and GREEN at the end.
- The equivalence script output shows 80/80, a bijection and equal rationale hashes against `3717c7ea`; `src/` is unchanged.
- `_destructive_op_census.py` has no qualname algorithm of its own; `enclosing_qualname` is the `_ratchet_keys` re-export; no tree-accepting shim remains.
- `diff_against_allowlist` delegates to `_content_identity.partition_findings`; stale stays WARN.
- No `rsplit(":", 2)`, `"{rel}:{lineno}:{op}"` builder or `_RESEARCH_PY_ALLOWLIST_PREFIX` string-prefix check remains in any census gate.
- The mutation `_ALLOWLIST` has 56 entries; `_baselines.yaml` and `test_ratchet_baselines.py` are untouched.
- The drop-one-entry and planted-op non-vacuity tests in all three gates still pass.
- ruff check, ruff format --check and mypy are clean on the four files; the full `tests/architectural/` run is recorded.

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

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
