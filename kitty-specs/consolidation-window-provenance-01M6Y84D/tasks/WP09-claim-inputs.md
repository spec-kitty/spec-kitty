---
work_package_id: WP09
title: ClaimInputs and its one constructor
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-012
- FR-013
- C-004
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T047
- T048
- T049
- T050
- T051
- T052
- T053
phase: Phase 2 - Record and unify inputs
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/claim_inputs.py
create_intent:
- src/specify_cli/consolidation/claim_inputs.py
- tests/consolidation/test_claim_inputs_parity.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/claim_inputs.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/phase_gate.py
- tests/consolidation/test_claim_inputs_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – ClaimInputs and its one constructor

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
- **Report progress**: `spec-kitty agent tasks add-history WP09 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

The forecast, the fresh run and the resume call the same builder, `build_approved_wp_set`, but each assembles its inputs itself, so parity is lost in the **inputs** (research R-05, paula P-07). Give them **one** construction point (FR-012) with three sources, **without changing a single verdict** (C-004): every per-mode quirk is preserved exactly in this work package and aligned later, red-first, in WP17 and WP18.

Done means:

1. `src/specify_cli/consolidation/claim_inputs.py` defines `ClaimInputSource` (`LIVE`, `LIVE_THEN_SAVED`, `SAVED`), the frozen `ClaimInputs` value (data-model section 6 fields) and one constructor with one small resolver per source (CI-1).
2. A thin `build_claim(repo_root, manifest, inputs) -> ApprovedWpCommitSet` adapter calls `build_approved_wp_set` with **today's** keyword arguments. `reconciliation.py` is **not** touched.
3. `forecast.py` (~422), `phase_claim.py` (~521) and `phase_gate.py` (~72) obtain their inputs from the constructor and call `build_claim`. No call site assembles claim inputs itself.
4. `tests/consolidation/test_claim_inputs_parity.py` pins the equal fields between `LIVE` and `LIVE_THEN_SAVED` on an unmutated state, and pins each known divergence as its **own** strict `xfail` (CI-2): the forecast's empty excluded set, the forecast's live coordination base name, the forecast's status directory.
5. The characterization golden file is unchanged; the refusal-precedence matrix and intended-verdict pins are unchanged.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` section 6 (field table per source, invariants CI-1..CI-5).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-08 (Risks: resume anchor checks first; frozen dependency anchors derived from `pre_interrupt_lane_tips`; parity equality definition; complexity).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-012, FR-013 (equality: refs by resolved SHA, `status_dir` by resolved path and event-log digest), US5, C-004.
- Today's three call sites (read them fully before changing anything):
  - `phase_claim.py` `_phase_claim` (~495-545): `_enforce_resume_anchor_integrity(run, coord_topology=...)` **then** `_resolve_pre_mutation_coord_sha(run.state, run)`; `coord_base = coord_base_sha or checkpoint.sha or run.lanes_manifest.mission_branch`; `run.target_expected_old_sha = _resolve_pre_mutation_target_sha(...)`; kwargs `coord_base_ref`, `excluded_canceled_wp_ids=run.excluded_canceled_wp_ids`, `excluded_window_base=run.target_expected_old_sha`, `external_dependency_refs=run.dependency_refs`, `external_dependency_pins=run.dependency_ref_pins`. `run.is_resume` distinguishes `SAVED` from `LIVE_THEN_SAVED`.
  - `forecast.py` (~405-445): `window_base = resolve_commit(main_repo, resolved_target_branch)`; `status_dir = _forecast_claim_status_dir(...)`; `coord_base_ref=lanes_manifest.mission_branch` (live **name**); **no** `excluded_canceled_wp_ids` (empty quirk).
  - `phase_gate.py` (~70-82, defensive rebuild when `run.approved_wp_set is None`): `coord_base_ref=run.lanes_manifest.mission_branch` (live name quirk), the run's excluded set and target base.
- `ConsolidationState` fields (`consolidation/state.py`): `pre_mutation_target_sha`, `pre_mutation_coord_sha`, `pre_interrupt_lane_tips`, `dependency_refs`, `dependency_ref_pins`, `strategy`.
- Cross-cutting: C-009 (no rollback caller), C-013, C-014, NFR-004 (every function <= 15; one resolver per source), NFR-005, `__all__` declared (C-007 convention).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP09 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T047 – `ClaimInputSource` and `ClaimInputs`

