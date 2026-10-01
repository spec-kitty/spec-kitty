---
work_package_id: WP11
title: Memory sampler
dependencies: []
requirement_refs:
- NFR-005
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T046
- T047
- T048
phase: Phase 5 - Battery reshaping
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/memory_sampler.py
- tests/ci/test_memory_sampler.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/memory_sampler.py
- tests/ci/test_memory_sampler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Memory sampler

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

NFR-005 requires the peak resident memory of each battery job to stay below 12 GB on the
16 GB runner, as recorded in the job log by a memory sampler. Today nothing records it. The
battery is about to go from 2 to 4 xdist workers (FR-002), which raises peak memory for the
AST-scanning tests.

This WP delivers only the tool, `scripts/ci/memory_sampler.py`, with its tests. WP12 wires it
into the router's `architectural-fast` job and both `architectural-heavy` legs.

Done means:

- `python3 -m scripts.ci.memory_sampler start --out PATH` returns at once and leaves a
  detached background sampler running.
- `python3 -m scripts.ci.memory_sampler stop --out PATH` stops it and prints exactly one
  parseable line, `peak_rss_bytes=<int> source=<meminfo|unavailable> ...` (T048). It also
  appends one line to `$GITHUB_STEP_SUMMARY`, and emits `::warning::` at ≥ 10 GB and an
  `::error::` annotation at ≥ 12 GB. It always exits 0: the sampler measures, it never fails
  a job.
- The module is stdlib-only, so it runs before `uv sync` on the runner's system `python3`
  (3.12 on ubuntu-24.04; the code stays 3.11-compatible). Its pure functions stay at
  complexity ≤ 15. `ruff check`, `ruff format --check` and `mypy --strict` all pass with zero issues.
- `tests/ci/test_memory_sampler.py` is red on the planning base (the module is missing) and
  green on the WP tip.

## Context & Constraints

- **Read first**: in `research.md`, decision row D-07, the fold row D-28 (separate new file
  with its own test), and R1 §6 "NFR-005 — memory sampler". Then `spec.md` NFR-005, `plan.md`
  (post-plan folds: "IC-03 splits: memory sampler as its own new-file unit"), and
  `.kittify/charter/charter.md`.
- **Measurement choice (D-07)**: sample `/proc/meminfo` and record
  `MemTotal − MemAvailable`. This is system-wide non-reclaimable use, which is the
  OOM-relevant number on the 16 GB VM. Page cache counts as available, so the full-history
  checkout and the uv cache do not inflate it. As a **secondary** figure, read the job
  cgroup's `memory.peak` (cgroup v2) when it is readable. Its path comes from
  `/proc/self/cgroup` (`0::/<path>` → `/sys/fs/cgroup/<path>/memory.peak`).
- **Rejected**: `/usr/bin/time -v`. It reports the max RSS of the largest single process, not
  the sum across xdist workers, and wrapping the pytest command would break the gate model's
  command parse and trip the blind-runner guard in `test_no_duplicate_suite_execution.py`.
  The sampler must therefore never wrap pytest. It runs in its own steps.
- **Background lifetime**: on GitHub-hosted runners, a process detached in one step survives
  into later steps of the same job, and the runner reaps orphans at job end. `start` must
  detach for real (`start_new_session=True`, stdio to `DEVNULL`), so the step's shell does
  not wait for it.
- **Clock gates**: `tests/architectural/test_clock_call_ban.py` and `test_clock_import_ban.py`
  scan `scripts/`. Use only `time.monotonic()` and `time.sleep()`, which are duration calls
  and allowed. Never call `time.time()`, `datetime.now()` or `date.today()`, and do not import
  `datetime`. Express timestamps as monotonic elapsed seconds.
- **Workflow import guard**: `tests/ci/test_workflow_script_import_guard.py` covers bare-script
  invocations. WP12 invokes the module with `-m`, from the repository root, which is exempt.
  Still, do not import any `scripts.*` sibling, so the module is safe either way.
  `scripts/ci/` has no `__init__.py`; `-m scripts.ci.memory_sampler` works as a namespace package.
