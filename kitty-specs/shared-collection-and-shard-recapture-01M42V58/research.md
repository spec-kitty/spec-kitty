# Research: Shared battery collection and complete shard-timing provenance

Grounded on the primary branch (`main`) at `b2c466d7d1`. Findings come from two grounding scouts and two post-spec adversarial reviewers, each adjudicated against the code where they disagreed.

## Findings that shaped the scope

| # | Finding | Source |
|---|---|---|
| R-01 | Each per-PR job runs `collect_universe()` once. `test_fast_tier_marker_completeness.py` is in battery leg 1/2, `test_same_tier_uniqueness.py` in leg 2/2 (resolved with `_gate_coverage._battery_partition()`), and `tests/ci/test_corpus_blocking_home.py` in the `ci` module shard. | `tests/architectural/_gate_coverage.py:1576`, `:1952` |
| R-02 | The legs run in `ci-router.yml` on Python 3.12; module shards run in `ci-modules.yml` → `module-tests.yml` on the project pin (3.11). Both trigger independently on `pull_request`. | `.github/workflows/ci-router.yml:709-784`, `.github/workflows/ci-modules.yml` |
| R-03 | The measured 114 / 166 / 170 s is one collection inside a module-scoped fixture under `-n 4`. | `kitty-specs/ci-runtime-stabilisation-01M3TZH6/evidence/ci-measurements.md` |
| R-04 | `collect_universe()` passes the whole inherited environment, a fresh `HOME`, and `-o addopts=` to a `pytest --collect-only` subprocess, and records marker **names** per item. | `_gate_coverage.py:1952-2010`, `_gate_collect_plugin.py` |
| R-05 | `tests/conftest.py` adds a `skip` marker at collection from `sys.platform`, `SPEC_KITTY_RUN_QUARANTINE` and `SPEC_KITTY_RUN_PERFORMANCE`. These change recorded marker names. | `tests/conftest.py:316-344` |
| R-06 | The mismatch allowlist holds 17 modules; `_BASELINE_ALLOWLIST_COUNT = 17`. `charter`, `agent` and `consolidation` are outside it and have drifted. | `tests/architectural/test_module_length_agreement.py:118-147`, issue #5536 |
| R-07 | The scheduled recapture is single-module by construction (`MODULE = "charter"`, one in-process pytest run), computes drift only after a full capture, trusts exit status 0 or 1, publishes to one fixed branch, and skips publishing while a proposal is open. Its job is gated to the primary branch. | `scripts/ci/recapture_charter_shard_timings.py`, `.github/workflows/ci-charter-shard-recapture.yml:57-124` |
| R-08 | The floor-constant and derived-set items of #5561 were ruled out in the parent issue's triage (2026-09-26) and the code agrees. | triage comment on the closed parent issue; `tests/architectural/test_mutation_ownership_routing.py:1018` |

## Decisions

### D-01 — Key is the committed tree plus the environment

- **Decision**: key = digest of (`git rev-parse HEAD^{tree}`, interpreter version, `sys.platform`, digest of installed distributions, values of the declared environment family). The store is disabled when `git status --porcelain` is non-empty.
- **Rationale**: collection depends on files well outside `tests/` (parametrised ids built from `src/`, `packs/`, `.github/`, `docs/`, `kitty-specs/`, `scripts/`). A hand-kept input list would go stale; the tree id covers every tracked file in about 2 ms. Untracked files that affect collection make the checkout dirty, which disables the store.
- **Alternatives considered**: hashing an enumerated file list (unsound, R-04/R-05); hashing file contents of the whole tree (slow, redundant with the tree id).

### D-02 — Declared environment family

- **Decision**: the key includes every variable named `SPEC_KITTY_*` and `PYTEST_ADDOPTS`, minus variables the collection itself sets (`SK_GATE_*`), per-process pytest/xdist variables (`PYTEST_CURRENT_TEST`, `PYTEST_XDIST_*`), and variables the test session sets for itself (`tests/conftest.py` writes `SPEC_KITTY_REAL_HOME_FOR_TESTS` and `SPEC_KITTY_ENABLE_SAAS_SYNC` into every pytest process; a pre-test step has neither). A test asserts that the key computed inside a pytest process equals the key computed in a plain process, so a new session-set variable cannot silently stop every match. The family and its exclusions are one constant with a test that a new `SPEC_KITTY_*` switch changes the key.
- **Rationale**: R-05 shows two such switches change the universe today; keying the family, not a list of two, means a future switch is covered without an edit. Excluding per-process variables is required or no two workers would ever share a key.
- **Alternatives considered**: hashing the whole environment (never matches between a step and a test); a two-variable list (stale on the next switch).

