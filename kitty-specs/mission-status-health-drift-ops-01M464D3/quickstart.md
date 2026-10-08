# Quickstart: running the checks locally

For implementers and reviewers of Mission `mission-status-health-drift-ops-01M464D3`. Commands are written with the checkout paths `.venv/bin/python` and `.venv/bin/ruff`; run as a gate of this Mission, each reads `<synced-python>` and `<synced-ruff>` (the synced environment of the Environment section below; the hand-built checkout `.venv` lacks ruff, mypy and respx), and, in a command that runs from a lane workspace (the `cutover-guard` gate), `.venv/bin/spec-kitty` reads `<synced-spec-kitty>`, the `<scratch>/venv/bin/spec-kitty` of the same environment (orchestrator note 18 of `reviews/tasks.ruling.md`: a lane workspace does not carry the checkout `.venv`; the symbol check below needs only the standard library and may run with either interpreter). Never a bare `uv run`, which re-syncs and can destroy a hand-built environment. Commands assume the repository root as the working directory. Charter rule: no full architectural, end-to-end or performance sweep and no `make test-full` in mission work; run the named files below (except the three-leg architectural battery of WP03, WP07 and WP08 only, and, by orchestrator note 17 extending ruling 14, the orchestrator's Step 0 baseline run of the same three legs on the unchanged D-0 tip (and its note 16 fallback run of them on a lane tip), which operator ruling 14 makes binding for the three work packages; every other work package keeps named files only). **Placeholders:** `<scratch>` is a scratch directory, `<tmp>` a temporary directory **whose ancestors hold no `.git`** (a stray repository at the system temporary root breaks tools that refuse a temporary directory below a repository; set `export TMPDIR=<tmp>` before any pytest or replay run), `<main>` the ref holding upstream `main`, `<baseline sha>` the full SHA recorded at the run. Commands marked "run in the plan phase" were run on this checkout; the others are marked "not run" with the reason.

## What runs locally and what only in CI

| Step | Locally | CI only |
|---|---|---|
| The ten `contracts/tools/*.py` content and hygiene checks | yes | also in the Contracts workflow `python-checks` job |
| Tool unit tests, the three new reader modules, the proof edits (`tests/contract/` except three modules) | yes | router job `tests (contract tools)` |
| Reality check, payload helper tests | yes (about two minutes; needs the network for the resolver's remote probes) | router job `tests (corpus-blocking)` |
| Bundle (`--bundle-only`), vacuum lint, `breaking_check.py` | `breaking_check.py` yes, after `install_tools.py` has fetched the pinned `oasdiff` into a scratch directory; vacuum and the bundle's JVM validation need a JDK | the Contracts workflow |
| The JVM-needing contract checks (Gradle validation, Java view, TypeScript client smoke, resolver parity, lint, the tamper plant, the tag-less release dry run, `negative-tests` without skip tags) | **no JDK on the agent hosts**: replayed by the orchestrator or operator after IC-06 (J-1) | the Contracts workflow, which runs only on pull requests and pushes to `main` |
| `ruff` (check, format, TID251) | **not available in the checkout `.venv`**: obtain the locked version (0.15.12 in `uv.lock`) in a scratch environment first (see "Environment") | router jobs `ruff` and `import-linter` |
| `architectural-fast`, `layer-rules`, `archive-freeze`: the named files below | yes (the two registration gates need the synced test extras) | router jobs of the same names, on every pull request |
| `architectural-fast` and `architectural-heavy` battery (three legs) | yes, and only for WP03, WP07 and WP08 and, by orchestrator note 17 extending ruling 14, the orchestrator's Step 0 baseline run of the same legs on the unchanged D-0 tip (operator ruling 14, item 3 of `reviews/tasks.ruling.md`, overriding the charter's no-full-sweep rule for the three work packages, and note 17 for those runs; the legs are written out in WP03) | router jobs, selected on this PR by the registration edits (plan PD-2) |

## Environment (orchestrator Step 0, before any work package is dispatched)

The checkout `.venv` is hand-built: it lacks `ruff`, `mypy` and `respx` (research R-6), which makes 17 registration-gate tests error at collection and 4 home-pin tests fail, and leaves ruff unavailable. Obtain a synced environment without touching it, for example (not run in the plan phase: it downloads packages):

```text
UV_PROJECT_ENVIRONMENT=<scratch>/venv uv sync --frozen --all-extras
<scratch>/venv/bin/ruff --version
```

then run the commands below with `<scratch>/venv/bin/python` (the `<synced-python>` of the work package prompts, defined once at orchestrator Step 0) and `<scratch>/venv/bin/ruff`; before the first battery leg check that `<synced-python> -c "import specify_cli; print(specify_cli.__file__)"` prints a path inside the `src/` of the workspace under test (else prefix `PYTHONPATH=<workspace>/src`); battery durations are compared only with the Step 0 local run of the same leg, main-CI durations being informational (note 15 of `reviews/tasks.ruling.md`); a red is binned against the plan-time baseline (plan, Baseline section) and the Step 0 record. A red that survives the sync is binned (plan, Baseline: rule) before work continues.

## Python checks over the contract (each prints a final `counts:` line; exit 0 pass, 1 violation, 2 cannot do its job; run in the plan phase, all exit 0)

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

Plan-time `counts:` lines: `layout_check` `path_files=8 index_files=7`; `citation_check` `properties=191 x_source=140 x_derived=51 inputs_resolved=93`; `provisional_check` `provisional_elements=22`; `example_check` `examples=75 validated=75`; `enum_pin_check` `enums=7 values=43`; `leak_scan` `files=1062 values_strict=682 values_human=8792 values_all=26219 values_artifact_path=37`; `structure_check` `readme_headings=20 changelog_headings=7`. `citation_check` prints `CITATION_REUSE` notes (a symbol cited by more than five properties) and `event_mapping_check` prints `LIFECYCLE_TYPE_NOT_FORWARDED` notes; both exit 0, and new properties citing `materialize_snapshot` or `StatusSnapshot` add reuse notes, not failures. `citation_check` and `event_mapping_check` read git and the sources: run them from a checkout, not from a bare copy of `contracts/`. The planted negatives of the leak scan run through the registry:

```text
.venv/bin/python contracts/tools/run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch>/negative-work --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff
```

(the cases that need those binaries are skipped and counted; not run in the plan phase).

## Tool tests, reader tests and the reality check (targeted files only)

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_project.py tests/contract/test_mission_status_drift.py tests/contract/test_mission_status_ops.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py
.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_drift.py
.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_drift.py
```

The second line exists after IC-03, IC-07 and IC-08 land (the three modules); before that it names files that do not exist yet. Those three modules are fixture-built only; every case that reads the real corpus runs in the third line's reality module. **Each new module declares `pytestmark` as one single-line list holding `pytest.mark.corpus`**, in the form of `tests/contract/test_mission_status_detail.py` (`pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]`): the registry gate's `_CORPUS_MARK_APPLICATION_RE` matches `pytestmark = ... pytest.mark.corpus` within one line only, so a mark spelled through a shared list or wrapped across lines would be reported as in the registry but no longer marked. The registry row and the `--deselect` go in the commit that creates the module, in sorted position. The last two lines prove the module is selected by the router's marker expression and **not** by the nightly's: the first collects the module, the second must collect nothing (pytest exits 5 and prints no test ids; that is the pass condition); run in the plan phase on the previous slice's detail module, which has the same marker set (241 collected, then none). The tool job's whole selection, as the router runs it:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract --ignore=tests/contract/test_example_round_trip.py --ignore=tests/contract/test_mission_status_payloads.py --ignore=tests/contract/test_mission_status_reality.py -n 4 --dist loadfile -q
```

