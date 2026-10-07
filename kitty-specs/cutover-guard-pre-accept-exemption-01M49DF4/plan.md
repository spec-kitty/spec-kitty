# Implementation Plan: Cutover guard exempts pre-accept Missions

**Branch**: `fix/cutover-guard-pre-accept-exemption` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/cutover-guard-pre-accept-exemption-01M49DF4/spec.md`

## Summary

Add one shared, fail-closed **pre-accept exemption** decision to `src/specify_cli/status/cutover_eligibility.py`. The cut-over predicate (`is_cut_over`, consumed by the CI `cutover-guard`) and the corpus eligibility helper (`eligible_runtime_missions` → `assert_birth_invariant_holds`, consumed by the dogfood corpus test, #5300) both route through it. The exemption fires only for a Mission that has event-log runtime evidence and a well-formed, absent or `< 1` `status_phase`, no terminal evidence in `meta.json`, and no non-empty legacy *frontmatter* runtime. Every remaining failure carries a reason-specific message and remedy in the guard report. No `status_phase` writer changes.

```mermaid
flowchart LR
  subgraph cutover_eligibility.py
    X[pre_accept_exemption(mission_dir)\n-> note or None\nraises nothing; undecidable -> None]
    I[is_cut_over] --> X
    E[eligible_runtime_missions] --> X
  end
  G[cutover_guard.evaluate_touched_missions\n+ _print_report / _payload] --> I
  D[test_dogfood_corpus_backfilled\nassert_birth_invariant_holds] --> E
  X --> L[LegacyWPRuntime.has_frontmatter_runtime\n(backfill_runtime_state.py, same dataclass)]
  X --> M[meta.json terminal evidence\naccepted_at / merged_at / mission_number]