- **Pinning inventory**: `scripts/ci/derive_pinning_inventory.py` scans `scripts/` and
  `tests/` for the literals `ci-quality.yml`, `sonarcloud` and `make test-fast`. Do not use
  them in the new files, or `tests/release/pinning_rule_inventory.json` goes stale.
- **C-009**: no local heavy suites.
- **Terminology**: "Mission", never "feature". Never bare "routing".

### Current-state anchors (verified 2026-10-01)

| Surface | Anchor | Today |
|---|---|---|
| Sampler | `scripts/ci/memory_sampler.py` | does not exist |
| Stdlib-only script precedent | `scripts/ci/release_nightly_gate.py` docstring | "stdlib-only (urllib) so the gate step can run it with a bare `python3`" |
| Test precedent | `tests/ci/test_release_nightly_gate.py` | `pytestmark = pytest.mark.fast`; loads the script by file path (an `importlib.util` spec) |
| Module row | `.github/ci-module-registry.yml` row `ci` (`test_dirs: [tests/ci]`) | `tests/ci` runs serially, marker `not performance and not stress` |
| `-m` invocation precedent | `ci-router.yml` job `docs-lint` | `uv run --frozen python -m scripts.docs.check_spelling` |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T046 – Red-first unit tests with fake `/proc` and cgroup files

- **Purpose**: pin behaviour before writing code. Tests drive pure functions over fake
  files under `tmp_path`, never the real `/proc`. They are red today because the module
  does not exist (import fails, so every test errors).
- **Steps**:
  1. Create `tests/ci/test_memory_sampler.py` with `pytestmark = pytest.mark.fast`. Load
     the module by file path (the `test_release_nightly_gate.py` pattern) or import
     `scripts.ci.memory_sampler`. Pick one and stay consistent.
  2. Write a fixture `fake_proc(tmp_path, total_kb, available_kb, cgroup_line=...)` that
     writes `meminfo` and `self/cgroup` under `tmp_path/proc`, and optionally
     `tmp_path/sys/fs/cgroup/<path>/memory.peak`.
  3. Tests (names indicative):
     - `test_parse_meminfo_reads_total_and_available_in_bytes`: kB × 1024. Ignore unrelated
       lines and tolerate extra whitespace.
     - `test_parse_meminfo_without_memavailable_is_unavailable`: returns `None`; never guess
       from `MemFree`.
     - `test_used_bytes_is_total_minus_available`.
     - `test_peak_tracking_keeps_the_maximum_and_the_baseline`: feed 3 samples. Baseline is
       the first, peak the max, delta = peak − baseline, samples = 3. The state is immutable
       (a frozen dataclass or a fresh value per update).
     - `test_cgroup_peak_path_from_unified_hierarchy_line`: `0::/system.slice/x.scope` →
       `<root>/sys/fs/cgroup/system.slice/x.scope/memory.peak`.
     - `test_cgroup_peak_absent_or_unreadable_is_none`: a missing file, a v1-only cgroup line,
       or non-integer content all give `None`. No exception.
     - `test_render_report_line_contract`: the exact key order and format of the T048 line,
       `cgroup_peak_bytes=na` when absent, and `source=unavailable` when meminfo never yielded a sample.
     - `test_threshold_annotations`: below 10 GB, no annotation; at ≥ 10 GB, one
       `::warning title=memory sampler::…`; at ≥ 12 GB, one `::error title=memory sampler::…`.
       Pin the boundaries at exactly 10 GiB and 12 GiB (state the unit in the docstring:
       GiB = 1024³ bytes).
     - `test_step_summary_line_appended_when_env_set`: monkeypatch `GITHUB_STEP_SUMMARY` to a
       tmp file. One line is appended and existing content is preserved. With the env unset,
       nothing is written.
     - `test_sample_loop_writes_state_atomically` (in-process): `main(["sample", "--out", p,
       "--interval", "0", "--max-samples", "3", "--proc-root", fake])`. The state file holds
       3 samples. Write it via tmp file + `os.replace`, so the file is always complete JSON.
     - `test_start_then_stop_round_trip` (subprocess): `start` with `--interval 0.05` and the
       fake proc root, a short wait for the state file to appear (poll with a bounded loop),
       then `stop`. Assert stdout carries the `peak_rss_bytes=` line and the child pid is
       gone. Keep the total test time under 2 s.
     - `test_stop_without_start_degrades_to_a_warning_and_exit_zero`: no state file → one
       `::warning::` and `peak_rss_bytes=0 source=unavailable`, exit code 0.
     - `test_module_is_stdlib_only`: AST-scan the module's imports and assert every top-level
       name is in `sys.stdlib_module_names`. The module runs before `uv sync`.
  4. Run the file and confirm it is **red**. Record that in the Activity Log.
