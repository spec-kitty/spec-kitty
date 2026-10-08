# Research: Mission Status contract, health, drift and ops reads

Mission `mission-status-health-drift-ops-01M464D3` (#5776). Evidence ledger of the plan phase, 2026-10-06. Every figure was taken on this checkout (`.venv` Python 3.11.15, CLI 4.0.0rc6, branch merge-base `b61d1fa336478dae023a2d82808fef0d811816c3`) unless a row says otherwise. Counts move with the tree: only the floors of the plan bind (plan D-P13). Commands use `<scratch>` for a scratch directory and `<tmp>` for a temporary directory whose ancestors hold no `.git`; no absolute path of this host appears here (C-005). Plain text fences only (the corpus round-trip gate collects `yaml` fences of this directory).

## R-1 Upstream moved after the plan base

**Question.** Is the plan base current?

**Evidence.** `git fetch --dry-run origin` lists a newer `main` tip than the local `origin/main` (`b61d1fa33`); the GitHub compare API (`gh api repos/spec-kitty/spec-kitty/compare/<base>...<tip> --jq ...`, read-only) reports the tip `2261ad522` as 133 commits ahead of the base. The ref was **not** fetched (fetching moves the base ref that the cut-over guard reads, the previous slice's friction F-38). The changed files fall in these groups:

- **No file under `contracts/` and none under `tests/contract/`**: the contract tree and the reference-reader test tree are identical at the base and at the tip, so the frozen Project copies, the byte-identity baseline and the `breaking_check.py` spike (R-5) are valid for both.
- `.github/workflows/ci-router.yml`: one line, a `setup-uv` action pin in another job; the `contract_tools` group is unchanged.
- `src/` files that the reference reader imports: `coordination/surface_resolver.py`, `mission_metadata.py`, `lanes/branch_naming.py`, `status/__init__.py`, `missions/_read_path_resolver.py`, `workspace/context.py`, `core/dependency_graph.py`. An upstream decision record dated 2026-10-05 (not on this checkout yet) concerns bare-slug coordination directories that carry two directory names and a consolidation fold; it states that none of 50 coordination Missions in this repository has a bare primary directory.
- `pyproject.toml` and `ruff.toml` changed; five new Mission directories and one new Op file arrived (the corpus counts of R-2 are therefore a lower bound of the tip's).

**Decision.** D-0 (plan, Branch contract): fetch, merge `origin/main` into the Mission branch, re-run the symbol check (quickstart), re-run the gate files, classify the delta on the files above. A change in the observable outcome of the coordination resolver is reported to the orchestrator, not absorbed (spec R-9; this phase did not read the resolver beyond its outcomes, R-9 below).

## R-2 The corpus, re-counted (A-2)

Read-only scripts (quickstart, "Counts of the corpus"); plain JSON reads, no product reader.

| Fact | 2026-10-05 (spec) | 2026-10-06 (this checkout) |
|---|---|---|
| Directories under `kitty-specs/` | 569 | 569 (all hold a `meta.json`) |
| Status files: both / log only / snapshot only / neither | 536 / 31 / 0 / 2 | 536 / 31 / 0 / 2 |
| `lanes.json` files; legacy-shaped (`feature_slug`, no `mission_slug`) | 489; 1 (`064-complete-mission-identity-cutover`) | 489; 1 (the same Mission) |
| Missions declaring a `coordination_branch`; merged (`merged_at`) | not stated | 51; 14 |
| Op files in `kitty-ops/` (ULID-named `.jsonl`) | 480 | 480 |
| Other entries in `kitty-ops/` | index, spine, `lifecycle.jsonl`, `.yaml` files, `evidence/` | the spine, `lifecycle.jsonl`, `evidence/` and 8 `.yaml` review files; no index |
| Spine records | 6 | 6 (each closes an Op that is open in its own file) |
| Op outcomes by direct scan | 467 own-file completions, 7 legacy | 467 own-file closed with `closed_by`, 7 legacy completions with no spine record, 6 open in file and closed by the spine |
| So served / skipped | 473 / 7 | 473 / 7 |
| Evidence of the 467 own-file completions | none 351, absolute 32, free text 56, relative 28, url 0 | none 351, absolute 32, free text 56, relative-or-other 28 |
| Distinct `profile_id` among them | not stated | 12 (most frequent three: 157, 93 and 65 Ops) |

This Mission's own directory is one of the 31 log-only Missions until its status is bootstrapped (spec, Reflexivity). The scan is a one-off measure; IC-01 repeats it after the D-0 sync.

## R-3 Kind 3 inputs, the fallback agreement and the corpus condition

**What this phase measured (it did not run the resolver; the spec forbids peeling into its internals and the re-measurement of kind 3 under the final rule is IC-01's first task).** Structural inputs only, by plain git and JSON:

- 51 Missions declare a coordination branch; 14 are merged (the resolver re-anchors those on their own directory); 37 are not merged and the declared branch is neither a local head nor in `git worktree list --porcelain`. **37 equals the spec's fallback count** (35 of topology `coord`, 2 of `lanes_with_coord` per the spec's own derivation).
- Of the 37, **0 has the declared branch as a remote-tracking ref only**: the corpus condition of FR-025 (no non-merged Mission declaring a branch present only on a remote or as a remote-tracking ref) **holds today**. The clone holds 0 local `kitty/*` heads and 15 remote-tracking `kitty/*` refs; `git ls-remote --heads origin` lists 15 `refs/heads/kitty/*` heads (all attributed to merged Missions by the 0 above).
- `git ls-remote --heads origin` succeeds from this host (a read-only query through the network), so the remotes were reachable for every figure of this phase.

**Not measured and owed (IC-01, step 1):** the kind-3 population under the final rule (completion first, three-way manifest classification, expected lane, coordination branch versus `mission_branch`, local listing). The old 93 of the spec included the coordination false positive that ARCH-001 removes; **no plan-time floor or assertion rests on it**, and no kind-3 corpus floor is ever pinned.

## R-4 FR-013: Gate B and the no-op, re-checked

| Check | Result |
|---|---|
| `.kittify/derived/` exists in the corpus | no (`ls` fails) |
| It is ignored | yes (`.gitignore` line 65, `git check-ignore -v`) |
| It is tracked | no (`git ls-files .kittify/derived` lists 0 files) |
| `validate_derived_views` (`src/specify_cli/status/validate.py`) | still a no-op stub whose docstring says frontmatter lane drift validation was removed; it returns an empty list |
| `check_drift` of `status/doctor.py` | present; not re-read beyond the spec's statement |

Gate B fails and the decision of FR-013 (not shipped) stands. IC-01 repeats the three commands after the D-0 sync; a change returns the decision to the squad.

## R-5 The additive proof, measured on a spike (FR-022 item 3)

**Method.** Scratch trees under `<tmp>/spike`: `base` is `git archive HEAD contracts/mission-status contracts/_shared` (the contract tree on the base); `cand` is a copy whose `schemas/Project.yaml` gains the five required properties (`health` carries `x-provisional`, the other four a citation each; nothing else changes, no new path); `lowered` and `samemajor` are copies of `base` whose `info.version` is rewritten to `0.9.0` and `1.0.0`. The pinned `oasdiff` 1.32.1 was fetched by `contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest <scratch>/tools --only oasdiff` (checksum verified by the installer). `breaking_check.py --root <tmp>/spike/cand --baseline-root <tmp>/spike/<baseline>`; the module layout is `<root>/mission-status` and `<root>/_shared`.

| Baseline | Exit | Result |
|---|---|---|
| lowered major (`0.9.0`) | 0 | `counts: modules=1 baselines=1 breaking=4 provisional_changes=1 no_baseline_initial=0 preview_ref=skipped`; the provisional line is `GET /project: added the required property health` |
| same major (`1.0.0`) | 1 | four `BREAKING_WITHOUT_MAJOR` lines, one each for `currentBranch`, `lastActivityAt`, `schemaVersion`, `specKittyVersion` (all `GET /project`, status `200`), same `counts:` line; candidate version `1.0.0-SNAPSHOT` |

**Pinned by the plan:** `breaking=4` (the four non-provisional additions, all on `GET /project` 200). `provisional_changes` is 1 on this spike and is re-measured and pinned on the final tree (the new operations and schemas carry provisional elements). Controls to record at W-7: an extra property on `WorkPackage` raises `breaking` to 5; with the `Project` change reverted and the `/drift` and `/ops/invocations` operations and their two tags removed, the same-major run exits 0 (reverting the `Project` change alone exits 1 with `BUNDLE_CHANGED_VERSION_SAME`, because the two new operations still change the bundle). IC-04 repeats the lowered-major run after the two path keys and the two tags are added, to show that a new path and a new tag change neither `breaking` nor the exit code.

**Also measured:** against a baseline whose version equals the candidate's, `breaking_check.py` refuses any bundle change (`BUNDLE_CHANGED_VERSION_SAME`) and against `1.0.0` it treats `1.0.0-SNAPSHOT` as below the baseline for non-breaking changes; hence the scratch baseline of the lowered-major run (spec FR-022 item 3).

## R-6 Baselines of the gate set (run, 2026-10-06, `TMPDIR` outside any directory whose ancestors hold a `.git`)

| Command | Result |
|---|---|
| The ten `contracts/tools` checks (quickstart) | exit 0 each; `layout_check` 8 path files; `citation_check` 191 properties, 140 `x-source`, 51 `x-derived`, 93 inputs resolved; `provisional_check` 22 provisional elements; `example_check` 75 validated; `enum_pin_check` 7 enums, 43 values; `leak_scan` 1062 files, 37 artifact-path values; `structure_check` 20 README headings, 7 CHANGELOG headings; `codeowners_check` rules=1; `no_pytest_scan` 25 scripts. `citation_check` prints `CITATION_REUSE` lines (a property citing a symbol used by more than five properties) and `event_mapping_check` prints `LIFECYCLE_TYPE_NOT_FORWARDED` lines; both exit 0 (notes). New properties that cite `materialize_snapshot`, `StatusSnapshot` or `MissionFinding` add reuse notes; they are not failures. |
| Nine named gate files (plan, gate set) | 352 passed, 1 skipped, **17 errors in 114 s**: `test_same_tier_uniqueness.py` (16) and `test_corpus_blocking_home.py` (1), all `ModuleNotFoundError: respx` raised while collecting the test universe (`tests/auth/*`, `tests/zeitgeist_client/*` and eight other modules import `respx`, a declared and locked package that the hand-built `.venv` lacks). Class 4, stale venv. **These two files are exactly the gates that guard the registrations of a new module.** |
| Tool-job selection (`pytest -m "corpus and not windows_ci" tests/contract` minus three `--ignore`, `-n 4 --dist loadfile`) | 1,778 passed, 37 skipped in 176 s |
| Reality module and payload helper (`-m "corpus and not windows_ci"`) | 819 passed in 108 s |
| Eight census files of the plan-time selection (home-pin, global-state, dead-symbol; the heavy battery owns the home-pin and dead-symbol ones, see plan gate set) | 167 passed, 4 failed in 173 s; all four are `No module named mypy` (`test_spec_kitty_home_pin_census.py::test_t024_sc005_mypy_strict_over_the_real_exempt_module` and three in `test_spec_kitty_home_pin_guard.py`). Class 4. |
| `test_layer_rules.py` and `test_pyproject_shape.py` | 83 passed in 25 s |
| `tests/architectural/test_archive_root_byte_identical.py` | 25 passed in 8 s |
| `spec-kitty cutover-guard --base-ref origin/main` | 1 Mission touched, 0 un-cut-over |
| `ruff check .`, `ruff format --check .`, `ruff check --select TID251 .` | **not run**: the `.venv` has no ruff (`uv.lock` pins 0.15.12; no offline cache). Class 4. |
| `pytest --collect-only -m "corpus and not windows_ci" tests/contract/test_mission_status_detail.py` | 241 tests; with `-m "fast or unit"` none (exit 5), which is how a non-`fast` module is shown |

No red is a product defect, so no tracker issue is owed now. The orchestrator's Step 0 re-takes the baseline in a synced environment before any dispatch; a surviving red is binned and, if pre-existing, reported before work continues (plan, Baseline).

## R-7 CI placement, registrations and the router group

- `ci-router.yml` job `tests-contract-tools` (name `tests (contract tools)`, 15-minute timeout, `uv sync --frozen --no-install-project`): `pytest -m "corpus and not windows_ci" tests/contract` with three `--ignore` modules (the example round trip, the payload helper and the reality check), `-n 4 --dist loadfile`, checkout depth 0. A new corpus-marked module under `tests/contract/` is selected automatically.
- Job `tests-corpus-blocking` (`tests (corpus-blocking)`, 10-minute timeout): the three ignored modules, two integration modules and one performance class; it is where the reality extension runs.
- Selection: both jobs run when the router group `corpus` (owns `contracts/**`) matches; the tool job also when the `contract_tools` group matches (`tests/contract/**`, the two contract workflows, the lock, pytest configuration, `tests/conftest.py`, `**/status/lifecycle_events.py` and the `**/...` globs of the reader's `src/` imports).
- **The import pin.** `tests/ci/test_contracts_workflows.py` derives the required `src/` file list from the imports of every `tests/contract/*mission_status*.py` module (`ImportFrom` and `Import` nodes, a candidate `.py` or `__init__.py` under `src/`) and fails until each is named in the group. Hence plan D-P8 (new helpers carry `mission_status` in their names; entries land in the commit that adds the import).
- **The two registrations a new corpus-marked module needs**: a row in `_CORPUS_MARKED_MODULES` of `tests/architectural/test_ci_corpus_trigger_completeness.py` (the test fails both for a marked module missing from the registry and for a registry row whose module is missing or unmarked), and a `--deselect tests/contract/<module>` in the single physical `built-in-corpus-suite` command line of `.github/workflows/packs.yml` (`test_same_tier_uniqueness.py` and `test_no_duplicate_suite_execution.py`). The previous slice proved both necessary and sufficient on a scratch repository (its research R-6).
- **Heavy battery.** Editing `.github/workflows/packs.yml` selects `architectural-heavy` through router group `ci_config` (`.github/workflows/**`); editing the registry test selects it through group `architectural` (`tests/architectural/**`). Two shards, 30-minute timeout each, full history, `--all-extras`; CI-owned.
- `architectural-fast` runs `pytest tests/architectural -m "not performance and not stress and not timing" -n 4 --dist loadfile` minus a handful of deselected files that have their own jobs (terminology, layer rules, pyproject shape, archive root); `layer-rules`, `archive-freeze`, `terminology`, `import-linter`, `ruff`, `uv-lock`, `regen-check`, `docs-lint`, `commit-msg` and `markdownlint` are router jobs of the same names (the last two print only; `markdownlint` ends in `|| true`).
- `contracts.yml` jobs (the FR-028 record has one line each): `verify-pins`, `python-checks`, `validate-bundle`, `resolver-parity`, `lint`, `breaking-change`, `release-dry-run`, `negative-tests`, `contracts-gate`. Triggers: `pull_request` and `push` to `main` on `contracts/**`, `tests/contract/**`, `.github/CODEOWNERS`, the two contract workflow files, `uv.lock`, `pyproject.toml`, `pytest.ini`, `tests/conftest.py` and the lifecycle source; **no `workflow_dispatch`**, so nothing runs before the draft PR.
- The `docs/development/reference/ci-gate-mechanics.md` paragraph on the group already says "the `src/` modules the mission-status reference reader imports", so no documentation edit is needed.

## R-8 Symbols and paths cited (checked on this checkout)

A script (quickstart, "Symbol and path check") resolves every path and symbol of the spec's field catalogue and requirements; all resolve. Where the spec names a symbol without its module, the module is:

- `CoordAuthorityUnavailable`, `MissionMetadataUnavailable`, `InvalidMissionSlug`: `src/specify_cli/status/aggregate.py` (beside `MissionStatus`). `CoordinationBranchDeleted`, `WorktreeRegistryUnavailable`: `src/specify_cli/coordination/surface_resolver.py`.
- `MissionMetaReadError` and `load_meta_fail_closed`: `src/specify_cli/core/paths.py`. `load_meta` and `resolve_mission_identity`: `src/specify_cli/mission_metadata.py` (the module `mission_runtime/identity.py` holds `resolve_mid8`).
- `append_to_index` (NFR-003's writer to replace): `src/specify_cli/cli/commands/invocations_cmd.py`, beside `_iter_index_reverse`, `_iter_records_from_dir` and `_apply_completion_status`.
- `COORDINATION_WORKTREE_NEVER_CREATED` is an error-code string of `src/specify_cli/cli/commands/_coordination_doctor.py`, not a symbol; the spec cites it as the nearest shipped check only.
- `STRICT_FIELDS` is defined in `contracts/tools/fixture_builder.py` (`leak_scan.py` derives its own frozenset from it).
- v1 test-tree helpers the plan relies on (A-5): in `tests/contract/_mission_status_payloads.py`: `resolve_read_dir`, `load_source`, `derive_project`, `write_fixture_mission`, `tree_fingerprint`, `require_cases`, `floor_failures`, `enumerate_missions`, `git_init`, `commit_all`, `Floors`/`FLOORS`. In `tests/contract/test_mission_status_contract_1_1.py`: `DEFERRED_GAPS`, `CHANGED_ALLOWED`, `NEW_PATH_KEYS`, `_make_pair`, `additive_proof_problems`, `ScopeRule`, `SLICE_ALLOWED`, `EXTRA_ALLOWED_REGISTRATIONS`, `scope_problems`, `IN_SCOPE_CHANGES`, `REGISTRATION_CHANGES`. In `test_mission_status_examples.py`: `MIN_EXAMPLES` (47) and `EXPECTED_PATH_KEYS`. `test_enum_pin_check.py` pins the line `counts: enums=7 values=43`.
- Module sizes (lines): payload helper 1,365; reality module 2,099; 1.1 proof module 1,073; examples module 1,388; payload tests 1,158; detail tests 1,788.

## R-9 The resolver: what the plan relies on, and nothing deeper

The plan consumes **outcomes**, as the spec fixes them (FR-015, R-9 of the spec): a directory (own or coordination), or one of `CoordinationBranchDeleted` (the one named fallback), `CoordAuthorityUnavailable`, `MissionMetadataUnavailable`, `InvalidMissionSlug`, `WorktreeRegistryUnavailable`, or a directory outside the repository. Facts read for citation only: the exception classes exist where R-8 says; `src/specify_cli/git/remote_probes.py` holds `_LS_REMOTE_TIMEOUT_SECONDS = 5.0`, `remote_branch_lookup` and `_reset_remote_branch_lookup_cache`; the v1 test helper `resolve_read_dir` catches three of the exceptions and falls back for a read directory outside the checkout (its docstring says so). Anything about how the resolver decides, orders its arms or caches is an assumption of the spec (R-9) and a risk of the plan (P-6), never a rule or a task. The offline fixture (a remote whose URL is a non-existent local path) and the cache reset exist so the observable outcome is constructed, not discovered.

## R-10 Markers and homes of the new modules

`pytest.ini` defines `fast` as pure logic with no subprocess or git, `git_repo` as tests that create real git repositories, `corpus` as tests that read the committed corpus (new corpus readers must carry it; the registry test enforces that), and `timing` as a wall-clock gate that no live CI job selects. The nightly interpreter shard selects `fast or unit` over `tests/contract` on a checkout without tags. Decision (plan D-P5): the project and drift modules carry `contract`, `corpus`, `git_repo`; the ops module `contract`, `corpus`; none carries `fast`; the previous slice's detail module is the precedent (241 tests, none selected by `fast or unit`). Every new module declares a module-level `pytestmark` list; a module without `corpus` would be silently never run by the corpus lanes and is caught only by the registry test.

## R-11 Timed-test precedent (NFR-008, NFR-002)

`tests/contract/test_leak_patterns.py` times the linear e-mail matchers with `time.perf_counter()` over 256 KiB values in several shapes with generous absolute bounds (0.5 second and similar) and no `timing` marker (the marker is selected by no live job). NFR-008 asks for 0.1 second per shape; the plan measures first and records the margin (plan P-7), and times each shape as the minimum of at least 5 in-test repeats (plan D-P16, an operator ruling), because the precedent's generous bound (5 times) is not available at 0.1 second. The 10,000-file `kitty-ops/` listing (30 seconds) and the real 480-file listing (5 seconds) follow the same pattern; neither is sub-second, which is another reason the ops module is not `fast`.

## R-12 Timing proxies, local

| Quantity | Local figure | Source |
|---|---|---|
| Reality module plus payload helper (the unchanged corpus job selection) | 108 s | this phase (819 passed) |
| Tool-job selection | 176 s | this phase (1,778 passed, 37 skipped) |
| One project-wide drift scan composed of the real readers, resolver included, remotes reachable | 40.3, 48.0, 52.0 s (569 directories, 37 fallbacks, 785 subprocesses) | spec NFR-001 (tracer, 2026-10-05) |
| The resolver alone | 36.7 to 37.9 s, 784 subprocesses | same |
| One `Project` build proxy (v1 `load_source` over 569 directories) | 44.4 s | same |
| One listing of the real 480-file `kitty-ops/`, and at least 5 repeats of it (the in-test repeat count) | not measured yet; to be measured, not estimated (estimate about 5 s for the repeats) | IC-01 step 4 |
| The AC-DRIFT row 19 completion equality with `is_mission_completed` over the real corpus (about 518 own directories) | not measured yet; to be measured, not estimated (estimate 5 to 10 s) | IC-01 step 4 |
| Median CI duration of `tests (corpus-blocking)` and `tests (contract tools)` on `main` (last five successful runs) | not measured; the remembered figure of about 3 minutes for the corpus job is not a baseline | the orchestrator's Step 0 (plan, Baseline) |
| A synthetic 10,000-file `kitty-ops/` without index | not measured yet | IC-08 |

The CI-runner figures of NFR-001 and NFR-009 cannot exist before the code does (plan, Departs 3); they are read from the first CI run and recorded at W-7. The bounds (120 seconds) are about 2.3 times the slowest measured scan.

## R-13 Plan-phase hygiene and environment

- **The scaffold.** `spec-kitty agent mission setup-plan --mission mission-status-health-drift-ops-01M464D3 --json` ran once: `result: success`, `scaffold_only: true`, `plan_substantive: false`; it created `plan.md` from the template and modified `status.events.jsonl` (a lifecycle event) without committing. Its JSON carries absolute paths of this host (never paste it). It is not run again: a second call auto-commits.
- **The directory scan** (C-005; the Mission directory joins the corpus the new reads run over): every non-review, non-status file is valid UTF-8, has no NUL, is at most 262,144 bytes, is not a symlink and has zero hits of the human leak patterns line by line. Command in the quickstart ("Hygiene scan"); run at the end of this phase (zero problems) and again by IC-10 and at W-7.
- **Environment hazards.** (a) A stray `.git` exists at the system temporary root: any `TMPDIR` below `/tmp` makes tools that refuse a temporary directory below a repository fail (the tamper check) and mis-resolves placement tests; every run here set `TMPDIR` to a directory whose ancestors hold no `.git`. (b) The checkout `.venv` lacks `ruff`, `mypy` and `respx` (R-6). (c) No JDK, so no Gradle, Java view, TypeScript smoke or vacuum run (J-1 is an orchestrator step). (d) `oasdiff` is available through the pinned installer into a scratch directory (R-5). (e) The global `spec-kitty` on `PATH` is not the checkout's: the event-log merge driver named in `.gitattributes` resolves `spec-kitty` from `PATH`, so a merge (D-0, W-1) runs with the checkout `.venv/bin` first on `PATH`.

## R-14 Tooling hazards and known-defect classes accounted for (no private ids)

Entries of the maintainers' defect ledger that touch this behaviour, described by class:

1. **The reducer ignores schema-5 task finalizer events**, so a persisted `status.json` can agree with an empty reduction while the CLI's task listing disagrees: kind 1 can be wrong in both directions (spec R-8; the `DriftFinding` description says the disagreement is with `materialize_snapshot`'s output at the snapshot's own generation). No check is added; no fixture asserts a clean report is true.
2. **A manifest's `mission_branch` can name a branch the product never created** (finalisation derives it from the slug even when the Mission used another start branch): a source of kind-3 false positives for non-coordination Missions that no independent oracle sharing the expectation can see. Handled by the provisional marker, the "no local branch" wording, the absence of a corpus floor, the IC-01 re-measure and the honest-rule criterion; not fixable here (C-006).
3. **The legacy lanes manifest reader refuses the legacy shape** (the one archive-frozen file): the reason of the GOV-007 ruling.
4. **Finalisation hazards for the tasks phase.** `finalize-tasks` fills a package's `owned_files` only when empty, so an amended manifest never propagates to the package frontmatter or the lane write scope and the command still reports success; editing `wps.yaml` after finalisation leaves `lanes.json` stale and `--validate-only` does not see it; `tasks.md` is regenerated wholesale (authored sections are dropped); `finalize-tasks` can leave a zeroed `status.json` when its commit fails; a literal path to a file that does not exist yet is refused unless the package frontmatter declares `create_intent`. Consequence (plan, Lanes): author the final `owned_files` and `create_intent` before the first finalisation, run it once, and re-read the computed `lanes.json` against the expected outcome.
5. **Planning scaffold and phase guards.** The plan scaffold is an unfilled template until filled (the research and tasks steps refuse an unfilled plan); a guard may read the coordination surface rather than the primary planning surface for a Mission with that topology (this Mission is `lanes`, so it is not exposed).
6. **Commit-message hygiene.** Machine-authored acceptance and analysis commits do not use conventional subjects; the commit-msg job only prints. The finalisation message uses a retired word; W-5 replaces it by the leading planning-artifacts commit.
7. **Environment-class reds.** A stale venv shows as import errors (R-6); a global CLI install with a symlinked library directory crashed at startup in a past release, which is why the merge driver must resolve the checkout's CLI (R-13 e).