(plan-time: 1,778 passed, 37 skipped in 176 s; the reality module and the payload helper 819 passed in 108 s). The reality check is read-only: it never calls `materialize` and fingerprints `kitty-specs/` and `kitty-ops/` (bytes and directory names) before and after. A shallow clone made with `git clone --depth 1 file://<checkout> <scratch>/shallow` runs the pure modules green (no tag exists or is needed).

## The additive proof against the contract tree on main (no tag, no new version; repeat on the final tree)

This is the recipe run in the plan phase on a spike (research R-5). The comparison is the recorded wrap-up command of FR-022 item 3 (W-7), not a committed test.

1. Extract the baseline (the contract tree on `<main>` at the merge-base): `mkdir -p <scratch>/base && git archive <baseline sha> contracts/mission-status contracts/_shared | tar -x -C <scratch>/base`, then move the two directories up one level so that `<scratch>/base/mission-status` and `<scratch>/base/_shared` exist. Copy that directory twice, to `<scratch>/lowered` and `<scratch>/samemajor`, and rewrite `info.version` in each `mission-status/openapi.yaml`: `0.9.0` in the first, `1.0.0` in the second (scratch only; the candidate keeps `1.0.0-SNAPSHOT`; against a baseline of the same version the check refuses any bundle change with `BUNDLE_CHANGED_VERSION_SAME`).
2. Fetch the pinned diff tool (run in the plan phase; the installer verifies the pinned checksum before anything runs): `.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest <scratch>/tools --only oasdiff`.
3. Run the breaking check from the candidate checkout, once per scratch baseline (the candidate root is `contracts` when run on the real tree, a scratch copy in a spike):

