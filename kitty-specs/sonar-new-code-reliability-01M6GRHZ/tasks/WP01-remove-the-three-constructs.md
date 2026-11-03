---
work_package_id: WP01
title: Remove the three new-code reliability constructs at source
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-004
- SC-001
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-sonar-new-code-reliability-01M6GRHZ
base_commit: 5b193449971ab049113e0b18b1d652abfaaa8307
created_at: '2026-11-03T13:15:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - The three source fixes and their guard
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/
create_intent:
- tests/architectural/test_new_code_reliability_shapes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/events.py
- src/charter/activation/compiler.py
- src/specify_cli/migration/backfill_identity.py
- src/specify_cli/upgrade/tracked_meta_notice.py
- tests/architectural/test_new_code_reliability_shapes.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7113'
---

# Work Package Prompt: WP01 – Remove the three new-code reliability constructs at source

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission sonar-new-code-reliability-01M6GRHZ`) and address every item before handing back.

## Objectives & Success Criteria

- `src/specify_cli/cli/commands/events.py` resolves the `--kind` default by **name** from the closed registry, not by calling the functional-API `Enum`; `_LOG_KIND_DEFAULT` is still the member whose value is `status`.
- `src/charter/activation/compiler.py::_default_active_charter_service` binds `ActiveCharterService` before the annotation that names it, in the same function scope, and keeps the import function-local.
- `src/specify_cli/migration/backfill_identity.py::_tracked_mission_id` no longer contains a provably-dead `None` guard; the invariant is stated explicitly and both outcomes are unchanged.
- `tests/architectural/test_new_code_reliability_shapes.py` fails on the pre-change tree (all three assertions) and passes after, and pins both the absent construct and the behaviour each rewrite preserves.
- No `NOSONAR`, no `sonar.issue.ignore`, no change to `sonar-project.properties` or `.github/workflows/sonar.yml` (NFR-001), and no file outside the four `owned_files` changes (NFR-002).
- `pytest tests/architectural/test_new_code_reliability_shapes.py -q` passes in under 5 s and carries the `architectural` + `fast` markers (NFR-003).

## Context

`spec-kitty_spec-kitty` on `main` fails the nightly SonarCloud quality gate on `new_reliability_rating = 5 (E)` against a threshold of `1` (#7113). The rating is a function of the worst new-code severity, and the new-code set is exactly four findings (`new_bugs = 4`; `sinceLeakPeriod=true` on `types=BUG`). Two of the four are `BLOCKER`, so they alone produce the E:

1. `python:S5756` at `src/specify_cli/cli/commands/events.py:102` — `_LOG_KIND_DEFAULT = _LogKind("status")`. `_LogKind` is built by the functional API (`Enum("_LogKind", _LOG_KIND_MEMBERS, type=str)`), so it *is* a class and the value lookup is valid; Sonar's symbolic engine cannot model that and reports a call on a non-callable.
2. `python:S3827` at `src/charter/activation/compiler.py:1153` — `service: ActiveCharterService = build_active_charter_service(repo_root)` sits above the `from charter.activation.resolver import ActiveCharterService` at line 1156. `from __future__ import annotations` is imported at module top, so the annotation is never evaluated and the name resolves at call time; Sonar reads a use-before-definition.

The third is a **true positive but harmless**: `pythonbugs:S2583` at `src/specify_cli/migration/backfill_identity.py:132` — `return None, None if refusal is None else refusal.notice` inside `if tracked.unavailable:`. `tracked_meta_refusal` returns `None` only when `not tracked.unavailable`, which the caller's guard has already excluded, so the condition is provably false.

The fourth (`java:S5960` in `acceptance-jvm`) is **out of scope**: `sonar.yml` analyses that tree as MAIN code on purpose. Do not touch it. The 19 older findings are out of scope too; see `kitty-specs/sonar-new-code-reliability-01M6GRHZ/evidence/README.md`.

The fix policy for all three: replace the flagged construct with one that says the same thing in a shape the analyzer can read. **No suppression comment, no analyzer config, no scan-scope change, no behaviour change.** Where a rewrite is genuinely impossible, stop and report instead of reaching for `NOSONAR`.

## Subtasks

- **T001** Red first. Create `tests/architectural/test_new_code_reliability_shapes.py` (`pytestmark = [pytest.mark.architectural, pytest.mark.fast]`) with three tests that fail on the current tree:
  - the `events` module's default kind is not produced by a value lookup on the functional-API `Enum` (assert the `_LogKind("status")` call shape is absent from the module source);
  - in `_default_active_charter_service`, every name used in an annotation is bound by a statement that precedes it in that function's body (walk the AST of the function; a positive control asserts the probe *does* find a preceding binding for a name it must, such as `build_active_charter_service` inside the `repo_root` branch, so the probe cannot pass vacuously on an empty match);
  - the `backfill_identity` module no longer carries the `None if refusal is None else refusal.notice` conditional expression.
  Run it; capture the three failures verbatim. Do not "fix" the test to pass.
- **T002** `events.py`: introduce a single `_DEFAULT_LOG_KIND = "status"` constant next to the registry, and resolve the default as `_LogKind[_DEFAULT_LOG_KIND.upper()]`. Keep the default typed as before. Add a short comment naming the `S5756` false positive and why the name lookup is equivalent (`_LOG_KIND_MEMBERS` maps `kind.upper() -> kind`, so `"STATUS"` is the member whose value is `"status"`). Do not change `_LOG_KIND_MEMBERS`, the `Enum(...)` construction, or any other use of `_LogKind`.
- **T003** `compiler.py`: move `from charter.activation.resolver import ActiveCharterService` to the top of `_default_active_charter_service`'s body (before the `if repo_root is not None:`), and delete the now-duplicate import below. Keep it function-local (a module-level import is what the local import avoids). Leave the annotation and both return paths alone. Confirm the builder module already imports `resolver`, so this adds no new import edge.
- **T004** `backfill_identity.py`: replace the dead ternary with an explicit narrowing — `assert refusal is not None` carrying a one-line comment naming `S2583` and the invariant — then `return None, refusal.notice`. Also state the precondition in `tracked_meta_refusal`'s docstring (it has exactly one caller; a future caller must not expect a live `None` branch the narrowing no longer expresses). No signature change.
- **T005** Non-vacuity half by half. Revert each of the three edits in turn (git stash the single hunk or re-apply the old line), re-run the guard module, and confirm the matching assertion reds each time; restore. Add the behavioural half of each test: for `events`, `_LOG_KIND_DEFAULT.value == "status"` and `_LOG_KIND_DEFAULT is _LogKind["STATUS"]`; for `compiler`, `_default_active_charter_service(None)` and `_default_active_charter_service(tmp_path)` both return an instance of `charter.activation.resolver.ActiveCharterService`; for `backfill`, monkeypatch `specify_cli.mission_metadata.read_tracked_meta` with a fake that reports `unavailable` and assert `(None, <notice>)`, then a usable fake and assert `(<id>, None)` — both outcomes on one fixture shape, so the probe is shown to see each.
- **T006** Confirm the diff surface: `git diff --stat` over `src/` and `tests/` shows exactly the three source files and the one new test module; `rg -n "NOSONAR|sonar.issue.ignore" src/` shows no new hit; `sonar-project.properties` and `.github/workflows/sonar.yml` are untouched.

## Constraints

- Behaviour is frozen: the three modules' existing tests must pass with **no edits to them**. If one fails, the rewrite changed behaviour — revert and rethink, do not update the test.
- `_LOG_KIND_MEMBERS`, `SUPPORTED_LOG_KINDS`, `_LogKind`'s construction and every `_LogKind` use other than the default stay byte-identical; the closed-registry single-authority rule is what makes the default legitimate.
- The `compiler.py` import stays inside the function. Do not move it to module scope, and do not touch unrelated local imports in the same module (`compiler.py` has several, at `:343` and elsewhere).
- No `assert` is added inside a `try` that catches `AssertionError` (that would be `S5779`, the very class of finding this mission is about).
- Do not touch `acceptance-jvm/**`, `sonar-project.properties`, `.github/workflows/sonar.yml`, any ratchet baseline, exclusion list, or test marker.
- Do not edit the 19 pre-existing findings' sites listed in the evidence README.

## Definition of Done

- `pytest tests/architectural/test_new_code_reliability_shapes.py -q` passes; it failed on the pre-change tree for all three sites, and each single-hunk revert reds only its own assertion.
- `pytest tests/cli/test_events_tail.py tests/cli/test_events_tail_log_selector.py tests/cli/test_events_tail_logs_unit.py -q` passes.
- `pytest tests/charter/test_compiler.py tests/charter/test_charter_whole_kind_invariants.py tests/charter/synthesizer/ -q` passes.
- `pytest tests/specify_cli/migration/test_backfill_identity.py tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py tests/specify_cli/test_remaining_meta_writers.py -q` passes.
- `ruff check` and `ruff format --check` are clean on the four files (`make format-check-files FILES=...`).
- `mypy` is no worse than `main` on the three touched files.
- The hand-off quotes each red-then-green observation and the exact test counts.
