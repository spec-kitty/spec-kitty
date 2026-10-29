# Implementation Plan: Synthesis record integrity

**Branch**: `issue-6453-synthesis-record-integrity` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/synthesis-record-integrity-01M5ZBC9/spec.md`

## Summary

Three narrow fixes in `charter.activation.synthesizer`, plus CLI wiring:

1. **#6456 (reconcile):** a full run uses the same "regenerated in this run" filter a topic-scoped run already uses when it strips legacy `applies` edges, in both the overlay merge and the manifest delta. A behaviour-preserving first commit threads the regenerated set through `_graph_delta`.
2. **#6453 (lock):** a new `synthesis_lock(repo_root)` context manager (re-entrant, bounded 10 s wait, `CHARTER_SYNTHESIS_LOCK_HELD` on timeout) over `kernel.locks.machine_file_lock`. The lock file lives at `<git-common-dir>/spec-kitty-locks/charter-synthesis/<digest of resolved worktree root>.lock`; outside git it is `.kittify/runtime/locks/charter-synthesis.lock` (git-ignored runtime dir). The record read-merge-write and `restamp_bundle_hash` take it, and both CLI commands hold it from just after `assert_charter_yaml_sound` to the end of the command (writing modes only).
3. **#6455 (warning):** `_UNREADABLE_RECORD_WARNING` gains a restore-or-repair step and the deletion caution.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib + in-tree `kernel.locks`, `kernel.git_topology`, `kernel.content_digest`; ruamel.yaml (existing). No new dependency (DIRECTIVE_051 supply-chain checks: not applicable, nothing added/upgraded/removed).
**Storage**: files — `.kittify/charter/synthesized-artifacts.yaml`, project overlay graph, synthesis manifest; lock file in the git common dir.
**Testing**: pytest; red-first unit tests in `tests/charter/synthesizer/`; deterministic two-thread interleaving for the race; CLI-level test for the held-lock refusal via `typer.testing.CliRunner`.
**Target Platform**: Linux, macOS, Windows (lock primitive is cross-OS by contract).
**Project Type**: single (Python CLI)
**Performance Goals**: uncontended lock acquire adds < 50 ms per run.
**Constraints**: complexity ≤ 15; no new `noqa`/`type: ignore`; `__all__` on new `src/charter/` module (C-007); lock primitive ban gate.
**Scale/Scope**: ~5 source files, ~7 test files.

## Charter Check

- **Single canonical authority:** one lock primitive (`kernel.locks`), one strip predicate (`_is_legacy_applies`) used with the same regenerated set by both callers. ✅
- **Architectural alignment:** the lock is in `charter.activation` and exported through `charter.activation.api`; `specify_cli` imports it only from there (layer chain `kernel <- charter <- specify_cli`). ✅
- **ATDD-first / red-first (DIRECTIVE_041, DIRECTIVE_034):** each WP lands its acceptance test red on the pre-change code first. ✅
- **Tidy-first (Standing Order #2):** WP01 opens with a behaviour-preserving refactor commit. ✅
- **Gate discipline (Standing Order #5):** no new allowlist; existing `test_lock_primitive_ban.py` covers the new module. ✅
- **Terminology:** "Mission", "status commit" untouched; no "feature" wording. ✅
- **NO_FULL_HEAVY_SUITES_IN_MISSION:** targeted tests + `tests/charter/`, `tests/charter_offering/`, `make test-fast`, named arch gates only. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/synthesis-record-integrity-01M5ZBC9/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/charter/activation/synthesizer/
├── reconcile.py          # IC-01: full-run strip filter (#6456)
├── synthesis_lock.py     # IC-02: NEW lock module (#6453)
└── reach_only.py         # IC-02 record wrapper; IC-03 warning text (#6455)
src/charter/activation/bundle_restamp.py           # IC-02 restamp takes the lock (FR-011)
src/charter/activation/api.py                       # IC-02 export
src/specify_cli/cli/commands/charter/synthesize.py   # IC-02 hold lock over write phase
src/specify_cli/cli/commands/charter/resynthesize.py # IC-02 hold lock over write phase
tests/charter/synthesizer/
├── test_synthesize_reconcile.py        # IC-01 (re-pin full-run assertion)
├── test_styleguide_reach_only.py       # IC-01 (re-pin styleguide assertion)
├── test_synthesis_lock.py              # IC-02 NEW
└── test_synthesize_activation_append.py # IC-02 race, IC-03 warning
```

