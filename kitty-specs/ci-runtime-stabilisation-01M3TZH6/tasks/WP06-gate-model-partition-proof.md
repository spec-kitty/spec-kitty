---
work_package_id: WP06
title: Gate-model partition field and three-way proof
dependencies:
- WP05
requirement_refs:
- FR-004
- C-001
- C-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
phase: Phase 3 - Battery partition
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_battery_partition_proof.py
- scripts/ci/battery_partition_plugin.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/_gate_coverage.py
- tests/architectural/test_battery_partition_proof.py
- pyproject.toml
- scripts/ci/battery_partition_plugin.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Gate-model partition field and three-way proof

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
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

## Objectives & Success Criteria

FR-004 requires the battery split to be **provable from the commands the workflows actually
run**: fast ∪ S1 ∪ S2 = base, pairwise disjoint, "evaluable by the existing gate-coverage
model". Today `_gate_coverage` has no notion of a runtime partition. A `Gate` is static
(paths, ignores, marker). Once the router passes `--battery-part`, the model would read
three identical whole-directory gates, and FR-010 (WP15) would see every battery test as
selected three times.

This WP:

1. Teaches `_gate_coverage` the partition. `Gate` and `SuiteInvocation` gain
   `partition: str | None = None`, parsed from a literal `--battery-part X`.
   `CompiledGate.selects` restricts a partitioned gate to its part's files, computed by the
   **shared selector** (D-24). `collect_job_nodeids` forwards
   `-p scripts.ci.battery_partition_plugin --battery-part X`.
2. Adds `tests/architectural/test_battery_partition_proof.py`, a static proof that runs in the
   fast roster (no collection, ≤ 10 s). It covers completeness, disjointness and file
   granularity over the live router's battery family, with positive controls (an injected
   unassigned file, a missing leg, a duplicated leg, a leaked roster file).
3. Proves the plugin's per-file keep/ignore decision equals the model's part sets (D-24).
4. Handles the companions: the ruff-format exclude for `_gate_coverage.py`, and pinning-inventory
   regeneration.

Done means FR-004's proof obligations from `contracts/battery-partition.md` are met
statically, C-001 holds (no architectural test is lost or added), the red-first test is red
on the planning base and green on the tip, and the inventory is regenerated.

## Context & Constraints