- **Steps**:
  1. `class ClaimInputSource(StrEnum)`: `LIVE = "live"`, `LIVE_THEN_SAVED = "live_then_saved"`, `SAVED = "saved"`.
  2. `@dataclass(frozen=True) class ClaimInputs` with: `source`, `target_base: str | None`, `coord_base: str` (a SHA or, for the Phase 2 forecast quirk, the live branch **name**), `lane_tips: Mapping[str, str]`, `dependency_anchors: Mapping[str, tuple[str, ...]]`, `dependency_refs: tuple[str, ...]`, `dependency_pins: Mapping[str, str]`, `excluded_canceled_wp_ids: frozenset[str]`, `strategy: str`, `status_dir: Path`. Use `MappingProxyType` / tuples so the value is truly immutable.
  3. `dependency_anchors` in this work package: computed for completeness (dependency lane id -> frozen tip(s) from `lane_tips`, `SAVED` from `pre_interrupt_lane_tips`) but **not passed** to the builder; WP18 consumes it. Document that in the field docstring.
- **Files**: `src/specify_cli/consolidation/claim_inputs.py`.

### Subtask T048 – The constructor, one resolver per source

- **Steps**:
  1. Public entry: `claim_inputs(source: ClaimInputSource, context: ClaimInputContext) -> ClaimInputs`, where `ClaimInputContext` is a small frozen dataclass of what the call sites already have (repo root, manifest, feature/status dir, state or `None`, requested strategy, declared refs/pins, excluded set, checkpoint sha, target branch). Keep the context explicit; do not pass `_MergeRunState` into this module (it would import the executor family into a leaf module).
  2. Private resolvers: `_live(context)`, `_live_then_saved(context)`, `_saved(context)` each <= 15 complexity. Each reproduces **exactly** the values the call site computes today (see Context). The `SAVED` resolver never falls back to a live read for a value it has saved (CI-3); a missing saved value keeps today's behaviour.
  3. The resume fail-closed checks (`_enforce_resume_anchor_integrity`, `lane_tip_cas_ok`) stay in `phase_claim.py` and run **before** the constructor (IC-08 risk). Do not move them.
- **Files**: `claim_inputs.py`.

### Subtask T049 – `build_claim` adapter

- **Steps**: `build_claim(repo_root: Path, manifest: LanesManifest, inputs: ClaimInputs) -> ApprovedWpCommitSet` calls `build_approved_wp_set(repo_root, inputs.status_dir, manifest, coord_base_ref=inputs.coord_base, excluded_canceled_wp_ids=..., excluded_window_base=inputs.target_base, external_dependency_refs=inputs.dependency_refs, external_dependency_pins=inputs.dependency_pins)`. For the forecast, pass `excluded_canceled_wp_ids` exactly as today (omitted -> the builder default). Implement the omission faithfully: if today's forecast omits the kwarg, the `LIVE` inputs carry an empty frozenset **and** `build_claim` must produce the same call semantics (check the builder's default value; if the default is `frozenset()`, passing it explicitly is equivalent — confirm and note it in the docstring).
- **Notes**: Import `build_approved_wp_set` from `specify_cli.consolidation.reconciliation` (facade). After the split (Phase 3) the facade re-exports it; the WP04 guard is about patches, not imports.

### Subtask T050 – Adopt in `forecast.py`

- **Steps**: Replace the inline kwargs at ~422 with `inputs = claim_inputs(ClaimInputSource.LIVE, ...)` and `claim = build_claim(main_repo, lanes_manifest, inputs)`. Keep `window_base`'s `GitProbeError` early return, `_forecast_claim_status_dir`, and everything after the claim exactly as is.
- **Files**: `src/specify_cli/consolidation/forecast.py`.

### Subtask T051 – Adopt in `phase_claim.py`