### D-03 — Store location and retention

- **Decision**: one directory under the repository's git-ignored cache area, resolved by one helper; one file per key; a write evicts every other key's file.
- **Rationale**: FR-012. A single current record bounds the size (one record is about 10.7 MB) and makes the `actions/cache` path a single directory.
- **Alternatives considered**: the system temp directory (not restorable by path across CI steps in a stable way); keeping N records (no use case).

### D-04 — Lock and write

- **Decision**: reuse `kernel.locks.machine_file_lock` around "read-or-collect-then-write", called with `blocking=True` (its default is non-blocking) and a timeout above the 900 s collection timeout, on one fixed lock file; write to a temporary file and rename.
- **Rationale**: FR-005; an existing, tested primitive (C-001 forbids changing it, not calling it).
- **Alternatives considered**: a new lock helper (second authority); no lock (parallel workers each collect).

### D-05 — Transport is a pre-test step plus `actions/cache`

- **Decision**: per ruling `01M42VM0CEBBZHCJEAN4KTDYYC`, each consuming job collects before pytest. `actions/cache` restores and saves the store directory keyed on the collection key so a re-run of the same checkout restores instead of collecting.
- **Rationale**: R-02 makes a single shared producer impossible without aligning interpreters and chaining workflows. The content key is the guard, so a cache entry from another commit can never match.
- **Alternatives considered**: producer job with artefact hand-off (adds 1.5–2 min to the legs, still two collections); local store only (does not address R-03).

### D-06 — The consuming module shard is selected, not hard-coded

- **Decision**: in `module-tests.yml` the pre-test step runs only in per-PR mode and only when the shard's selected test list contains the consuming test node (the selection is per test, and the consuming file spans both `ci` shards). A test pins that the named node still exists and still requests the universe. Full mode is excluded because its warm-up may rewrite the tracked lock file, which would make the checkout dirty.
- **Rationale**: the workflow is shared by every module and shard; an unconditional step would add a collection to every shard.
- **Alternatives considered**: `if: module == 'ci'` (runs on every `ci` shard, and breaks silently if the test moves).

### D-07 — Fallback after a successful pre-test step is a failure