- **Read first**: in `research.md`, decision rows D-02 and D-24 (one base-file enumeration,
  shared by the plugin and the gate model), D-25 (pinned-file lane discipline), D-28 (FR-010
  logic belongs in `_live_uniqueness.py`, not here) and D-20 (companion gotchas). Then R1 §4e
  "Partition proof evaluable by `_gate_coverage`" and R1 §1 D-PLUG. Also read
  `contracts/battery-partition.md`, `data-model.md` (Battery shard partition),
  `spec.md` (US2 AS-2/AS-3, FR-004, C-001, C-010) and `.kittify/charter/charter.md`
  (Standing Order #5: a gate needs a positive control).
- **Dependency WP05 (must be merged into your base first)** delivers
  `scripts/ci/battery_partition_plugin.py` and the registry entry `special_tiers.architectural`
  (with `base`, `workers`, `fast_gate.roster` and `shards.shard_count`). With WP02 before it,
  it delivers `scripts/ci/shard_select.py` (`enumerate_base_files`, `battery_parts`,
  `lpt_loads`, file-mode weights with the median default). **Read those two files before
  writing code** and use the names they actually ship. This prompt uses the research names.
- **Router state is not yours**: WP12 (which depends on this WP) adds `architectural-fast` and
  the 2-leg `architectural-heavy` matrix with `--battery-part`. At WP06 time the router may
  still run one unpartitioned battery. The live proof must therefore hold in **both** states
  (see T023). Do not edit `ci-router.yml`.
- **D-28**: keep `_gate_coverage.py` changes minimal (the field, the parse, the selection,
  collection forwarding, one cached part-file helper). The proof logic lives in the new test
  file. FR-010 logic goes to WP15's `_live_uniqueness.py`.
- **Roster placement — this WP does not edit the registry**: research.md R1 §4b row 33 puts
  "the partition test" in the fast roster (it calls it `test_battery_partition.py`). This WP
  creates it as `tests/architectural/test_battery_partition_proof.py`. WP05 deliberately left
  row 33 out (the file did not exist yet), and **WP14** — which owns the registry after WP05 and
  depends on this WP — adds it to `fast_gate.roster` as row 33 (budget 10 s + reason). Until
  WP14 lands, the file runs in a leg instead of the fast job, which is harmless. Do not touch
  `.github/ci-module-registry.yml` here.
- **C-009**: never run `tests/architectural` whole. `--collect-only` per part is allowed.
- **Terminology**: "Mission", never "feature". Never bare "routing".

### Current-state anchors (verified 2026-10-01; `_gate_coverage.py` is 2,799 lines)

| Surface | Anchor | Today |
|---|---|---|
| `Gate` | `_gate_coverage.py:288-310` | `@dataclass` with `workflow, job, shard, paths, ignores, marker_expr, via`; `label()` |
| Matrix expansion | `_matrix_includes` :329, `substitute_matrix` :335, `parse_workflow` :823-861 | only a static `include:` **list** expands; `Gate.shard = mvars.get("shard")`; `${{ matrix.X }}` is substituted in the run text |
| Command parse | `parse_pytest_invocation` :407 (returns `(paths, ignores, marker)`); `strip_to_command` :363 (strips `uv run --frozen`, `python -m`) | `--deselect` is folded into `ignores`; `-p`/`--battery-part` are ignored today |
| Invocation record | `SuiteInvocation` :523 (frozen), `_as_invocation` :704, `suite_invocations` :772 | three construction sites (:710, :762, plus the direct path :790) |
| Selection | `CompiledGate.__init__/selects` :1482-1519 | path, ignore and marker only; the `_zero_producer` fail-closed rule (#2967) |
| Real collection | `collect_job_nodeids` :1910 | `sys.executable -m pytest --collect-only -q -p no:cacheprovider -o addopts= <paths> --ignore=… -m …`, cwd = repo |
| Workflow models | `load_workflow_models()` :2155 | |
| Format exclude | `pyproject.toml:883` `"tests/architectural/_gate_coverage.py"` in `[tool.ruff.format].exclude` | shrink-only ratchet: `tests/architectural/test_ruff_format_exclude_ratchet.py` |
| Pinning inventory | `scripts/ci/derive_pinning_inventory.py` (`--check`, `--stdout`) → `tests/release/pinning_rule_inventory.json`; gate `tests/release/test_pinning_inventory_fresh.py` | 3 rules in `_gate_coverage.py` with **line numbers** (`WORKFLOW_FILES` :118, `NON_EMITTER_JOBS`, `_COMPOSITE_ROUTING`, plus module/docstring rows). **Already stale on the base on 2026-10-01**: the derivation adds a `test_pytest_ini_timeout_default.py::<module-docstring>` row |
| Battery base today | `ci-router.yml` job `architectural-heavy` | `tests/architectural`, `-m "not performance and not stress and not timing"`, 4 `--deselect` = the always-on lanes' files (`terminology`: `test_no_legacy_terminology.py`; `layer-rules`: `test_layer_rules.py` + `test_pyproject_shape.py`; `archive-freeze`: `test_archive_root_byte_identical.py`) |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T023 – Red-first: the partition proof, with positive controls

- **Purpose**: the static three-way proof (FR-004, US2 AS-2/AS-3), written before the model
  supports partitions. It is red today because `gc.Gate` has no `partition` attribute,
  `gc.battery_part_files` does not exist, and the fixture workflow's `--battery-part` legs
  parse as three identical whole-directory gates, so the overlap check fires.
- **Steps**:
  1. Create `tests/architectural/test_battery_partition_proof.py` with
     `pytestmark = [pytest.mark.architectural]` (match the neighbouring files' markers). It
     must not collect or spawn pytest, because it sits in the fast roster with a 10 s budget.
  2. Write **one production function** in the file,
     `partition_violations(family: Sequence[gc.Gate], base_files: frozenset[str], files_of: Callable[[gc.Gate], frozenset[str]], *, shard_count: int, roster: frozenset[str], base: BaseSpec) -> list[str]`.
     It returns one message per broken obligation:
     - **family args**: every gate's `(paths, set(ignores), marker_expr)` equals the registry
       `base` (`paths`, `deselect`, `marker`);
     - **shape**: either the family is exactly one **unpartitioned** gate (the pre-WP12 router),
       or every gate is partitioned and the partitions are exactly
       `{"fast"} ∪ {f"{i}/{shard_count}" for i in 1..shard_count}`, each once. A mix is reported;
     - **completeness**: ⋃ `files_of(g)` == `base_files`; name up to 10 missing files;
     - **disjointness**: no file in two gates' sets; name the file and both gate labels;
     - **fast = roster ∩ base** when a `fast` gate exists, and `roster ⊆ base_files`;
     - **deselect ownership (C-002)**: `set(base.deselect)` equals the union of the always-on
       architectural lanes' pytest file paths. Those lanes are the `ci-router.yml` gates whose
       paths are files under `tests/architectural/` and whose job carries only the fork-guard `if:`.
  3. Live test, `test_live_router_battery_partition_is_complete_and_disjoint`:
     - the family is the `gc.parse_workflow(ci-router.yml)` gates with
       `paths == ["tests/architectural"]`;
     - `files_of(g)` is `gc.battery_part_files(g.partition)` when partitioned, otherwise
       `gc.battery_base_files()` minus nothing;
     - assert `partition_violations(...) == []`.

     This holds both today (one unpartitioned gate) and after WP12 (fast + 1/2 + 2/2). A
     half-migrated router (fast partitioned, heavy not) fails on disjointness.

     **The single-unpartitioned-gate shape branch is transitional.** Mark it with a comment
     naming WP12 (e.g. `# TRANSITIONAL (WP12 T052 deletes): pre-partition router tolerated`).
     Once the router is partitioned the tolerance is a hole — a regression back to one
     unpartitioned battery would pass. **WP12 owns this file after you** (it depends on WP06) and
     its T052 deletes the branch and adds a positive control that a lone unpartitioned gate is
     reported, so the shape rule becomes "partitioned family only". Keep the branch isolated (one `if`, one message) so
     that deletion is a small, obvious diff.
  4. Positive controls. Write tmp fixture workflows, parse them with `gc.parse_workflow(tmp)`,
     and feed them to the **same** function:
     - `test_missing_leg_is_reported_as_file_in_no_set`: fast + `1/2` only;
     - `test_duplicated_leg_is_reported_as_file_in_two_sets`: fast + `1/2` + `1/2`;
     - `test_mixed_partitioned_and_unpartitioned_family_is_reported`: fast partitioned plus an
       unpartitioned heavy;
     - `test_injected_unassigned_file_is_reported` (the contract's named positive control):
       `base_files | {"tests/architectural/test_zz_injected_unassigned.py"}` with the real
       `files_of`, so the file is in no part;
     - `test_roster_file_leaked_into_a_shard_is_reported`: a stub `files_of` that also puts
       one roster file in `1/2`;
     - `test_injected_file_without_timing_is_assigned_to_exactly_one_leg`: call the real
       `shard_select.battery_parts` with the synthetic file added to the base and absent from
       the timings. It lands in exactly one leg (the FR-005 median weight) and the
       missing-timing report names it.
  5. Run the file and confirm it is **red** on the planning base. Record that.
- **Files**: `tests/architectural/test_battery_partition_proof.py` (new).
- **Parallel?**: No (first commit).
- **Notes**:
  - Fixture workflow text: copy the minimal job skeleton (`jobs: <name>: runs-on/steps/run`)
    with literal commands, including `-p scripts.ci.battery_partition_plugin --battery-part fast`
    and a 2-leg `strategy.matrix.include` using `shard: '1/2'` / `'2/2'` with
    `--battery-part ${{ matrix.shard }}`. That is exactly the shape WP12 ships.
  - Avoid the inventory subject literals in this file.

### Subtask T024 – `Gate.partition` and part-aware selection in `_gate_coverage`

- **Purpose**: make the gate model evaluate the literal `--battery-part` command (D-02), so
  the proof, the duplicate-suite ledger (WP12) and FR-010 (WP15) see legs as disjoint.
- **Steps**:
  1. Add `partition: str | None = None` as the **last** field of `Gate` (after `via`) and of
     `SuiteInvocation`. The defaults keep every existing constructor call valid. Make
     `Gate.label()` append ` [part X]` when it is set.
  2. Parse: add `_BATTERY_PART_RE = re.compile(r"--battery-part(?:=|\s+)(?P<part>\S+)")` and a
     helper `extract_battery_part(logical_line: str) -> str | None`. Keep
     `parse_pytest_invocation`'s 3-tuple return **unchanged**, because other code depends on
     its shape. Thread the partition in `suite_invocations`' direct branch (`_as_invocation(direct,
     via=None, partition=extract_battery_part(logical_line))`). `parse_workflow` copies
     `invocation.partition` onto the `Gate`. Matrix substitution has already resolved
     `${{ matrix.shard }}` by then.
  3. Add the cached part-file helpers (one enumeration, D-24):
     ```python
     @functools.cache
     def battery_base_files() -> frozenset[str]: ...      # shard_select.enumerate_base_files(<registry base>)
     @functools.cache
     def battery_part_files(partition: str) -> frozenset[str]: ...  # shard_select.battery_parts(...)[partition]
     ```
     Read the registry (`.github/ci-module-registry.yml` → `special_tiers.architectural`) and
     the timings (`.github/ci-shard-timings.json`, battery key) exactly as the plugin does.
     Ideally call the **same** loader the plugin uses (import it from
     `scripts.ci.battery_partition_plugin` or `scripts.ci.shard_select`). If the plugin has no
     reusable loader, export the thinnest one from `scripts/ci/battery_partition_plugin.py`
     yourself (this WP co-owns that file after WP05, **only** to export existing logic as a
     public pure helper — no behaviour change; `tests/ci/test_battery_partition_plugin.py` must
     stay green untouched). Never duplicate the loader in `_gate_coverage.py`. An unknown partition raises `ValueError` (fail closed).
  4. `CompiledGate`: when `gate.partition` is set, `selects` returns False for any `relpath`
     not in `battery_part_files(gate.partition)`. Do this check after the path/ignore checks
     and before marker evaluation. Compute the set once in `__init__`.
  5. `collect_job_nodeids`: when `gate.partition` is set, append
     `["-p", "scripts.ci.battery_partition_plugin", "--battery-part", gate.partition]`. It
     already runs `sys.executable -m pytest` with `cwd=repo`, which `-p scripts.…` needs.
  6. Do not reformat the file (see T025). Match its existing style by hand.
  7. **Production-path test for the forwarding** (add to `test_battery_partition_proof.py`; it
     spawns one collect-only subprocess, so mark it `slow` — it is **not** part of the fast-roster
     budget, keep the static proof tests separate): build a partitioned `gc.Gate` exactly as
     `parse_workflow` would for a battery leg (base paths, the 4 deselects in `ignores`, base
     marker, `partition="1/2"`), call the real `gc.collect_job_nodeids(gate)` and assert it
     returns (no `RuntimeError`, i.e. no `UsageError` / exit 4) and that every returned node id's
     file ∈ `gc.battery_part_files("1/2")`. Run it with `GITHUB_ACTIONS=true` in the env as well
     (monkeypatch `os.environ`; `collect_job_nodeids` copies it into the child). This pins the two
     WP05 T019 plugin argument rules the forwarding depends on: `collect_job_nodeids` passes the
     deselects as whole-file `--ignore=<file>` (`_gate_coverage.py:1940`) and passes no `-n`, so
     the plugin must treat `--ignore=<file>` as `--deselect <file>` and skip the worker check under
     `--collect-only`. If it fails on either rule, the fix belongs in WP05's plugin (raise it with
     the orchestrator), never in a looser call here.
- **Files**: `tests/architectural/_gate_coverage.py`.
- **Parallel?**: No (after T023).
- **Notes**:
  - Importing `scripts.ci.*` from `tests/architectural/` has precedent:
    `test_dual_mode_contract.py` imports `scripts.ci.router_gate`. Import lazily inside the
    helpers, so `_gate_coverage` import cost does not grow for the many consumers that never
    see a partitioned gate.
  - `Gate` equality now includes `partition`. Grep consumers that compare `Gate` objects:
    `rg "Gate\(" tests/architectural tests/ci`. Construction sites that omit `partition`
    default to `None` and keep comparing equal.
  - Whole-tree fallback (#2967): a partitioned gate has `paths == ["tests/architectural"]`,
    so the zero-producer rule is unaffected.

### Subtask T025 – Format-exclude companion and pinning-inventory regeneration

- **Purpose**: the same-commit companions (D-20, D-25). Skipping them causes CI-only reds.
- **Steps**:
  1. **Preferred**: do **not** run `ruff format` on `_gate_coverage.py`. It stays in
     `[tool.ruff.format].exclude` (`pyproject.toml:883`), and `pyproject.toml` stays
     untouched. `ruff check` still applies to it and must stay clean.
  2. **If you do reformat it** (for example the diff becomes unreadable otherwise), delete
     line 883's entry in the **same commit**. The shrink-only ratchet
     (`test_ruff_format_exclude_ratchet.py`) then passes, and the whole-repo
     `ruff format --check` covers the file. Re-run both.
  3. Regenerate the inventory: `python3 scripts/ci/derive_pinning_inventory.py`, then `--check`.
     The edit shifts the line numbers of the `_gate_coverage.py` rules.
     `tests/release/pinning_rule_inventory.json` is **not** in `owned_files`, so record a
     one-line out-of-map rationale in the Activity Log ("regenerated, D-20/D-25; `_gate_coverage.py`
     line shifts only"). Never hand-merge it. On a lane-merge conflict, regenerate. This WP is the
     **first** lane-a WP to regenerate the inventory. The base inventory is already fresh
     (#5523 fixed on main by `e3794ded2d` and CLOSED — D-37), so the regenerated diff must hold
     only this WP's own line shifts (see tasks.md Global rules for who regenerates and who never
     does).
  4. Run `tests/release/test_pinning_inventory_fresh.py` and confirm it is green.
- **Files**: `pyproject.toml` (only in the reformat branch), `tests/release/pinning_rule_inventory.json` (generated companion).
- **Parallel?**: No (after T024).
- **Notes**: D-25 serialises edits to `_gate_coverage.py`, `_ci_integrity_oracle.py` and
  `test_no_duplicate_suite_execution.py`. Make sure no other in-flight lane holds
  `_gate_coverage.py` (WP15 comes after you).

### Subtask T026 – Plugin enumeration equals the model's (D-24)

- **Purpose**: prove the plugin's runtime keep/ignore decision and the static model are the
  same function. Without this, the static proof could pass while CI ran different files.
- **Steps**:
  1. In `test_battery_partition_proof.py`, add
     `test_plugin_keep_decision_equals_model_part_sets`. For each part in
     `{"fast", "1/2", "2/2"}` (derive `n` from the registry `shard_count`) and each file in
     `gc.battery_base_files()`, assert that the plugin's pure decision helper (the function its
     `pytest_ignore_collect` delegates to) keeps the file iff `file in gc.battery_part_files(part)`.
     Also assert that both sides got their base set from `shard_select.enumerate_base_files`
     (identity of the function object, or equality of the two base sets).
  2. Positive control `test_divergent_enumeration_is_detected`: feed the comparison a stub
     enumeration that drops one file, and assert the mismatch is reported by name.
  3. Manual node-level check (collection only, allowed under C-009). Run once and record the
     counts in the Activity Log. Expect fast + 1/2 + 2/2 to equal the unpartitioned count:
     ```bash
     BASE='tests/architectural -m "not performance and not stress and not timing" --deselect tests/architectural/test_no_legacy_terminology.py --deselect tests/architectural/test_layer_rules.py --deselect tests/architectural/test_pyproject_shape.py --deselect tests/architectural/test_archive_root_byte_identical.py'
     eval uv run --frozen python -m pytest $BASE --collect-only -q | tail -1
     for p in fast 1/2 2/2; do eval uv run --frozen python -m pytest $BASE -p scripts.ci.battery_partition_plugin --battery-part $p --collect-only -q | tail -1; done
     ```
     A mismatch means an enumeration gap. Stop and fix it with WP05's owner. Do not paper over it.
- **Files**: `tests/architectural/test_battery_partition_proof.py`.
- **Parallel?**: No.
- **Notes**: if the plugin exposes no pure decision helper (D-28 requires hooks to delegate to
  pure helpers ≤ 15 complexity), extract and export it in `scripts/ci/battery_partition_plugin.py`
  (co-owned for exactly this; behaviour-preserving, `mypy --strict` + ruff clean, WP05's plugin
  tests green unchanged) rather than reimplementing it here. This co-ownership is also what keeps
  WP05 → WP06 → WP14 in one execution lane now that WP06 does not touch the registry.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_battery_partition_proof.py -q --durations=5   # must stay well under the 10 s roster budget
# Consumers of _gate_coverage (specific gate files, never the whole directory):
uv run --frozen pytest tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_gate_coverage_runner_prefix.py tests/architectural/test_marker_job_completeness.py \
  tests/architectural/test_fast_tier_marker_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_ci_quality_path_filters.py \
  tests/architectural/test_ruff_format_exclude_ratchet.py -q
uv run --frozen pytest tests/ci/test_battery_partition_plugin.py tests/ci/test_shard_select.py -q   # WP05/WP02 tests stay green
uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/architectural/_gate_coverage.py tests/architectural/test_battery_partition_proof.py
uv run --frozen ruff format --check .
uv run --frozen mypy tests/architectural/test_battery_partition_proof.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

If a consumer test you did not change goes red, check whether it compares `Gate` objects
or depends on `SuiteInvocation` field order. Fix the cause in `_gate_coverage.py`, never in
the consumer.

## Risks & Mitigations

- **`_gate_coverage.py` whole-tree fallback marks legs as duplicates**: handled by
  part-aware `selects`. Proven by the live test after WP12.
- **Pinning-inventory line drift**: regenerate in the same commit and never hand-merge (D-25).
- **Import cost or cycles from `scripts.ci` inside `_gate_coverage`**: lazy imports inside
  the cached helpers.
- **The proof is vacuous on today's router** (one gate): the shape branch is exercised by the
  fixture-workflow controls, and WP12 makes the live family three gates. WP12's reviewer
  re-runs this file, and WP12 T052 removes the transitional one-unpartitioned-gate tolerance.
- **Proof file not yet in the fast roster**: expected until WP14 adds row 33. Do not edit
  the registry here.

## Review Guidance

- Red on the planning base (no `partition` attribute or helpers; the fixture legs overlap),
  green on the tip. Run it yourself on both.
- Every positive control calls the same `partition_violations` the live test calls, and each
  asserts the specific message.
- `parse_pytest_invocation` keeps its 3-tuple, and `Gate`/`SuiteInvocation` gained a
  defaulted last field. No consumer was edited to accommodate the change.
- Part sets come from `shard_select` (one enumeration). There is no second roster or file
  list anywhere (C-010).
- Format exclude: either untouched, or the entry was removed in the same commit as the
  reformat. The inventory was regenerated with an Activity Log rationale (this WP is the first
  inventory regeneration in the mission; its diff holds only this WP's line shifts — no #3143
  row, which is already on the base, D-37).
- The transitional one-unpartitioned-gate branch is isolated and commented for WP12's removal.
- `collect_job_nodeids` on a partitioned gate returns the part's node ids (T024 step 7), also
  under `GITHUB_ACTIONS=true`.
- `.github/ci-module-registry.yml` is untouched (WP14 adds the proof to the roster).
- Any edit to `scripts/ci/battery_partition_plugin.py` only exports an existing loader / pure
  decision helper (no behaviour change; WP05's plugin tests unchanged and green).
- Confirm the implementer ran mypy as well as pytest on the new typed test file and that its
  diagnostics passed.
- **Definition of Done**: FR-004's static proof obligations are met with positive controls.
  The D-24 equality is proven. C-001 is evidenced by the recorded collect-only counts.
  The companions are done.

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