**Structure Decision**: single project; changes stay in the existing synthesizer package and its two CLI commands.

## Complexity Tracking

None. No charter violation to justify.

## Design notes

- **Lock span (squad finding).** Both commands take the lock right after `assert_charter_yaml_sound` (`synthesize.py:223`, `resynthesize.py:110`) and hold it to the end of the command body, so `_converge_legacy_project_intent_directive` and the fresh-project seed path (`synthesize.py:252-300`) are covered. Skipped when `--dry-run`, `--dry-run-evidence` (synthesize) or `--list-topics` (resynthesize) is set. Both bodies carry `# noqa: C901` already: acquire through an `ExitStack` (or one small helper) so no new branch is added; do not add a new suppression.
- **Re-entrancy.** `machine_file_lock(..., reentrant=True)` is thread-local and keyed on the resolved lock path; the CLI's outer hold, the record wrapper and `restamp_bundle_hash` (called from `append_synthesized_activations`) nest without deadlock; two threads contend normally. Every acquisition site passes `reentrant=True`.
- **Timeout.** Module constant `SYNTHESIS_LOCK_TIMEOUT_S = 10.0`; `synthesis_lock(repo_root, *, timeout_s: float | None = None)` uses the constant when `None`. Unit test spies on `machine_file_lock` to assert `blocking=True, timeout_s=10.0, reentrant=True`; the CLI refusal test monkeypatches the constant to 0.2 s. No test waits 10 s.
- **Lock path.** `repo_root.resolve()`, `os.path.normcase`, sha256, first 32 hex chars (same as `kernel.event_log_append.event_log_lock_path`). `NotAGitRepositoryError` → `.kittify/runtime/locks/charter-synthesis.lock`; `GitTopologyUnavailableError` → `SynthesisLockUnavailableError`.
- **Refusal.** `SynthesisLockHeldError(KittyInternalConsistencyError)` with code `CHARTER_SYNTHESIS_LOCK_HELD`; both CLI commands already render that base type with its code and exit 1. Git not invocable → `SynthesisLockUnavailableError` (`CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`), never an unlocked write.
- **#6456 predicate (squad finding: keep #6443 separate).** `_is_legacy_applies` today passes one `regenerated_urns` to both the `applies` branch and `_is_dead_mission_type_edge` (`reconcile.py:323`). Split it: the `applies` branch always filters by the regenerated set (full and topic-scoped runs); the dead-edge branch keeps today's rule (filter only on a topic-scoped run, `None` on a full run). `merge_project_overlay` (`:393`) and `_graph_delta` (`:610`, `:621`) both use the split rule, with `fresh_node_urns` as the regenerated set in `_graph_delta`. `topic_scoped` stays a keyword (one production caller, `resynthesize_pipeline.py:395`), now only selecting the dead-edge rule.
- **Prune / orphan / conflicts.** A kept edge joins the preserved refs, so `--prune` removes it with its non-regenerated node as ordinary prune content (prune excises via removed nodes, `reconcile.py:833-840`); the orphan refusal is unaffected (the edge's `backing_artifact` is its source artifact's path). A kept edge whose target directive is gone now surfaces as a non-blocking `preserved_dangling_endpoint` conflict (`reconcile.py:704`) — pinned by a test.

## Implementation Concern Map

### IC-01 — Full-run strip limited to regenerated artifacts

