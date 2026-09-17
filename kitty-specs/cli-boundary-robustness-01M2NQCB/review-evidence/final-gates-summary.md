# Final-gates run summary + corrective cycle re-verification

Frozen core SHA: `ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92`.
Evidence dir (core checkout, not copied into PR — logs are large; see hashes/commands below): `final-gates-ea5fc3678ebb-20260916T231123Z/`.
Launcher: `run-final-gates.py --core . --e2e ../EXPERIMENTAL-spec-kitty-end-to-end-testing --base b17a81506 --execute`, PID 46130, ran 2026-09-16T23:11Z to 2026-09-17T01:00Z.

## Gate results (13 recorded steps)

| Gate | Exit | Result |
|---|---|---|
| fast | 0 | 1842 passed, 5 skipped, 424.45s |
| owners-callers-coverage | 1 | 38 failed / 10663 passed / 58 skipped, 3529.28s — see classification below |
| contract | 0 | pass |
| architecture | 1 | 1 failed (`test_no_public_symbol_in_all_is_unimported`), 2628 passed — fixed, see below |
| stress | 0 | 2 passed |
| timing | 0 | 3 passed, 1 skipped |
| unmarked-timing | 0 | 3 passed |
| external-e2e | 0 | 5 passed, 593.39s (5/5 maintained scenarios) |
| coverage-xml / mission-normalize / mission-diff-cover / critical-normalize | 0 | mission diff coverage 90% (523 lines, 51 missing) |
| critical-diff-cover | 1 | 89% (48 lines, 5 missing in consistency_check.py) — fixed, see below |

## owners-callers-coverage 38-failure classification

- 3: stale `get_project_root_or_exit` zero-arg mocks in `tests/agent/test_commands.py`, already fixed on review-pr (`0e906806`) before this run; frozen core predates that fix — expected here, not new.
- 33: exact match against `review-evidence/final-other-baseline-nodes.txt` — 32 research/schema assertions (#4671) + 1 relay/SSE (#4672).
- 2: new, non-baseline — `tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows` and `::test_rendered_json_contains_every_mid8`. Same defect class as `0e906806` (stale zero-arg mock of `get_project_root_or_exit`, which gained a `json_output` keyword-only param); missed by the earlier same-file audit because it's a different file. Confirmed via `git diff` that this test file was untouched by the mission itself — a real regression from the mission's own production signature change.

## Corrective cycle: 3 fixes, independently reviewed twice

Implementer and independent-reviewer evidence: `dashboard-mock-and-gate-fixes-handoff.md`, `dashboard-mock-and-gate-fixes-independent-review.md` (parent workspace; copied into this folder as `corrective-cycle-handoff.md` / `corrective-cycle-independent-review.md`).

All three commits confirmed test-only (`git diff --stat <parent>..<commit> -- src/` empty) before being trusted for anything, then independently re-executed by this root review (not re-reading claims):

1. **Dashboard mocks** — core `21a5aabec`, review-pr `264f566d7`. Re-run command: `pytest tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows tests/dashboard/test_duplicate_prefix_rendering.py::test_rendered_json_contains_every_mid8 tests/agent/test_commands.py::test_dashboard_kill_stops_instance tests/agent/test_commands.py::test_verify_setup_command_runs tests/agent/test_commands.py::test_verify_setup_json_output -q` → **5 passed, 40.89s**.
2. **Dead-symbol gate** — core `08f83da3b`, review-pr `ccd787071`. Re-run command: `pytest tests/architectural/test_no_dead_symbols.py -q` → **34 passed, 122.90s**.
3. **Coverage gap** — core `d8e05ee7d`, review-pr `2d0864eb8`. Independent re-measurement (not the implementer's own number): copied frozen `measurement.coverage`, ran `pytest tests/doctrine/test_activation_parity_guard.py tests/charter/test_enforcement_lattice.py tests/charter/test_decision_documentation_on_implement.py tests/charter/test_consistency_check.py tests/charter/test_tension_unreconciled.py -q --cov=src --cov-append --cov-report= --cov-config=<ini pointing at the copy>`, regenerated `coverage.xml`, reran `diff-cover <xml> --diff-file critical.statements.diff --fail-under=90` (same diff-file as the original failing gate) → **`consistency_check.py` 100%, Total 100% (0/48 missing)** — exceeds both the 90% gate and the implementer's own conservative scoped claim of 93.8%.

## Latency (NFR005)

`final-quiet-latency.py`, 3 repeats, `--version`, `SPEC_KITTY_ENABLE_SAAS_SYNC` unset throughout: baseline median **0.963s**, integrated median **0.948s** (both < 2s budget). Single-command sample only.

## Follow-up event

`spec-kitty mission follow-up cli-boundary-robustness-01M2NQCB --pr 4674 --json` → `FollowUpRecorded`, event `01M2PJPX6S8S8ZWP47GEK4SCEB`. Committed in core (`0fcecb2bd`) and mirrored into review-pr's `status.events.jsonl`.

## Round 3: a third stale-mock instance, caught only by real CI

Pushing the round-2 fixes to the PR branch triggered a real `CI Modules` run. `module-tests (dashboard shard 1/1)` failed for real: `tests/test_dashboard/test_dashboard_preflight.py::test_dashboard_command_persists_passed_advisory_warning` and `::test_dashboard_command_non_git_project_exits_1_with_git_init_advice`, same defect class (zero-arg `lambda: tmp_path` mock of `get_project_root_or_exit`, lines 212/359), in a location neither the local final-gates test list nor the round-2 grep audit had covered. GitHub's fail-fast then cancelled ~20 unrelated module-tests shards in the same run — those cancellations were noise, not real failures; only the dashboard shard had an actual defect.

Fixed in core `41287f5c6` / review-pr `4b991e31c` (test-only, +17/-2 in `tests/test_dashboard/test_dashboard_preflight.py`, confirmed zero `src/` diff). Independent reviewer performed a broader sweep this time: diffed `helpers.py` against the mission baseline `be490214b` to confirm `get_project_root_or_exit` is the only function that gained a new keyword-only parameter in this mission; checked every function born with a `json_output` parameter for lambda mocks (zero hits); confirmed the ~90 pre-existing `locate_project_root` lambda mocks elsewhere are unrelated debt against an unchanged signature, not this defect class.

Re-verified locally before pushing (`pytest tests/test_dashboard/test_dashboard_preflight.py -q` → 12 passed), then pushed to the PR branch and watched real GitHub Actions CI (run `35178102806` and sibling runs) to completion — **every check passed**, including `module-tests (dashboard shard 1/1)` (2m45s), `CI Modules gate`, `architectural battery (heavy, code-scoped)` (14m47s), and `router gate`. No pending or failing checks remain. This is the first point in the mission where the green verdict rests on GitHub's own CI run rather than a local scoped rerun.