- **Files**: `tests/ci/test_memory_sampler.py` (new).
- **Parallel?**: No (first commit).
- **Notes**: the tests run in the serial `ci` module row on Linux. Do not depend on the real
  `/proc` values. Avoid wall-clock assertions: bound waits by iteration count and poll
  intervals, not by `time.time()`.

### Subtask T047 – Implement the sampler

- **Purpose**: the tool itself, as small pure functions behind a thin CLI.
- **Steps**:
  1. `scripts/ci/memory_sampler.py`, `from __future__ import annotations`, stdlib only
     (`argparse`, `dataclasses`, `json`, `os`, `signal`, `subprocess`, `sys`, `time`, `pathlib`).
  2. Pure layer, each function ≤ 15 complexity:
     - `parse_meminfo(text: str) -> MemInfo | None`, where `MemInfo` is a frozen
       `(total_bytes, available_bytes)`.
     - `used_bytes(info: MemInfo) -> int`.
     - `SamplerState` (frozen): `baseline_bytes`, `peak_bytes`, `samples`, `elapsed_seconds`,
       `source`, `pid`. Plus `update(state, used, elapsed) -> SamplerState`, `to_json` and `from_json`.
     - `cgroup_peak_path(proc_self_cgroup: str, sys_root: Path) -> Path | None` (unified `0::` line only).
     - `read_int_file(path: Path) -> int | None`.
     - `render_report(state, cgroup_peak, *, warn_bytes, error_bytes) -> list[str]`: the
       report line first, then any annotations.
     - `summary_line(state, cgroup_peak) -> str`.
  3. Edge layer (`main(argv)`), with subcommands:
     - `sample --out P [--interval 2.0] [--max-samples N] [--proc-root /proc] [--sys-root /]`:
       a foreground loop. Read meminfo, update the state, write it atomically, then sleep.
       Handle SIGTERM by writing a final state and exiting 0.
     - `start --out P [--interval 2.0] [--proc-root] [--sys-root]`: spawn
       `[sys.executable, "-m", "scripts.ci.memory_sampler", "sample", ...]` with
       `start_new_session=True`, `stdin/stdout/stderr=DEVNULL` and `cwd` = the repository root
       derived from `__file__`. Record the child pid in `P.pid`, print
       `memory_sampler started pid=<n> out=<P>`, and return 0. On any `OSError`, print a
       `::warning::` and return 0.
     - `stop --out P [--warn-gb 10] [--error-gb 12] [--proc-root] [--sys-root]`: read the pid
       and SIGTERM it, wait a bounded number of polls (e.g. 50 × 0.1 s via `time.sleep`), take
       one final sample yourself, read the cgroup peak, print `render_report(...)`, append
       `summary_line` to `$GITHUB_STEP_SUMMARY` when it is set, and return 0 in every case.
  4. Make the module docstring the contract (T048). Cover purpose (NFR-005), what is measured
     and why (D-07), what was rejected and why, the CLI, the output line, thresholds and
     units, and the lifetime model (detached child reaped at job end).
- **Files**: `scripts/ci/memory_sampler.py` (new).
- **Parallel?**: No (T046 first).
- **Notes**:
  - Never raise out of `main`. Measurement must not turn a green battery red. The
    `::error::` annotation at 12 GB is a visible signal, not a job failure, per R1 §6.
  - Do not add `# noqa` or `# type: ignore`. If mypy struggles with `json.loads` typing,
    validate the shape explicitly in `from_json`.
  - Keep repeated literals (for example the annotation title `memory sampler`) in module
    constants (Sonar S1192).

### Subtask T048 – Output contract documented and pinned

- **Purpose**: WP12 and the evidence file (C-011) parse the report line, so it must be
  stable and documented.
