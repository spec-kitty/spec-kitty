# Planner-Priti — Group C issue-coverage check

Themes: test-suite-speed-flakes, test-env-venv-install, ci-gates-routing, sonar-coverage, ruff-mypy-format, atdd-red-first, windows-cross-os, upgrade-migrations. Input: 212 tracer items from 70 missions (`groupC_items.json`), clustered into 34 clusters; every item is assigned to exactly one cluster.

**Profile applied:** planner-priti (role planner; directive 003; modes decomposition, sequencing, risk-analysis, prioritisation). Boundaries: I did not implement anything or make architectural decisions, and I was read-only on GitHub and the repo. Plan-action charter context loaded (DIRECTIVE_010/024/025, the DIR-001..013 project directives, ATDD-first C-011, the Pre-existing Failure Reporting Rule). Priorities use the Eisenhower lens: false-green or correctness risk ranks above cost or ergonomics.

**Verdicts:** COVERED 9 · PARTIAL 14 · CLOSED-ONLY 6 · UNCOVERED 5

## Clusters → verdict → issues

| ID | Kind | Statement (short) | Missions/Items | Max sev | Verdict | Issues |
|---|---|---|---|---|---|---|
| C-01 | cause | Lane worktrees have no lane-scoped interpreter; the shared editable .pth points at the PRIMARY (or another lane/clone) src, so bare python/pytest/mypy silently test the w… | 13/15 | high | **PARTIAL** | #2803(o,exact), #1907(o,partial), #3959(o,adjacent) |
| C-02 | cause | Several spec-kitty installs coexist (uv-tool/pyenv global shim, sibling-clone editable, checkout .venv); PATH resolves a different version than the checkout, so shell-out… | 7/8 | high | **PARTIAL** | #3123(o,partial), #3074(o,adjacent), #1907(o,adjacent) |
| C-03 | cause | The shared .venv drifts from uv.lock (typer 0.26.8 vs 0.24.2, click/rich skew, missing coverage module, interrupted installs), producing false reds that missions record a… | 6/7 | high | **PARTIAL** | #3123(o,adjacent), #4922(o,partial) |
| C-04 | cause | Dev tooling is split across optional extras: a bare 'uv sync' installs neither test nor lint; mypy lives only in the lint extra; tests shell out to 'python -m ruff'/'pyth… | 6/6 | medium | **UNCOVERED** | #2803(o,adjacent) |
| C-05 | cause | Nested/unpinned 'uv run' (in two tests, scripts/docs/build_cli_reference.py and make test-fast) re-syncs or downgrades the hand-built venv mid-run and costs ~75s per invo… | 5/6 | high | **COVERED** | #4922(o,exact), #3950(o,exact) |
| C-06 | cause | The session-scoped isolated test_venv fixture pays a ~25-80s pip install -e per worktree (dominating short red-first runs and the golden-path budget) and, under xdist, on… | 4/4 | high | **COVERED** | #3959(o,exact), #3283(c,exact) |
| C-07 | cause | Fixed per-invocation CLI cost (global agent-command render of 13x8 templates, eager imports) inflates every shell-out, wall-clock budgets and the golden-path NFR. | 4/4 | medium | **COVERED** | #4517(o,partial), #3048(o,partial), #4409(c,partial) |
| C-08 | both | Full tests/architectural and heavy seam suites (tests/runtime ~10 min, tests/specify_cli ~10.5 min, 37k-node collection ~100s) exceed agent session/wall-clock budgets, so… | 6/7 | medium | **PARTIAL** | #3943(o,adjacent), #2645(o,adjacent) |
| C-09 | cause | No default per-test timeout: pytest.ini addopts lacks --timeout, so loop-driving tests hang instead of failing (pytest-timeout installed but unused outside the stress/tim… | 2/2 | medium | **CLOSED-ONLY** | #3143(c,exact), #3115(c,partial) |
| C-10 | cause | Concurrent pytest sessions on one host interfere: shared auto-numbered /tmp/pytest-of-<user> basetemp eviction (~66 FileNotFoundErrors), daemon tests pgrep/port-scan and … | 4/5 | high | **PARTIAL** | #2927(o,adjacent), #3978(o,adjacent), #4666(o,adjacent), #1071(c,partial) |
| C-11 | cause | Test-isolation leaks: process-global fixture state (tests/status _SEED_COUNTER, reset_adapters() emptying the resolver registry, shared asyncio loop), pipelines defaultin… | 8/9 | high | **CLOSED-ONLY** | #1842(c,partial), #4666(o,adjacent), #4589(o,adjacent) |
| C-12 | cause | Vacuous / wrong-reason green tests: suites mock the gated seam (_build_engine), autouse conftest fixtures inject consent the test did not arrange (guarded by filename tok… | 6/11 | high | **PARTIAL** | #2935(o,partial), #4708(o,adjacent) |
| C-13 | cause | Patch-target coupling blocks refactors: from-import by-value rebinding makes patches inert after moves, ~900 legacy @patch seams force adapter subclasses/re-export facade… | 6/11 | high | **PARTIAL** | #2561(o,partial), #2935(o,adjacent), #4851(o,adjacent) |
| C-14 | both | Mutation evidence rots silently: mutation plugins go obsolete when patched symbols move (3 of 5 inert, TypeErrors counted as kills), the CI mutation job is disabled, and … | 3/3 | high | **UNCOVERED** | #4810(o,adjacent), #3125(c,adjacent) |
| C-15 | cause | Architectural marker/gate runs are vacuous under a dotted checkout path (.worktrees/): a green run inside an execution worktree scans nothing. | 2/2 | high | **COVERED** | #2475(o,exact) |
| C-16 | both | Baseline-red churn: every mission re-measures pre-existing reds (100-1700s runs, off-by-one narratives, ambiguous 'fast/unit' selector giving 1666/325 vs 1621/380) becaus… | 12/12 | high | **PARTIAL** | #4916(o,partial), #4787(o,partial), #5044(o,partial), #4668(o,partial), #3284(c,partial), #2632(c,exact) |
| C-17 | cause | Quarantined tests run nowhere: since ci-quality.yml's quarantine job was retired (planning#57) no workflow runs -m quarantine, so quarantined tests rot invisibly (31 fail… | 2/3 | high | **UNCOVERED** | #4708(o,adjacent), #5030(c,adjacent) |
| C-18 | cause | Marker/tier taxonomy traps: function-level markers stack on module pytestmark (a git_repo test under a fast module is mis-tiered), a second file-path-keyed shard authorit… | 4/4 | high | **PARTIAL** | #2979(o,partial), #4729(o,adjacent), #3241(c,partial) |
| C-19 | cause | Pre-review regression gate uses a fixed, non-tunable 300s budget (CAPTURE_BASELINE_TIMEOUT_SECONDS) over a scope whose subset alone takes ~634s, blocking for_review on br… | 2/2 | high | **COVERED** | #3046(o,exact), #2801(o,partial), #3980(c,partial) |
| C-20 | cause | Breaks surface only on CI: blast-radius tests outside make test-fast dirs, golden-help/contract fixtures and doc-freshness/terminology gates in CI-only shards, sibling te… | 11/13 | high | **PARTIAL** | #1979(o,exact), #3943(o,partial), #2283(c,exact) |
| C-21 | cause | CI routing blind spots produce false greens: trigger allowlists omitting data paths, dorny group vs on.paths two-layer structure, brace-expansion mismatch, packages route… | 3/12 | high | **COVERED** | #4708(o,exact), #3265(o,exact), #4368(o,partial), #3008(c,exact) |
| C-22 | cause | Tool-generated lifecycle commits fail commitlint: 'Add scaffold for mission <slug>' (core/mission_creation.py:1009) escapes the ignore regex (which only allows meta/spec/… | 4/5 | medium | **CLOSED-ONLY** | #3844(c,exact), #3678(c,exact) |
| C-23 | cause | Charter-mandated quality checks are absent or vacuous in live CI: no workflow invokes mypy, the commit-msg job only runs 'git log ... // true' (commitlint never runs), ma… | 3/3 | medium | **UNCOVERED** | #1928(o,adjacent), #2844(o,adjacent) |
| C-24 | cause | CI workflow changes cannot be validated by their own PR: workflow_run-triggered workflows execute main's copy, ci-nightly is schedule/dispatch-only, stacked PRs on missio… | 3/3 | medium | **PARTIAL** | #1271(o,partial), #4845(o,adjacent) |
| C-25 | cause | Shard-duration weights silently fall back to uniform when the committed duration list length disagrees with collection (producer/consumer marker mismatch); nightly wall-c… | 1/4 | high | **CLOSED-ONLY** | #4864(c,exact), #4951(o,adjacent) |
| C-26 | cause | CI-model guard tooling friction: architectural CI-model guards key off inline caller steps and break when a job moves into a reusable workflow; derived ci_topology_census… | 3/7 | high | **PARTIAL** | #2929(o,exact), #4367(c,partial) |
| C-27 | cause | Coverage gate gives little signal outside a narrow allowlist: diff-cover >=90% binds only CRITICAL_PATHS (validators/, acceptance/, cli/ excluded), earlier single-star gl… | 5/5 | high | **PARTIAL** | #1843(o,partial) |
| C-28 | cause | mypy results depend on invocation scope: follow_imports=skip for specify_cli.*/charter.* makes single-file runs report no-any-return that batch runs call redundant-cast; … | 7/9 | medium | **COVERED** | #2844(o,exact), #4188(o,partial), #3719(c,partial) |
| C-29 | cause | Formatter/lint friction: ruff format on a touched file drags in pre-existing whole-file drift; local ruff != pinned; TID251 bans hashlib with no sanctioned digest helper … | 8/10 | medium | **PARTIAL** | #4506(o,exact), #1928(o,adjacent) |
| C-30 | cause | Interpreter divergence is invisible: locals run 3.14 while CI runs 3.11/3.12 (Path.exists on EACCES raises vs returns False), 3.13 dir_fd teardown errors also reproduce o… | 3/5 | high | **COVERED** | #3189(o,exact), #4951(o,partial) |
| C-31 | cause | Windows-only defects are verified on Linux via mocks (is_windows seam, simulated follow_symlinks rejection, no-op chmod helpers) - risk of passing for the wrong reason; a… | 2/7 | medium | **COVERED** | #3864(o,partial), #4925(o,exact), #4063(o,adjacent) |
| C-32 | cause | Sync-residue env vars (SPEC_KITTY_ENABLE_SAAS_SYNC, SAAS_SYNC) inherited into agent sessions triggered sync attempts/lock contention and armed gates that made refusal tes… | 2/2 | medium | **CLOSED-ONLY** | #2801(o,adjacent), #4949(o,adjacent) |
| C-33 | cause | upgrade minted last_upgraded_at on bookkeeping-only bumps at the single per-worktree mint site (runner.py) with three callers. | 1/1 | medium | **CLOSED-ONLY** | #4972(c,exact) |
| C-34 | improvement | Red-first anchor mechanics: characterization tests that encode the bug must be inverted, companion tests can be vacuously red/green, RED shape choice (AttributeError vs I… | 5/5 | medium | **UNCOVERED** | #4891(o,adjacent) |

Legend: (o/c, fit) = open/closed, exact/partial/adjacent.

## Gaps and evidence per cluster

### C-01 — PARTIAL
Lane worktrees have no lane-scoped interpreter; the shared editable .pth points at the PRIMARY (or another lane/clone) src, so bare python/pytest/mypy silently test the wrong code (false greens) unless PYTHONPATH=<lane>/src is prepended; WP prompts/doctrine snippets and fixtures assume a local .venv/bin/*.
- Evidence: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:3`; `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:24`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:89`; `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:35`
- Tracer-cited: #3115
- Gap / note: #2803 frames it as 'lane .venv missing pytest'; the tracers show most lanes have NO venv at all, WP prompt/doctrine snippets and the tests/upgrade preview_support fixture hard-code <worktree>/.venv/bin/*, and nothing fails loud when specify_cli is imported from outside the lane (import-origin guard).

### C-02 — PARTIAL
Several spec-kitty installs coexist (uv-tool/pyenv global shim, sibling-clone editable, checkout .venv); PATH resolves a different version than the checkout, so shell-outs, record-analysis and finalize-tasks behave per a stale CLI (e.g. SK-20 charter.md vs charter.yaml hash).
- Evidence: `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:15`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:8`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-tooling-friction.md:9`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-tooling-friction.md:14`
- Tracer-cited: SK-04, SK-06, SK-20
- Gap / note: No issue covers the core hazard that mission-lifecycle commands (record-analysis, finalize-tasks, next) and test shell-outs run whichever spec-kitty is first on PATH instead of the checkout's pinned CLI, nor a hard refusal when the running CLI version != the project's pyproject version in a dogfood checkout.

### C-03 — PARTIAL
The shared .venv drifts from uv.lock (typer 0.26.8 vs 0.24.2, click/rich skew, missing coverage module, interrupted installs), producing false reds that missions record as 'pre-existing' (e.g. 34 phantom failures across three design phases).
- Evidence: `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:104`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:119`; `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:344`; `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:13`
- Gap / note: No check at pytest session start (or in make test-fast) that the active environment matches uv.lock; the CLAUDE.md 'stale-venv false reds' gotcha is prose-only.

### C-04 — UNCOVERED
Dev tooling is split across optional extras: a bare 'uv sync' installs neither test nor lint; mypy lives only in the lint extra; tests shell out to 'python -m ruff'/'python -m mypy' and fail with ModuleNotFoundError; radon is invoked by WP validation steps but not installed.
- Evidence: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:29`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:85`; `kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/tracer-tooling-friction.md:5`; `kitty-specs/cascade-org-inert-01M07E9P/tracer-tooling-friction.md:6`
- Gap / note: Searched titles for extras/uv sync/radon/'No module named mypy' and semantic search on venv/extras; no issue covers the extras split or tests that depend on lint-extra tools.

### C-05 — COVERED
Nested/unpinned 'uv run' (in two tests, scripts/docs/build_cli_reference.py and make test-fast) re-syncs or downgrades the hand-built venv mid-run and costs ~75s per invocation; 'uv run --no-sync' silently creates an empty venv when UV_PROJECT_ENVIRONMENT is missing.
- Evidence: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:53`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:729`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-design-decisions.md:291`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:8`
- Tracer-cited: #4866, #4922, #3284
- Gap / note: Minor residue not named in either issue: scripts/docs/build_cli_reference.py capture_help() hard-codes ('uv','run','spec-kitty'); 'uv run --no-sync' empty-venv behaviour untested.

### C-06 — COVERED
The session-scoped isolated test_venv fixture pays a ~25-80s pip install -e per worktree (dominating short red-first runs and the golden-path budget) and, under xdist, one worker holds the build lock while siblings time out.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-approach.md:191`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:171`; `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-tooling-friction.md:203`; `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:5`
- Tracer-cited: #4213, #4211, #3283

### C-07 — COVERED
Fixed per-invocation CLI cost (global agent-command render of 13x8 templates, eager imports) inflates every shell-out, wall-clock budgets and the golden-path NFR.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-design-decisions.md:376`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-approach.md:28`; `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-evidence-base.md:61`; `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/nfr005-baseline.md:27`
- Tracer-cited: #4213, #4211, #4417, #4409, #3780, #3825
- Gap / note: The per-call render cost itself was addressed by the freshness stamp now in src/specify_cli/runtime/agent_commands.py (_read_freshness_stamp); residual cost is tracked by #4517.

### C-08 — PARTIAL
Full tests/architectural and heavy seam suites (tests/runtime ~10 min, tests/specify_cli ~10.5 min, 37k-node collection ~100s) exceed agent session/wall-clock budgets, so agents and reviewers cannot run them locally and push to CI to find out.
- Evidence: `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-tooling-friction.md:475`; `kitty-specs/modular-per-package-ci-01M025GV/tracers/design-decisions.md:47`; `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:6`; `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-design-decisions.md:9`
- Tracer-cited: #3283
- Gap / note: No issue owns a bounded-time local path for tests/architectural (parallel-safe sharding, a documented 'make test-arch' target with -n auto --dist loadfile, or a changed-file-scoped selection).

### C-09 — CLOSED-ONLY
No default per-test timeout: pytest.ini addopts lacks --timeout, so loop-driving tests hang instead of failing (pytest-timeout installed but unused outside the stress/timing passes).
- Evidence: `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-evidence-base.md:87`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:394`
- Tracer-cited: #3115
- Gap / note: Residual after #3143's close: ordinary local runs and the per-PR module-tests matrix still have no per-test timeout (verified at HEAD).

### C-10 — PARTIAL
Concurrent pytest sessions on one host interfere: shared auto-numbered /tmp/pytest-of-<user> basetemp eviction (~66 FileNotFoundErrors), daemon tests pgrep/port-scan and reap each other, collection walks a tree other agents mutate, subprocess tests import live source edited mid-run, CPU contention breaks wall-clock budgets.
- Evidence: `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:244`; `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-tooling-friction.md:351`; `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:649`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:80`
- Tracer-cited: #3283, #1071
- Gap / note: No issue makes local pytest concurrency-safe across worktrees (per-session basetemp root, no machine-global process/port reaping, no scanning of other agents' scratch dirs).

### C-11 — CLOSED-ONLY
Test-isolation leaks: process-global fixture state (tests/status _SEED_COUNTER, reset_adapters() emptying the resolver registry, shared asyncio loop), pipelines defaulting repo_root to Path.cwd() writing real .kittify artifacts, ambient context-state.json, cwd-in-worktree guards firing on the test process, gitignored generated files, ULID-window identity-collision flake.
- Evidence: `kitty-specs/charter-catalog-coherence-01M2XQQF/tracer-tooling-friction.md:40`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:25`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:153`; `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:195`
- Gap / note: Residual instances are live at HEAD: tests/status/conftest.py:86 _SEED_COUNTER global; src/specify_cli/invocation/adapters.py:144 reset_adapters(); no open issue lists them.

### C-12 — PARTIAL
Vacuous / wrong-reason green tests: suites mock the gated seam (_build_engine), autouse conftest fixtures inject consent the test did not arrange (guarded by filename tokens), arming env gates abort before the path under test, tests pin attributes production never sets, count-based acceptance is blind to predicate widening.
- Evidence: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-red-first.md:30`; `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-design-decisions.md:143`; `kitty-specs/tracker-egress-refusal-3108-01KYWF1R/tracer-squad-findings.md:31`; `kitty-specs/tracker-egress-refusal-3108-01KYWF1R/tracer-squad-findings.md:50`
- Gap / note: tests/sync (the filename-token consent guard) was deleted with the sync transport, but tests/specify_cli/saas_client/conftest.py still carries a directory-level autouse premise fixture; no issue asks for an audit of autouse premise-fabricating fixtures or a positive-control requirement for refusal tests.

### C-13 — PARTIAL
Patch-target coupling blocks refactors: from-import by-value rebinding makes patches inert after moves, ~900 legacy @patch seams force adapter subclasses/re-export facades, source-inspection tests pin literal text/except-clause shape, identity asserts pin module location.
- Evidence: `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:566`; `kitty-specs/tracker-egress-refusal-3108-01KYWF1R/tracer-evidence-base.md:468`; `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-squad-findings.md:2087`; `kitty-specs/coord-authority-trio-degod-01KX7094/tracers/acceptance.md:14`
- Tracer-cited: #2308
- Gap / note: No repo-wide issue for the patch-location/source-text-inspection coupling class or for a sanctioned seam (constructor DI / seam factory) replacing module-attribute monkeypatching.

### C-14 — UNCOVERED
Mutation evidence rots silently: mutation plugins go obsolete when patched symbols move (3 of 5 inert, TypeErrors counted as kills), the CI mutation job is disabled, and guard predicates live inline in test bodies so they cannot be mutated.
- Evidence: `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:8`; `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-squad-findings.md:2141`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:203`
- Gap / note: Searched titles for mutation/mutant and a semantic query on vacuous tests/mutation; nothing covers plugin self-verification or re-enabling a CI mutation lane.

### C-15 — COVERED
Architectural marker/gate runs are vacuous under a dotted checkout path (.worktrees/): a green run inside an execution worktree scans nothing.
- Evidence: `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:10`; `kitty-specs/mission-resolver-port-01KX1C05/tracer-tooling-friction.md:9`

### C-16 — PARTIAL
Baseline-red churn: every mission re-measures pre-existing reds (100-1700s runs, off-by-one narratives, ambiguous 'fast/unit' selector giving 1666/325 vs 1621/380) because there is no canonical, machine-readable known-red ledger keyed to a main commit.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-design-decisions.md:876`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:27`; `kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/tracer-design-decisions.md:200`; `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:27`
- Tracer-cited: #4916, #4669, #4986, #3284, #2782, #2182
- Gap / note: Reds are tracked one issue at a time; nothing gives missions a single queryable 'known red at <sha>' set (nightly-produced) nor pins the literal fast-tier selector missions must quote.

### C-17 — UNCOVERED
Quarantined tests run nowhere: since ci-quality.yml's quarantine job was retired (planning#57) no workflow runs -m quarantine, so quarantined tests rot invisibly (31 fail on CI vs 16 locally; a relocated literal-presence test broke 4/6 assertions while dark).
- Evidence: `kitty-specs/refactor-stable-gate-substrate-01KWK3FY/tracers/design-decisions.md:56`; `kitty-specs/refactor-stable-gate-substrate-01KWK3FY/tracers/tooling-friction.md:16`; `kitty-specs/tasks-py-degod-wave2-01KWH9EQ/tracers/tooling-friction.md:33`
- Tracer-cited: #2308, #2057, #2059
- Gap / note: Verified at HEAD: grep for 'quarantine' in .github/workflows/*.yml returns nothing, and tests/architectural/test_quarantine_marker.py documents that the non-blocking-job check was removed. Semantic search on quarantine rot found no open issue.

### C-18 — PARTIAL
Marker/tier taxonomy traps: function-level markers stack on module pytestmark (a git_repo test under a fast module is mis-tiered), a second file-path-keyed shard authority (_next_shard_map), stale marker-registry references, warnings.warn used as a reporting channel polluting output.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-tooling-friction.md:157`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:129`; `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:107`; `kitty-specs/relocation-hardened-dead-code-scanners-01KX958P/tracers/warning-remediation.md:7`
- Tracer-cited: #3241
- Gap / note: Marker stacking (module fast + function git_repo both apply) is not guarded anywhere; no issue for warnings-as-reporting noise.

### C-19 — COVERED
Pre-review regression gate uses a fixed, non-tunable 300s budget (CAPTURE_BASELINE_TIMEOUT_SECONDS) over a scope whose subset alone takes ~634s, blocking for_review on broad WPs even when tests pass.
- Evidence: `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:441`; `kitty-specs/verdict-seam-boundary-hardening-01KZG179/tracers/tooling-friction.md:14`
- Tracer-cited: #3980

### C-20 — PARTIAL
Breaks surface only on CI: blast-radius tests outside make test-fast dirs, golden-help/contract fixtures and doc-freshness/terminology gates in CI-only shards, sibling tests in untouched dirs asserting retired behaviour, shared fixtures/contract artifacts (upstream_contract.json, charter_preflight _fixtures.py) outside owned_files — one discovery per ~15-min CI round.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-design-decisions.md:218`; `kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/tracer-tooling-friction.md:6`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:30`; `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:384`
- Tracer-cited: #3281, #3826, #3396, #2732, #2263, #1931
- Gap / note: make ci-parity only PREVIEWS the selected gates/shards; there is no local command that executes the CI selection for a diff, so the drip persists.

### C-21 — COVERED
CI routing blind spots produce false greens: trigger allowlists omitting data paths, dorny group vs on.paths two-layer structure, brace-expansion mismatch, packages routed by name not construction site, suites stopping when a module is added to only one group, path-filtered workflows without push:main backstop.
- Evidence: `kitty-specs/ci-scoping-gate-reliability-01KZP80D/tracer-tooling-friction.md:7`; `kitty-specs/ci-scoping-gate-reliability-01KZP80D/tracer-tooling-friction.md:9`; `kitty-specs/ci-scoping-gate-reliability-01KZP80D/tracer-squad-findings.md:7`; `kitty-specs/ci-scoping-gate-reliability-01KZP80D/tracer-squad-findings.md:17`
- Tracer-cited: #3008, #3147, #3265, #3127, #2034
- Gap / note: Most tracer evidence predates the #3995 router/module-registry rewrite; the class is owned by #4708.

### C-22 — CLOSED-ONLY
Tool-generated lifecycle commits fail commitlint: 'Add scaffold for mission <slug>' (core/mission_creation.py:1009) escapes the ignore regex (which only allows meta|spec|tasks|plan), and type-enum lacks tasks/analyze - each mission needs PR-prep fixups.
- Evidence: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:8`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:131`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-approach.md:329`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:69`
- Tracer-cited: #3678
- Gap / note: Residual verified at HEAD: commitlint.config.cjs ignores[0] = /^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) / does not match 'Add scaffold for mission ...'. Also the ignore still accepts the prohibited 'feature' term.

### C-23 — UNCOVERED
Charter-mandated quality checks are absent or vacuous in live CI: no workflow invokes mypy, the commit-msg job only runs 'git log ... || true' (commitlint never runs), markdownlint is '|| true', no bandit/pip-audit job, mutation job disabled.
- Evidence: `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-approach.md:94`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-approach.md:184`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-approach.md:31`
- Gap / note: Verified at HEAD 4fb54f3f: 'grep mypy .github/workflows/*.yml' = 0 hits; ci-router.yml:399 commit-msg = 'git log --format=%s ... || true'; :407 markdownlint '|| true'. Semantic search 'mypy not run in CI' returned only closed per-error issues.

### C-24 — PARTIAL
CI workflow changes cannot be validated by their own PR: workflow_run-triggered workflows execute main's copy, ci-nightly is schedule/dispatch-only, stacked PRs on mission branches don't trigger CI, so acceptance is a post-merge observation window.
- Evidence: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-design-decisions.md:20`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-design-decisions.md:92`; `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-squad-findings.md:2382`
- Gap / note: #1271 demands real-runner proof but gives no mechanism for workflow_run/schedule-only workflows (which always run main's copy) or for mission-branch stacked PRs that CI ignores; no actionlint/static check over changed workflow files.

### C-25 — CLOSED-ONLY
Shard-duration weights silently fall back to uniform when the committed duration list length disagrees with collection (producer/consumer marker mismatch); nightly wall-clock long poles vary ~2x with CI variance; renamed job consumers unverified.
- Evidence: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:541`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-approach.md:224`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-approach.md:272`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:593`
- Tracer-cited: #4864
- Gap / note: Residual verified at HEAD: scripts/ci/capture_shard_timings.py docstring still states the consumer 'falls back to uniform weights ... That fallback is silent and no gate notices it'; tracer recommendation (length-agreement check) not tracked.

### C-26 — PARTIAL
CI-model guard tooling friction: architectural CI-model guards key off inline caller steps and break when a job moves into a reusable workflow; derived ci_topology_census.json/_gate_coverage.py are merged textually; gate-coverage probes are invalid without real collection; scoped baseline runs produce no JUnit artifact.
- Evidence: `kitty-specs/modular-per-package-ci-01M025GV/tracers/design-decisions.md:10`; `kitty-specs/modular-per-package-ci-01M025GV/tracers/design-decisions.md:57`; `kitty-specs/modular-per-package-ci-01M025GV/tracers/design-decisions.md:75`; `kitty-specs/modular-per-package-ci-01M025GV/tracers/design-decisions.md:72`
- Gap / note: Derived CI artifacts committed and merged textually (census/_gate_coverage regenerated on both sides) has no issue.

### C-27 — PARTIAL
Coverage gate gives little signal outside a narrow allowlist: diff-cover >=90% binds only CRITICAL_PATHS (validators/, acceptance/, cli/ excluded), earlier single-star globs dropped nested files, '--cov=<path>' silently collects zero, no --cov-fail-under anywhere.
- Evidence: `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:47`; `kitty-specs/custom-mission-type-second-class-citizens-01M1FQXD/tracer-design-decisions.md:311`; `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-approach.md:43`; `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-design-decisions.md:132`
- Gap / note: Glob defect fixed at HEAD (scripts/ci/aggregate_source.py uses git pathspecs). Remaining: CRITICAL_PATHS scope decision (src/specify_cli/cli, acceptance, validators) is not tracked.

### C-28 — COVERED
mypy results depend on invocation scope: follow_imports=skip for specify_cli.*/charter.* makes single-file runs report no-any-return that batch runs call redundant-cast; per-module quarantine overrides fail verbatim moves; stale .mypy_cache under-reports.
- Evidence: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-blast-radius.md:96`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:95`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:191`; `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md:688`
- Tracer-cited: #3719

### C-29 — PARTIAL
Formatter/lint friction: ruff format on a touched file drags in pre-existing whole-file drift; local ruff != pinned; TID251 bans hashlib with no sanctioned digest helper (inline noqa everywhere); timestamp literal duplicated 18x; noqa kept for test-imported privates; CLAUDE.md __init__ version-bump rule ambiguous for nested packages.
- Evidence: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:826`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:15`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/tooling-friction.md:19`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:841`
- Gap / note: No issue for a sanctioned file-digest helper under TID251, the duplicated ISO timestamp format constant, or clarifying the __init__.py version-bump rule.

### C-30 — COVERED
Interpreter divergence is invisible: locals run 3.14 while CI runs 3.11/3.12 (Path.exists on EACCES raises vs returns False), 3.13 dir_fd teardown errors also reproduce on 3.12, isolation-sensitive 3.13 failures.
- Evidence: `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:664`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-design-decisions.md:88`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-design-decisions.md:277`; `kitty-specs/egress-refusal-consolidation-3110-01KYW895/tracer-evidence-base.md:66`
- Tracer-cited: #3189

### C-31 — COVERED
Windows-only defects are verified on Linux via mocks (is_windows seam, simulated follow_symlinks rejection, no-op chmod helpers) - risk of passing for the wrong reason; a real Windows run is needed (e.g. #4925 deferred).
- Evidence: `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/tracer-tooling-friction.md:6`; `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/tracer-approach.md:5`; `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/tracer-design-decisions.md:21`; `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/tracer-design-decisions.md:16`
- Tracer-cited: #4925, #4923, #4714
- Gap / note: Small doctrine gap: the mock-fidelity rules (patch kernel.paths.is_windows not os.name; crash repros must raise on follow_symlinks=False) are not written down in testing docs.

### C-32 — CLOSED-ONLY
Sync-residue env vars (SPEC_KITTY_ENABLE_SAAS_SYNC, SAAS_SYNC) inherited into agent sessions triggered sync attempts/lock contention and armed gates that made refusal tests vacuous.
- Evidence: `kitty-specs/charter-authority-flip-01M14RB3/tracer-tooling-friction.md:3`; `kitty-specs/durable-concurrent-review-cycle-records-01M0QRX7/tracers/tooling-friction.md:12`
- Gap / note: Behaviour is obsolete (sync transport deleted Aug 2026); SPEC_KITTY_ENABLE_SAAS_SYNC still appears in 11 src files as residue. No new issue needed beyond existing residue sweeps.

### C-33 — CLOSED-ONLY
upgrade minted last_upgraded_at on bookkeeping-only bumps at the single per-worktree mint site (runner.py) with three callers.
- Evidence: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-root-cause.md:6`
- Tracer-cited: #4972

### C-34 — UNCOVERED
Red-first anchor mechanics: characterization tests that encode the bug must be inverted, companion tests can be vacuously red/green, RED shape choice (AttributeError vs ImportError) matters to avoid breaking collection, staged schema bumps avoid accidental RED, fixtures must fail for the intended reason.
- Evidence: `kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/tracer-approach.md:9`; `kitty-specs/event-push-watch-channel-01M1K6W2/tracer-tooling-friction.md:34`; `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:287`; `kitty-specs/charter-activate-empty-action-sequence-01M0STSX/tracer-design-decisions.md:102`
- Tracer-cited: #4891
- Gap / note: Title grep for red-first/ATDD/characterization found only #5047 (fixture-specific). Charter ATDD-first section exists but has no 'red for the intended reason' checklist.

## Draft issues (NOT filed)

### [P1] Lane worktrees: provision a lane-scoped interpreter (or fail loud on foreign-src import) and stop hard-coding <worktree>/.venv in prompts and fixtures  (C-01, PARTIAL)
- Scope: implement-time lane provisioning (or a conftest import-origin assertion that specify_cli.__file__ is under the running checkout's src/); update WP prompt/doctrine snippets and tests/upgrade preview_support fixtures to resolve the interpreter via one helper. Extends #2803.
- Labels: reliability, domain:git, catfooding, tech-debt
- Relates to or extends: #2803, #1907, #3959

### [P1] Wire the charter's zero-mypy / commitlint / security-audit gates into live CI (currently absent or '|| true')  (C-23, UNCOVERED)
- Scope: Add a mypy --strict job (diff-scoped or ratcheted baseline) and a real commitlint step to ci-router; decide blocking vs reported for markdownlint and pip-audit explicitly instead of '|| true'.
- Labels: domain:ci, reliability, tech-debt
- Relates to or extends: #1928, #2844

### [P2] Dogfood checkouts: refuse or warn loudly when the spec-kitty on PATH is not the checkout's CLI (version/origin skew guard for lifecycle commands and test shell-outs)  (C-02, PARTIAL)
- Scope: One resolver (shared with #3123/#3074) that locates the project CLI; lifecycle commands that hash/validate governance artifacts refuse on version skew; tests that shell out use sys.executable -m specify_cli.
- Labels: reliability, catfooding, domain:cli
- Relates to or extends: #3123, #3074, #1907

### [P2] pytest session preflight: fail fast when the active environment does not match uv.lock (pinned CLI/test deps)  (C-03, PARTIAL)
- Scope: conftest/pytest plugin compares importlib.metadata versions of a small pinned set (typer, click, rich, pytest, coverage) against uv.lock and aborts with the exact 'uv sync --frozen --all-extras' remedy; opt-out env var for intentional overrides.
- Labels: reliability, tech-debt, catfooding
- Relates to or extends: #3123, #4922

### [P2] Make tests/architectural runnable within an agent session: parallel-safe make target + diff-scoped selection  (C-08, PARTIAL)
- Scope: Add a make target that runs tests/architectural with -n auto --dist loadfile (fixing any parallel-unsafe gates) and a scoped mode via scripts/ci/gate_selection.py; publish a wall-clock budget.
- Labels: tech-debt, domain:ci, catfooding
- Relates to or extends: #3943, #2645

### [P2] Residual of #3143: add a default per-test timeout for local and module-tests runs  (C-09, CLOSED-ONLY)
- Scope: Set a generous default --timeout (signal on POSIX, thread on Windows) in pytest.ini or module-tests.yml with a per-test override marker; document the hang failure mode.
- Labels: reliability, domain:ci, tech-debt
- Relates to or extends: none

### [P2] Make concurrent pytest sessions on one host safe: per-checkout basetemp, no machine-global reaping, collection immune to foreign scratch files  (C-10, PARTIAL)
- Scope: conftest sets --basetemp under the checkout (or a per-session unique root); daemon/port tests reap only processes they spawned; collection ignores other worktrees' scratch paths.
- Labels: reliability, tech-debt, catfooding
- Relates to or extends: #2927, #3978, #4666

### [P2] Test isolation residuals: global seed counter, registry reset-to-empty, cwd-defaulting synthesize(), ambient context-state.json  (C-11, CLOSED-ONLY)
- Scope: Replace process-global fixture state with per-test factories; fixtures restore (not empty) registries; make synthesize()/pipelines require repo_root in tests; add an autouse guard that fails if a test writes under the real checkout's .kittify/.
- Labels: tech-debt, reliability
- Relates to or extends: #4666, #4589

### [P2] Audit autouse premise fixtures and require positive controls for refusal/absence tests  (C-12, PARTIAL)
- Scope: Enumerate directory-level autouse fixtures that arrange domain premises (consent, ownership mode); convert to explicit opt-in fixtures; require each negative/refusal test to have a sibling positive control proving the path is reachable.
- Labels: tech-debt, domain:charter, catfooding
- Relates to or extends: #2935, #4708

### [P2] Publish a machine-readable known-red ledger from the nightly run and a canonical baseline selector for missions  (C-16, PARTIAL)
- Scope: ci-nightly emits known-reds.json (node ids -> tracking issue) as an artifact; a CLI/script diffs a local run against it; plans cite the literal make test-fast marker expression.
- Labels: domain:ci, tech-debt, catfooding
- Relates to or extends: #4916, #4787, #5044, #4668

### [P2] Restore a non-blocking CI lane for -m quarantine (SPEC_KITTY_RUN_QUARANTINE=1) and re-pin its wiring guard  (C-17, UNCOVERED)
- Scope: Add a nightly (non-blocking, visible) job running quarantined tests; restore the architectural check that some workflow selects -m quarantine; each quarantine entry names an owner issue and expiry.
- Labels: domain:ci, reliability, tech-debt
- Relates to or extends: #4708

### [P2] make ci-parity --run: execute the CI-selected shard set for the current diff locally  (C-20, PARTIAL)
- Scope: Extend scripts/ci/local_gate_parity.py to run the selected module shards/markers (same gate_selection authority), with a time estimate from ci-shard-timings.json; reference it from the WP review prompt.
- Labels: domain:ci, catfooding, enhancement
- Relates to or extends: #1979, #3943

### [P2] Fail loud on shard-duration length mismatch instead of silent uniform fallback  (C-25, CLOSED-ONLY)
- Scope: module-tests.yml emits a ::warning/::error and a summary line when len(durations) != len(node_ids); an arch/CI test re-collects each module with SELECTION_MARKER_EXPR and asserts agreement.
- Labels: domain:ci, reliability
- Relates to or extends: #4951

### [P3] Dev environment: make one documented sync command yield every tool the test suite and WP gates invoke (test+lint extras, radon) and skip-with-reason when absent  (C-04, UNCOVERED)
- Scope: Either fold test+lint into the dev dependency group or make tests needing ruff/mypy resolve them through the same interpreter and skip with an actionable reason; drop radon from WP validation or declare it.
- Labels: tech-debt, catfooding, good first issue
- Relates to or extends: #2803

### [P3] Test-seam hygiene: retire source-text-inspection tests and module-attribute patching of re-exported names in favour of injected seams  (C-13, PARTIAL)
- Scope: Inventory inspect.getsource tests and @patch targets on re-export facades (acceptance, tasks, implement); convert to behaviour tests or DI seams; add a lint/arch check against patching names re-exported from a package facade.
- Labels: tech-debt, tidy-up
- Relates to or extends: #2561, #2935, #4851

### [P3] Mutation plugins must prove they took effect; restore a (nightly) mutation lane  (C-14, UNCOVERED)
- Scope: Each scripts/mutants plugin asserts its patch bound (bind count > 0) and distinguishes kills from TypeErrors; run the plugin set in ci-nightly; extract inline guard predicates into importable functions.
- Labels: tech-debt, domain:ci
- Relates to or extends: #4810

### [P3] Guard contradictory tier markers (module pytestmark + function marker) and move report-only diagnostics off warnings.warn  (C-18, PARTIAL)
- Scope: Arch check rejecting nodes carrying mutually exclusive tier markers; convert intentional warnings.warn diagnostics to logging or a report fixture.
- Labels: tech-debt, domain:ci
- Relates to or extends: #2979, #4729

### [P3] Residual of #3844: 'Add scaffold for mission <slug>' auto-commit still fails commitlint; derive the ignore list from the generators  (C-22, CLOSED-ONLY)
- Scope: Add scaffold to the ignore (or emit a conventional 'chore(mission):' subject); add a test that every lifecycle commit-message generator's output passes commitlint; drop 'feature' from the ignore regex.
- Labels: tech-debt, domain:ci, good first issue
- Relates to or extends: none

### [P3] Mechanism for pre-merge proof of workflow_run/schedule-only CI edits (branch dispatch recipe + actionlint), feeding #1271's evidence gate  (C-24, PARTIAL)
- Scope: Script workflow_dispatch of ci-nightly/ci-aggregate against the PR branch and record run ids; add actionlint over changed workflow files in ci-router; document which workflows can only be proven post-merge.
- Labels: domain:ci, enhancement
- Relates to or extends: #1271, #4845

### [P3] Regenerate derived CI census artifacts at merge instead of merging them textually  (C-26, PARTIAL)
- Scope: Mark ci_topology_census.json/_gate_coverage.py as generated (merge driver 'ours'+regen or not committed), with a freshness check.
- Labels: domain:ci, tech-debt
- Relates to or extends: #2929

### [P3] Revisit diff-cover CRITICAL_PATHS scope (acceptance/, validators/, cli/ unenforced)  (C-27, PARTIAL)
- Scope: Decide per #1843 tiering which src trees join CRITICAL_PATHS; document the --cov dotted-module requirement in testing docs.
- Labels: domain:ci, tech-debt
- Relates to or extends: #1843

### [P3] Lint-policy papercuts: sanctioned file-digest helper for TID251, single UTC-stamp constant, clarify __init__ version-bump rule scope  (C-29, PARTIAL)
- Scope: Add kernel helper for raw file digests and allow it under TID251; consolidate '%Y-%m-%dT%H:%M:%SZ' into one kernel clock helper; state in CLAUDE.md/charter whether nested package __init__.py changes need a version bump.
- Labels: tech-debt, tidy-up, good first issue
- Relates to or extends: #4506, #1928

### [P3] ATDD tactic: prove a red-first anchor is red on the base for the intended reason (record failure text; invert bug-encoding characterization tests)  (C-34, UNCOVERED)
- Scope: Add to the ATDD doctrine tactic: record the RED failure message, choose RED shapes that do not break collection, and treat characterization tests pinning the defect as the anchor to invert.
- Labels: domain:charter, documentation
- Relates to or extends: #4891

## Sequencing and dependencies (planner view)

1. **Wave 1: false-green correctness, parallelisable.** C-23 (put mypy and commitlint into live CI), C-01 (a lane-scoped interpreter or an import-origin guard; extends #2803), C-17 (a quarantine lane). None depends on another.
2. **Wave 2: make local runs honest and bounded.** C-03 (lock-conformance preflight) comes before C-16 (known-red ledger), because a stale venv poisons any baseline. C-09 (default timeout) and C-10 (concurrency-safe sessions) come before C-08 (making the arch suite runnable), because hangs and eviction are the reasons the arch suite cannot run locally. C-20 (`ci-parity --run`) depends on C-08 and reuses `scripts/ci/gate_selection.py`.
3. **Wave 3: CI plumbing hygiene.** C-25 (fail loud on the silent uniform fallback), C-24 (feeds #1271), C-26, C-27 (scope decision under #1843).
4. **Wave 4: test-quality doctrine and tidy-ups.** C-12 → C-13 → C-14 (a mutation lane is meaningful only once the seams are real). Also C-18, C-22, C-29, C-34, C-11, C-02, C-04.

## Honest limits

- **Semantic search was heavily rate-limited.** The GitHub search API returned 403 on about half of my calls, because other delegates share the quota. Across 34 clusters I completed about 12 semantic searches. For every cluster I also grepped titles in `open_issues.tsv` with several keyword variants and read the bodies of about 20 key issues, including all the COVERED matches. UNCOVERED verdicts for C-04, C-14, C-17, C-23 and C-34 rest on title grep plus one semantic query each. An open issue whose title uses different words could have been missed.
- **Several verdicts rest on source I read at HEAD 4fb54f3f (2026-09-26).** The claims come from reading the code, not from running anything:
  - pytest.ini has no `--timeout`.
  - No workflow mentions mypy or quarantine.
  - The commit-msg job runs only `git log ... || true`.
  - The commitlint ignore regex does not match `Add scaffold for mission`.
  - The shard-timing fallback is still silent.
  - The diff-cover glob now uses git pathspecs.
  - The agent-command freshness stamp exists.
  - tests/sync was deleted.
- **Much ci-gates-routing evidence predates the CI rewrite (#3995 router and module registry).** It covers dorny groups, core_misc and ci-quality.yml, so I folded it into the class-level owner (#4708) rather than re-deriving each old defect.
- **Some items are one-off notes rather than fixable causes** (for example items 79, 80, 87, 129 and 171). I attached them to the nearest cluster for completeness. They inflate item counts slightly.
- **The #2803 and #3046 matches were confirmed from issue bodies. The other adjacent matches are title-level only.**