```text
PATH=<scratch>/tools/oasdiff-1.32.1:$PATH .venv/bin/python contracts/tools/breaking_check.py --root contracts --baseline-root <scratch>/lowered
PATH=<scratch>/tools/oasdiff-1.32.1:$PATH .venv/bin/python contracts/tools/breaking_check.py --root contracts --baseline-root <scratch>/samemajor
```

Expected on the final tree: the first exits 0 and ends `counts: modules=1 baselines=1 breaking=4 provisional_changes=<N> no_baseline_initial=0 preview_ref=skipped` (`breaking=4` measured on the spike; `<N>` is pinned on the final tree, the spike gave 1); the second exits 1 with four `BREAKING_WITHOUT_MAJOR` lines naming `currentBranch`, `lastActivityAt`, `schemaVersion` and `specKittyVersion` (all `GET /project`, status `200`). Controls to record: an extra required property on `WorkPackage` in the candidate raises `breaking` to 5; with the `Project` change reverted and the `/drift` and `/ops/invocations` operations and their two tags removed, the second run exits 0 (reverting the `Project` change alone exits 1 with `BUNDLE_CHANGED_VERSION_SAME`, because the two new operations still change the bundle).
4. Byte identity: `diff -rq <scratch>/base/mission-status contracts/mission-status` lists only new files plus the edited files of the slice (`CHANGELOG.md`, `openapi.yaml`, the four `_index.yaml`, the three Project files); `diff -rq <scratch>/base/_shared contracts/_shared` is silent. The recorded diff against the baseline commit: `git diff --exit-code <baseline sha> -- contracts/mission-status` limited to the paths outside the slice file set, with its planted byte change.
   The three frozen pre-slice Project copies are generated, never typed, and checked against the baseline commit. They keep the source layout (`schemas/`, `examples/`, `paths/`) so that no two names in one directory differ only by letter case: a flat directory would hold `Project.yaml` beside `project.yaml`, which a case-insensitive checkout (macOS, Windows) cannot materialise.