- **Steps**:
  1. Fix the line format, in this exact key order:
     `peak_rss_bytes=<int> source=<meminfo|unavailable> baseline_bytes=<int> delta_bytes=<int> samples=<int> elapsed_s=<float .1f> cgroup_peak_bytes=<int|na>`.
     The name `peak_rss_bytes` is the tasks.md contract key. The docstring must say it holds
     the peak of `MemTotal − MemAvailable` (system non-reclaimable memory), not per-process RSS.
  2. Add `test_report_line_is_parseable_by_a_key_value_split`: split on spaces, then on the
     first `=`. Assert the key set and order equal a module constant `REPORT_KEYS`, and that
     every integer field parses. WP12 and the evidence work rely on this.
  3. Document the WP12 wiring snippet in the docstring, so the consumer does not have to guess:
     ```yaml
           - name: Start memory sampler (NFR-005)
             run: python3 -m scripts.ci.memory_sampler start --out "$RUNNER_TEMP/memory-sampler.json"
           # ... uv sync + pytest ...
           - name: Report peak memory (NFR-005)
             if: always()
             run: python3 -m scripts.ci.memory_sampler stop --out "$RUNNER_TEMP/memory-sampler.json"
     ```
     The `start` step goes after `actions/checkout` (the script lives in the repo) and before
     `setup-uv`/`uv sync`, so the baseline reflects the idle runner.
- **Files**: `scripts/ci/memory_sampler.py`, `tests/ci/test_memory_sampler.py`.
- **Parallel?**: No.
- **Notes**: if the format changes later, WP12's wiring and the evidence file must change in
  the same commit. Say so in the docstring.

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_memory_sampler.py -q
make test-fast
# Specific architectural gates that scan scripts/ (never the whole directory):
uv run --frozen pytest tests/architectural/test_clock_call_ban.py tests/architectural/test_clock_import_ban.py -q
uv run --frozen pytest tests/ci/test_workflow_script_import_guard.py -q
uv run --frozen ruff check scripts/ci/memory_sampler.py tests/ci/test_memory_sampler.py
uv run --frozen ruff format --check scripts/ci/memory_sampler.py tests/ci/test_memory_sampler.py
uv run --frozen mypy --strict scripts/ci/memory_sampler.py
python3 -m scripts.ci.memory_sampler start --out /tmp/ms.json && sleep 3 && python3 -m scripts.ci.memory_sampler stop --out /tmp/ms.json   # manual smoke on a Linux dev box
```

(For the manual smoke, use your session scratchpad rather than `/tmp` if one is configured.)
Record the commands and pass/fail counts in the Activity Log and the PR's *Tests run*. A
`test_clock_*` red that predates your change is pre-existing. Classify it per the
baseline-red gotcha and do not chase it.
  **Pre-existing Failure Reporting Rule (charter, binding):** such a red needs a GitHub issue — cite the existing one or open one (command, failure summary, why it is pre-existing) — before you continue past it.

## Risks & Mitigations

- **Orphaned sampler outlives the job**: the runner reaps it at job end, and `stop` SIGTERMs it explicitly.
- **Flaky subprocess round-trip test**: bounded polling, a fake proc root, interval 0.05 s,
  and no wall-clock assertions.
- **cgroup layout differs on the hosted runner**: the cgroup figure is secondary and
  optional. `na` is a valid value.
- **Non-Linux dev box**: `/proc/meminfo` is missing → `source=unavailable` plus a warning,
  exit 0.

## Review Guidance

- Red on the planning base (module missing), green on the tip.
- Read the docstring as the contract: D-07 rationale, the `/usr/bin/time -v` rejection, the
  line format, units and lifetime.
- Grep the module for `time.time`, `datetime` and `.now(`; none may appear. Confirm it is
  stdlib-only and imports no `scripts.*` sibling.
- `main` never raises, and every path exits 0.
- Confirm mypy `--strict`, ruff check and ruff format all ran clean, with no suppressions.
- **Definition of Done**: NFR-005 has a working, documented, tested instrument whose output
  line WP12 can wire unchanged. The NFR itself is verified later from WP12's CI runs (C-011).

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