- **Decision**: a post-pytest check reads the report lines and exits non-zero when the pre-test step stored a record and any test in the job reported `collected`.
- **Rationale**: FR-011. Without it, a key that never matches is invisible, because the fallback keeps every gate green.
- **Alternatives considered**: summary-only reporting (nobody reads a green job's summary).

### D-08 — Recapture finds drift with a count-only pass

- **Decision**: the generalised recapture first collects each module's count (one count-only pass per module, no test execution), compares them with committed counts and provenance, and captures only modules that differ, each in its own subprocess via the canonical producer. When a recapture proposal is open, the proposal branch's timings file is the baseline, so carry-over makes progress instead of repeating the same modules.
- **Rationale**: R-07: today's script must run the full 18-minute capture to learn whether anything drifted. Count-only passes cost seconds per module.
- **Alternatives considered**: capture everything every night (hours); keep charter-only and document manual recapture (the #5536 class).

### D-09 — Time budget and carry-over

- **Decision**: the script takes a budget; it stops starting captures when the budget is spent, reports the deferred modules, and orders candidates so the longest-deferred goes first. No state file: the next run recomputes drift.
- **Rationale**: FR-019, NFR-007; statelessness keeps the script idempotent.
- **Alternatives considered**: a persisted queue (new state to corrupt); raising the job timeout without a budget (unbounded).

### D-10 — Refreshing an open proposal

- **Decision**: when the proposal branch has an open pull request, the workflow adds an ordinary follow-up commit on top of it. It never force-pushes.
- **Rationale**: FR-020 against the existing rule (R-07) that a branch with an open proposal is never force-pushed. A fast-forward push respects that rule.
- **Alternatives considered**: skip while open (today's behaviour; proposals go stale and the strict check stays red); force-push (forbidden by the existing design).

### D-11 — Valid capture

- **Decision**: per ruling `01M42VM1YPDQPPGP1FK0W9AECK`, a provenance record is valid when the capture run's exit status is 0 or 1 and it recorded at least one duration. The rule is one shared predicate used by both the recapture script and the provenance-completeness check.
- **Rationale**: one authority for "trustworthy capture"; today it exists only inside the charter script.
- **Alternatives considered**: exit status 0 only (holds the mission on unrelated red tests).

### D-12 — Allowlist removal, not zeroing

- **Decision**: delete `_MISMATCH_ALLOWLIST`, `_BASELINE_ALLOWLIST_COUNT`, and the tests that only police the allowlist. Keep the agreement check and its self-mutation proof.
- **Rationale**: Burn-down Policy (a) and ADR `2026-09-30-1`: a drained baseline entry is removed. An empty dict would leave the shape tests passing vacuously.
- **Alternatives considered**: keep an empty dict and a zero baseline (vacuous tests, a mechanism waiting to be refilled).

### D-13 — Capture order and environment

- **Decision**: captures run from `uv sync --frozen --all-extras` on the pinned interpreter, serially, by the orchestrator, after every code-bearing work package is approved; `ci` and the module that owns the mission's new tests are captured last. A rebase after capture is followed by the count-only pass, recapturing only what moved.
- **Rationale**: the mission adds tests to `tests/ci` and `tests/architectural`; capturing earlier would be stale on arrival.
- **Alternatives considered**: dispatching the CI capture workflow (the generalised workflow is gated to the primary branch until it lands).

## Planning checks

| Check | Result |
|---|---|
| The CI cache can restore the store in a re-run, keyed on the collection key | Supported: `actions/cache` restores by exact key within the same ref scope; both workflows can use the same key because the key already includes the interpreter. Verified in implementation by the workflow-shape test and the first re-run. |
| No parametrised test id embeds the temporary home directory | Confirmed: 0 differences across two passes (see "Two-pass collection" below). |
| Total serial capture time | Not measurable before implementation. Committed durations for the 17 sum to about 27 minutes but are stale; `charter` alone is about 18 minutes. Measured on one small and one large module first, then recorded in `evidence/`. |
| Which environment switches change collection | `SPEC_KITTY_RUN_QUARANTINE`, `SPEC_KITTY_RUN_PERFORMANCE`, `sys.platform`, and `PYTEST_ADDOPTS` (R-04, R-05). Covered by D-02. |
| Nightly job layout for the equivalence check | `ci-nightly.yml` runs marker lanes as separate jobs; the comparison is added as its own small job so it survives an upstream red. |

### Two-pass collection

Two consecutive `collect_universe()` calls, each with its own fresh `HOME`, returned 54,723 records with 0 differences (95.3 s cold, 21.6 s warm, on a workstation). No test id or marker set depends on the temporary home directory. Details: `evidence/two-pass-collection.md`.

## Brownfield findings (seam map, 2026-10-04)

| # | Finding | Consequence |
|---|---|---|
| B-10 | The skew check passes trivially at `shard_count == 1`, and counts also encode the per-shard time cap (`.github/ci-module-registry.yml:173-199`). | FR-016 never reduces a count: a count that fails skew on recaptured durations is raised to the nearest higher count that passes; a needed reduction goes to the operator. |
| B-01 | No shard-count derivation tool exists. `scripts/ci/reconcile_shards.py` reconciles coverage artefacts; `shard_count` is declared in the registry and validated by `tests/architectural/test_module_shard_registry.py:274` (`_lpt_bin_pack` :116, `_MAX_SKEW` :59). | FR-016 and C-004 were reworded: counts must pass the existing skew check on recaptured durations. No derivation tool is built (it would be a second authority beside `scripts/ci/shard_select.py:lpt_assign`). |
| B-02 | `module-tests.yml:195` writes `shard_tests.txt` into the checkout; it is not git-ignored, so `git status --porcelain` is non-empty for the rest of the job. | The shard list moves to the runner's temp directory, and `check` also fails on `bypassed` when the pre-test step stored a record (D-14). |
| B-03 | The #5536 publish failure is `403 Permission denied` on `git push --force` to the proposal branch (runs 37182764995, 37097776055). The last six scheduled runs failed; three ran 30m19–21s against the 30-minute cap. | FR-021 became "classify and make loud". The token is the operator's to fix. The time budget (D-09) addresses the cap. |
| B-04 | There is no minimum-universe constant today. | The store adds one sanity floor (D-15); it is a corruption guard, not a ratchet. |
| B-05 | `uv sync` and pytest share one `run:` block in the heavy battery job (`ci-router.yml:758-773`). | The block is split so the key can be computed after the environment exists and before pytest. |
| B-06 | Workflow step shape is pinned by `tests/ci/test_ci_module_wiring.py:485-556`, `tests/ci/test_xdist_worker_policy.py`, `tests/architectural/test_no_duplicate_suite_execution.py:240,911`, `tests/architectural/test_dual_mode_contract.py:226-310`, `tests/architectural/test_module_tests_matrix.py:155-266`, `tests/ci/test_nightly_exit_code_honesty.py:58-302`, `tests/ci/test_fork_guard.py:124`. `gc.suite_invocations` does not see a `python -m` step. | The workflow work package runs exactly these files. |
| B-07 | `actions/cache` is pinned once, at `.github/actions/warmup/action.yml:103` (`55cc8345863c7cc4c66a329aec7e433d2d1c52a9`, v6.1.0). | Reuse the same pin. |
| B-08 | The recapture workflow's file name is listed in `_gate_coverage.WORKFLOW_FILES` (:138) and `test_no_duplicate_suite_execution.NON_CHANGE_TRIGGERED_WORKFLOWS` (:176); its job key is pinned in the script's test; the pinning inventory is re-derived by `tests/release/test_pinning_inventory_fresh.py`. The secret name is a repository secret. | The script and its test are renamed in the recapture work package; the workflow file is renamed in the final code work package, after the store work has landed, with the inventory regenerated. The secret keeps its name. |
| B-09 | `_gate_coverage.py` is on the ruff-format exclude ratchet. | Never run `ruff format` on it by explicit path without `--force-exclude`. |

### D-14 — `bypassed` after a successful pre-test step also fails the check

- **Decision**: `check` exits non-zero when the pre-test step stored or reused a record and any later request in the job reported `collected` or `bypassed` for the repository root. `bypassed / root-override` is exempt.
- **Rationale**: B-02 showed a dirty checkout would silently disable reuse while every gate stays green.
- **Extension (WP02 review, 2026-10-04)**: the same rule applies to the pre-test step's own line. A pre-test step that is bypassed for a dirty checkout, an unavailable git, or a lock or store failure, or that collects without storing, fails both `collect` and `check`. Otherwise a pre-test step that never stores would leave reuse permanently broken behind a green job. The only legitimate fallback is an unsupported platform.
- **Alternatives considered**: ignoring untracked files in the dirty test (an untracked new test file changes collection); summary-only reporting.

### D-16 — The key overlays the operator env file

- **Decision**: before selecting the environment family, the key applies the product's own operator env-file loader to a copy of the environment (real values win, as in the product). An unreadable env file bypasses the store with reason `env-file-unreadable`.
- **Rationale**: the command-line package seeds a git-ignored `.kitty.env` into the environment when it is imported. A pytest session imports it; a plain pre-test process may not. On a machine with such a file the two computed different keys, so reuse could never happen there. Found after merging the primary branch, in the repository root checkout, which has such a file; lane worktrees and CI do not.
- **Alternatives considered**: excluding each affected variable by name (any operator-chosen variable would hit the same problem, and such a variable can change collection).

### D-15 — Sanity floor for a stored universe

- **Decision**: a stored record with fewer than 1,000 records is treated as absent. The universe holds 54,723 records today.
- **Rationale**: FR-007; guards against a truncated-but-parseable file. It is deliberately far below the real size so it never needs maintenance.
- **Alternatives considered**: a tight floor near the real count (a ratchet needing upkeep, and C-006 forbids new baselines).

## Open risks carried into tasks

- Existing architectural gates parse the two workflows; adding steps may trip a step-shape pin. The brownfield scout maps them before work is cut.
- Renaming the recapture script and workflow touches workflow-inventory gates and documentation references.
- A workstation capture feeds the skew check with workstation durations. Shard counts depend on relative durations within a module, so the skew is second-order; the first scheduled run on the primary branch corrects it.