- **Purpose**: stop a full run from deleting the stored directive link of artifacts it did not regenerate, and make the strip notice true.
- **Relevant requirements**: FR-007, FR-008, FR-009, NFR-002, C-005
- **Affected surfaces**: `src/charter/activation/synthesizer/reconcile.py`; tests below.
- **Tests to re-pin (assert today's strip; deliberately reversed):** `tests/charter/synthesizer/test_synthesize_reconcile.py::test_legacy_applies_strip_is_limited_to_regenerated_reach_only_sources` (`full.edges` and the `legacy_applies_edges(existing, synthesized)` assertion), `tests/charter/synthesizer/test_styleguide_reach_only.py::test_legacy_styleguide_applies_edge_is_stripped_and_reported` (reverses an earlier mission's styleguide "scenario 5").
- **Tests to re-check (inject a legacy edge on a non-regenerated tactic):** `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` prune and dry-run tests (`:168-185`, `:279`, `:330`), `tests/specify_cli/cli/commands/charter/test_synthesis_report_6404.py` (`stripped_legacy_edges`, `:46`), `test_orchestrator_resynthesize.py::...strips_legacy_applies`, `tests/charter/synthesizer/test_project_intent_directive.py` (#6443).
- **New tests:** full run with an untargeted tactic and styleguide (edge kept, not in notice); full run with a NOT-regenerated `PROJECT_*` dead edge (still stripped, FR-010); kept edge with a missing target directive (`preserved_dangling_endpoint`); NFR-002 `reach_only_ids` parity; prune removes the kept edge with its node.
- **Sequencing/depends-on**: none
- **Risks**: #6443 regression if the filters are not split (FR-010 test guards it).

### IC-02 — Run-wide synthesis lock

- **Purpose**: serialize a worktree's synthesis write phase so the created-artifacts record never loses an id.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-011, NFR-001, C-001, C-002, C-004, C-006
- **Affected surfaces**: new `src/charter/activation/synthesizer/synthesis_lock.py`; `reach_only.py`; `src/charter/activation/bundle_restamp.py`; `src/charter/activation/api.py`; `src/specify_cli/cli/commands/charter/synthesize.py`, `resynthesize.py`; new `tests/charter/synthesizer/test_synthesis_lock.py`; `test_synthesize_activation_append.py`; CLI tests under `tests/specify_cli/cli/commands/charter/` (or the existing synthesize CLI test home)
- **Sequencing/depends-on**: none (independent of IC-01)
- **Race test (deterministic, squad finding):** drive two threads through the real entry point `append_synthesized_activations`. Red-first commit: a `threading.Barrier` after `_read_record` shows the lost id on today's code. After the lock: writer A pauses inside `_write_record` on an `Event`; writer B's first failed `_LockCore.try_lock_once` (wrapped spy) sets a second `Event` that releases A; assert the record holds `t1,t2,t3`. Every wait has a timeout so the test fails rather than hangs. Held-lock CLI tests hold the lock from ANOTHER thread (same-thread re-entry would pass vacuously), with a lock-free positive control on the same fixture; cover `--json` envelopes (synthesize `{"result":"failure","code":...}`, resynthesize `_emit_error`) and `--dry-run` / `--list-topics` not waiting. Crash case: a subprocess takes the lock and `os._exit(0)`s; the next acquire succeeds.
- **Risks**: holding the lock across adapter generation; a test fixture with no git repo (non-git fallback path); `charter.activation.api` `__all__` gate; the `# noqa: C901` command bodies (no new suppressions).

### IC-03 — Actionable unreadable-record warning

- **Purpose**: tell the operator how to repair the record and that deleting it re-adds removed artifacts.
- **Relevant requirements**: FR-005, FR-006, C-003
- **Affected surfaces**: `reach_only.py` (`_UNREADABLE_RECORD_WARNING`); `test_synthesize_activation_append.py`; `docs/api/charter-commands.md`
- **Sequencing/depends-on**: IC-02 (same file; sequence to avoid lane conflicts)
- **Risks**: text must stay one actionable message and keep the `{path} is unreadable` prefix (asserted by `test_synthesize_activation_append.py:183` and `test_styleguide_reach_only.py:420`). Cover the legacy `synthesized-tactics.yaml` path through `_read_record`.