```text
mkdir -p tests/contract/fixtures/mission_status_pre_slice/schemas tests/contract/fixtures/mission_status_pre_slice/examples tests/contract/fixtures/mission_status_pre_slice/paths
git show <baseline sha>:contracts/mission-status/schemas/Project.yaml > tests/contract/fixtures/mission_status_pre_slice/schemas/Project.yaml
git show <baseline sha>:contracts/mission-status/examples/Project.example.yaml > tests/contract/fixtures/mission_status_pre_slice/examples/Project.example.yaml
git show <baseline sha>:contracts/mission-status/paths/project.yaml > tests/contract/fixtures/mission_status_pre_slice/paths/project.yaml
git show <baseline sha>:contracts/mission-status/schemas/Project.yaml | cmp - tests/contract/fixtures/mission_status_pre_slice/schemas/Project.yaml
```

   (the `cmp` line is repeated for the other two files at W-7; the generation commands were exercised in the plan phase against the base commit's `Project.yaml` into a scratch directory, not into the repository).
5. `breaking_check.py --root contracts` with no `--baseline-root` finds no tag and accepts `1.0.0-SNAPSHOT` as the first release (`NO_BASELINE_INITIAL_VERSION`); it proves nothing about additivity.

**The FR-022 baseline record (W-7):** `git merge-base HEAD <main>` gives the baseline; `git merge-base --is-ancestor <baseline sha> <main>` must exit 0 (run in the plan phase: the base `b61d1fa33` is an ancestor of the local `origin/main`); a planted commit on no branch makes the assertion fail.

## Lane consolidation, before the wrap-up checks (W-1 ii; not run in the plan phase)

The lane work reaches the target branch only through the CLI, in two hops, run from the repository root after `spec-kitty accept --mission mission-status-health-drift-ops-01M464D3` and after every work package is approved or done; put the checkout `.venv/bin` first on `PATH` (the event-log merge driver resolves `spec-kitty` from `PATH`):

```text
spec-kitty consolidate --mission mission-status-health-drift-ops-01M464D3 --strategy rebase --dry-run
spec-kitty consolidate --mission mission-status-health-drift-ops-01M464D3 --strategy rebase --keep-branch
git rev-parse HEAD
```

Nothing is pushed; `--push` is not used. `rebase` keeps the per-package red then green commits for the squad and the compaction; `squash` would make the Mission one commit and the retained lane branches the only record. After the run, `HEAD` is the tip of the target branch; the scope check and the gate files read it.

## Scope check over the real branch diff (W-1 and W-7; SC-008 and AC-CROSS 2)

The scope function is proven on planted lists by committed tests; this is the run that proves **this branch** stays inside the slice file set. The allowed data are the module constants `SLICE_ALLOWED` and `EXTRA_ALLOWED_REGISTRATIONS` of `tests/contract/test_mission_status_contract_1_1.py` (each rule carries the statuses it admits: `A` under the new-files prefix, `M` for the named existing files, `A` or `M` under `tests/contract/`, never `D`). **Run from the repository root** (the block imports the module by file path and the module imports helpers as `tests.contract...`) and **after lane consolidation**: before it, `HEAD` holds only the Mission directory and the block exits 1 on its own empty-list guard, which is what happened when the block was run in the plan phase (28 entries, all in the Mission directory, `problems: ['no_changes: no entry was examined']`).

```text
BASE=$(git merge-base HEAD <main>)
git diff --name-status --no-renames "$BASE"..HEAD > <tmp>/changed.txt
.venv/bin/python - <<'PY'
import importlib.util, os, pathlib, sys
path = pathlib.Path("tests/contract/test_mission_status_contract_1_1.py")
spec = importlib.util.spec_from_file_location("proof_module", path)
mod = importlib.util.module_from_spec(spec)
sys.modules["proof_module"] = mod
spec.loader.exec_module(mod)
mission_dir = "kitty-specs/mission-status-health-drift-ops-01M464D3/"
entries = [tuple(line.split("\t", 1)) for line in pathlib.Path(os.environ["TMPDIR"], "changed.txt").read_text().splitlines() if line]
changed = [(status, path) for status, path in entries if not path.startswith(mission_dir)]
allowed = list(mod.SLICE_ALLOWED) + list(mod.EXTRA_ALLOWED_REGISTRATIONS)
problems = mod.scope_problems(changed, allowed)
print("changed outside the Mission directory:", len(changed), "problems:", problems)
sys.exit(1 if problems or not changed else 0)
PY
git diff --name-status --no-renames "$BASE"..HEAD -- kitty-specs/ | grep -v -P '^A\tkitty-specs/mission-status-health-drift-ops-01M464D3/' ; test $? -eq 1
```

The Python block must exit 0 and the last line must print no output (every `kitty-specs/` entry is an addition under the Mission directory: add-only). Both outputs, with the merge-base commit, go into the PR body as the final scope evidence (W-7 re-runs them on the rebased tree). The dependency check of AC-CROSS 3 is a pure function over the same entries: no entry may name `pyproject.toml` or `uv.lock`.

## Named gate files (run after every rebase and before hand-off)

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_archive_root_byte_identical.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
<synced-spec-kitty> cutover-guard --base-ref origin/main
```

Plan-time baseline (run in the plan phase): the first pytest line 352 passed, 1 skipped, 17 errors (all `respx` missing, stale venv); the archive-root file 25 passed; `cutover-guard` 1 Mission touched, 0 un-cut-over; the ruff lines **not run** (no ruff in the `.venv`). In a synced environment the first line must be green. For a per-file format check use `ruff format --check --force-exclude <files>`.

## Architectural files that read `tests/` (run at Step 0, at implement start, after every new or edited test module, and at the wrap-up)

The router jobs `architectural-fast`, `layer-rules` and `import-linter` run on every pull request; the `architectural-heavy` battery is selected on this PR by the registration edits and is run locally, in full, by WP03, WP07 and WP08 as a binding gate (operator ruling 14; the three legs and their commands are in `tasks/WP03-project-vertical.md`). Several census files read all of `tests/`: real-git fixtures, a `subprocess` stub, a counting wrapper, git identity setup, any manual `os.chdir`, `os.environ` or `sys.path` change, a shared-temp literal and a wall-clock call in a new test module are what they inspect. Run **named files, never the directory**.

**The list is derived, not remembered.** At Step 0 and at W-1, re-derive it from the registry and check that every path exists:

```text
awk '/fast_gate:/,/shards:/' .github/ci-module-registry.yml | grep -o 'tests/architectural/[A-Za-z0-9_/]*\.py' | sort -u > <tmp>/fast_roster.txt
xargs -a <tmp>/fast_roster.txt grep -l -E '_TESTS_ROOT|tests_root|rglob\(.test_' | sort
ls <the heavy files below>
```

The second command is a first filter, not the authority: it finds scanners that name the tests root themselves (at plan time `test_issue_named_test_census.py`, `test_no_tmp_paths_in_tests.py`, `test_module_shard_registry.py` and `test_ci_quality_path_filters.py`) and misses scanners that read the tree through a helper (`test_no_manual_global_state_mutation.py` uses `_global_state_scan.py`), so the orchestrator also reads the imports of each roster file. The roster files that read the test tree and can fail on a new test module (as derived at plan time) are `test_no_manual_global_state_mutation.py`, `test_no_tmp_paths_in_tests.py` and `test_issue_named_test_census.py`; of the other two filtered files, `test_module_shard_registry.py` is in the named gate files above and `test_ci_quality_path_filters.py` checks CI path filters, not test-module content (its docstring). The heavy-battery files that read it, which are **not** in the `fast_gate` roster (the registry excludes `test_no_dead_symbols.py` and `test_dead_symbol_allowlist_contract.py` from it on purpose and lists no home-pin file), are the home-pin census, the sealed global-state allowlist and the two clock bans. All paths below were checked to exist in the plan phase.

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_no_tmp_paths_in_tests.py \
  tests/architectural/test_issue_named_test_census.py \
  tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

The two dead-symbol files (`test_no_dead_symbols.py`, `test_dead_symbol_allowlist_contract.py`) walk `src/`, where this slice changes nothing, and are heavy-battery files of about 30 s each: they run once in the Step 0 baseline, not after every module.

Plan-time baseline (run in the plan phase, the earlier eight-file selection: global-state, sealed allowlist, three home-pin files, verdict and the two dead-symbol files): 167 passed, 4 failed in 173 s (every failure is `No module named mypy`); 83 passed in 25 s; TID251 not run (no ruff). The shared-temp scan and the clock bans were not part of that baseline: Step 0 takes theirs. No allowlist or baseline entry is added to make a new module pass: the module is written to satisfy the scans (`monkeypatch`, a scratch `HOME`, an injected clock).

## Counts of the corpus (read-only; run in the plan phase)

Plain JSON and git reads, no product reader; the output is the measure of research R-2 and R-3. Re-run at IC-01 after the D-0 sync and at W-7.

```text
.venv/bin/python -I - <<'PY'
import collections, json, re, subprocess
from pathlib import Path


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


root = Path("kitty-specs")
dirs = [d for d in root.iterdir() if d.is_dir()]
has = lambda d, n: (d / n).is_file()
print("directories", len(dirs), "with meta.json", sum(has(d, "meta.json") for d in dirs))
print("status files: both", sum(has(d, "status.json") and has(d, "status.events.jsonl") for d in dirs),
      "log only", sum(not has(d, "status.json") and has(d, "status.events.jsonl") for d in dirs),
      "snapshot only", sum(has(d, "status.json") and not has(d, "status.events.jsonl") for d in dirs),
      "neither", sum(not has(d, "status.json") and not has(d, "status.events.jsonl") for d in dirs))
legacy = []
manifests = [d for d in dirs if has(d, "lanes.json")]
for d in manifests:
    try:
        doc = json.loads((d / "lanes.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        legacy.append("unreadable " + d.name)
        continue
    if isinstance(doc, dict) and "feature_slug" in doc and "mission_slug" not in doc:
        legacy.append(d.name)
print("lanes.json", len(manifests), "legacy-shaped or unreadable", legacy)
heads = {line.split()[-1].removeprefix("refs/heads/") for line in git("for-each-ref", "refs/heads").splitlines()}
remotes = {line.split()[-1] for line in git("for-each-ref", "refs/remotes").splitlines()}
worktrees = git("worktree", "list", "--porcelain")
declared = merged = 0
remote_only, absent = [], []
for d in sorted(dirs):
    if not has(d, "meta.json"):
        continue
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        continue
    branch = meta.get("coordination_branch") if isinstance(meta, dict) else None
    if not branch:
        continue
    declared += 1
    if meta.get("merged_at"):
        merged += 1
    elif branch not in heads and branch not in worktrees:
        (remote_only if any(r.endswith("/" + branch) for r in remotes) else absent).append(d.name)
print("declared coordination branches", declared, "merged", merged, "not merged and absent locally", len(absent), "of which remote-tracking only", len(remote_only))
ops = Path("kitty-ops")
ulid = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}\.jsonl")
spine_path = ops / "op-closures.jsonl"
spine = set()
if spine_path.is_file():
    for line in spine_path.read_text(encoding="utf-8").splitlines():
        try:
            spine.add(json.loads(line)["invocation_id"])
        except (ValueError, KeyError):
            pass
counts, evidence = collections.Counter(), collections.Counter()
for f in sorted(ops.iterdir()):
    if not ulid.fullmatch(f.name):
        continue
    lines = f.read_text(encoding="utf-8").splitlines()
    started = json.loads(lines[0])
    completed = next((o for o in (json.loads(x) for x in lines[1:]) if o.get("event") == "completed"), None)
    if completed is None:
        counts["open in file" + (", closed by the spine" if started.get("invocation_id") in spine else "")] += 1
    elif "closed_by" not in completed:
        counts["legacy completion"] += 1
    else:
        counts["closed in file"] += 1
        ref = completed.get("evidence_ref")
        evidence["none" if not ref else "absolute" if ref.startswith("/") else "free text" if re.search(r"\s", ref) else "relative or other"] += 1
print("Op files", sum(counts.values()), dict(counts), "evidence", dict(evidence), "spine ids", len(spine))
PY
```

Plan-time output: 569 directories, all with `meta.json`; status files 536 both, 31 log only, 0 snapshot only, 2 neither; 489 `lanes.json` with one legacy-shaped (`064-complete-mission-identity-cutover`); 51 declared coordination branches, 14 merged, 37 not merged and absent locally, 0 of them remote-tracking only (the corpus condition of FR-025 holds); 480 Op files: 467 closed in file, 7 legacy completions, 6 open in file and closed by the spine; evidence none 351, absolute 32, free text 56, relative or other 28; 6 spine ids. The kind-3 population is **not** measured here: it is IC-01's first task, under the final rule.

## Symbol and path check (run at D-0, after every rebase and at W-7; run in the plan phase: 91 checked, 0 missing)

```text
.venv/bin/python -I - <<'PY'
import re
from pathlib import Path
PAIRS = """
src/specify_cli/upgrade/metadata.py ProjectMetadata
src/specify_cli/core/version_checker.py get_project_version
src/specify_cli/migration/schema_version.py get_project_schema_version MIN_SUPPORTED_SCHEMA MAX_SUPPORTED_SCHEMA check_compatibility REQUIRED_SCHEMA_VERSION
src/specify_cli/core/git_ops.py get_current_branch
src/kernel/clock.py now_utc
src/specify_cli/audit/classifiers/status_json.py classify_status_json
src/specify_cli/status/validate.py validate_derived_views validate_materialization_drift _validate_materialization_files
src/specify_cli/lanes/models.py LanesManifest
src/specify_cli/lanes/branch_naming.py code_lane_branch_name
src/specify_cli/lanes/_git.py branch_exists
src/specify_cli/lanes/persistence.py read_lanes_json CorruptLanesError
src/specify_cli/status/lifecycle.py is_mission_completed derive_mission_lifecycle
src/specify_cli/status/reducer.py materialize_snapshot materialize_to_json materialize
src/specify_cli/status/models.py StatusSnapshot
src/specify_cli/status/aggregate.py MissionStatus CoordAuthorityUnavailable MissionMetadataUnavailable InvalidMissionSlug
src/specify_cli/coordination/surface_resolver.py CoordinationBranchDeleted WorktreeRegistryUnavailable _coord_branch_exists
src/specify_cli/git/remote_probes.py remote_branch_lookup _LS_REMOTE_TIMEOUT_SECONDS _reset_remote_branch_lookup_cache
src/specify_cli/core/paths.py load_meta_fail_closed MissionMetaReadError
src/specify_cli/mission_metadata.py load_meta resolve_mission_identity
src/specify_cli/status/doctor.py check_drift
src/specify_cli/audit/models.py Severity MissionFinding
src/specify_cli/status/wp_metadata.py WPMetadata
src/specify_cli/status/views.py write_derived_views
src/specify_cli/cli/commands/materialize.py materialize
src/specify_cli/cli/commands/invocations_cmd.py _iter_index_reverse _iter_records_from_dir _apply_completion_status append_to_index
src/specify_cli/invocation/writer.py InvocationWriter EVENTS_DIR read_op_closures closed_invocation_ids normalise_ref
src/specify_cli/invocation/record.py OpStartedEvent OpCompletedEvent parse_op_event
src/specify_cli/invocation/errors.py LegacyRecordError
src/specify_cli/cli/commands/_coordination_doctor.py COORDINATION_WORKTREE_NEVER_CREATED
contracts/tools/leak_patterns.py redact_emails email_matches SECRET_PATTERNS
contracts/tools/leak_scan.py malformed_artifact_path STRICT_FIELDS
contracts/tools/fixture_builder.py STRICT_FIELDS
tests/contract/_mission_status_payloads.py resolve_read_dir load_source derive_project write_fixture_mission tree_fingerprint require_cases floor_failures enumerate_missions git_init commit_all FLOORS
tests/contract/test_mission_status_contract_1_1.py DEFERRED_GAPS CHANGED_ALLOWED NEW_PATH_KEYS _make_pair additive_proof_problems SLICE_ALLOWED EXTRA_ALLOWED_REGISTRATIONS scope_problems IN_SCOPE_CHANGES REGISTRATION_CHANGES
tests/contract/test_mission_status_examples.py MIN_EXAMPLES EXPECTED_PATH_KEYS
.github/workflows/ci-router.yml contract_tools
.github/workflows/packs.yml built-in-corpus-suite
tests/architectural/test_ci_corpus_trigger_completeness.py _CORPUS_MARKED_MODULES
tests/ci/test_contracts_workflows.py test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import
""".strip().splitlines()
missing = checked = 0
for line in PAIRS:
    path, *symbols = line.split()
    file = Path(path)
    if not file.is_file():
        print("NOFILE", path)
        missing += 1
        continue
    text = file.read_text(encoding="utf-8")
    for symbol in symbols:
        checked += 1
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(symbol) + r"(?![A-Za-z0-9_])", text):
            print("NOSYMBOL", path, symbol)
            missing += 1
print(f"checked={checked} missing={missing}")
PY
```

`COORDINATION_WORKTREE_NEVER_CREATED` is an error-code string, not a symbol (research R-8); the check finds it as text.

## Hygiene scan of this directory (C-005; run in the plan phase at the end, zero problems; repeat at IC-10 and W-7)

The Mission directory joins the corpus the new reads run over, so it must hold nothing they refuse and nothing the human leak patterns flag (research R-13):

```text
.venv/bin/python -I - <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("leak_patterns", "contracts/tools/leak_patterns.py")
lp = importlib.util.module_from_spec(spec)
sys.modules["leak_patterns"] = lp
spec.loader.exec_module(lp)
root = Path("kitty-specs/mission-status-health-drift-ops-01M464D3")
problems = files = 0
for f in sorted(root.rglob("*")):
    rel = f.relative_to(root).as_posix()
    if f.is_dir() or rel.startswith("reviews/") or rel in ("status.events.jsonl", "status.json"):
        continue
    files += 1
    if f.is_symlink():
        print("SYMLINK", rel)
        problems += 1
        continue
    raw = f.read_bytes()
    if len(raw) > 262144:
        print("TOO_BIG", rel, len(raw))
        problems += 1
    if b"\0" in raw:
        print("NUL", rel)
        problems += 1
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("NOT_UTF8", rel)
        problems += 1
        continue
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() and lp.leak_codes(line, lp.HUMAN):
            print("LEAK", rel, number, lp.leak_codes(line, lp.HUMAN))
            problems += 1
print(f"files={files} problems={problems}")
PY
```

A placeholder home path quoted in a sentence trips the host-path pattern: describe such a rule in words, never type the literal.

## JVM replay J-1 (after IC-06 is approved; orchestrator or operator step; not run in the plan phase: no JDK, no Gradle)

The Contracts workflow has no `workflow_dispatch` trigger; it runs on `pull_request` and push to `main`. On a JVM-capable machine, with `TMPDIR` set to `<tmp>`, replay the steps of every job of `.github/workflows/contracts.yml` over the final shapes, in the workflow's own order and with its pinned tools: `verify-pins`, `python-checks` (the ten scripts above), `validate-bundle` (bundle, Gradle validation, Java view, `tamper_check.py --contracts contracts`, `client_smoke.py --root contracts --out <scratch>/bundle-out`), `resolver-parity` (`resolver_parity.py --root contracts --bundles <scratch>/staged`), `lint` (`lint_check.py --ruleset contracts/lint/ruleset.yaml --bundles <scratch>/lint-out` and its plants), `breaking-change` (the two `--baseline-root` runs of the additive-proof section), `release-dry-run` (`release_check.py --root contracts --out <scratch>/release-out`), `negative-tests` (`run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch>/negative-work`, no skip tags) and `contracts-gate`. Add the camel-case enum plant on a scratch copy (the vacuum `enum-case` rule refused kebab-case values in the previous slice and no Python gate runs it). Record in `tracer-design-decisions.md` the commit of the final `contracts/` change and **one line per job** (nine lines) with its conclusion; the wrap-up commands of AC-VERSION check it: the cited commit exists (`git cat-file -t`), is an ancestor of `HEAD`, is the last commit touching `contracts/mission-status`, and `git diff --exit-code <cited commit> HEAD -- contracts/mission-status` is clean (re-cited after compaction, plan Departs 4).

## Writing files safely

Editing tools may decode a unicode escape typed into a file into the raw character. A contract pattern is therefore written with the hex escape (`\x00`), and any test that needs a NUL builds it with `chr(0)` and a backslash with `chr(92)`. After writing a contract or test file, check it for raw NUL bytes. Planted leaking values (host paths, e-mail addresses, tokens) are assembled from fragments at run time and never committed as literals; **no shared-temp literal appears in a plant** (the shared-temp scan of `test_no_tmp_paths_in_tests.py` reads every test file, and an evidence-class plant for an absolute path is where one is easiest to type), so host-path shapes are built from fragments; a contract example never holds an at-sign file name. Never paste the JSON output of the planning commands: it carries absolute paths of the host.
