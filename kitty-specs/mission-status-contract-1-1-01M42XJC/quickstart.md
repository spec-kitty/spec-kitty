# Quickstart: running the checks locally

For implementers and reviewers of Mission `mission-status-contract-1-1-01M42XJC`. Use the checkout's own virtual environment (`.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/pytest`), never a bare `uv run`, which re-syncs and destroys a hand-built environment. Commands assume the repository root as the working directory. Charter rule: no full architectural, end-to-end or performance sweep and no `make test-full` in mission work; run the named files below.

## What runs locally and what only in CI

| Step | Locally | CI only |
|---|---|---|
| The ten `contracts/tools/*.py` content and hygiene checks | yes | also in the Contracts workflow `python-checks` job |
| Tool unit tests and the new reader tests (`tests/contract/` except three modules) | yes | router job `tests (contract tools)` |
| Reality check, payload helper tests, example round trip | yes | router job `tests (corpus-blocking)` |
| Bundle (`--bundle-only`), vacuum lint, `breaking_check.py` | yes, after `install_tools.py` has fetched the pinned `vacuum` and `oasdiff` into a scratch directory | the Contracts workflow |
| The JVM-needing contract checks: the full mechanism (a) list of plan W-2 (Gradle validation, Java view, TypeScript client smoke, resolver parity, lint, `negative-tests` without the skip tags; the tag-less release dry run included; only `breaking-change` with `--baseline-root` waits for the final `CHANGELOG.md`) | no (no JVM here); replayed on a JVM-capable machine first after WP04 is approved (tasks.md step J-1) and again at the W-2 shake-out (below) | the Contracts workflow, which runs only on pull requests and pushes to `main`, so first on the draft PR unless W-2 ran |
| `architectural-fast`, `layer-rules`, `import-linter` (TID251): the named files and command below | yes (WP05, WP06, WP07 also run the whole battery part, see their prompts) | router jobs of the same names, on every pull request |
| `architectural-heavy` battery | only for WP05, WP06 and WP07, on the operator's explicit request (the commands are in those prompts); otherwise no (charter: no full sweep) | router job, only when `tests/architectural/**` or `.github/workflows/**` changes (plan OD-1 X-pure selects it through both registration files) |

## Python checks over the contract (each prints a final `counts:` line; exit 0 pass, 1 violation, 2 cannot do its job)

```text
.venv/bin/python contracts/tools/layout_check.py --root contracts
.venv/bin/python contracts/tools/citation_check.py --root contracts
.venv/bin/python contracts/tools/provisional_check.py --root contracts
.venv/bin/python contracts/tools/example_check.py --root contracts
.venv/bin/python contracts/tools/event_mapping_check.py --root contracts
.venv/bin/python contracts/tools/enum_pin_check.py --root contracts
.venv/bin/python contracts/tools/leak_scan.py --root contracts
.venv/bin/python contracts/tools/structure_check.py --root contracts
.venv/bin/python contracts/tools/codeowners_check.py
.venv/bin/python contracts/tools/no_pytest_scan.py
```

`citation_check` and `event_mapping_check` read git and the sources: run them from a checkout, not from a bare copy of `contracts/`. The planted negatives of the leak scan run through the registry: `.venv/bin/python contracts/tools/run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch> --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff` (the cases that need those binaries are skipped and counted).

## Tool tests, reader tests and the reality check (targeted files only)

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_artifacts.py tests/contract/test_mission_status_detail.py tests/contract/test_mission_status_contract_1_1.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py
.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_artifacts.py
```

There is no committed live baseline test (OD-1 X-pure is decided): the comparison against the contract tree on `main` is a recorded command at wrap-up W-7. The artifacts and 1.1 proof modules carry `contract`, `fast` and `corpus`; the detail module carries `contract`, `corpus` and `git_repo` and not `fast`, so `.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_detail.py` must collect nothing (expect exit code 5 and no test ids: pytest exits 5 when nothing is collected, and that is the pass condition). A shallow clone made with `git clone --depth 1 file://<absolute path of this checkout> <scratch>/shallow` (then the same venv or a synced one) runs the pure modules green (no tag exists or is needed). The last line of the block proves a new module is selected by the marker expression the router uses. The tool job's whole selection, as the router runs it: `PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract --ignore=tests/contract/test_example_round_trip.py --ignore=tests/contract/test_mission_status_payloads.py --ignore=tests/contract/test_mission_status_reality.py -n 4 --dist loadfile -q`. The reality check is read-only: it never calls `materialize` and fingerprints `kitty-specs/` (bytes and directory names) before and after.

