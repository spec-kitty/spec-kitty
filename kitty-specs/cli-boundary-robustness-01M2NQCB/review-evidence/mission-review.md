# Mission Review: CLI Boundary Robustness

Reviewer: codex:gpt-6:reviewer-renata:reviewer (root orchestrator; no product implementation).
Mission: cli-boundary-robustness-01M2NQCB.
Specification baseline: be490214baa3cb1ee54b153e254b48f572ca40a1.
Integration base: b17a81506331bc434b93a692f4f6261d008dc81e (upstream changes separately accounted for).
Reviewed integrated source: ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92.
Canonical acceptance passed; canonical local merge completed; authoritative status reports all six WPs done. Remote main has not been merged.

## Gate Results

Final immutable-SHA execution complete (frozen core `ea5fc3678ebbf2d474fe55ecf1a2e02eba5c8c92`, evidence dir `final-gates-ea5fc3678ebb-20260916T231123Z`, launcher PID 46130, all 13 recorded gate steps finished). A follow-on scoped corrective cycle (below) fixed the two genuine non-baseline defects this run surfaced, independently re-verified by a separate root pass (not the implementer, not the fix's own reviewer).

| Gate | argv (abridged) | Result |
|---|---|---|
| fast (`make test-fast`) | — | PASS: 1842 passed, 5 skipped, 424.45s |
| owners-callers-coverage | pytest, ~90 owning/caller/affected paths, `-m "not timing and not stress" -n2 --cov=src --cov-append` | FAIL on frozen SHA: 38 failed / 10663 passed / 58 skipped, 3529.28s. Classified below. |
| contract (`tests/contract`) | pytest, `-n2 --cov` | PASS |
| architectural (`tests/architectural`) | pytest, `-n2 --cov` | FAIL on frozen SHA: 1 failed (`test_no_public_symbol_in_all_is_unimported`, 3 dead symbols), 2628 passed, 1648.67s. Fixed and re-verified below. |
| stress | pytest `-m "stress and not windows_ci" -n0` | PASS: 2 passed |
| timing | pytest `-m timing -n0` | PASS: 3 passed, 1 skipped |
| unmarked-timing | env-loader overhead + tasks-status baseline | PASS: 3 passed |
| external-e2e | EXPERIMENTAL-spec-kitty-end-to-end-testing `scenarios/`, quiet | PASS: 5 passed, 593.39s — all 5 maintained cases (the 3 scenario files / 5 cases the upstream `saas_sync_enabled` retirement e59564bd8b82f7912b8db67087712ec84fc47cf8 left current; that retired scenario was intentionally not restored) |
| coverage-xml / mission-normalize / mission-diff-cover / critical-normalize | diff-cover on frozen `coverage.xml` | PASS: mission diff coverage 90% (523 lines, 51 missing, exactly at threshold) |
| critical-diff-cover | diff-cover, `--fail-under=90`, diff = `origin/main...HEAD` | FAIL on frozen SHA: 89% (48 lines, 5 missing in `src/charter/activation/consistency_check.py`: 628,632,636,1363,1504). Fixed and re-verified below. |

**owners-callers-coverage 38-failure classification** (each node ID cross-checked, not assumed):
- 3 × stale `get_project_root_or_exit` zero-arg mocks in `tests/agent/test_commands.py` — already fixed on review-pr in `0e906806` before this run; frozen core predates that fix, so failing here is expected, not a regression.
- 33 × prior-classified owner baseline, exact match against `final-other-baseline-nodes.txt`: 32 research/schema assertions (#4671, `tests/research/test_research_plan_missions_integration.py`) + 1 relay/SSE case (#4672, `tests/status/test_zeitgeist_decision_moment_docker_local.py`).
- 2 × genuinely new, non-baseline regression: `tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows` and `::test_rendered_json_contains_every_mid8` — same stale-mock defect class as `0e906806` (production `get_project_root_or_exit` gained a `json_output` keyword-only param; these two tests still monkeypatched a zero-arg lambda), missed by the earlier same-file audit because it lives in a different test file. Confirmed via `git diff` that the test file itself was untouched by this mission, i.e. the mission's own production signature change broke it.

### Corrective cycle (post-final-gates, pre-PR-ready)

Three genuine defects — the 2 dashboard mocks above, the 3 architectural dead symbols, and the critical-diff-cover shortfall — were fixed by a separate implementer agent and approved by a separate independent reviewer agent (implementation/review separation preserved; this root reviewer did neither the fix nor that review). All three fix commits were independently re-verified in this review by direct, fresh command execution against the actual new commits (not by re-reading the implementer's or reviewer's claims):

1. **Dashboard mocks** — core `21a5aabec`, review-pr `264f566d7` (test-only: `tests/agent/test_commands.py`, `tests/dashboard/test_duplicate_prefix_rendering.py`; confirmed zero `src/` diff). Re-run: `tests/dashboard/test_duplicate_prefix_rendering.py::test_dashboard_json_cli_renders_three_distinct_rows`, `::test_rendered_json_contains_every_mid8`, plus the 3 original `test_commands.py` mocks — **5 passed, 40.89s**.
2. **Dead-symbol gate** — core `08f83da3b`, review-pr `ccd787071` (test-only: `tests/architectural/test_no_dead_symbols.py`; confirmed zero `src/` diff). Claim: the two `register()` symbols were stale content-tier `body_hash` entries already allowlisted under `_CATEGORY_C_DOCTOR_AUTO_DISCOVERY_SEAM` (reached via `doctor.py`'s dynamic `getattr(module, "register")`), invalidated by the CLI-boundary refactor's nested-body edits — hashes refreshed, no behavior change; `MissionTypeEmptyActionSequenceError` is allowlisted as an intentionally-uncaught exception per `charter/activate.py:172`, tracked under #4600/FR-303 for a real wire-or-prune decision. Re-run: full `tests/architectural/test_no_dead_symbols.py` — **34 passed, 122.9s**.
3. **Coverage gap** — core `d8e05ee7d`, review-pr `2d0864eb8` (test-only: `tests/doctrine/test_activation_parity_guard.py`, `tests/charter/test_enforcement_lattice.py`, `tests/charter/test_decision_documentation_on_implement.py`; confirmed zero `src/` diff). Adds real behavioral tests for the 5 previously-uncovered fail-closed branches (3 post-parse `isinstance` shape guards in `_load_reference_ids_by_kind`, 2 DRG/doctrine-disagreement `RuntimeError` paths). Independent re-measurement: fresh `--cov=src --cov-append` run of the 5 relevant test files (the 3 changed plus 2 pre-existing sibling files the implementer's commit message named) layered onto the frozen `measurement.coverage`, `coverage xml` regenerated, `diff-cover` rerun against the original `critical.statements.diff` with the same `--fail-under=90` — result: **`src/charter/activation/consistency_check.py` 100%, Total 100% (0/48 lines missing)**, exceeding both the 90% gate and the implementer's own more conservative scoped claim of 93.8%.

No hard gate remains failing for a real, unresolved reason. All three post-final-gates defects were product-adjacent-but-test-only corrections, each independently reviewed twice (once by the dedicated reviewer agent, once by this root pass via direct re-execution).

### Architectural tests
See Gate Results table and corrective cycle above: PASS after fix (34/34).

### Cross-repository E2E
PASS: 5/5 maintained scenarios. The former `saas_sync_enabled` scenario was deliberately retired upstream in `e59564bd8b82f7912b8db67087712ec84fc47cf8`; current scenarios are authoritative and were not restored. `SPEC_KITTY_ENABLE_SAAS_SYNC` was confirmed unset/unmodified throughout this review.

### Issue matrix
PASS. Canonical issue-matrix.json has22 rows:7 fixed,1 verified-already-fixed,14 deferred-with-followup. No empty/unknown verdict; every deferred row names a concrete issue. JSON is the current runtime-owned authority; the historical Markdown table is not treated as a parallel mutable authority. Seven fixed targets:4600,4601,4643,4597,4598,4533,4532. Actual GitHub closure occurs when the implementation PR merges, not on local acceptance.

### Latency (NFR005)
`final-quiet-latency.py`, 3 repeats each, warm interpreter, same-process `--version` invocation, `SPEC_KITTY_ENABLE_SAAS_SYNC` preserved unset: baseline (`wp06-original-source`) median **0.963s**, integrated (`spec-kitty` core) median **0.948s** — both comfortably under the 2s budget and consistent with WP01's prior 1.153s/1.112s medians. This is a single-command (`--version`) sample only; it demonstrates no regression on process-startup overhead, not that every CLI command meets a 2s bound.

### Follow-up recording
`spec-kitty mission follow-up cli-boundary-robustness-01M2NQCB --pr 4674 --json` recorded successfully (`FollowUpRecorded`, event `01M2PJPX6S8S8ZWP47GEK4SCEB`, mission already terminal per fail-closed check). Recorded against PR #4674 as a whole (rather than a single `--commit`) because the corrective PR now contains four relevant commits (`0e906806` plus the three fixes above); the CLI supports exactly one of `--commit`/`--pr` per invocation, and `--pr` is the accurate reference for the full set. Event appended to core's `status.events.jsonl` and committed (`0fcecb2bd`); identical line transferred into review-pr's copy of the same file for publication-checkout parity.

## FR Coverage Matrix

Paths below are repository-relative. Tests were read for actual assertions and production entry points, not merely requirement labels.

| FR | WP | Implementation | Constraining tests | Assessment |
|---|---|---|---|---|
|001|01|bootstrap/env_file.py optional pointer decode boundary|tests/specify_cli/bootstrap/test_cli_boundary_config_4600.py fresh-process version/doctor healthy-versus-corrupt comparison|Adequate; genuine red-first original entry point|
|002|04|charter/mission_type.py mission_type_error_boundary uses named CharterPackConfigError.body|test_cli_boundary_mission_types.py real invalid UTF8 over aliases|Adequate|
|003|04|same boundary covers content loading and rejects nonmapping required configuration|same tests with parseable invalid root|Adequate|
|004|01|consistency_check.py typed required-load error; runtime/doctor.py warning outcome; explicit git metadata encodings|tests/charter/test_cli_boundary_config_mapping.py; tests/runtime/test_cli_boundary_version_file.py; tests/specify_cli/core/test_cli_boundary_git_encoding.py|Adequate|
|005|02–06|cli/json_contract.py authority; doctor and adopted command error adapters|test_cli_boundary_json_seam.py; context/mission_types/glossary/remaining_callers regressions; test_json_contract_enumeration.py|Adequate within ratified adopted surface|
|006|05–06|pure build_kanban_status and command-owned zero-WP JSON success|test_cli_boundary_status_empty.py; actual zero-WP and seven empty-list fixtures in enumeration guard|Adequate; real aggregate, not fabricated result|
|007|02–06|plain console.emit_json transport, diagnostic guards, one error emission|JSON parsing and stream assertions on107 classified registrations; wrong-payload/prose mutations|Adequate for driven allow-list paths|
|008|02,05|defaulted JSON-aware root helper;19 doctor guards; verify/dashboard opt-in|frozen doctor tests, root helper tests, remaining-caller tests, actual root stream guard|Adequate; human-only callers retain interfaces|
|009|03|context info real Annotated defaults|test_4597_default_invocation_matches_info, real command registration|Adequate|
|010|04|explicit include_inactive=False at alias call; doctrine roster preserved|partial activation, explicit inactive flag, all aliases and exact doctrine three-key rows|Adequate|
|011|06|behavioral guard executes all four no-subcommand callbacks|test_cli_placeholder_output.py callback spies and injected placeholder mutations|Adequate; no AST style enforcement|
|012|01–06|seven filed defects tied to red-first tests and final issue verdicts|per-WP red/green commit provenance and review evidence|Ready for PR closure; remote issues are not prematurely described as closed|

## Review history and drift

All final approvals were independent of their implementation. WP03 and WP05 each had two substantive rejection rounds and four recorded review cycles. WP03 corrected real non-UTF8 token reads and directory-at-workspace-file errors. WP05 corrected ambiguous selectors, status envelope/exit fidelity, then its missed status-only golden fixture. Final source preserves these corrections; no rejection was closed by forced approval.

Canonical logs mark backward review rewinds as force=true even when the caller did not pass --force. Four explicit same-lane in_progress actor repairs address runtime bug#4673; they did not skip implementation, review or acceptance. The auto-retrospective's generic wording must be read with these exact transition reasons. WP02's immutable approval actor defaults to user because --agent was omitted; actual reviewer was independent task_author, not Robert. Clarification and#4670 preserve provenance rather than rewriting history.

Two process deviations remain documented: WP05's initial extraction and adoption shared one functional commit rather than separate tidy-first commits; WP06's initial discovery invoked idempotent regen/doctrine generation before target audit. Immediate source status was clean and generated bytes unchanged; final guards avoid those write paths. These are historical process notes, not fabricated clean execution or evidence of product defects.

No locked-decision violation found: fail-soft import probe remains stdlib/kernel only; required config fails loud; error shape has one authority while successful payloads remain command-specific; error exits match established human behavior; alias defaults fixed at callsite; doctrine's distinct full roster retained; no AST/binding-style enforcement, new dependency, release version or hosted API change. The ratified gate classification is44 adopted+63 already-parseable+64 explicitly deferred registrations. The generic error arm plus explicit empty fixtures does not prove every arbitrary input; broader convergence remains#4664.

NFR001–004 are supported by structural bool-flag discovery, real callback execution, frozen explicit classifications, mutation tests, dedicated red-first commits and direct reexports of the shared envelope. NFR005 final quiet paired measurement pending. NFR006: all47 changed Python files pass ruff; whole-repo format passes1,949 files; whitespace passes. Strict mypy exits1 with exactly the same22 full baseline diagnostic lines in three files (21 inherited selector-test annotation/generic errors and tasks_shared.py:572 no-any-return), no new/removed/relocated diagnostics and no suppression introduced. Do not call inherited diagnostic debt an all-green strict check.

## Silent Failure Candidates

| Location | Condition and result | Assessment |
|---|---|---|
|bootstrap/env_file.py optional pointer read|OSError/UnicodeDecodeError returns None|Explicit FR001/C004/C009 fail-soft requirement, preserving repair commands|
|workspace/context.py existing loader|Malformed record returns None; lists skip malformed records|Unchanged loader semantics; owned OSError boundaries now fail loud, no newly introduced swallowing|
|agent_utils/status.py|No work packages yields empty aggregate|Legitimate success, normal schema/exit0; not error masking|
|runtime/doctor.py version lock|Unreadable file yields failed warning DoctorCheck|Visible named diagnostic, not silent fallback|

## Security and integration notes

New boundary adapters render existing failures; no shell=True, dynamic shell command, network call, credential mutation or lock protocol is introduced. Files are decoded explicitly; error messages retain filenames and diagnostic reasons. Context load handling does not alter path resolution or authorize new writes. JSON guards restore logging-disable thresholds in finally and warning filters through catch_warnings; no stdout parsing or global stream reassignment. Independent bounded JSON and mission-type audits found no blocker. A49-file blob/SHA256 comparison proves all approved product/test/config contents survive consolidation. The prior shared CLI candidate differs only in five expected paths (latest WP03 source/test, WP05 golden fixture, two WP06 guards); final affected and architectural gates cover those differences.

New public build_kanban_status has a live production caller through show_kanban_status. Shared json_error/guard helpers have registered callers and identity reexports. All functional corrections are exercised through real commands/filesystem conditions; root-registration tests explicitly isolate unrelated startup work and do not substitute for fresh-process P0 tests. Shared tasks helper extension defaults to unchanged behavior for non-status callers; the unrelated list-tasks golden fixture is byte-identical.

## Post-consolidation correction

RESOLVED in independently reviewed test-only follow-up0e906806015e4260d7846b29d1d956bd905d3fbc: CI agent shard3 exposed two stale get_project_root_or_exit mocks in tests/agent/test_commands.py (verify setup and dashboard kill). A same-file audit found the corresponding JSON verify mock also lacks the new keyword. These are actionable integration fixture defects, not baseline33 failures. Exact CI evidence: run35162191953/job105015345713,498passed2failed6skipped. All three cases independently reproduced before editing (3failed95.33s), then passed after correction (3passed76.01s). Review verified typed keyword-only mocks, exact False/False/True mode assertions and preservation of every original assertion. Ruff passes; the file retains32 normalized baseline type diagnostics and one unrelated preexisting formatting hunk, with no new exclusion. The final core validation source remains frozen; product code is unchanged. Record the reviewed commit using the canonical completed-mission `mission follow-up` command after immutable gates finish. Do not reopen done work packages or claim these failures are waived.

## Final Verdict

**PASS — confirmed by real GitHub Actions CI, not local reruns alone.**

Provenance on the corrective cycle, disclosed honestly rather than smoothed over — it took three rounds, not one:

1. **Round 1** (before this review began): `0e9068060` fixed 3 stale `get_project_root_or_exit` zero-arg mocks in `tests/agent/test_commands.py`, found by a CI shard failure on the original PR push.
2. **Round 2** (this review's own final-gates run): surfaced 2 more instances in `tests/dashboard/test_duplicate_prefix_rendering.py`, plus 3 dead-symbol false positives and a 5-line critical-diff-cover gap. Fixed in `264f566d7` / `ccd787071` / `2d0864eb8`, each independently reviewed, each re-verified in this review by direct execution against the actual commits. Local scoped reruns of the previously-failing node IDs all went green.
3. **Round 3** (pushing round 2's fixes to real CI): the `CI Modules` workflow's `module-tests (dashboard shard 1/1)` shard failed for real — a **third** instance in `tests/test_dashboard/test_dashboard_preflight.py` lines 212/359, a location neither the local final-gates test list nor the corrective-cycle audit had covered. This review recorded a corrected ("not yet ready") verdict in the interim rather than letting the round-2 PASS stand uncorrected. Fixed in `41287f5c6` / `4b991e31c`, independently reviewed with an explicitly broader sweep this time (diffed `helpers.py` against the mission baseline to confirm `get_project_root_or_exit` is the only function that gained a new keyword-only parameter in this mission; checked every function born with a `json_output` param for lambda mocks — zero hits; confirmed the ~90 pre-existing `locate_project_root` lambda mocks are unrelated debt against an unchanged signature). Re-verified locally (`tests/test_dashboard/test_dashboard_preflight.py`: 12/12 passed) before pushing.

**Real CI confirmation (not a local claim):** pushed `4b991e31c` to the PR branch and watched the resulting GitHub Actions run (`35178102806` and its sibling workflow runs) to actual completion. Every check passed, including the previously-failing `module-tests (dashboard shard 1/1)` (now 2m45s, green), `CI Modules gate`, `architectural battery (heavy, code-scoped)` (14m47s, green), and `router gate`. No pending or failing checks remain on the PR. This is the first point in the mission where "green" rests on GitHub's own run rather than a local scoped rerun — the two prior rounds each missed a real instance that only a full CI run caught, so this final verdict does not repeat that mistake.

All hard gates (contract, architecture, cross-repo E2E, issue matrix, mission/critical diff coverage) pass. The 38 owners-callers-coverage failures observed on the original frozen SHA are fully accounted for: 3+33 as classified above, with zero unexplained residue anywhere in the record. Latency is within budget on the sampled command. The canonical follow-up event is recorded. Production/config source tree remains byte-identical to frozen core outside of the six test-only correction commits across all three rounds.

This verdict is a real PASS, not a forced one: it rests on gates that were actually red being made actually green through three successive implement→independent-review→independent-re-verification cycles, with the final confirmation coming from GitHub's own CI rather than from any local claim, agent report, or relayed message.

## Retrospective Reminder

The runtime authored kitty-specs/cli-boundary-robustness-01M2NQCB/retrospective.yaml at terminus, recorded by RetrospectiveCaptured event01M2P7T1QPRP145S8XN24FKRZA. This is the current placement, superseding the skill's historical .kittify/missions path. Canonical `retrospect summary` and `agent retrospect synthesize --mission <slug>` (dry-run) already ran with 0 planned/applied/conflicts/rejected/events — no regeneration performed in this review. Preserve the generated record and explain #4670/#4673 provenance alongside it; do not rewrite immutable transitions. The corrective cycle in this review (3 additional fix commits + 1 follow-up event) postdates that retrospective capture and is not itself reflected in it; that is expected — the retrospective is a point-in-time capture at mission terminus, and this corrective work is deliberately recorded as a `FollowUpRecorded` event rather than by reopening or regenerating the retrospective.

## Limitations

- The corrective-cycle implementer and its dedicated reviewer are agents whose full transcripts this root review did not read line-by-line; trust in their work rests on (a) commit-level verification of exact file scope (`git show --stat`, confirmed zero `src/` diff for all three fixes) and (b) this review's own independent re-execution of the specific previously-failing checks against the actual resulting commits, not on narrative claims.
- Latency measurement is a single-command (`--version`) sample, not a full CLI command survey; do not generalize NFR005 compliance beyond process-startup overhead.
- `critical-diff-cover`'s scoped re-verification measured `src/charter/activation/consistency_check.py` in isolation (that file was the entire gap); it did not re-run the full owners-callers-coverage suite, per the operating constraint against redundant full-suite reruns for a scoped correction.
- Remote GitHub issue closures for the 7 fixed issue-matrix targets occur on merge, not on this local review.
