---
work_package_id: WP16
title: green_match helper and shared base binding
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T064
- T065
- T066
- T067
- T068
phase: Phase 7 - Skip-if-green
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/green_match.py
- tests/ci/test_green_match.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/green_match.py
- tests/ci/test_green_match.py
- tests/ci/fixtures/green_match/**
- scripts/ci/aggregate_source.py
- tests/ci/test_aggregate_source.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 – green_match helper and shared base binding

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Build the decision half of FR-011 (skip-if-green on `ready_for_review`) as one stdlib-only,
unit-tested helper, and extract the merge-parent binding that `aggregate_source.py` already
enforces into one shared pure function (D-27). No workflow file is touched in this WP. WP17
wires `effective-source` into CI Aggregate. WP18 wires `decide` into the three selection jobs.

Done means all of the following are true:

1. `scripts/ci/green_match.py` exists with two subcommands, `decide` and `effective-source`,
   whose cores are pure functions with no I/O. A thin transport edge does the REST calls.
2. Every row of the contract table in `contracts/green-match.md` is a parametrised unit row in
   `tests/ci/test_green_match.py`. That covers the 15 negative rows N1–N15, the positive rows
   P1–P2 and the Aggregate rows A1–A4 (A4 is new, see T067). The rows run over recorded API
   fixtures in `tests/ci/fixtures/green_match/`.
3. A mutation-style control proves the base, PR and marker conjuncts carry the decision
   (Standing Order #5).
4. `bind_tested_base(parents, head)` and `merge_reference(run, repository)` have one definition,
   in `green_match.py`. `aggregate_source.py` imports them and keeps its observable behaviour
   byte-identical: same outputs and same `ValueError` messages.
5. The helper runs as a bare script under `python3 -I -S` from an unrelated directory. That
   proves it is stdlib-only, needs no `scripts.*` import, no `yaml` and no `uv sync`. `ruff check`,
   `ruff format --check` and `mypy --strict` are clean on both scripts.

Acceptance anchors: FR-011 (decision logic and Aggregate re-point logic), SC-005 (enabler),
spec Edge Cases on in-progress, re-run, dispatch and moved base.

## Context & Constraints

Read these, in this order:

- `kitty-specs/ci-runtime-stabilisation-01M3TZH6/research.md`. Read the decision log first:
  D-15, D-16, D-27 and D-30 govern this WP. Then read R3 §1.1–§1.9. §1.3 is the helper contract,
  §1.5 the negative cases, §1.8 the red-first tests.
- `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/green-match.md`. This is the binding
  contract: tested key, decision table, outputs.
- `kitty-specs/ci-runtime-stabilisation-01M3TZH6/spec.md`: FR-011, User Story scenarios 4–5,
  and the Edge Cases list.
- `.kittify/charter/charter.md`: ATDD-First Discipline, single canonical authority, and Standing
  Order #5 (positive controls).

Live anchors, verified 2026-10-01 against `issue-5510-ci-runtime-stabilisation`:

- `scripts/ci/aggregate_source.py`:
  - **Line 13** is the bare sibling import `from prose_only import is_prose_only`. The script is
    only ever run as a bare script, so `sys.path[0]` is `scripts/ci/`.
  - `prepare_source` spans lines 71–150.
  - The reference extraction is lines 86–102. It raises
    `ValueError("source run lacks one immutable PR merge workflow reference")`.
  - The parent binding is lines 106–110. It reads `git show -s --format=%P <tested>` and raises
    `ValueError("tested merge parents do not bind the source run head")`.
- `tests/ci/test_aggregate_source.py` runs the script as a **subprocess** (`run_source`, around
  line 118). It asserts both messages above:
  - `test_source_rejects_ambiguous_or_stale_evidence` (line 191, 11 mutations);
  - `test_immutable_reference_must_bind_the_source_head` (line 305).

  Because of the bare `prose_only` import, `aggregate_source` **cannot** be imported in-process
  as `scripts.ci.aggregate_source`. That is why the shared functions live in `green_match.py`,
  a leaf with no sibling imports. Tests can import it as `scripts.ci.green_match`, the pattern
  `tests/ci/test_fleet_verdict.py:15` uses. `aggregate_source.py` imports it bare, next to
  `prose_only`.
- `scripts/ci/fleet_verdict.py:145-212` (`GitHub`, `GitHubCLI`) is the model for the transport
  edge and for token-redacted error messages. Copy the shape; do **not** import it, because it
  imports `yaml` and `scripts.ci.reconcile_retry`.
- `tests/ci/test_workflow_script_import_guard.py`:
  - The guard derives every workflow-invoked bare script (regex at line 173). It executes only
    the scripts whose module-level code imports `scripts.*`.
  - `green_match.py` is not workflow-invoked until WP17/WP18. From then on it joins the
    candidate list and `test_workflow_invoked_scripts_resolve_to_real_files` (line 303) asserts
    it exists.
  - The guard does not prove "stdlib-only". Your own `-I -S` bare-run test does (T068).
- `tests/architectural/test_clock_import_ban.py` scans `scripts/`, so no `datetime` import is
  allowed anywhere in the helper. `test_clock_call_ban.py` bans `time.time()`. The helper needs
  neither:
  - artifact expiry is the API's own `expired` flag;
  - candidate order is by run `id`;
  - the one timestamp comparison (A4) compares fixed-format `YYYY-MM-DDTHH:MM:SSZ` strings,
    validated by regex, failing closed on anything else.
- Recorded API shapes, verified live (read-only) on 2026-10-01:
  - Run `36823737462` is a CI Modules `pull_request` run with **zero module selection** (only
    `generate-matrix`, `modules-gate` and `summarize` succeeded). It still carries exactly one
    `referenced_workflows` entry: `path .../module-tests.yml@a8f4ac8c…`, `ref refs/pull/5509/merge`.
    So a skip run of CI Modules keeps the immutable merge reference that `effective-source` needs.
  - `GET git/commits/a8f4ac8c…` returns `parents: [ecb5dd91… (base), a5cd2d26… (head)]`.
  - `GET actions/runs/<id>/artifacts?name=<exact>` filters server-side. Each artifact has
    `expired`, `created_at` and `workflow_run.{id,head_sha}`.

Constraints:

- **Fail-safe direction differs per subcommand.**
  - `decide` never skips on doubt. Any lookup error yields `Run` with a `::warning::`, and the
    process exits 0.
  - `effective-source` never passes on doubt. Any lookup error or mismatch exits non-zero with
    `re-run CI Modules to execute`.
- Functions must stay at complexity ≤ 15 (Ruff `C901`, Sonar `S3776`). Split `decide` into small
  predicates.
- If a literal appears three or more times, make it a module constant (S1192).
- No `# noqa` and no `# type: ignore`.
- Never print a token. Mirror `fleet_verdict._http_failure` redaction.
- Use "Mission", never "feature". Never write bare "routing": write "CI path routing" or
  "selection-step suppression".

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T064 – Red-first: the parametrised `decide` table over recorded fixtures

- **Purpose**: Pin every row of the green-match contract before any implementation exists
  (ATDD, charter ATDD-First Discipline). An `ImportError` on `scripts.ci.green_match` counts as red.
- **Steps**:
  1. Record the fixtures read-only. Keep them small: trim them with `jq` to the fields the helper
     reads, and say so in a `README.md` inside the fixture directory.
     ```bash
     unset GITHUB_TOKEN
     D=tests/ci/fixtures/green_match
     gh api repos/spec-kitty/spec-kitty/actions/runs/36823737462 > $D/run-ci-modules-zero-selection.json
     gh api repos/spec-kitty/spec-kitty/git/commits/a8f4ac8c897fee4067d20ddfb5552a03a1650d27 > $D/commit-merge-5509.json
     gh api "repos/spec-kitty/spec-kitty/actions/runs/36823737462/artifacts?name=selected-modules" > $D/artifacts-by-name.json
     gh api "repos/spec-kitty/spec-kitty/actions/workflows/ci-router.yml/runs?event=pull_request&head_sha=a5cd2d26a5f9384d639a9eea0d6cae8afdaf1506&per_page=5" > $D/workflow-runs-by-head.json
     ```
     The tested-key and green-match markers do not exist on any real run yet. Synthesize those
     artifact records from the recorded `artifacts-by-name.json` **shape**, changing only `name`,
     `expired` and `created_at`. State in the fixture README that the names are synthesized and
     the shapes are recorded.
  2. Create `tests/ci/test_green_match.py` with `pytestmark = pytest.mark.fast`. A module-level
     marker is mandatory (`test_fast_tier_marker_completeness.py` / `test_marker_job_completeness.py`).
     Import with `from scripts.ci import green_match`.
  3. Write one table-driven test, `test_decide_contract_row`, parametrised with readable `id=`s
     `N1-push`, `N1-workflow_dispatch`, `N1-workflow_call`, `N1-schedule`, `N2-opened`,
     `N2-synchronize`, `N2-reopened`, then N3…N15, P1 and P2. Each row builds an `EventMeta`, a
     `TestedKey | None`, a candidate list and a marker map from the fixtures, then asserts the
     result type (`Skip`/`Run`), `reason` and `marker`:
     - N1–N2, N11: `marker` is `''` for N1 and N11 and the tested-key name for N2.
     - N3–N10, N12–N15: `marker` is the tested-key name `ci-tested-key-pr<N>-base-<base40>`.
     - P1–P2: `marker` is `ci-green-match-run-<id>-attempt-<n>` of the newest match.
  4. Add `test_decide_mutation_control`. Monkeypatch the helper's marker predicate to "always
     present" and assert that rows N7 (moved base), N8 (different PR) and N9 (no marker /
     skip run) **flip to Skip**. This proves those rows discriminate. Without it, a decide that
     skips on any green run would pass the table.
  5. Run it and record the red: `uv run --frozen pytest tests/ci/test_green_match.py -q`, which
     fails with `ImportError`. Commit the red tests first, as their own commit.
- **Files**: `tests/ci/test_green_match.py` (new), `tests/ci/fixtures/green_match/*.json` +
  `README.md` (new).
- **Parallel?**: No. T065 depends on it.
- **Notes**:
  - N5: with per-ref `cancel-in-progress`, a `ready_for_review` arriving mid-run cancels the
    draft run, so the candidate list shows it as `in_progress` or `cancelled`. Both mean Run.
  - N6: iterate every non-success conclusion literally: `failure`, `cancelled`, `timed_out`,
    `action_required`, `startup_failure`, `neutral`, `skipped`.
  - N13: the candidate's id equals `GITHUB_RUN_ID`.
  - N14: the candidate's `path` names another workflow file.
  - N15: a fork PR's `pull_requests: []`. The helper never reads that field; assert it decides
    from the event payload alone.

### Subtask T065 – Implement `decide`, the tested-key binding and artifact-name matching

- **Purpose**: Make T064 green with a pure core and a thin edge (R3 §1.3).
- **Steps**:
  1. Module docstring: cite FR-011, `contracts/green-match.md` and D-15. State the two
     fail-safe directions. Imports must be stdlib only, for example `argparse`, `json`, `os`,
     `re`, `subprocess`, `sys`, `dataclasses`, `collections.abc`, `pathlib`, `typing`.
     `urllib` is allowed only if you ship a urllib transport. No `datetime`, `yaml` or `scripts.*`.
  2. Frozen dataclasses:
     - `EventMeta(event_name, action, pr_number, head_sha, merge_sha, run_id, run_attempt, workflow_file, repository)`
     - `TestedKey(pr, head, base)`, with a `marker_name` property → `ci-tested-key-pr{pr}-base-{base}`
     - `RunMeta(id, run_attempt, path, event, status, conclusion, head_sha, html_url, repository)`
     - the results `Skip(reason, marker, matched)` and `Run(reason, marker)`
  3. Shared binding, defined here and reused by T066:
     - `bind_tested_base(parents: Sequence[str], head: str) -> str` raises
       `ValueError("tested merge parents do not bind the source run head")` unless
       `len(parents) == 2 and parents[1] == head`. It returns `parents[0]`. Validate 40-hex.
     - `merge_reference(run: Mapping[str, Any], repository: str) -> tuple[str, int]` is a
       verbatim lift of `aggregate_source.py:86-102`: it returns the merge SHA and the PR
       number, with the identical message on failure.
  4. `decide(event, tested, candidates, markers) -> Skip | Run`, pure. The step order is fixed
     by R3 §1.3, steps 1–7:
     1. not a `pull_request` event → Run
     2. `tested is None` → Run (`merge-ref-unbound`)
     3. `action != "ready_for_review"` → Run
     4. `run_attempt != 1` → Run (`re-run-never-suppressed`)
     5. filter candidates
     6. walk newest first by `id` and Skip on the first candidate whose `markers[id]` contains
        `tested.marker_name`
     7. otherwise Run

     Extract `_is_candidate(run, event) -> bool` for step 5. It checks `id != run_id`,
     `path == f".github/workflows/{workflow_file}"`, `event == "pull_request"`,
     `status == "completed"`, `conclusion == "success"`, `head_sha == event.head_sha`,
     and `repository == event.repository`.
  5. Thin edge, `_gather(event, transport) -> tuple[TestedKey | None, list[RunMeta], dict[int, frozenset[str]]]`:
     - `GET git/commits/{merge_sha}`, then `bind_tested_base`. A `ValueError` here means
       `tested=None`.
     - `GET actions/workflows/{file}/runs?event=pull_request&head_sha={head}&status=success&per_page=100`.
     - For at most the 10 newest filtered candidates, `GET actions/runs/{id}/artifacts?name={marker}`.
       Keep only names with `expired is False`.
  6. The transport is a `Protocol` with `get(path) -> Any`. Ship `GhTransport`, which runs
     `gh api <path>` through `subprocess`. Two reasons: every existing Actions API call in these
     workflows already uses `gh api` (router-gate, summarize, Aggregate collect), and WP17's
     fake-`gh` harness in `tests/ci/test_aggregate_attempts.py` can drive it.
     - Parse stdout with a `json.JSONDecoder().raw_decode` loop, so concatenated `--paginate`
       pages also parse.
     - Redact on failure: never echo captured output.
     - R3 §1.3 mentions urllib. Ship a urllib transport only if you find `gh` unavailable at
       one of the call sites, and record that choice in the Activity Log.
  7. `decide` CLI: `green_match.py decide --workflow <file> [--marker-dir DIR]`.
     - Validate `--workflow` against `^[a-z0-9-]+\.yml$`.
     - Read `GITHUB_EVENT_NAME`, `GITHUB_EVENT_PATH` (payload: `action`, `pull_request.number`,
       `pull_request.head.sha`), `GITHUB_SHA` (the merge commit), `GITHUB_RUN_ID`,
       `GITHUB_RUN_ATTEMPT`, `GITHUB_REPOSITORY` and `GH_TOKEN`.
     - Append `skip`, `reason`, `marker`, `matched-run-id`, `matched-run-attempt` and
       `matched-run-url` to `$GITHUB_OUTPUT`. Use the delimiter form for any value that could
       hold a newline.
     - If `marker != ''`, write a ~1 KB JSON body
       `{pr, head, base, merge_sha, workflow, run_id, run_attempt, decision}` to
       `<marker-dir>/<marker>.json`, ready for WP18's upload step.
     - On Skip, print `::notice::` naming the matched run URL and append one
       `$GITHUB_STEP_SUMMARY` line (scenario 4: "its log names the matched prior run").
     - Wrap everything after argument parsing in `try/except Exception`: print `::warning::`
       and emit Run(`lookup-failed: <class>`). Always `return 0`.
- **Files**: `scripts/ci/green_match.py` (new).
- **Parallel?**: No.
- **Notes**: `pull_requests[].base.sha` is a live projection (R3 §0.1) and must **never** be read.
  Keep `decide` free of I/O so the table tests stay pure.

### Subtask T066 – Extract the shared binding in `aggregate_source.py` (behaviour-preserving)

- **Purpose**: D-27 calls for one binding authority. Today `aggregate_source.py:86-110` encodes
  the merge-reference and parent rule that `green_match` also needs. After this subtask it calls
  the shared functions instead of carrying its own copy.
- **Steps**:
  1. Red-first. Add
     `tests/ci/test_aggregate_source.py::test_tested_identity_matches_prepare_source`:
     - build `source_fixture(tmp_path)` and run `run_source(repo, run)`;
     - then, in-process,
       `from scripts.ci.green_match import bind_tested_base, merge_reference`. Compute
       `merge_reference(run, "spec-kitty/spec-kitty")` and
       `bind_tested_base(git(repo, "show", "-s", "--format=%P", merge).split(), run["head_sha"])`;
     - assert they equal `source.json`'s `tested_sha`, `pr_number` and `base_sha`.

     It is red until T065 lands the functions.
  2. In `aggregate_source.py`, add `from green_match import bind_tested_base, merge_reference`
     next to line 13 and keep ruff's import ordering. Then:
     - replace lines 90–102 with `tested, number = merge_reference(run, repository)`;
     - replace the binding at lines 107–110 with `base = bind_tested_base(parents, head)`, with
       `parents` still read by the existing `git show -s --format=%P` call.
  3. Do not change `prepare_source`'s signature, `CRITICAL_PATHS` or any output file.
     `source_fixture` and `run_source` keep their signatures, because WP17's harness imports
     `source_fixture` (`tests/ci/test_aggregate_attempts.py:16`).
  4. Run the whole file: `uv run --frozen pytest tests/ci/test_aggregate_source.py tests/ci/test_aggregate_attempts.py -q`.
     All existing rows must stay green unchanged. That includes the 11
     `test_source_rejects_ambiguous_or_stale_evidence` mutations, which assert the exact
     messages.
- **Files**: `scripts/ci/aggregate_source.py`, `tests/ci/test_aggregate_source.py`.
- **Parallel?**: It can follow T065 directly. It is independent of T067.
- **Notes**:
  - `aggregate_source.py` runs bare in Aggregate on the **trusted default-branch** checkout. The
    sibling import resolves because `sys.path[0]` is `scripts/ci/`, exactly as `prose_only` does.
  - mypy resolves the bare sibling import. `mypy --strict scripts/ci/aggregate_source.py` is
    clean today; keep it clean.
  - `aggregate_source.py` is **not** in `[tool.ruff.format].exclude`, so format normally.

### Subtask T067 – `effective-source` subcommand (consumed by WP17)

- **Purpose**: Give CI Aggregate a verified way to aggregate the matched run's evidence when its
  source is a skip run (R3 §1.3 "effective-source", §1.4, D-15/D-16). Without it, a skip run
  silently drops diff-cover: its empty selection gives `complete=true, coverage=false` (R3 §0.2).
- **Steps**:
  1. Red-first rows in `tests/ci/test_green_match.py`, parametrised over the pure core
     `effective_source(source_run, source_artifacts, matched_run, identity_of) -> Effective`:
     - **A2** (regression): no `ci-green-match-run-*` artifact → returns the source id and
       attempt unchanged, with `repointed=False`.
     - **A1** (each row a separate id): the matched run is missing (lookup raises); the matched
       run's conclusion is not success or its status is not completed; its `head_sha` differs;
       its `path` is not `.github/workflows/ci-modules.yml`; its event is not `pull_request`;
       or the tested identity differs (a different base parent). Each raises
       `EffectiveSourceError`.
     - **A3**: a `workflow_dispatch` replay of a skip run re-points identically. The core takes
       no event input.
     - **A4** (new, found while verifying the contract): a marker uploaded by an **earlier
       attempt** of the source run must not re-point a later attempt. After a skip on attempt 1
       and a "re-run all jobs" on attempt 2, `decide` returns Run (N3) and attempt 2 executes.
       The artifacts list still holds attempt 1's skip marker.
       - Bind each marker to the requested attempt by requiring
         `marker.created_at >= source_attempt.run_started_at`. Both are fixed-format UTC `Z`
         strings: regex-validate them, then compare them as strings.
       - An earlier-attempt marker is ignored, so the row expects `repointed=False`.
       - A malformed timestamp raises.
     - **A5**: two or more distinct green-match markers bound to the attempt raise `ambiguous`.
       A name that fails the strict regex
       `^ci-green-match-run-([1-9][0-9]*)-attempt-([1-9][0-9]*)$` is ignored.
  2. Implement the core. The tested identity `(pr, head, base)` of **both** runs comes from
     `merge_reference` plus `bind_tested_base` over each run's own merge commit parents
     (`GET git/commits/<merge_sha>`). Compare identities, not merge SHAs: GitHub may regenerate
     the merge commit with the same parents but a different SHA.
  3. Implement the CLI:
     `green_match.py effective-source --repository R --run-id ID --attempt N [--transport gh]`.
     - It fetches `actions/runs/ID/attempts/N` and `actions/runs/ID/artifacts?per_page=100`
       (paginated through the transport), and the matched attempt plus both commits when a
       marker is bound.
     - It prints `run-id=…`, `run-attempt=…`, `repointed=true|false` and `matched-run-url=…` to
       stdout. The step appends them to `$GITHUB_OUTPUT`, as `select_source_artifacts.py` does.
     - On any `EffectiveSourceError` or transport error it prints
       `::error::green-match source could not be verified (<reason>); re-run CI Modules to execute`
       and exits 1.
  4. Add a CLI-level test that drives `main([...])` with an injected fake transport built from
     the fixtures. It asserts the stdout lines for A2 and P-repoint, and exit 1 for one A1 row.
- **Files**: `scripts/ci/green_match.py`, `tests/ci/test_green_match.py`, fixtures.
- **Parallel?**: It can run alongside T066.
- **Notes**:
  - The output keys `run-id` and `run-attempt` are the interface WP17 consumes. Do not rename
    them later.
  - Security: the marker *name* is written by a PR-controlled run, and Aggregate runs on
    trusted `main` code. The head, workflow, event, success and identity re-verification is what
    makes a forged marker harmless. A forged name can only point at a run with the same tested
    identity. Keep every conjunct.

### Subtask T068 – Bare-run guard, clock-ban check, lint and type cleanliness

- **Purpose**: The helper runs in three selection jobs **before** any `uv sync` or `pip install`.
  Prove it needs nothing beyond the stdlib and the repo-local file, and keep the code gates green.
- **Steps**:
  1. Add `test_helper_runs_bare_without_site_packages(tmp_path)`, copied from the
     `tests/ci/test_aggregate_attempts.py:27` pattern. It runs
     `subprocess.run([sys.executable, "-I", "-S", str(ROOT / "scripts/ci/green_match.py"), "--help"], cwd=tmp_path)`
     and asserts exit 0 and no `ModuleNotFoundError` in stderr.
  2. Add `test_helper_respects_the_clock_import_boundary`, mirroring
     `test_aggregate_attempts.py:21`: `collect_import_ban_violations([ROOT / "scripts/ci/green_match.py"]) == []`.
  3. Add a static AST test asserting that `green_match.py` imports no `yaml` and no `scripts`
     module at any depth. This keeps WP18's pre-install placement safe by construction.
  4. Run the gates:
     ```bash
     uv run --frozen ruff check scripts/ci/green_match.py scripts/ci/aggregate_source.py tests/ci/test_green_match.py tests/ci/test_aggregate_source.py
     uv run --frozen ruff format --check scripts/ci/green_match.py scripts/ci/aggregate_source.py tests/ci/test_green_match.py tests/ci/test_aggregate_source.py
     uv run --frozen mypy --strict scripts/ci/green_match.py scripts/ci/aggregate_source.py
     ```
  5. Run `python3 scripts/ci/derive_pinning_inventory.py --check`.
     - The committed `tests/release/pinning_rule_inventory.json` is green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37): the #3143
       `test_pytest_ini_timeout_default.py::<module-docstring>` entry is already in it.
     - **Never regenerate it in this WP** (tasks.md Global rules: WP16 is not a lane-a
       pinned-file WP; WP19 regenerates last).
     - Confirm `--check` stays green on your tip. If it is red, diff `--stdout` against the
       base: a delta from another lane's pinned-file edit (merged into your base) is not yours —
       record it for WP19; a delta from your own text is yours to fix.
- **Files**: `tests/ci/test_green_match.py`.
- **Parallel?**: Last.
- **Notes**: `tests/ci/test_workflow_script_import_guard.py` does not yet see the helper, because
  no workflow invokes it until WP17. Run it anyway; it must stay green.

## Test Strategy

Red-first order. First commit: T064's table plus T066's identity test, both red. Then the
implementation commits.

Targeted runs:

```bash
uv run --frozen pytest tests/ci/test_green_match.py tests/ci/test_aggregate_source.py tests/ci/test_aggregate_attempts.py -q
uv run --frozen pytest tests/ci/test_workflow_script_import_guard.py -q
uv run --frozen pytest tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py -q
uv run --frozen pytest tests/architectural/test_fast_tier_marker_completeness.py tests/architectural/test_ruff_format_enforcement.py -q
make test-fast
```

Typecheck: `uv run --frozen mypy --strict scripts/ci/green_match.py scripts/ci/aggregate_source.py`
must report zero issues. A passing pytest run does not replace this.

Never run `pytest tests/architectural` as a directory, and never run `make test-full` (C-009).
Record the exact commands and pass/fail counts in the Activity Log and the PR's *Tests run*
section.

## Risks & Mitigations

- **Silent behaviour change in `aggregate_source.py`.** Mitigation: the 11 existing
  exact-message mutation rows plus the new identity-equality test.
- **A `decide` that skips too eagerly.** Mitigation: the mutation control in T064 and the
  fail-open-to-Run edge.
- **An `effective-source` that passes on doubt.** Mitigation: every error path raises and exits
  1. A2 pins the unchanged pass-through.
- **Stale-attempt marker (A4).** This is a real gap in the contract text as written, closed
  here by binding markers to the attempt window. Record it in the Activity Log so WP19's ADR
  amendment mentions it.
- **Recorded fixtures drift from the live API.** Mitigation: trim them to the read fields and
  document the recording commands in the fixture README.

## Review Guidance

- Confirm every contract row has a named parametrised id. Rows that pass "by type" (asserting
  only `isinstance`) are not enough: assert `reason` and `marker` too.
- Confirm the mutation control really flips N7, N8 and N9.
- Diff `aggregate_source.py`. The only changes should be the import and two call-site
  replacements. The error strings must be byte-identical.
- Confirm there is no `datetime`, no `yaml`, no `scripts.*` import, and no token in any message.
- Confirm the implementer ran `mypy --strict` and `ruff format --check` and recorded the counts.
- Confirm the pinning inventory was not regenerated here and `--check` is green (or any delta is
  attributed and recorded for WP19, not "fixed" out of map).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
