---
work_package_id: WP15
title: Live cross-job test-set uniqueness
dependencies:
- WP06
- WP12
requirement_refs:
- FR-010
- NFR-004
- SC-004
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T059
- T060
- T061
- T062
- T063
phase: Phase 6 - Duplicate-selection guard
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/_live_uniqueness.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/_live_uniqueness.py
- tests/architectural/test_same_tier_uniqueness.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – Live cross-job test-set uniqueness

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

FR-010 / NFR-004 / SC-004: duplicate per-PR test selections must not creep back. Today the same-tier uniqueness relation is **vacuous** — `_gate_coverage._gate_tier` keys tiers on the job-name prefixes `fast-tests` / `integration-tests`, which no live job carries (R2 F11), and `test_same_tier_uniqueness.py` keeps only synthetic fault-injection tests under a stale "no workflow YAML left to parse" premise. Restore the live half:

1. New sibling module `tests/architectural/_live_uniqueness.py` (D-28 — not in the 2,799-line `_gate_coverage.py`): one real `--collect-only` universe, per-job selection evaluated with pytest's own marker `Expression` through the existing `CompiledGate`, dynamic jobs expanded through the shared selectors (one gate per module row; one gate per battery part), pairwise overlap within a tier.
2. Tiers keyed on **OS family only** (D-14), consuming the OS-family tier model **WP06 provides** in `_gate_coverage.py` (WP06 T024 steps 8–11: `Gate.runs_on`, the splice carrying the delegate's `runs-on`, `os_family`, `gate_os_tier`, `os_tier_shard_counts`) — this WP does not edit `_gate_coverage.py`: module rows run on Python 3.11 (`.python-version` via the warmup action), router/Packs jobs on 3.12 (R2 F8) — an interpreter-keyed tier would put exactly the router-vs-module duplicates in different tiers and hide them. Interpreter diversity stays the nightly matrix's job (#5250).
3. Live assertions restored in `test_same_tier_uniqueness.py` against a reasoned, shrink-only allowlist: every entry has a reason and an issue, must match ≥ 1 live overlapping node (stale fails), and `len(ALLOWLIST) <= _ALLOWLIST_CEILING <= 10` (expected 4).
4. Positive controls: an injected overlapping job is reported; the same overlap inside an allowlisted scope is not; the retired router duplicate shape is reported.
5. `change_triggered` / `NON_CHANGE_TRIGGER_EVENTS` and their helpers are **imported** by `_live_uniqueness.py` from `test_no_duplicate_suite_execution.py`, where they stay (one per-change classifier, C-010). This WP does **not** edit `test_no_duplicate_suite_execution.py` (owned by the router lane: WP08–WP12).
6. Runtime of the new live tests ≤ ~55 s on CI (measured, recorded).
7. This WP does **not** touch the partition proof (`test_battery_partition_proof.py`, WP06) or `test_no_duplicate_suite_execution.py`: the proof's transitional one-unpartitioned-gate branch and WP08's directory-level pre-check are both removed by **post-consolidation orchestrator folds** (tasks.md closeout).

**The red-first is recorded on the merge-base (D-30).** By the time this WP runs, WP08–WP10 have already removed the duplicates, so the restored check is only red against the pre-Mission workflows. You run the new check against the merge-base's `.github/workflows/` and record that red; on the lane tip, the first commit is red too because the allowlist starts empty.

## Context & Constraints

- Mission docs: `spec.md` (FR-010, NFR-004, SC-004, C-009, C-010), `plan.md` (IC-08), `research.md` **D-14, D-20, D-24, D-25, D-28, D-30** (govern) and R2 "FR-010" (F6, F7, F8, F10, F11, allowlist table, cost) plus #5250 / #1868 context (D-34).
- **Depends on WP06** (gate-model partition field + `battery_parts`, the single base-file enumeration via `scripts/ci/shard_select.enumerate_base_files`, D-24, **and the re-keyed OS-family tiers**: `Gate.runs_on`, delegate `runs-on` splice, `os_family`, `gate_os_tier`, `os_tier_shard_counts`) **and WP12** (live `architectural-fast` + `architectural-heavy` 2-leg matrix with `--battery-part`). Before coding, read `tests/architectural/test_battery_partition_proof.py`, `test_gate_os_tier.py` and `_gate_coverage.py` to learn the exact names WP06 landed; consume them — do not re-derive a partition or a tier (C-010). If a tier/partition helper you need is missing from `_gate_coverage.py`, stop and raise it with the orchestrator — do not edit that file.
- Module-row expansion must reuse the shared shard selector's test-dir resolution (`scripts/ci/shard_select.py`, WP01) and the single consumer marker constant (WP01/WP02; today `_CONSUMER_MARKER_EXPR = "not performance and not stress"` at `tests/architectural/test_module_length_agreement.py:111`). It is **not** `gate_selection._canonical_test_mirror` (the `next` row differs). If the selector lacks a public helper you need, stop and raise it — do not write a third resolver.
- `load_gates()` default behaviour must not change (`test_marker_job_completeness`, `test_fast_tier_marker_completeness`, the census rely on it). Expansion is opt-in, inside `_live_uniqueness.py`.
- **Lane split (ownership)**: this WP is its **own lane** — it owns only `_live_uniqueness.py` and `test_same_tier_uniqueness.py`. It does **not** own `_gate_coverage.py` / `test_battery_partition_proof.py` (WP06, lane-a) or `test_no_duplicate_suite_execution.py` (router lane: WP08–WP12) — read and import from them, never edit them. WP08's temporary directory-overlap pre-check and the partition proof's transitional branch are removed by **post-consolidation orchestrator folds** (tasks.md closeout), not here.
- Pinned files (D-20/D-25): this WP edits **no** pinned file (`_gate_coverage.py` is WP06's), so it never regenerates `tests/release/pinning_rule_inventory.json` — run `--check` only and record any delta in the Activity Log for WP19 (tasks.md global rule). `test_same_tier_uniqueness.py` is in `[tool.ruff.format].exclude`: hand-format edits; do not run `ruff format` over it (the ratchet only requires excluded files to exist; dropping an entry is a `pyproject.toml` edit you do not own).
- C-009: never run `pytest tests/architectural` whole or `make test-full`; run the specific files below.

### Current-state anchors (verified 2026-10-01; WP06/WP12 will have edited `_gate_coverage.py` — re-anchor by name; WP06 adds `runs_on`, `os_family`, `gate_os_tier`, `os_tier_shard_counts`)

| Surface | Anchor | Today |
|---|---|---|
| `_gate_coverage.py` | `class Gate` (≈ 289): `workflow, job, shard, paths, ignores, marker_expr, via` | no `runs_on` |
| same | `parse_workflow` (≈ 823) builds a `Gate` per suite invocation, matrix-substituted via `_matrix_includes`/`substitute_matrix` | |
| same | `_FAST_TIER_PREFIX = "fast-tests"`, `_INTEGRATION_TIER_PREFIX = "integration-tests"` (≈ 1999-2000), `_gate_tier` (≈ 2458), `shard_counts_for_test` (≈ 2467), `same_tier_shard_counts` (≈ 2489), `_selected_nodeids` (≈ 2512), `cross_job_disjoint_selection` (≈ 2525) | tiers dead; only consumer of the tier helpers is `test_same_tier_uniqueness.py` |
| same | `collect_universe` (≈ 1842; ~23 s for ~51,500 nodes locally, R2 F7), `collect_job_nodeids` (≈ 1910), `CompiledGate` (≈ 1482; a gate with no paths falls back to the whole tree, narrowed by its marker — so `ci-modules.yml::test` reads as the whole tree with `not performance and not stress`, R2 F10), `path_matches` (`::` entries are node-id prefixes) | |
| `test_same_tier_uniqueness.py` | `_TRIGGER_DISJOINT_FAST_JOBS = frozenset({"fast-tests-corpus"})`, two synthetic tests keyed on `fast-tests-*` job names; docstring "Retired (planning#57) …" | stale premise |
| `test_no_duplicate_suite_execution.py` | `NON_CHANGE_TRIGGER_EVENTS` (≈ 179), `PER_CHANGE_PUSH_FILTERS` (≈ 185), `normalized_triggers` (≈ 333), `push_is_per_change` (≈ 360), `change_triggered` (≈ 374), `enumerate_workflows` (≈ 391) | the per-change classifier; `NON_CHANGE_TRIGGERED_WORKFLOWS` (the reviewed exclusion ledger) stays in the test module |
| Per-change suite jobs (post WP08–WP12) | `ci-modules.yml::test` (a reusable-workflow caller with **no** `runs-on` of its own; `_gate_coverage._splice_local_uses` (≈ :1261) copies only the delegate's `steps`, so the spliced job's `runs-on` is `None` today — the delegate `module-tests.yml` job has `runs-on: ubuntu-24.04`; WP06 T024 step 9 carries it), `ci-router.yml` `terminology`, `layer-rules`, `archive-freeze`, `architectural-fast`, `architectural-heavy` (legs `1/2`, `2/2`), `tests-docs`, `tests-e2e`, `tests-corpus-blocking`; `packs.yml` `built-in-pack-manifest`, `built-in-corpus-suite`, `internal-packaging-safety`; `ci-windows.yml::windows-critical` (`runs-on: windows-latest`) | `module-tests.yml` is `workflow_call`-only and `release.yml` tags-only push → excluded by `change_triggered` |
| Merge-base | `git merge-base HEAD main` = `956ed5e8d8` at planning time (in this checkout the upstream remote is `skupstream`) | carries router `tests-consolidation`, `tests-status`, `tests-cli`, `tests-corpus` |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T059 – Red-first on the merge-base; red on the lane tip with an empty allowlist

- **Purpose**: Prove FR-010 bites on the very duplicates the Mission removed (FR-010 "no-op passable: no"), even though they are gone from the lane tip.
- **Steps**:
  1. First commit: `tests/architectural/_live_uniqueness.py` skeleton (T060 API with a `main()` CLI) and the live tests in `test_same_tier_uniqueness.py` (T062) with `ALLOWLIST: tuple[OverlapAllowance, ...] = ()`. Running `test_no_per_change_overlap_outside_the_allowlist` on the lane tip is **red** — it reports the legitimate overlap families (expected: Packs corpus × `charter` row, Packs corpus × `glossary` row, Packs corpus × battery family, Packs pack-manifest × battery family).
  2. Merge-base evidence, using the CLI's injectable workflows dir:
     ```bash
     MB=$(git merge-base HEAD main)            # 956ed5e8d8 at planning time
     WF=$(mktemp -d)
     git archive "$MB" .github | tar -x -C "$WF"     # the WHOLE .github: splicing reads .github/actions (and the registry) relative to the workflows dir
     uv run --frozen python -m tests.architectural._live_uniqueness --workflows-dir "$WF/.github/workflows" --summary
     ```
     Archive `.github` whole, not only `.github/workflows`: `_splice_local_uses` resolves
     composite actions at `workflows_dir.parent / "actions"`, so a workflows-only archive
     silently drops the spliced `warmup`-style steps from the merge-base model.
     Expected (R2 F6, measured on the pre-Mission tree): router `tests-cli` × `ci-modules.yml::test[cli]` ≈ 889, `tests-status` × `[status]` ≈ 1,311, `tests-consolidation` × `[consolidation]` ≈ 1,460, `tests-corpus` × Packs corpus ≈ 1,542, plus corpus × `charter`/`glossary`/battery and pack-manifest × corpus (4). On the merge-base the battery is one unpartitioned `architectural-heavy` gate — the expansion must accept a battery gate without a partition flag and treat it as a plain gate.
  3. Paste the CLI summary (pairs + counts) into the Activity Log and the PR body as the FR-010 red-first evidence (C-011).
- **Files**: `tests/architectural/_live_uniqueness.py` (new), `tests/architectural/test_same_tier_uniqueness.py`.
- **Parallel?**: No — first commit.
- **Notes**: Do not pin merge-base counts in a test (history-dependent). The permanent twin of this red is T062's planted-retired-job control.

### Subtask T060 – `_live_uniqueness.py`: collection, per-job filter, expansion, pairwise overlap

- **Purpose**: One extension of the existing selection engine (D-044: `CompiledGate` / `_selected_nodeids`), no new authority.
- **Steps**:
  1. Types (frozen dataclasses, `__all__` declared, `mypy --strict` clean, every function ≤ 15 complexity):
     ```python
     JobKey = tuple[str, str, str | None]          # (workflow, job, row-or-leg)
     @dataclass(frozen=True)
     class LiveJob:
         key: JobKey
         tier: str                                  # OS family: "linux" | "windows" | "macos"
         family: str                                # e.g. "battery" for fast + legs, else the job label
         gates: tuple[gc.Gate, ...]
     @dataclass(frozen=True)
     class OverlapAllowance:
         job_a: str                                 # label, e.g. "packs.yml::built-in-corpus-suite"
         job_b_family: str                          # label or family, e.g. "ci-modules.yml::test[charter]", "battery"
         scope_marker: str | None                   # e.g. "corpus"
         scope_files: frozenset[str]                # relpaths; exactly one of marker/files is set
         reason: str
         issue: str
     ```
  2. `per_change_jobs(workflows_dir: Path = gc.WORKFLOWS_DIR, registry_path: Path = …) -> list[LiveJob]`: enumerate workflows with the imported `enumerate_workflows` + `change_triggered` (T063; they stay in `test_no_duplicate_suite_execution.py`), `gc.parse_workflow` each, group gates by `(workflow, job, shard/leg)`. Replace the whole-tree `ci-modules.yml::test` gate with one `LiveJob` per registry row (`paths` = the shared selector's resolved test dirs, `marker_expr` = the single consumer marker constant); replace each battery leg / the fast job with the WP06 partition-evaluated selection (family `"battery"`). Fail closed: a per-change suite gate whose tier cannot be resolved raises (never silently skipped).
  3. `selected_by_job(jobs, universe) -> dict[JobKey, frozenset[str]]` using `gc._selected_nodeids` once per job (O(jobs × N), not O(pairs × N); ~2 s over ~34 jobs per R2 F7).
  4. `pairwise_overlaps(jobs, selected) -> dict[tuple[JobKey, JobKey], frozenset[str]]`: same-tier pairs only, including pairs inside the battery family (they must be empty — the partition proof says so; a non-empty one is a real finding, never allowlisted).
  5. `uncovered_overlaps(overlaps, allowlist, records_by_nodeid) -> dict[...]` and `stale_allowances(overlaps, allowlist, records_by_nodeid) -> list[OverlapAllowance]`: a node is covered when an allowance names one side (`job_a`) and the other side's label or family (`job_b_family`) and the node's markers contain `scope_marker` or its relpath is in `scope_files`.
  6. `main(argv)`: `--workflows-dir`, `--summary` (prints `pair -> count` lines, exit 1 when any uncovered overlap exists). Invoked as `python -m tests.architectural._live_uniqueness` (module mode, so no bare-script import guard applies).
- **Files**: `tests/architectural/_live_uniqueness.py`.
- **Parallel?**: No.
- **Notes**: `_gate_coverage.cross_job_disjoint_selection` stays as the two-job primitive; `analyze()` is unchanged (its duplicate count stays report-only).

### Subtask T061 – Consume WP06's OS-family tiers; re-target the synthetic tests

- **Purpose**: Make the same-tier relation non-vacuous (R2 F11) without hiding the duplicates behind an interpreter split (D-14, R2 F8). **WP06 provides the `_gate_coverage.py` side** (WP06 T024 steps 8–11: `Gate.runs_on`, the splice carrying the delegate's `runs-on` with its unit test in `test_gate_os_tier.py`, `os_family`, `gate_os_tier`, `os_tier_shard_counts`); this subtask only consumes it.
- **Steps**:
  1. `_live_uniqueness.py` tiers every `LiveJob` with `gc.gate_os_tier` (fail closed on `None` for a per-change suite gate, T060 step 2). Confirm on the live tree that every expanded `ci-modules.yml::test` row is tiered `linux` (WP06's splice carry makes this hold; if it does not, stop and raise it with the orchestrator — do not patch `_gate_coverage.py`).
  2. Re-target the two synthetic tests in `test_same_tier_uniqueness.py` onto WP06's `gc.os_tier_shard_counts`, tiering by `runs_on` (`"ubuntu-24.04"` on both synthetic gates) rather than `fast-tests-*` names, keeping their meaning: a planted double-run is flagged; the scoped exemption does not become a blanket pass. Replace the `_TRIGGER_DISJOINT_FAST_JOBS` carve-out with the allowlist mechanism (T062). After this step the file no longer references the legacy `_gate_tier` / `shard_counts_for_test` / `same_tier_shard_counts` / `count_fast_shards` — that leaves them dead for the post-consolidation orchestrator fold (tasks.md closeout) to delete; do not delete them here (not your file).
  3. Add `test_interpreter_split_does_not_split_the_tier`: two synthetic gates, same `runs_on` family, one standing for a 3.11 module row and one for a 3.12 router job, selecting the same node — flagged (pins D-14).
- **Files**: `tests/architectural/_live_uniqueness.py`, `tests/architectural/test_same_tier_uniqueness.py`.
- **Parallel?**: Can proceed alongside T060 after T059.
- **Notes**: `_gate_coverage.py` is not edited by this WP (no pinning-inventory regeneration).

### Subtask T062 – Restore live assertions, reasoned allowlist, positive controls

- **Purpose**: FR-010's actual guard plus non-vacuity (Standing Order #5: architectural gates carry positive controls).
- **Steps**:
  1. Rewrite the module docstring of `test_same_tier_uniqueness.py`: FR-010 / NFR-004 / SC-004, OS-family tiers (D-14), one universe + model filtering (D-14 cost), the allowlist rules, and that the earlier "no workflow YAML left to parse" premise was stale.
  2. Module-scoped fixtures: `universe = gc.collect_universe()`, `jobs = per_change_jobs()`, `selected = selected_by_job(jobs, universe)`.
  3. Allowlist (start from R2's measured table; reconcile against what the live run actually reports — the battery roster may move a corpus ratchet into `architectural-fast`, which the `"battery"` family absorbs):
     | job_a | job_b_family | scope | reason | issue |
     |---|---|---|---|---|
     | `packs.yml::built-in-corpus-suite` | `ci-modules.yml::test[charter]` | marker `corpus` | corpus-reader overlay: Packs fires on pack/kitty-specs/.kittify data diffs and unmatched src, the row on `src/charter/**`; re-judges readers against changed data | #3315 |
     | `packs.yml::built-in-corpus-suite` | `ci-modules.yml::test[glossary]` | marker `corpus` | same overlay (`tests/glossary/test_gate_terms.py`) | #3315 |
     | `packs.yml::built-in-corpus-suite` | `battery` | files `tests/architectural/test_bare_prose_corpus_ratchet.py`, `tests/architectural/test_transition_guard_shrink_only.py` | corpus ratchets must run on data-only diffs; the battery is code-scoped and removing them from it would break C-001 | #3008 |
     | `packs.yml::built-in-pack-manifest` | `battery` | files `tests/architectural/test_pack_manifest_no_author_edit.py` | blocking pack-manifest guard on built-in data diffs; the battery copy covers code diffs (C-001) | #5510 |

     `_ALLOWLIST_CEILING = 4` (ratchet constant; may only be lowered; hard cap 10).
  4. Live tests: `test_no_per_change_overlap_outside_the_allowlist` (message lists pair, count, first 10 node-ids); `test_allowlist_entries_are_reasoned_live_and_capped` (non-empty reason/issue, exactly one scope kind, no stale entry, `len(ALLOWLIST) <= _ALLOWLIST_CEILING <= 10`); `test_per_change_job_set_is_non_vacuous` (≥ 1 module row, ≥ 1 battery gate, ≥ 1 Packs job, `ci-modules.yml::test` expanded into exactly as many jobs as registry rows, every job tiered); `test_modelled_selection_matches_real_collect_for_anchor_jobs` (fidelity anchor: for `terminology`, `layer-rules`, `archive-freeze`, `tests-corpus-blocking`, `built-in-pack-manifest`, `internal-packaging-safety`, modelled selection == `gc.collect_job_nodeids(gate)`; ~5–10 s).
  5. Positive controls (synthetic, no real workflow mutation): `test_planted_overlap_outside_allowlist_is_reported` (a third Linux job duplicating one module row's dir is flagged; the same overlap restricted to an allowlisted marker scope is not); `test_retired_router_duplicate_shape_is_reported` (a fixture router job `tests-cli` running `pytest tests/cli -q`, as on the merge-base, against the expanded `cli` row is flagged — the permanent twin of T059's merge-base red).
  6. **Do not touch the partition proof or WP08's structural pre-check.** The partition proof's
     transitional one-unpartitioned-gate branch (`test_battery_partition_proof.py`, WP06) and
     WP08's directory-level pre-check in `test_no_duplicate_suite_execution.py`
     (`module_owned_test_dirs`, `router_dirs_owned_by_a_module`,
     `test_router_runs_no_module_owned_test_tree`, `test_router_module_tree_guard_flags_a_planted_job`)
     are both removed by **post-consolidation orchestrator folds** (tasks.md closeout), applied on
     the mission branch after lane consolidation. Step 5's `test_retired_router_duplicate_shape_is_reported`
     is the pre-check's permanent node-level twin: note the subsumption in the Activity Log so the
     fold can cite it.
  7. All green on the lane tip.
- **Files**: `tests/architectural/test_same_tier_uniqueness.py`.
- **Parallel?**: No.
- **Notes**: Per-node allowlist entries are rejected (R2): pair × scope keeps the cap meaningful and still fails on a new overlap shape.

### Subtask T063 – Reuse the per-change classifier; check pinning inventory; measure runtime

- **Purpose**: One per-change classifier (C-010), pinned-file hygiene (D-25), NFR-004 cost evidence.
- **Steps**:
  1. **Import, do not move**: `_live_uniqueness.py` imports `NON_CHANGE_TRIGGER_EVENTS`, `change_triggered`, `enumerate_workflows` (and any other helper it needs from that family) from `tests.architectural.test_no_duplicate_suite_execution`, where they stay verbatim. That file is owned by the router lane (WP08–WP12); this WP never edits it, so every existing test there runs unchanged. If importing a test module into a helper turns out to be unworkable (e.g. an import cycle or collection side effect), stop and raise it with the orchestrator — do not copy the classifier (C-010: one per-change classifier).
  2. Pinning inventory: this WP edits no pinned file (`_gate_coverage.py` is WP06's), so it does **not** regenerate (tasks.md global rule). Run `uv run --frozen python scripts/ci/derive_pinning_inventory.py --check` and `uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q`; confirm your diff adds no delta and record any delta in the Activity Log for WP19.
  3. Runtime: `uv run --frozen pytest tests/architectural/test_same_tier_uniqueness.py -q --durations=0` locally; expect ~25–35 s (universe ~23 s + filtering ~2 s + anchors ~5–10 s). Record it; budget ≤ ~55 s on CI (D-14). The file's duration enters the battery timings through WP05's junit capture; until refreshed, the selector's median weight places it.
- **Files**: `tests/architectural/_live_uniqueness.py`.
- **Parallel?**: No.
- **Notes**: Import direction: `_live_uniqueness` imports `_gate_coverage` and `test_no_duplicate_suite_execution`; the ledger test must **not** import `_live_uniqueness` — no cycle.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_same_tier_uniqueness.py -q --durations=0
uv run --frozen pytest tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_battery_partition_proof.py tests/architectural/test_gate_os_tier.py tests/architectural/test_ci_collection_completeness.py tests/architectural/test_marker_job_completeness.py tests/architectural/test_ci_integrity_oracle_nonvacuous.py -q
uv run --frozen python -m tests.architectural._live_uniqueness --summary
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check && uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/architectural/_live_uniqueness.py tests/architectural/test_same_tier_uniqueness.py
uv run --frozen ruff format --check tests/architectural/_live_uniqueness.py
uv run --frozen mypy --strict tests/architectural/_live_uniqueness.py
```

`test_marker_job_completeness.py` and `test_ci_collection_completeness.py` exercise `load_gates()` / `collect_universe()` and prove the default model did not change. Never run `tests/architectural` whole or `make test-full`.

## Risks & Mitigations

- **Whole-tree fallback mis-read as duplicates** (R2 F10) — `ci-modules.yml::test` and the battery legs must be replaced by expanded jobs before comparison; `test_per_change_job_set_is_non_vacuous` pins the expansion.
- **Second partition/resolver authority** — consume WP01/WP06 surfaces only (C-010); stop and raise if missing.
- **Runtime creep inside the battery** — one universe per module; no per-job real collection except the small anchor set.
- **Tier fail-open** — an untiered per-change gate raises instead of being dropped.
- **Allowlist drift** — stale entries fail; ceiling only lowers.
- **Pinning inventory** — this WP edits no pinned file; `--check` only, never regenerate or hand-merge.
- **Missing WP06 surface** — if `gate_os_tier` / `os_tier_shard_counts` / the splice carry is absent or wrong, stop and raise it; never edit `_gate_coverage.py` from this lane.

## Review Guidance

- Merge-base red recorded (pairs and counts), and the lane-tip first commit was red with an empty allowlist.
- Tiers are OS family via WP06's `gc.gate_os_tier` / `gc.os_tier_shard_counts`; no interpreter split;
  `test_same_tier_uniqueness.py` no longer references the legacy prefix-tier helpers (their
  deletion is a post-consolidation orchestrator fold); every expanded `ci-modules.yml::test` row
  is tiered `linux`; the merge-base archive was `.github` whole.
- The diff touches only `_live_uniqueness.py` and `test_same_tier_uniqueness.py`:
  `_gate_coverage.py`, `test_battery_partition_proof.py` and `test_no_duplicate_suite_execution.py`
  are untouched (the transitional branch and WP08's T034 directory guard are removed by
  post-consolidation orchestrator folds, tasks.md closeout); the subsumption is noted in the
  Activity Log.
- Module rows and battery parts expanded through WP01/WP06 surfaces, not re-derived; `load_gates()` default unchanged.
- Allowlist: ≤ `_ALLOWLIST_CEILING` (4) ≤ 10, every entry reasoned with an issue, none stale; battery-family internal pairs never allowlisted.
- Positive controls present and meaningful (planted overlap, allowlisted twin, retired router shape).
- `change_triggered` family imported (not moved, not copied); ledger tests unchanged and green; pinning inventory `--check` shows no delta from this WP.
- Measured runtime recorded.
- Definition of Done: FR-010 (live check over real collection, OS-family tiers, reasoned capped allowlist), NFR-004 (0 overlaps outside the allowlist on the final tree; allowlist ≤ 10), SC-004.

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

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
