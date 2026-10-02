---
work_package_id: WP09
title: Packs is the sole (advisory) corpus owner
dependencies:
- WP08
requirement_refs:
- FR-009
- FR-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 4 - CI path routing and duplicate removal
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- scripts/ci/corpus_select.py
- tests/ci/test_corpus_select.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/corpus_select.py
- tests/ci/test_corpus_select.py
- .github/workflows/packs.yml
- .github/workflows/ci-router.yml
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/architectural/test_workflow_coherence.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
- tests/ci/test_ci_module_wiring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Packs is the sole (advisory) corpus owner

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

FR-009: the corpus suite (`pytest -m "corpus and not windows_ci"`, ~1,540 node-ids) runs twice per corpus-touching PR today — router `tests (corpus)` and Packs `built-in / -m corpus suite` select identical node-ids (R2 F6: 1,542). Make Packs the **only** owner, with a trigger that is a superset of the router's, explicitly **advisory** (operator-accepted downgrade, DM 01M3V027T8WF0CR3D1B8VY2VZ0), with the dead coverage target fixed and four workers (FR-002).

Done means:

1. `scripts/ci/corpus_select.py` decides "corpus selected" through the single gate-selection authority (`gate_selection.select_gates`) — no glob copy in `packs.yml` (C-003, #2476).
2. Packs `changes` exports a `corpus` output computed by that helper, with the pre-`uv sync` pattern `ci-modules.yml` uses; it folds `full` mode and `push`.
3. The Packs corpus job runs on `built_in || corpus`, is job-level `continue-on-error: true`, is removed from `packs-gate.needs`, runs `-n 4` without `-q`, uses `--cov=charter.offering`, deselects the pack-manifest test, and emits an `::warning::` on failure.
4. Router `tests (corpus)` (`tests-corpus`) is deleted with its `router-gate.needs` entry and ledger row. The router `corpus` filter group and output **stay** (consumed by `prose-scan`, by `corpus_select.py`, and — from WP10 — by `tests (corpus-blocking)`).
5. The blocking pack-manifest guard (`built-in-pack-manifest`) fires on `built_in || corpus`, so deselecting it from the advisory corpus run weakens nothing.
6. Red-first tests: superset proof, `corpus_select` truth table, advisory-shape pin, live `--cov` target check.

## Context & Constraints

- Mission docs: `spec.md` (FR-009, FR-002, C-001 scoped exception, C-003, C-008), `plan.md` (IC-07), `research.md` decision log **D-05, D-12 as amended by D-22, D-13, D-20, D-25, D-28, D-34 (#4368)** and R2 "FR-009"; `contracts/router-two-authority-amendment.md` A3.
- **D-22 amends D-12:** `corpus` does **not** become a permanently ungated group — WP10 re-gates it with a small required router job. This WP therefore adds `corpus` to `_DELIBERATELY_UNGATED_FILTER_GROUPS` **only transitionally** (see T041) so the lane tip stays green; WP10 removes it.
- Helper name is `scripts/ci/corpus_select.py` (D-28), not `packs_corpus_selection.py` (the name R2 used).
- `packs gate` is not a required check (ADR 2026-09-23-1), but `ci-fleet-verdict` reads the **Packs workflow-run conclusion** (`scripts/ci/fleet_verdict.py` `PR_WORKFLOWS`, `classify`): only job-level `continue-on-error` keeps a red corpus run from turning the fleet verdict red (R2 F13).
- Workflow-invoked scripts must survive a bare `python3 scripts/ci/<x>.py --help` run (`tests/ci/test_workflow_script_import_guard.py`): resolve the repo root from `__file__` and insert it on `sys.path` before `from scripts.ci.gate_selection import …` — copy the guard from `scripts/ci/stale_running_sweep.py` (lines ≈ 38-42, with its narrow `# noqa: E402` rationale).
- **WP18 later adds a skip-if-green step to Packs `changes`** — keep your step self-contained and named; do not restructure the job.
- Lane discipline: `uv run --frozen …`; never `git stash`.

### Current-state anchors (verified 2026-10-01; router lines shift after WP07/WP08 — anchor by name)

| Surface | Anchor | Today |
|---|---|---|
| Router trigger for corpus | `changes.outputs.corpus` = `(inputs.mode == 'full' \|\| steps.unmatched.outputs.unmatched == 'true') && 'true' \|\| steps.filter.outputs.corpus`; filter group `corpus:` = `packs/**`, `kitty-specs/**/spec.md`, `kitty-specs/**/plan.md`, `kitty-specs/**/tasks/**`, `kitty-specs/**/contracts/**`, `kitty-specs/**/acceptance-matrix.json`, `.kittify/charter/**`, `.kittify/glossaries/**`, `.kittify/doctrine/**` | Fires on those globs **∪ any unmatched `src/**` (C-008 fan-out, #4368) ∪ dispatch `mode=full`**. Push to `main` is diff-based. |
| Router job `tests-corpus` | `needs: [changes]`, `if: ${{ needs.changes.outputs.corpus == 'true' }}`, `fetch-depth: 0`, `uv run --frozen pytest -m "corpus and not windows_ci" -q -n auto --dist loadfile` | to delete |
| `ci-router.yml` `prose-scan` | `_doc_globs = tuple(_router.filters.get("docs", ())) + tuple(_router.filters.get("corpus", ()))` | live consumer of the `corpus` group — keep the group |
| `packs.yml` `changes` | `outputs.built_in`/`internal` = `(inputs.mode == 'full' \|\| github.event_name == 'push') && 'true' \|\| steps.filter.outputs.<g>`; checkout without `fetch-depth`; dorny `built_in` = `packs/built-in/**`, `tests/doctrine/**`, the pack-manifest test, `.kittify/command-skills-manifest.json`, two snapshot dirs, `src/charter/offering/{schemas,drg}/**` | Misses `packs/internal/**`, the five `kitty-specs` leaves, the three `.kittify` roots and the unmatched-src fan-out (R2 F3); push already forces everything |
| `packs.yml` `built-in-pack-manifest` | `if: ${{ needs.changes.outputs.built_in == 'true' }}` | runs `pytest tests/architectural/test_pack_manifest_no_author_edit.py -q` |
| `packs.yml` `built-in-corpus-suite` | name `built-in / -m corpus suite (--cov=src/doctrine)`; `uv run --frozen pytest -m "corpus and not windows_ci" -n auto --dist loadfile --cov=src/doctrine --cov-report=term-missing -q` | `src/doctrine` is dead (absorbed into `src/charter/offering/`); verified it is the **only** dead literal `--cov` target across `load_workflow_models()` |
| `packs.yml` `packs-gate.needs` | includes `built-in-corpus-suite` | |
| Pre-sync pattern | `ci-modules.yml` `generate-matrix`: checkout `fetch-depth: 0` → `pip install --quiet --disable-pip-version-check --only-binary=:all: "pyyaml==6.0.2"` → `git diff --name-only "$base" "$HEAD_SHA"` with `base` = `github.event.pull_request.base.sha` (PR) or `github.event.before` (push), `HEAD_SHA: ${{ github.sha }}`, fail closed on empty/zero base or a git error → `python3` with `PYTHONPATH: ${{ github.workspace }}` importing `scripts.ci.gate_selection`; the diff list is passed through an env var, not stdin | copy this shape |
| `test_workflow_coherence.py` | `_DELIBERATELY_UNGATED_FILTER_GROUPS = frozenset({"any_src", "ci"})` (≈ 309); `test_every_restored_filter_group_is_consumed_live` | deleting `tests-corpus` leaves router `corpus` unconsumed until WP10 |
| `test_ci_corpus_trigger_completeness.py` | `_CI_QUALITY` + `test_corpus_changes_trigger_reduced_ci_quality_live` (reads `ci-quality.yml`), `_CORPUS_GLOBS`/`_CORPUS_DATA_ROOTS` hand lists | `_CORPUS_GLOBS` carries `.kittify/release/downstream-verified.json`, which is **not tracked** (`git ls-files .kittify/release/` → only `shared-package-compatibility.json`) and not in the router group |
| `test_no_duplicate_suite_execution.py` | ledger rows `("ci-router.yml", "tests-corpus")`, `("packs.yml", "built-in-corpus-suite")` | |

**Out-of-map companions (one-line rationale each):** `tests/ci/test_ci_module_wiring.py` (line `assert jobs["tests-corpus"]["needs"] == ["changes"]` in the prose-only golden must go); `tests/release/pinning_rule_inventory.json` (regenerate — `test_workflow_coherence.py`, `test_ci_corpus_trigger_completeness.py` and `test_no_duplicate_suite_execution.py` all carry pinned rules). Do **not** edit `.github/ci-module-registry.yml` (its `tests/contract` out-of-matrix reason still names "ci-router.yml's marker-selected 'tests (corpus)' job"): that file belongs to the registry lane (WP03/WP05/WP14) — record the stale prose in the Activity Log for WP19.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T038 – Red-first: superset proof, truth table, advisory pin, live cov targets

- **Purpose**: Encode FR-009's acceptance before any workflow edit; every test below is red today.
- **Steps**:
  1. `tests/ci/test_corpus_select.py` (new, `pytestmark = pytest.mark.fast`), importing `from scripts.ci.corpus_select import corpus_selected, decide` at module top (red today: `ModuleNotFoundError` — never `importorskip`). Truth table for `corpus_selected(paths, router=load_router(), mode=...)`:
     - True: `packs/built-in/missions/x.md`, `packs/internal/x.yaml`, `kitty-specs/m/spec.md`, `kitty-specs/m/plan.md`, `kitty-specs/m/tasks/WP01.md`, `kitty-specs/m/contracts/c.md`, `kitty-specs/m/acceptance-matrix.json`, `.kittify/charter/charter.md`, `.kittify/glossaries/g.yaml`, `.kittify/doctrine/d.yaml`, `src/specify_cli/__unmapped_probe__/x.py` (unmatched-src fan-out), and `docs/x.md` with `mode="full"`.
     - False: `src/specify_cli/consolidation/x.py`, `docs/x.md`, `kitty-specs/m/status.events.jsonl`, `.github/workflows/ci-router.yml`.
     - `decide(None, ...)` (diff unavailable) → selected True with a "fail-closed" reason; `decide([...], event_name="push")` → True.
     - `test_corpus_group_is_live_and_feeds_prose_scan_and_packs` — the pin that makes the transitional exemption in T041 safe: the router still has a non-empty `corpus` filter group, `changes.outputs` still exports `corpus`, `prose-scan`'s run text still reads `filters.get("corpus"`, and `corpus_select` consumes it.
  2. `tests/architectural/test_ci_corpus_trigger_completeness.py` (format-excluded — hand-format your additions; never run `ruff format` on the file):
     - `test_packs_corpus_lane_covers_every_router_corpus_trigger`: for **each glob of the live router `corpus` group** (from `scripts.ci.gate_selection.load_router().filters["corpus"]`, never a hand copy) build a probe path (`**/` → `m/`, trailing `**` → `probe.md`), assert the router side selects it (`"corpus" in select_gates([p]).matched_groups`) and `corpus_selected([p])` is True; same for an unmatched-src probe and `mode="full"`; then assert the Packs wiring: `jobs["changes"]["outputs"]["corpus"]` folds `inputs.mode == 'full'` and `github.event_name == 'push'` over `steps.corpus.outputs.selected`, and the corpus job `if:` references `needs.changes.outputs.corpus`.
     - `test_packs_corpus_lane_is_advisory_and_sole_owner`: Packs corpus job has `continue-on-error: true`, is absent from `packs-gate.needs`, and no `ci-router.yml` gate (via `gc.parse_workflow`) selects the `corpus` marker **without positional paths** (a whole-tree corpus run in the router is the duplicate; WP10's node-level job has explicit paths).
  3. `tests/architectural/test_workflow_coherence.py` (format-excluded — hand-format): `test_every_literal_cov_target_is_live` over `gc.load_workflow_models()` (`_gate_coverage.py` ≈ 2155): for each `model.cov_targets` value, skip targets containing `$`, require `Path(gc.cov_target_repo_path(t)).exists()` (relative to `gc.REPO_ROOT`). Red today only on `packs.yml::built-in-corpus-suite` `src/doctrine` (verified).
  4. Run all three; record the red in the Activity Log.
- **Files**: `tests/ci/test_corpus_select.py` (new), `tests/architectural/test_ci_corpus_trigger_completeness.py`, `tests/architectural/test_workflow_coherence.py`.
- **Parallel?**: No — first commit.
- **Notes**: Keep `_CI_QUALITY` and `test_corpus_changes_trigger_reduced_ci_quality_live` **intact** — they are rows in `tests/release/pinning_rule_inventory.json`; deleting or renaming them makes the inventory "greener by deletion" and needs a disposition change in `scripts/ci/derive_pinning_inventory.py`, which is out of scope. Add, do not rename.

### Subtask T039 – Implement `corpus_select.py` and wire Packs `changes`

- **Purpose**: One encoding of the corpus trigger (C-003): Packs asks the router's own parser.
- **Steps**:
  1. `scripts/ci/corpus_select.py` (stdlib + PyYAML via `gate_selection`; `mypy --strict` clean; every function ≤ 15 complexity; `__all__` declared):
     ```python
     def corpus_selected(paths: Sequence[str], *, router: Router, mode: str = "pr") -> bool:
         sel = select_gates(paths, router=router, mode=mode)
         return mode == "full" or sel.unmatched_src or "corpus" in sel.matched_groups
     def decide(changed: Sequence[str] | None, *, router: Router, mode: str, event_name: str) -> tuple[bool, str]:
         """(selected, reason). None == diff unavailable -> fail closed True; push -> True."""
     def main(argv: Sequence[str] | None = None) -> int:
         """argparse: --mode, --event. Reads CHANGED_FILES (JSON array) and CHANGED_OUTCOME
         ('success' or anything else -> None) from env; writes `selected=true|false` to
         $GITHUB_OUTPUT when set; prints `corpus selection: <bool> (<reason>)`."""
     ```
     Module docstring states the contract and that the router `changes.outputs.corpus` fold is the predicate being mirrored (FR-009, #4368 fan-out).
  2. `packs.yml` `changes`: checkout gains `with: fetch-depth: 0`; after the dorny step add two steps — `Install PyYAML (corpus selection only, no editable install)` (the exact `pip install` line from `ci-modules.yml`) and `Corpus selection via the single gate-selection authority (FR-009)` (`id: corpus`), which computes `git diff --name-only "$BASE_SHA" "$HEAD_SHA"` for `pull_request` only (env `EVENT_NAME`, `BASE_SHA: ${{ github.event.pull_request.base.sha }}`, `HEAD_SHA: ${{ github.sha }}`, `MODE: ${{ inputs.mode || 'pr' }}`), passes the list as a JSON array via `CHANGED_FILES`/`CHANGED_OUTCOME` env vars, and runs `python3 scripts/ci/corpus_select.py --mode "$MODE" --event "$EVENT_NAME"`. Any missing base or git error → outcome ≠ success → helper fails closed to `true`.
  3. Add the output: `corpus: ${{ (inputs.mode == 'full' || github.event_name == 'push') && 'true' || steps.corpus.outputs.selected }}`.
  4. Do **not** add a dorny `corpus` group to `packs.yml` (that would be the second encoding, and `test_every_restored_filter_group_is_consumed_live` would also start policing it).
  5. `tests/ci/test_corpus_select.py` green; `uv run --frozen pytest tests/ci/test_workflow_script_import_guard.py -q` green (the new script is now workflow-invoked and imports `scripts.*`).
- **Files**: `scripts/ci/corpus_select.py` (new), `.github/workflows/packs.yml`.
- **Parallel?**: Can run alongside T042 once T038 is committed.
- **Notes**: Do not apply the prose-only reduction: the router's `corpus` output is not prose-subtracted either. A command line must not start with `$VAR` / `${{ … }}` as its command word (`test_no_change_triggered_step_hides_its_command_behind_a_reference`).

### Subtask T040 – Packs corpus job: advisory, four workers, live coverage target

- **Purpose**: Make "advisory" true on all three verdict surfaces (PR check, `packs gate`, fleet verdict) and apply FR-002 to the corpus lane.
- **Steps**:
  1. `built-in-corpus-suite`:
     - `name: built-in / -m corpus suite (advisory)`
     - `if: ${{ needs.changes.outputs.built_in == 'true' || needs.changes.outputs.corpus == 'true' }}`
     - job-level `continue-on-error: true` with a comment: advisory per FR-009 / operator DM 01M3V027T8WF0CR3D1B8VY2VZ0; fleet verdict reads the Packs run conclusion.
     - command: `uv run --frozen pytest -m "corpus and not windows_ci" -n 4 --dist loadfile --deselect tests/architectural/test_pack_manifest_no_author_edit.py --cov=charter.offering --cov-report=term-missing` — literal `-n 4` (CI only, D-05), **no `-q`** so the log shows `created: 4/4 workers`; keep the exit-5 floor comment (#3008), `fetch-depth: 0`, and the `__pycache__` sweep step byte-identical (`tests/architectural/test_pycache_sweep.py`).
     - final step `- name: Advisory corpus failure notice` with `if: failure()` running `echo "::warning::corpus suite failed (advisory, FR-009) -- this does not block packs gate or router gate"`.
  2. `packs-gate.needs`: remove `built-in-corpus-suite` (excluding it is unambiguous; do not stake the gate on how `needs.<job>.result` reports under `continue-on-error`).
  3. Update the header comment (built-in lane bullet, ≈ lines 21-25): corpus suite is the advisory sole owner, `--cov=charter.offering`, trigger = `built_in ∪ router-derived corpus`.
  4. `test_every_literal_cov_target_is_live` and `test_packs_corpus_lane_is_advisory_and_sole_owner` now green.
- **Files**: `.github/workflows/packs.yml`.
- **Parallel?**: No (same file as T039/T042).
- **Notes**: WP12's worker-policy guard will later assert the literal `-n 4` here; WP10 adds three more `--deselect` flags to this same command.

### Subtask T041 – Delete router `tests (corpus)`; ledger, coherence and completeness companions

- **Purpose**: Remove the duplicate executor and keep every guard honest at this lane tip.
- **Steps**:
  1. `ci-router.yml`: delete job `tests-corpus` and its `router-gate.needs` entry; update the "Non-code shards (data groups)" banner (corpus now runs in Packs; the exit-5 floor note moves with it). Keep the `corpus` filter group and output unchanged.
  2. `test_no_duplicate_suite_execution.py`: delete `("ci-router.yml", "tests-corpus")`; reword `("packs.yml", "built-in-corpus-suite")` to "Packs lane: the corpus suite — sole owner, advisory (job-level continue-on-error, outside packs-gate.needs), FR-009."
  3. `test_workflow_coherence.py`: `_DELIBERATELY_UNGATED_FILTER_GROUPS = frozenset({"any_src", "ci", "corpus"})` with a bullet: "``corpus`` — TRANSITIONAL (D-22): router ``tests (corpus)`` was retired by FR-009; WP10 re-gates the group with ``tests (corpus-blocking)`` and removes this entry. Live consumers meanwhile: ``prose-scan`` and ``scripts/ci/corpus_select.py``, pinned by ``tests/ci/test_corpus_select.py::test_corpus_group_is_live_and_feeds_prose_scan_and_packs``." Update the `test_every_restored_filter_group_is_consumed_live` docstring list.
  4. `test_ci_corpus_trigger_completeness.py`: derive `_CORPUS_GLOBS` from the live router `corpus` group (one source); drop the dead `.kittify/release/downstream-verified.json` entry from `_CORPUS_DATA_ROOTS` with a one-line note (not a tracked file; adding it to the router would red `test_every_restored_filter_glob_is_live`). Fix stale docstring prose naming `fast-tests-corpus`. `_CORPUS_MARKED_MODULES` stays as is.
  5. Out-of-map `tests/ci/test_ci_module_wiring.py`: delete `assert jobs["tests-corpus"]["needs"] == ["changes"]` and adjust the "Explicitly untouched" comment.
  6. Regenerate the pinning inventory (`uv run --frozen python scripts/ci/derive_pinning_inventory.py`, then `--check` and `tests/release/test_pinning_inventory_fresh.py`); if a row comes out with `disposition: null`, you renamed a pinned rule — restore the name instead of editing dispositions.
- **Files**: `.github/workflows/ci-router.yml`, `tests/architectural/test_no_duplicate_suite_execution.py`, `tests/architectural/test_workflow_coherence.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`; out-of-map `tests/ci/test_ci_module_wiring.py`, `tests/release/pinning_rule_inventory.json`.
- **Parallel?**: No.
- **Notes**: `test_dual_mode_contract.py` (needs == all non-gate jobs) must stay green — delete job and needs entry together.

### Subtask T042 – Pack-manifest test: out of the corpus run, blocking job trigger widened

- **Purpose**: Remove the 4-node Packs-internal duplicate (pack-manifest guard × corpus run, same trigger) without weakening the blocking guard.
- **Steps**:
  1. The `--deselect tests/architectural/test_pack_manifest_no_author_edit.py` flag is in T040's command.
  2. `built-in-pack-manifest.if`: `${{ needs.changes.outputs.built_in == 'true' || needs.changes.outputs.corpus == 'true' }}` — the blocking guard now fires on every trigger the advisory corpus lane fires on.
  3. Add to `test_packs_corpus_lane_is_advisory_and_sole_owner` (or a sibling): the pack-manifest job's `if:` references both outputs, and the corpus gate (via `gc.parse_workflow`) carries the deselect in `ignores`.
- **Files**: `.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`.
- **Parallel?**: Yes with T039.
- **Notes**: The pack-manifest test is still also in the battery (code-path trigger); that overlap is FR-010 allowlist entry "Packs pack-manifest × battery family" (WP15).

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_corpus_select.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_ci_module_wiring.py tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py -q
uv run --frozen pytest tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_pycache_sweep.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_coverage_artefact_contract.py -q
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check && uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check scripts/ci/corpus_select.py tests/ci/test_corpus_select.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py
uv run --frozen ruff format --check scripts/ci/corpus_select.py tests/ci/test_corpus_select.py tests/architectural/test_no_duplicate_suite_execution.py
uv run --frozen mypy --strict scripts/ci/corpus_select.py tests/ci/test_corpus_select.py
python3 scripts/ci/corpus_select.py --help   # from a tmp cwd, no PYTHONPATH
```

Do not run the corpus suite or `tests/architectural` whole locally. Evidence comes from the PR's own Packs run (record its run ID and the `created: 4/4 workers` line in the Activity Log).

## Risks & Mitigations

- **Transitional ungated `corpus` outlives WP10** — WP10's red-first test asserts `corpus` is not in the exemption set; reviewers of WP10 check the entry is gone.
- **Fleet verdict red on an advisory failure** — job-level `continue-on-error`, not step-level.
- **Unmatched-src fan-out silently dropped** — truth-table row and superset probe pin it.
- **Corpus ratchets on data-only diffs become advisory** (`test_bare_prose_corpus_ratchet`, `test_transition_guard_shrink_only` run blocking only through the code-scoped battery) — this is inside the operator-accepted FR-009 downgrade; the orphaned corpus tests with no other blocking home get WP10's job.
- **Pinning inventory churn** — add tests, never rename pinned rules; regenerate.

## Review Guidance

- `corpus_select.py` contains no glob; it calls `select_gates`; bare-run `--help` survives.
- Superset test reads the live router group (no hand copy) and covers unmatched-src and `full`.
- Corpus job: `continue-on-error: true`, not in `packs-gate.needs`, `-n 4`, no `-q`, `--cov=charter.offering`, pack-manifest deselected, warning step present; pack-manifest job trigger widened.
- Router `tests-corpus` gone (job, needs, ledger); `corpus` group/output kept; transitional exemption carries its D-22 rationale and pin.
- Pinning inventory fresh; out-of-map edits justified; registry prose drift recorded for WP19.
- Definition of Done: FR-009 (single advisory owner, superset trigger, coverage target fixed), FR-002 for the corpus lane (literal `-n 4`, worker line visible).

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