## The additive proof against the contract tree on main (no tag, no new version; repeat on the final tree)

1. Extract the baseline (the contract tree on `main`, `aef7cc967` or the current `origin/main`: v1 at `1.0.0-SNAPSHOT`): `git archive <main> contracts/mission-status contracts/_shared | tar -x -C <scratch>/b` then move the two directories up one level so that `<scratch>/baseline/mission-status` and `<scratch>/baseline/_shared` exist. Then rewrite `info.version` in `<scratch>/baseline/mission-status/openapi.yaml` to a lower value (scratch only): the candidate keeps `1.0.0-SNAPSHOT`, and against a baseline of the same version the check fails any bundle change with `BUNDLE_CHANGED_VERSION_SAME` (research R-7, row `1.0.0-SNAPSHOT`).
2. Fetch the pinned diff tool: `.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest <scratch>/tools --only oasdiff` (the installer verifies the pinned checksum before anything runs).
3. Run the breaking check against the scratch baseline from the candidate checkout: `PATH=<scratch>/tools/oasdiff-1.32.1:$PATH .venv/bin/python contracts/tools/breaking_check.py --root contracts --baseline-root <scratch>/baseline`. Expected: exit 0 and the last line `counts: modules=1 baselines=1 breaking=0 provisional_changes=0 no_baseline_initial=0 preview_ref=skipped` (run on a spike of the planned `listArtifacts`; see research R-7 for the planted failures and their messages).
4. Byte identity: `diff -rq <scratch>/baseline/mission-status contracts/mission-status` must list only new files plus `CHANGELOG.md`, `openapi.yaml` and the `_index.yaml` files; `diff -rq <scratch>/baseline/_shared contracts/_shared` must be silent.
5. At wrap-up W-7 (a recorded command; there is no committed live test) repeat steps 1 to 4 on the rebased tree. `breaking_check.py --root contracts` with no `--baseline-root` finds no tag and accepts `1.0.0-SNAPSHOT` as the first release; it proves nothing about additivity.

No tag exists and none is needed (operator ruling 2026-10-05): at `1.0.0-SNAPSHOT` without `--baseline-root` the check accepts the first release, so the Contracts workflow job is not red.

## Lane consolidation, before the wrap-up checks (wrap-up step W-1 ii)

