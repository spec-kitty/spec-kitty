---
work_package_id: WP17
title: Forecast uses the fresh run's claim inputs
dependencies:
- WP16
requirement_refs:
- FR-012
- FR-013
- NFR-002
- NFR-010
- SC-003
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T087
- T088
- T089
- T090
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/claim_inputs.py
create_intent:
- src/specify_cli/consolidation/claim_inputs.py
- tests/consolidation/test_claim_inputs_parity.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/consolidation/test_forecast_fresh_run_parity.py
- docs/changelog/unreleased/7403-forecast-claim-inputs.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/claim_inputs.py
- src/specify_cli/consolidation/forecast.py
- tests/consolidation/test_forecast_fresh_run_parity.py
- tests/consolidation/test_claim_inputs_parity.py
- tests/consolidation/test_reconciliation_intended_verdicts.py
- tests/consolidation/characterization/verdict_corpus.json
- docs/changelog/unreleased/7403-forecast-claim-inputs.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP17 – Forecast uses the fresh run's claim inputs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP17 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

WP09 gave the forecast (`consolidate --dry-run`), the fresh run and the resume one `ClaimInputs` constructor, but kept every per-mode quirk so no verdict changed. Three quirks make the forecast's inputs differ from the fresh run's on the **same unmutated state** (reviewer-renata F-06, data-model section 6, invariant CI-2):

| Field | `LIVE` (forecast) today | `LIVE_THEN_SAVED` (fresh run) |
|---|---|---|
| `excluded_canceled_wp_ids` | empty (the forecast passes none) | `acceptably_canceled_wp_ids(main_repo, mission_slug)` (`executor.py:455`) |
| `coord_base` | the live `mission_branch` **name** | the coordination tip **SHA** (`_capture_coord_checkpoint`, `run_state.py:445`), falling back to the `mission_branch` name only when no coordination ref resolves |
| `status_dir` | `_forecast_claim_status_dir` → `resolve_status_read(...).path` (`forecast.py:359`) | `_resolve_run_status_dir(seam)` → `seam.write_dir(STATUS_STATE)` (`entry_preflight.py:690`) |

This work package aligns all three in the `LIVE` resolver (FR-012, FR-013, plan IC-16), so `LIVE` and `LIVE_THEN_SAVED` are field-equal (except `source`) on an unmutated state, where equality compares refs **by resolved SHA** and the status directory **by resolved path and event-log digest** (FR-013, US5-1). Done means:

1. Each of WP09's three strict parity `xfail`s flips to pass **in its own fix commit**.
2. Any forecast **verdict** change is red-first through `consolidate --dry-run --json`, committed failing before its fix (NFR-010), and is limited to NFR-002 **(h)**.
3. The two (h) intended-verdict pins (WP05) lose their strict `xfail` marker in the fix commit that makes them pass.
4. The golden diff touches **forecast-mode** cells only, and only those whose claim inputs carry an excluded canceled work package or a coordination base that differs by name and SHA; every fresh-run and resume cell is byte-identical.
5. The forecast stays **read-only**: it never seeds, materializes or commits a coordination surface, and it still does not run the verify-side checks it skips today (plan IC-16 Risks, #7362).

**NFR-002 flip covered: (h)** (FR-013, the forecast's excluded canceled work packages and resolved coordination base). SC-003.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US5 (acceptance 1-3), FR-012, FR-013, NFR-002 (h), NFR-010, C-004, SC-003, Assumptions ("Forecast input alignment").
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` section 6 (`ClaimInputs` table, CI-1..CI-3).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-08 (equality definition), IC-16.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-05, post-plan disposition F-06.
- Code:
  - `src/specify_cli/consolidation/claim_inputs.py` (WP09): `ClaimInputSource`, `ClaimInputs`, `ClaimInputContext`, `claim_inputs(...)`, the `_live` resolver, `build_claim(...)`. Read WP09's history note first: it records the context shape and any default-kwarg equivalence.
  - `src/specify_cli/consolidation/forecast.py` `_refuse_unattributable_in_forecast` (`:380-470` before WP09; now builds `LIVE` inputs and calls `build_claim`). Keep its `window_base` `GitProbeError` early return, its claim-integrity refusal (`CLAIM_REFUSED_FORECAST`), and everything after the claim exactly as is.
  - `src/specify_cli/consolidation/done_bookkeeping.py:51` `acceptably_canceled_wp_ids(repo_root, mission_slug, *, owned=None)`: the single merge-side authority for the excluded set; reduces the status surface read-only and fails open to `set()` on an unreadable surface.
  - `src/specify_cli/consolidation/run_state.py:445` `_capture_coord_checkpoint` and `_status_surface_ref(main_repo, mission_slug)`: the fresh run resolves the coordination ref through `resolve_placement_only(..., kind=STATUS_STATE).ref`, then `git rev-parse`.
  - `src/specify_cli/consolidation/phase_claim.py` `_capture_reconciliation_claim` (`:485-560` before WP09): `coord_base = coord_base_sha or checkpoint.sha or run.lanes_manifest.mission_branch`.
  - `src/specify_cli/consolidation/entry_preflight.py:690` `_resolve_run_status_dir`: the **write** accessor; it may seed or materialize the coordination surface, so the forecast must **not** call it.
- Tests you change or reuse:
  - `tests/consolidation/test_claim_inputs_parity.py` (WP09): `test_forecast_excluded_canceled_set_equals_fresh_run`, `test_forecast_coord_base_resolves_to_fresh_run_sha`, `test_forecast_status_dir_equals_fresh_run` (each a strict `xfail(raises=AssertionError)` naming WP17); helpers `_ref_sha`, `_status_dir_identity`.
  - `tests/consolidation/test_reconciliation_intended_verdicts.py` (WP05): `test_forecast_uses_fresh_run_excluded_canceled_set`, `test_forecast_resolves_coordination_base_to_fresh_run_sha` (strict xfails, NFR-002 (h)). **Read WP05's history note**: if WP05 recorded that one of them could not show a visible difference, follow what it recorded.
  - `tests/consolidation/characterization_support.py` (WP02): `build_shape(tmp_path, "mixed_lane_canceled_wp" | "fully_canceled_dependency" | ...)`, `run_in_process`, `regenerate_cells`.
  - Existing forecast tests that must stay green: `tests/consolidation/test_forecast_seam.py`, `test_forecast_squash_parity.py`, `test_dependency_ref_forecast.py`, `test_dry_run_fails_closed_on_unmaterialized_coord.py`, `test_dry_run_refuses_missing_mission_branch.py`.
- Cross-cutting: C-009, C-013, C-014, NFR-004 (`_live` <= 15; add one helper per aligned field rather than growing `_live`), NFR-005, NFR-009, C-004.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP17 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Commit plan (red first, one fix per divergence)

1. **Red commit** (T087) — `test(consolidation): red-first forecast vs fresh-run excluded canceled set (WP17)`.
2. **Fix 1** (T088) — `fix(consolidation): the forecast excludes the canceled work packages the fresh run excludes (FR-013, WP17)`; removes the excluded-set parity xfail and the (h) excluded-set pin's marker; regenerates the affected forecast cells.
3. **Fix 2** (T089a) — `fix(consolidation): the forecast resolves its coordination base to the fresh run's SHA (FR-013, WP17)`; removes the coord-base parity xfail and the (h) coord-base pin's marker; regenerates affected forecast cells (if any).
4. **Fix 3** (T089b) — `fix(consolidation): the forecast reads the fresh run's status directory, read-only (FR-013, WP17)`; removes the status-dir parity xfail.

If T087 finds a visible verdict change for the coordination base too (see T087 step 4), add a second red commit for it before Fix 2. Record every red SHA with its failing summary line in the history note.

## Subtasks & Detailed Guidance

### Subtask T087 – Red-first tests through `consolidate --dry-run --json`

- **File**: `tests/consolidation/test_forecast_fresh_run_parity.py` (new). Mark `pytest.mark.integration` and `pytest.mark.git_repo`.
- **Steps**:
  1. Find the visible difference first. Look at the golden file for the forecast vs fresh cells of the shapes that carry an excluded canceled work package:
     ```bash
     uv run --frozen python -c "import json;d=json.load(open('tests/consolidation/characterization/verdict_corpus.json'));c=d.get('cells',d);[print(k, c[k]) for k in sorted(c) if 'canceled' in k and (k.startswith('forecast|') or k.startswith('fresh|'))]"
     ```
     Write down each pair where the forecast verdict (status, codes) differs from the fresh run's claim-time verdict. These are the cells Fix 1 may change.
  2. **`test_forecast_reports_the_fresh_runs_claim_verdict_with_an_excluded_canceled_wp`**: `mission = build_shape(tmp_path, "mixed_lane_canceled_wp")` (a lane holding an approved WP and a WP canceled **with operator provenance**, so `acceptably_canceled_wp_ids` returns it). Copy the repo (`shutil.copytree` of `mission.repo`, as WP02 does for mutating cells) so the forecast and the fresh run start from the same unmutated state. Run `run_in_process(mission, ["consolidate", "--mission", slug, "--dry-run", "--json"])` on one copy and `["consolidate", "--mission", slug, "--yes"]` on the other. Assert the forecast's claim-time outcome equals the fresh run's: both pass the claim, or both refuse at claim time with the same refusal code(s). Parse the forecast JSON (`error_code`, `error`) and the fresh output's refusal codes with WP02's parser.
  3. Assert the forecast moved nothing: the refs (`tests/terminus/rollback_harness.ref_shas`) and `git worktree list --porcelain` are identical before and after the dry run, and no new commit exists on the coordination branch (NFR-010 "no branch moved").
  4. Coordination base: try to build a visible verdict difference only if WP05's `test_forecast_resolves_coordination_base_to_fresh_run_sha` found one (read its docstring/history). If it found none, do **not** invent one: the field-level parity xfail (`test_forecast_coord_base_resolves_to_fresh_run_sha`) is the red evidence for Fix 2, and you record "no verdict-visible difference; field-level red only" in the tracer.
  5. Confirm the step-2 test **fails** on this commit for the stated reason (the forecast's verdict differs because its excluded set is empty), not a fixture error. Fixture preconditions raise `RuntimeError`, never `assert`.
  6. If step 1 found **no** forecast-vs-fresh verdict difference on any excluded-canceled cell, the entry-point test cannot be red. Stop and tell the orchestrator before writing fixes (spec Assumptions: the verdict change, if any, is red-first; if there is none, the alignment is field-level only and the red evidence is the parity xfail). Record the finding.
- **Do not**: hand-write `state.json`; use `run_terminus` (subprocess); compare free text where a code exists.

### Subtask T088 – Align the `LIVE` excluded canceled set (Fix 1)

- **File**: `src/specify_cli/consolidation/claim_inputs.py`; `forecast.py` only if the context needs a new value passed in.
- **Steps**:
  1. In the `LIVE` resolver, derive `excluded_canceled_wp_ids = frozenset(acceptably_canceled_wp_ids(main_repo, mission_slug))`, the **same** call the fresh run makes at `executor.py:455`. Put it in a small helper (e.g. `_live_excluded_canceled(context)`); import `acceptably_canceled_wp_ids` function-locally if a module-level import would create a cycle (check with `uv run --frozen python -c "import specify_cli.consolidation.claim_inputs"`).
  2. `build_claim` now passes the set to the builder for `LIVE` too. Remove the WP09 special case that omitted the kwarg for `LIVE`, and update `test_build_claim_passes_todays_kwargs`'s `LIVE` literal accordingly (that test pins kwargs per source; its `LIVE` row changes in this commit, its other rows do not).
  3. Remove the strict `xfail` marker from `test_forecast_excluded_canceled_set_equals_fresh_run` (parity) and from `test_forecast_uses_fresh_run_excluded_canceled_set` (WP05 (h) pin). Both must now pass. The T087 test must pass.
  4. Regenerate only the forecast cells T087 step 1 listed (`regenerate_cells(names)`), then run the subset check from T090 step 2. Record the keys.
- **Notes**: `acceptably_canceled_wp_ids` is read-only (it reduces the status surface; it never writes). It fails open to `set()` on an unreadable surface; that matches the fresh run, so keep it.

### Subtask T089 – Resolve the forecast coordination base to a SHA (Fix 2) and read the fresh run's status directory (Fix 3)

- **Fix 2 – coordination base** (`claim_inputs.py`, `_live`):
  1. Resolve the coordination base the way the fresh run does on a fresh (unpersisted) state: the coordination ref from `_status_surface_ref(main_repo, mission_slug)` (`run_state.py`), `git rev-parse` to a SHA; when no coordination ref resolves, `resolve_commit(main_repo, lanes_manifest.mission_branch)`; when that fails too, keep the `mission_branch` name (the fresh run's last fallback). Put this in `_live_coord_base(context) -> str`.
  2. Import direction: `claim_inputs.py` must not import the executor family at module level (WP09 rule). If `_status_surface_ref` lives in `run_state.py` and importing it would pull the executor family, import it function-locally, or lift the two-line read into a read-only helper next to it (in `run_state.py` only if WP17 owns it — it does not; then import function-locally). Check `uv run --frozen pytest -q tests/architectural/test_layer_rules.py` stays green.
  3. Remove the strict `xfail` marker from `test_forecast_coord_base_resolves_to_fresh_run_sha` (parity) and from `test_forecast_resolves_coordination_base_to_fresh_run_sha` (WP05 (h) pin). Both must pass. Regenerate only forecast cells that changed (likely none: a name and its SHA read the same history while nothing moves); run the subset check.
- **Fix 3 – status directory** (`claim_inputs.py` `_live`, `forecast.py` `_forecast_claim_status_dir`):
  1. The forecast must read the directory the fresh run's write accessor resolves to, **without** the write accessor's side effects. Compare on the fixtures (coordination topology, lanes topology, `single_branch`): `placement_seam(main_repo, slug).write_dir(MissionArtifactKind.STATUS_STATE)` (fresh run, may seed) vs `resolve_status_read(main_repo, slug).path` (forecast today) vs `placement_seam(main_repo, slug).read_dir(MissionArtifactKind.STATUS_STATE)`. Use a read-only resolution that yields the fresh run's path on every topology the corpus covers.
  2. Keep the forecast's fail-closed refusal when the status is ref-sourced (no checkout to read): `test_dry_run_fails_closed_on_unmaterialized_coord.py` must stay green. Keep `CLAIM_REFUSED_FORECAST` and its remedy text.
  3. If no read-only resolution can produce the fresh run's path on some topology without seeding, stop and ask the orchestrator; do not make the forecast seed or materialize (that would mutate on a dry run).
  4. Remove the strict `xfail` marker from `test_forecast_status_dir_equals_fresh_run` (compares `(path.resolve(), sha256(events bytes))`). It must pass. Regenerate only changed forecast cells (likely none).
- **Notes**: Record in the tracer which status-dir resolution you chose and why the paths are equal.

### Subtask T090 – Verify the flips and the golden subset

- **Steps**:
  1. Run `uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_intended_verdicts.py`: the three parity tests and the two (h) pins now **pass**; every other intended-verdict test is still XFAIL (the (d) pin passes since WP16); zero XPASS.
  2. Golden subset against the WP16 tip (the parent of your red commit):
     ```bash
     BASE=$(git rev-parse <first-red-commit>^)   # parent of your first red commit (WP02 helper, post-tasks squad R-03)
     uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; c = changed_cells('$BASE'); print(c); assert all(k.startswith('forecast|') for k in c), 'a non-forecast cell changed: C-004 violation'"
     ```
     The printed list must **equal** the named forecast cells T087 step 1 listed (not merely be a subset of the forecast cells).
     Every changed key must be a forecast cell whose inputs carry an excluded canceled WP (or the named (h) cell). Paste the list into the history note.
  3. Run the golden test twice: zero diff.
  4. Confirm SC-003 on the corpus: for every scenario where all three modes apply, the forecast's claim-time verdict now equals the fresh run's. List any remaining mismatch in the history with its cause; a remaining mismatch caused by the verify-side checks the forecast skips (#7362) is out of scope and must be named, not fixed.

## Test Strategy

Red-first through the entry point for each verdict change; field-level parity tests for each input. Unit tests sit alongside, never instead (NFR-010).

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_forecast_fresh_run_parity.py
uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
uv run --frozen pytest -q tests/consolidation/test_forecast_seam.py tests/consolidation/test_forecast_squash_parity.py tests/consolidation/test_dependency_ref_forecast.py tests/consolidation/test_dry_run_fails_closed_on_unmaterialized_coord.py tests/consolidation/test_dry_run_refuses_missing_mission_branch.py
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q -n auto --dist loadfile tests/consolidation/
uv run --frozen pytest -q tests/terminus/ -k "dry_run or forecast"
uv run --frozen pytest -q tests/architectural/test_layer_rules.py
uv run --frozen ruff check src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py tests/consolidation/test_forecast_fresh_run_parity.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py tests/consolidation/test_forecast_fresh_run_parity.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen mypy src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py tests/consolidation/test_forecast_fresh_run_parity.py
make test-fast
```

- [ ] Red evidence: each red commit SHA and its failing summary line are in the history note (and later the PR's *Tests run*). **Because lane SHAs can become unreachable after a squash consolidation with cleanup** (post-tasks squad R-14), also paste, for each red test, its full test id and the assertion message pytest printed (`uv run --frozen pytest -q -rf <test>` at the red SHA), so the PR and the post-merge mission review can check the red without checking out the SHA.
- [ ] One fix commit per divergence; each removes exactly its own xfail marker(s).
- [ ] Golden diff = forecast cells only (T090 step 2), keys recorded; `changed_cells(<first red commit>^)` equals them.
- [ ] **Changelog fragment** (post-tasks squad R-08; this WP owns it): if T087 found an operator-visible `consolidate --dry-run` verdict change, create `docs/changelog/unreleased/7403-forecast-claim-inputs.fixed.md`, one entry, section `fixed`, README style `- **\`spec-kitty consolidate --dry-run\` reports the claim verdict the real run reaches** (#7403). **Before:** ... **After:** ...`, written from the shipped red-first test, no version bump. Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`. If T087 found **no** operator-visible change, do not create the file; record "no operator-visible change, no fragment" in a design-decisions tracer entry instead.
- [ ] The dry run moves nothing and seeds nothing (T087 step 3 assertions green).
- [ ] No call site assembles claim inputs itself (`grep -n "build_approved_wp_set(" src/` shows only `claim_inputs.py` and the definition).
- [ ] No new `# noqa` / `# type: ignore`; every resolver <= 15 complexity.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP17" --entry "<summary>. <detail>"` for visible differences found in T087, the status-dir resolution chosen, any remaining SC-003 mismatch and its cause, and whether a changelog fragment was written; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Dry run mutates**: the write accessor seeds; never call it from the forecast. T087 step 3 checks refs and worktrees.
- **Fresh/resume cells change**: the T090 subset check fails on any non-forecast cell; fix the code, never the golden.
- **Import cycle**: function-local imports for executor-family helpers; the layer-rule gate is in the DoD.
- **No visible verdict change**: stop-and-ask in T087 step 6; do not fabricate a red.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (bounded alignment against the parity tests and the corpus).
- Check out each red commit and confirm the stated test fails for the stated reason.
- Diff `_live` against the fresh run's derivations (`executor.py:455`, `phase_claim._capture_reconciliation_claim`, `entry_preflight._resolve_run_status_dir`) field by field.
- Confirm the golden diff is forecast-only and each flipped marker sits in the commit that made it pass.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP17 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP17 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
