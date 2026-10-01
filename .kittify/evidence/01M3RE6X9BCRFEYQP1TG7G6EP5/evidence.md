# Test-suite slice identification: squad synthesis (2026-09-30)

- **Op:** `01M3RE6X9BCRFEYQP1TG7G6EP5` (researcher-robbie), under #5353.
- **Snapshot:** `upstream/main` `d620d03a76`; 3226 test files, 37996 tests.
- **Lenses:** each is read-only and ran no tests.
  - **S, static triage** (researcher-robbie, Sonnet): `lens-static.md`.
  - **C, CaaCS forensics** (researcher-robbie, Opus): `lens-caacs.md`.
  - **F, friction** (debugger-debbie, Opus): `lens-friction.md`.
- **Excluded:** `consolidation` (#5407, done), `charter` (#5416, in review), `cli` (next; the prompt is ready).

## Where the lenses disagree (kept separate, not averaged)

- **S vs C/F on `architectural` and `cross_cutting`.** S sets both aside: its false-positive rate there is 60–70%, because a guard test that only fails when it fires reads as "no assertion". C ranks `architectural` first (churn 822, 141 repair commits, 8 principal files), and F ranks it second (82 re-pin commits).
  - **Resolution:** both are right. The *oracles* are sound; the *friction* is in exact-count, hash and golden pins against live structure, which the static scanner cannot see. The pass these slices need is **pin honesty**, not vacuity.
- **C/F vs S on `integration`.** S does not rank it. C ranks it sixth (a 14% repair rate, skip growth of +15), and F ranks it first (a fake-git harness with gates stubbed out, and 11 of the nightly's reds).
  - **Resolution:** this is harness-writability friction, the "stubbing a new gate out of an old harness" anti-pattern. It is invisible to the scanner.

## Ranked slices

| # | Slice | Lenses | Review focus | Size |
|---|---|---|---|---|
| 1 | `tests/integration` (+ `integration/migration`) | F1, C6 | Harness honesty: move the fake-git merge harness onto the real-git fixture pattern from #5345, instead of stubbing each new gate. The nightly's 11 reds come from the reconciliation gate refusing lane branches the fixtures never create. **Red-main priority** (standing order 9). | Mission-sized |
| 2 | `tests/architectural` (the ratchet/pin gates) | C1, F2 (S blind) | Pin honesty: exact counts, body hashes and baselines inside the test source get re-pinned at every landing. Anchor them on stable content (DIRECTIVE_041; #5346 is open). Perf tests use wall-clock time (#4914). Principal files: `test_no_dead_symbols`, `test_no_dead_modules`, `test_inline_meta_read_gate`, `test_single_mission_surface_resolver`, `test_destructive_op_routing`, `test_archive_root_byte_identical`, `test_ratchet_baselines`, `test_egress_consent_boundary`. | Mission-sized; design first |
| 3 | `tests/specify_cli/cli/commands/agent` (147 files) + `tests/agent` (80) | S1+S4, C2+C3, F3 | Over-mocking, plus golden and frozen-subcommand checks that go red on correct changes (#4916). Agent-command tests are spread across three trees (tests/cli, tests/agent, specify_cli/cli/commands/agent), so consolidating placement is part of the job. Principal files: `test_tasks_compat_surface`, `test_feature_finalize_bootstrap`, `test_agent_feature` (persisted since 2026-05), `test_implement_command`, `test_orchestrator_commands_integration`. Run it after `tests/cli` lands. | 2 PRs |
| 4 | `tests/status` | C7, F6 | Core domain, so core rigour. `test_emit.py` is the most structure-sensitive unit test: 136 `src/` files across 33 subsystems. 5 reds on main have no owner (#5356). Collection INTERNALERROR (#2927); non-determinism in the stress tests. | 1 PR |
| 5 | `tests/doctrine` (+ `specify_cli/doctrine`) | C5, F8, F4 | Pair it with the `charter` residue once #5416 merges. It has the highest conftest churn. 146 frozen format/lint entries. Packaging tests turn a failed wheel build into a skip. | 1 PR |
| 6 | `tests/cross_cutting` (+ `_support`) | C8, F5 (S: guard-idiom false positive) | Masked greens: quarantined accept tests that no CI lane runs, and version-detection tests that turn errors into skips. 17% of commits are repairs (41% in `_support`). | Small |
| 7 | `tests/tracker` | S2 | Mocks the whole `httpx.Client` boundary and asserts on calls. Est. 15% false positives, with low churn. Cleanest one-PR case. | 1 PR, cheap |
| 8 | `tests/auth` | S3 | "Is idempotent" and noop tests that assert nothing, on the OAuth and credential-storage paths. Security-adjacent, so rank it above its churn. | 1 PR |
| 9 | `tests/specify_cli` (root files) | C4, F4 | Acceptance regressions and the meta-read census contract (`test_acceptance_regressions`, `test_meta_fail_closed_full_census_contract`). Outside the per-PR test matrix (#5201, #4374). | 1 PR |

**Watch, don't pick yet:**
- **`tests/next`:** S8. `test_runtime_bridge_unit` is a principal hotspot (C).
- **`test_dashboard`:** S6. `test_scanner` persisted from the 2026-05 run but is now cold.
- **The small-surface cluster:** `session_presence`, `widen`, `dashboard` and `specify_cli/next`. They share one "noop, no assertion" pattern, so batch them into one PR.
- **`tests/migration`:** cheap; has the open #5185.
- **`zeitgeist_client` and `runtime`:** their churn is feature work, not repair.

## Quick win: masked-green cleanup (one small PR, independent of the slices)

Verified by the orchestrator: `resolve_doctrine_root()` now resolves to `src/charter/offering`, and the shipped tactics live under `packs/built-in/tactics`. So the probe `resolve_doctrine_root()/tactics/built-in` is always false, and these tests **skip on every run** ("shipped doctrine not on disk"):

- `tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision`: 5 tests.
- `tests/integration/test_quickstart_end_to_end.py`: `test_step4a…`, `test_step4b…` (×2) and `test_step5…`.

**Skips and xfails citing closed issues.** Candidates only; each needs a `--runxfail` check:

- **`test_egress_consent_boundary.py::test_scanner_detects_each_sink_shape`:** 2 strict xfails citing #3113 (closed).
- **`cross_cutting/misc/test_acceptance_support.py`:** 5 quarantined tests citing EXPERIMENTAL#171 (closed). No lane sets `SPEC_KITTY_RUN_QUARANTINE`.
- **`test_saas_sync_gate_selection_invariance.py`:** the whole module guards a flag from the retired sync transport (#3213). Retire candidate.
- **Dead guards citing #932 (migration, 5) and #828 (packaging, 2):** the guards never fire now, so this is cleanup only.
- **`consolidation/test_reconciliation.py::test_squash_three_way_merge_resolution_is_unattributable`:** cites #5021/#5051 (closed). Re-point it to the residuals tracker #5330, and hand it to the #5407 owner.
- **Tests that turn an error into a skip:** `tests/conftest.py::build_artifacts` / `installed_wheel_venv`, `doctrine/test_wheel_packaging.py::_build_wheel_fallback`, three version-detection tests, and the stress test's time-budget skip.

The friction lens also flagged `charter/evidence/test_orchestrator.py::test_dry_run_evidence_on_spec_kitty_repo` (cites #4785, closed). That is a false positive: #4785 is the by-design linked-worktree refusal, not a defect waiting on a fix.

## Cross-cutting findings (not slices)

- **Nightly red:** 5 consecutive failures, the last on 2026-09-30, in the specify_cli out-of-matrix, integration+next, performance and 3.13 interpreter jobs. Under standing order 9 this outranks curation work, and slice 1 addresses part of it.
- **Test trees outside the per-PR lanes:** `specify_cli/{skills,invocation,doctrine,session_presence,charter_lint}` and its root files run nightly only (a 46.7-minute job), so their reds accumulate unseen (#5201, #4374, #4916).
- **Repair happens at landing:** 308 of the 571 test-repair commits are `test(landing)` re-pins. This is the structural cost of slice 2.
- **CLAUDE.md drift:** the "known P0 reds" it names (#2736, #2772, #1834) are all closed. It needs a curator pass.
- **Ambiguous quarantine citations:** `spec-kitty#171`, `#1021` and `#901` refer to EXPERIMENTAL-spec-kitty issues, but in `spec-kitty/spec-kitty` those numbers are unrelated PRs.
- **The 2026-05 CaaCS test hotspots mostly moved on:** the sync tests were deleted and the glossary tests went cold. Only `test_agent_feature` and `test_scanner` persisted.