The lane work reaches the target branch only through the CLI, in two hops (lane branches into `kitty/mission-<slug>`, then that branch into the target branch recorded in `meta.json`); run from the repository root after `spec-kitty accept --mission mission-status-contract-1-1-01M42XJC` (accept comes first: the tooling's order, plan W-1) and after every work package is approved or done:

```text
spec-kitty consolidate --mission mission-status-contract-1-1-01M42XJC --strategy rebase --dry-run
spec-kitty consolidate --mission mission-status-contract-1-1-01M42XJC --strategy rebase --keep-branch
git rev-parse HEAD
```

The target is the local branch recorded in `meta.json` as `target_branch` (the branch the repository-root checkout is on), reached through the intermediate `kitty/mission-<slug>` branch of `lanes.json` that `--keep-branch` leaves in place; nothing is pushed and `--push` is not used. `--strategy rebase` is the plan's recommendation (W-1 ii): it keeps the per-work-package red-first commits for the aggregate squad and the compaction, whereas the default `squash` would make the whole Mission one commit; `merge` is the second choice, and the orchestrator records a different strategy in the PR body. After the run, `HEAD` is the tip of the target branch; the scope check and the gate files below read it. Under `squash` the compaction (W-5) would have to split one tree by path, with the retained lane branches as the only record of red then green.

## Scope check over the real branch diff (wrap-up steps W-1 and W-7; SC-008 and the AC-VERSION scope bullet)

The scope function (plan D-P10) is proven on planted lists by the committed tests; this is the run that proves **this branch** stays inside the slice file set. `<main>` is the ref that holds upstream `main` (`origin/main` here; after the W-6 rebase, the ref the rebase used). The allowed data is the module constant `SLICE_ALLOWED` plus `EXTRA_ALLOWED_REGISTRATIONS` (the two registration paths of OD-1 X-pure; there is no constant for `required_examples.json` because OD-2 is Y); each rule carries the statuses it admits (`A` only under the prefix `contracts/mission-status/`, `M` only for the named existing files, `A` or `M` under `tests/contract/`, never `D`), so the input is **name-status entries**, not bare paths; the module is `tests/contract/test_mission_status_contract_1_1.py` (OD-1 X-pure). **Run from the repository root** (the block imports the module by file path and the module imports helpers as `tests.contract...`, which needs the `tests` package importable from the working directory), and **after lane consolidation** (plan W-1 ii): before it, `HEAD` holds only the Mission directory and the block exits 1 on its own empty-list guard.

```text
BASE=$(git merge-base HEAD <main>)
git diff --name-status --no-renames "$BASE"..HEAD > <scratch>/changed.txt
.venv/bin/python - <<'PY'
import importlib.util, pathlib, sys
path = pathlib.Path("tests/contract/test_mission_status_contract_1_1.py")
spec = importlib.util.spec_from_file_location("proof_module", path)
mod = importlib.util.module_from_spec(spec)
sys.modules["proof_module"] = mod
spec.loader.exec_module(mod)
mission_dir = "kitty-specs/mission-status-contract-1-1-01M42XJC/"
entries = [tuple(line.split("\t", 1)) for line in pathlib.Path("<scratch>/changed.txt").read_text().splitlines() if line]
changed = [(status, path) for status, path in entries if not path.startswith(mission_dir)]
allowed = list(mod.SLICE_ALLOWED) + list(mod.EXTRA_ALLOWED_REGISTRATIONS)   # the two registration paths (OD-1 X-pure); no constant for required_examples.json (OD-2 Y)
problems = mod.scope_problems(changed, allowed)
print("changed outside the Mission directory:", len(changed), "problems:", problems)
sys.exit(1 if problems or not changed else 0)
PY
git diff --name-status --no-renames "$BASE"..HEAD -- kitty-specs/ | grep -v -P '^A\tkitty-specs/mission-status-contract-1-1-01M42XJC/' ; test $? -eq 1
```

The python block must exit 0 and the last line must print no output (every `kitty-specs/` entry is an addition under the Mission directory: add-only, nothing else under `kitty-specs/`). Both outputs, with the merge base commit, go into the PR body as the final scope evidence (W-7 re-runs them on the rebased tree). **What was run at the plan fix, and what was not.** The git half (the two `git diff --name-status` commands and the final `grep`) was run on the committed planning tree: 51 entries, all `A`, all under the Mission directory, and the add-only command printed nothing. The Python half was **not** run: the module it imports does not exist yet, so it can first run at W-1 (iii) after IC-05; its parsing of the name-status lines was only checked against a stand-in module, and the scope function itself is proven by the committed planted-list tests (plan D-P10: a path in neither set, an `M` under the new-files prefix, an `M` for an unnamed tools file, a `D`).

## Named gate files (run after every rebase and before hand-off)

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/spec-kitty cutover-guard --base-ref origin/main
```

Baseline at planning: 368 passed and 1 skipped for the pytest line; ruff clean (3,103 files formatted); `cutover-guard` reports no un-cut-over Mission. For a per-file format check use `.venv/bin/ruff format --check --force-exclude <files>`.

## Architectural files that read `tests/` (run at implement start, after every new or edited test module, and at the wrap-up)

The router jobs `architectural-fast`, `layer-rules` and `import-linter` run on every pull request and census all of `tests/`; real-git fixtures, worktrees, git identity setup and any manual `os.chdir`, `os.environ` or `sys.path` change in a new test module are what they inspect. Run the named files, never the whole directory:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

Baseline at the plan fix: 171 passed in about 102 s; 83 passed in about 17 s; TID251 clean. No allowlist or baseline entry is added to make a new module pass: the module is written to satisfy the scans (`monkeypatch`, a scratch `HOME`).

## JVM shake-out (wrap-up step W-2, after the contract tree is frozen)

The Contracts workflow has no `workflow_dispatch` trigger; it runs on `pull_request` and push to `main`. To exercise the JVM-only jobs before the draft PR, replay the steps of `.github/workflows/contracts.yml` jobs `validate-bundle`, `resolver-parity`, `lint`, `release-dry-run` and `negative-tests` (without the JVM skip tags) on a JVM-capable machine, with `--baseline-root` for `breaking-change` before the tag. A throwaway draft PR against a scratch base is the alternative, only on the operator's word. Fix what it finds before the aggregate squad and the history compaction.

## Writing files safely

Editing tools may decode a unicode escape typed into a file into the raw character. The artifact-path pattern is therefore written with the hex escape (`\x00`), and any test that needs a NUL builds it with `chr(0)` and a backslash with `chr(92)`. After writing a contract or test file, check it for raw NUL bytes. Planted leaking values (host paths, e-mail addresses, tokens) are assembled from fragments at run time and never committed as literals.