```

## Technical Context

**Language/Version**: Python 3.11+ (repository floor)
**Primary Dependencies**: existing only — `specify_cli.status`, `specify_cli.migration.backfill_runtime_state`, typer/rich for guard output. No new dependency (DIRECTIVE_051 not triggered).
**Storage**: files — `kitty-specs/<mission>/meta.json`, `status.events.jsonl`, `tasks/WP*.md`, `tasks.md`
**Testing**: pytest. Red-first `@pytest.mark.regression` repro (issue-pinned #5835) through `evaluate_touched_missions` and the `cutover-guard` CLI via CliRunner; a #5300 repro through `assert_birth_invariant_holds` on a synthetic corpus; a synthetic verdict matrix in `tests/status/test_cutover_eligibility.py`. Targeted files only (no full-suite runs, per `NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: CLI on Linux/macOS/Windows; CI job `cutover-guard` in `.github/workflows/release-readiness.yml`
**Project Type**: single
**Performance Goals**: at most one extra read of `meta.json` plus the WP files of a touched Mission per evaluation; no git, no network (NFR-002)
**Constraints**: complexity ≤ 15 per function; ruff/mypy clean; fail closed on every undecidable path; no birth stamp, no new `status_phase` writer (C-001/C-002)
**Scale/Scope**: ~2 source modules, ~3 test modules, 1 doc page, changelog

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | PASS — one exemption helper consumed by both verdict paths; legacy detection is a predicate on the existing `LegacyWPRuntime` record; terminal-evidence fields match `migrate backfill-wp-status`. |
| Fail closed / no green-wash (SO #4, #9) | PASS — undecidable → no exemption; P0 gets a red-first repro. |
| ATDD-first / red-first (ADR `2026-07-17-1`) | PASS — repro lands red on the base before the fix, then is converted to a focused test. |
| Architectural gate discipline (SO #5) | PASS — no allowlist added; strict branches pinned by paired fixtures (non-vacuity). |
| Terminology canon | PASS — "Mission", never "feature", in new prose and identifiers. |
| Campsite (SO #2) | Fold only inside touched files: extract the exemption so `is_cut_over` stays ≤ 15. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/cutover-guard-pre-accept-exemption-01M49DF4/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/status/cutover_eligibility.py       # exemption helper; is_cut_over + eligible_runtime_missions consume it
src/specify_cli/migration/backfill_runtime_state.py # LegacyWPRuntime.has_frontmatter_runtime()
src/specify_cli/cli/commands/cutover_guard.py       # reason-specific remedy text + exempt-note reporting
tests/status/test_cutover_eligibility.py            # verdict matrix
tests/specify_cli/cli/commands/test_cutover_guard.py # #5835 repro via evaluate_touched_missions + CLI
tests/specify_cli/migration/test_dogfood_corpus_backfilled.py # #5300 synthetic-corpus repro
docs/development/how-to/cutover-guard.md
docs/changelog/CHANGELOG.md
```

**Structure Decision**: single project; changes stay inside the existing cutover-eligibility seam.

## Complexity Tracking

None. No charter violations.

## Implementation Concern Map

### IC-01 — Shared pre-accept exemption in the cut-over predicate

- **Covers**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-005
- **Seams**: `cutover_eligibility.py` (`is_cut_over` between the evidence check and the phase check; `eligible_runtime_missions`); `backfill_runtime_state.py` (`LegacyWPRuntime`, `read_legacy_runtime`)
- **Shape**:
  - Add `LegacyWPRuntime.has_legacy_claim_runtime()`: `shell_pid`, `shell_pid_created_at`, `assignee`, or a completed review override. Exclude `subtasks` (checkboxes are authoring) and, by the operator ruling of 2026-10-07, `agent` and `tracker_refs` (written at planning time by tasks-packages step 4a). `has_claim_state()` and `has_frontmatter_runtime()` are unchanged: backfill still uses them.
  - Add `pre_accept_exemption(mission_dir) -> str | None`, which returns the note (`"pre-accept: status_phase stamp deferred to accept"`) or `None`. Any exception, a missing or unparsable `meta.json`, or a malformed phase returns `None`.
  - In `is_cut_over`, read a malformed `status_phase` as its own explicit FAIL reason. When `phase < 1`, consult the exemption: a note means PASS with the note as the reason; otherwise FAIL with a reason that names terminal evidence or legacy runtime.
  - `eligible_runtime_missions` excludes exempt Missions, so `assert_birth_invariant_holds` agrees with `is_cut_over`.
- **Tests (red-first)**:
  - #5835: a fixture built from the real WP template frontmatter with a claim event in its event log. `evaluate_touched_missions` returns a FAIL on the base. Mark it `@pytest.mark.regression` with the issue pinned.
  - #5300: the same fixture placed in a synthetic corpus, run through `assert_birth_invariant_holds`.
  - The verdict matrix in `test_cutover_eligibility.py` covers: no evidence; exempt; exempt with checked subtasks; `accepted_at`; `merged_at`; `mission_number=0`; planning-time `agent`; a step-4a-filled WP; legacy `shell_pid`; legacy `assignee`; authored `tracker_refs`; malformed phase; malformed `meta.json`; an unreadable WP; and a stamped, verified Mission.

### IC-02 — Actionable guard output + docs

- **Covers**: FR-002 (report shows the exempt note), FR-007, FR-008
- **Seams**: `cutover_guard.py` (`remedy_command`, `_print_report`, `_payload`); `docs/development/how-to/cutover-guard.md`; `docs/changelog/CHANGELOG.md`
- **Shape**:
  - Report the exempt Missions in a separate line with their note; they are not failures.
  - Make the remedy per reason:
    - terminal evidence without a stamp, or legacy runtime → the `backfill-runtime-state` command;
    - malformed phase → fix `meta.json` by hand;
    - absent `mission_id` → `migrate backfill-identity`.
  - Keep the JSON payload backward-compatible: add fields, never rename them.
  - Docs: explain the exemption, its three conditions, and the accepted residual. Changelog: an `[Unreleased]` entry with (#5835, #5300).
- **Depends on**: IC-01 (reason vocabulary).