- **Steps**: Keep `_capture_coord_checkpoint`, `_enforce_resume_anchor_integrity` in place and order. Build `inputs` with `SAVED` when `run.is_resume` else `LIVE_THEN_SAVED`, then `run.approved_wp_set = build_claim(...)` inside the existing `try/except GitProbeError`. Keep `run.target_expected_old_sha` assignment (other phases read it) — set it from `inputs.target_base`. Store `run.claim_inputs = inputs` if `_MergeRunState` can carry it without touching files outside your ownership; otherwise keep it local and say so in the history (WP18 may add the field).
- **Files**: `src/specify_cli/consolidation/phase_claim.py`.

### Subtask T052 – Adopt in `phase_gate.py`

- **Steps**: The defensive rebuild uses the run's source, but **preserves the live `mission_branch` name** as the coordination base (today's quirk). Implement this as a documented, explicit override in the context (`coord_base_override=run.lanes_manifest.mission_branch`), not as a fourth source.
- **Files**: `src/specify_cli/consolidation/phase_gate.py`.

### Subtask T053 – `tests/consolidation/test_claim_inputs_parity.py`

- **Test names**:
  - `test_live_and_live_then_saved_agree_on_target_base` (by resolved SHA)
  - `test_live_and_live_then_saved_agree_on_lane_tips`
  - `test_live_and_live_then_saved_agree_on_dependency_refs_and_pins`
  - `test_live_and_live_then_saved_agree_on_strategy`
  - `test_saved_reads_the_persisted_record` (resume after a SIGKILL from WP02's `interrupt_after_claim`: `SAVED` values equal the `state.json` values; never a hand-written record)
  - strict `xfail(raises=AssertionError)`, one per divergence, `reason` naming WP17:
    - `test_forecast_excluded_canceled_set_equals_fresh_run`
    - `test_forecast_coord_base_resolves_to_fresh_run_sha`
    - `test_forecast_status_dir_equals_fresh_run` (resolved path + event-log digest)
  - `test_build_claim_passes_todays_kwargs` (unit: patch `build_approved_wp_set` where `claim_inputs` looks it up, capture kwargs per source, compare with the literal kwargs each call site passed before this change)
- **Equality helper**: `_ref_sha(repo, ref)` resolves names to SHAs; `_status_dir_identity(path)` returns `(path.resolve(), sha256(events bytes))`.

## Test Strategy

ATDD: write the parity test first. Zero verdict change is proven by the unchanged golden file.

## Definition of Done

```bash
uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/ -k "forecast or phase_claim or phase_gate or resume or dry_run"
uv run --frozen pytest -q tests/terminus/ -k "resume or dry_run or forecast"
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py src/specify_cli/consolidation/phase_claim.py src/specify_cli/consolidation/phase_gate.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py src/specify_cli/consolidation/phase_claim.py src/specify_cli/consolidation/phase_gate.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen mypy src/specify_cli/consolidation/claim_inputs.py src/specify_cli/consolidation/forecast.py src/specify_cli/consolidation/phase_claim.py src/specify_cli/consolidation/phase_gate.py
make test-fast
```

- [ ] `git diff --exit-code tests/consolidation/characterization/verdict_corpus.json` (golden unchanged).
- [ ] The three divergence `xfail`s are strict, `raises=AssertionError`, one per divergence.
- [ ] `reconciliation.py` untouched; no call site assembles claim kwargs itself (grep `build_approved_wp_set(` in `src/` shows only `claim_inputs.py` and the facade/definition).
- [ ] **Tracer files**: dated entries in `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (context shape, gate override, any default-kwarg equivalence) and `traces/tooling-friction.md`. Format `- **[YYYY-MM-DD][implement WP09] <summary>.** <detail>`. No `kitty-specs/` in your checkout: `spec-kitty agent tasks add-history WP09 --note "..."`.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Silent verdict change from a reordered resume check**: keep `_enforce_resume_anchor_integrity` before the constructor; the corpus resume cells catch a change.
- **Leaf module importing the executor family**: pass an explicit context.
- **Complexity creep**: one resolver per source.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid to top**.
- Diff each call site's old kwargs against `test_build_claim_passes_todays_kwargs`'s literals.
- Confirm the golden file is byte-identical.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP09 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP09 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
