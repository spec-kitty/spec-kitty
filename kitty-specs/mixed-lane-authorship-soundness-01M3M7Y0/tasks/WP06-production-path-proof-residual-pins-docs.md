---
work_package_id: WP06
title: Production-path proof, residual pins, docs
dependencies:
- WP03
- WP05
requirement_refs:
- FR-001
- FR-009
- NFR-001
- C-007
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T20:03:02.393953+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
phase: Phase 4 - Proof and polish
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/terminus/test_repro_5046_production_path.py
- tests/consolidation/test_canceled_content_residuals.py
- tests/consolidation/test_canceled_content_benchmark.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/terminus/test_repro_5046_production_path.py
- tests/consolidation/test_canceled_content_residuals.py
- tests/consolidation/test_canceled_content_benchmark.py
- docs/architecture/status-model.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Production-path proof, residual pins, docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

- **SC-006**: a mixed-lane mission whose attribution is written by the **real** capture path (WP03 — no hand-written `lane_head`) consolidates to FAIL; its superseded twin to PASS.
- **Half-by-half proof** (non-vacuity tactic): with WP03's stamping disabled the FAIL case becomes REFUSE (not PASS); with WP05's axis disabled it becomes PASS. Recorded in the activity log with commands.
- **Residual pins** (FR-009, C-007): strict `xfail` tests documenting the known limitations.
- **NFR-001** benchmark and the docs page update.

## Context & Constraints

- Spec SC-006, FR-009, NFR-001, C-007; plan IC-05/IC-06; research R-9 dispositions (R4 other-lane-identical, R6 post-cancel).
- Production capture path = the status shells: `specify_cli.status.emit.emit_status_transition` (flat) and `specify_cli.coordination.status_transition` transactional functions — both inject WP03's probe. Driving the full `spec-kitty implement` / `agent tasks move-task` CLI in a fixture repo may need the complete mission scaffold; **time-box that to one attempt**. If blocked, drive transitions through `emit_status_transition` against the WP01 builder's repo (still the production capture seam, not a hand-written stamp) and log the gap in `kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/traces/tooling-friction.md` via the orchestrator (you do not own that file — put the note in your activity log).
- Do NOT edit `conftest.py` (WP01), `reconciliation.py` (WP05), `wp_attribution.py` (WP04) or the status sources (WP03). For the half-by-half proof, monkeypatch in the test process or run with a temporary local revert that you do NOT commit.

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace from `spec-kitty agent action implement WP06 --agent claude`; it must contain WP03 and WP05.

## Subtasks & Detailed Guidance

### Subtask T028 – SC-006 production-path twin (time-boxed)

- `tests/terminus/test_repro_5046_production_path.py`: build with the WP01 builder using `canceled_lifecycle="none"` (WP02 left `planned`, no WP02 events or commits), then drive WP02's lifecycle (and WP01's rework for the twin) through the **production** shell that writes the surface consolidation reads (the fixture is coord topology — expect the transactional shell in `coordination/status_transition.py`; the WP01 builder docstring says which surface), committing to the lane branch between transitions (claimed → in_progress → commit(s) → for_review → … → canceled). Assert WP02's `in_progress` and `canceled` events carry `lane_head` equal to `git rev-parse <lane branch>` taken just before its first commit and just after its last commit (not merely "a stamp exists"). Then consolidate:
  - unsuperseded → FAIL text naming WP02;
  - superseded (WP01 rework rewrites the path) → exit 0.

### Subtask T029 – Half-by-half proof

- `run_terminus` spawns the CLI as a subprocess, so `monkeypatch` does not reach it. Plan both halves as follows:
  - **CLI half (preferred):** write a temporary `sitecustomize.py` into `tmp_path` that patches (a) `probe_lane_head` to return `None` for the capture-off run — note capture happens while *driving transitions* in-process, so for this half simply drive transitions with `monkeypatch` disabling the probe in the test process — and (b) `MergeOutcomeVerifier._canceled_content_divergence` to return no findings for the axis-off run, prepended to `PYTHONPATH` via `run_terminus(..., env=...)` (WP01 added `env`).
  - Expected: capture off → REFUSE (`no commit attribution`); axis off → exit 0.
  - **Fallback (only with a recorded failure of the CLI half):** the same two checks in-process via `build_approved_wp_set` + `MergeOutcomeVerifier.verify` on the same repo.

### Subtask T030 – Residual strict xfails [P]

`tests/consolidation/test_canceled_content_residuals.py` (git-backed, calling the claim builder + verifier directly), each `@pytest.mark.xfail(strict=True, reason="<residual> — follow-up under the parent epic")`, asserting the **ideal** outcome:
1. hunk-level supersession (FR-009): survivor edits on top of the canceled change keeping part of it → ideal FAIL (today PASS).
2. another approved lane authored the identical `(path, blob)` → ideal PASS (today FAIL — safe direction).
3. commit on the lane after WP02's cancel stamp that still carries WP02's work → ideal FAIL (today PASS).
4. commits by a WP that never entered implementation (see issue 5069) → ideal FAIL (today PASS).
Each docstring cites the research R-9/R-10 disposition.

### Subtask T031 – NFR-001 benchmark [P]

`tests/consolidation/test_canceled_content_benchmark.py`: git-backed mixed lane with 5 WPs and 50 first-parent commits (one canceled WP with stamps); time `build_approved_wp_set` + `verify` with and without a canceled WP (baseline = same lane with the WP approved) and assert the delta ≤ 1.0 s. Mark it `@pytest.mark.performance` (skipped unless `SPEC_KITTY_RUN_PERFORMANCE=1`, `tests/conftest.py:328`; do NOT use `timing`, which runs per-PR under coverage). Run it locally with the env var set and record the measured delta.

### Subtask T032 – Docs

`docs/architecture/status-model.md`: add a short section "Commit attribution stamp (`policy_metadata.lane_head`)" — what is stamped, when, best-effort semantics, that it is read only by the consolidation reconciliation gate for mixed lanes, and the verdict table link (`kitty-specs/.../contracts/attribution-and-verdicts.md` is a mission artifact — summarize the rules in the doc instead of linking to kitty-specs). Keep the page's frontmatter `updated:` date current (docs-freshness). Mission terminology only.

## Test Strategy

```bash
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5046_production_path.py -q
uv run --frozen pytest tests/consolidation/test_canceled_content_residuals.py tests/consolidation/test_canceled_content_benchmark.py -q -p no:randomly
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check tests/terminus/test_repro_5046_production_path.py tests/consolidation/test_canceled_content_*.py && uv run --frozen ruff format --check tests/terminus/test_repro_5046_production_path.py tests/consolidation/test_canceled_content_*.py
```
If the docs tooling exists: `uv run --frozen python scripts/docs/check_docs_freshness.py --ci`.

## Risks & Mitigations

- SC-006 fixture friction: time-boxed fallback described above; never replace capture with hand-written stamps in this file.
- Benchmark flakiness: generous warm-up, compare deltas, not absolutes.

## Review Guidance

- Confirm SC-006 test asserts stamps were produced by the production path (no `policy_metadata` in the builder call).
- Confirm the half-by-half outcomes are recorded and match (REFUSE / PASS).
- Confirm every residual is `strict=True` and asserts the ideal outcome.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
