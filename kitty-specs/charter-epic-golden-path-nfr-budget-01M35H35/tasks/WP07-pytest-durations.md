---
work_package_id: WP07
title: 'Actions-evidence measurability: pytest.ini durations'
dependencies: []
requirement_refs:
- NFR-002
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T03:42:31.592517+00:00'
subtasks:
- T024
- T025
history: []
agent_profile: python-pedro
authoritative_surface: pytest.ini
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- pytest.ini
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP07 – Actions-evidence measurability: pytest.ini durations

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ CHOKEPOINT

`pytest.ini`'s `addopts` line applies REPO-WIDE — this change affects every
pytest invocation across the whole repository, not just this mission's tests.
No open PR currently touches `pytest.ini` (checked at dispatch time), but treat
this as a real cross-cutting change, not a low-risk edit, because of its blast
radius.

## Objective

Add `--durations=0 --durations-min=1.0` to `pytest.ini`'s existing `addopts`
line so that the golden-path test's own **full** setup+call+teardown wall-clock
cost — not merely its single slowest phase — is visible in the `tests (e2e)`
job's Actions log, without any `.github/workflows/*.yml` change (which Ruling 4
forbids).

## Context

**Design history (superseded by this revision, recorded for continuity):** an
earlier draft of this WP specified `--durations=1`. Post-tasks analysis (finding
A1) found that mechanism measures the wrong quantity: `--durations=N` reports
only the single globally-slowest individual setup/call/teardown *phase* across
the whole `pytest tests/e2e -q` run (21 tests, 6 files) — never a per-test sum.
Verified live against this repo's installed pytest 9.0.3: with `--durations=1`,
only the golden path's `call` phase (73.58s) would print, silently omitting its
~29.36s `setup` phase (git init + `spec-kitty init` + git add/commit) — an
understatement of roughly a quarter of the true cost against Ruling 2's hard,
no-exception-band ≤110s bar. This revision fixes that.

Per `plan.md`'s "Actions evidence path" section: the `tests-e2e` job runs
`pytest tests/e2e -q` with a single `run:` step and no internal per-test timing.
Since the golden path does not log its own timing, and a workflow-level change
is explicitly ruled out by Ruling 4, `plan.md` chose `pytest.ini`'s `addopts`
line as the mechanism — `pytest.ini`, not `pyproject.toml`, is this repo's
canonical pytest-config home (per the comment at `pyproject.toml:228-236`,
guarded by `tests/architectural/test_marker_registry_single_source.py`).

**Corrected mechanism — `--durations=0 --durations-min=1.0`, not a scoped `-k`
filter, not a fixed top-N count.** `--durations=0` means "no count limit — show
every phase at or above the minimum," and `--durations-min=1.0` sets that
minimum to 1.0 seconds (pytest's own default is 0.005s). Together these
**deterministically** print every setup/call/teardown phase whose own duration
is ≥1.0s, for every pytest invocation across the repo — not just a heuristic
top-N slice. This closes the exact gap A1 found: the golden path's `setup`
(~29s) and `call` (~74s) phases are each, on their own, far above the 1.0s
floor, so **both always print, every time this test runs**, regardless of how
many other tests are in the same invocation or how their own durations compare
— unlike a `--durations=N` count limit, this is not a "probably shows up"
heuristic. The `teardown` phase (~0.03s, three orders of magnitude below the
1.0s floor and below the 110s budget by an even wider margin) is expected to be
filtered out by design — this is an intentional, immaterial omission (~30ms
against a budget with second-scale margins), not a repeat of A1's flaw (which
silently dropped ~29s, roughly a quarter of the true cost). Verified live this
session with a scratch pytest run (`/tmp` scratch, not this repo): a fixture
with a 1.3s setup / 1.6s call / 0.2s teardown, under `--durations=0
--durations-min=1.0`, printed exactly the setup and call lines and hid the
teardown line with a `(N durations < 1s hidden.)` footer — confirming the
threshold behavior empirically, not just from the `--help` text.

**Why this stays repo-wide and low-noise, unlike a bare `--durations=0`.** A
bare `--durations=0` (no minimum) would print every phase down to pytest's
default 0.005s floor — for large fast/unit-tier runs (thousands of
sub-second-by-definition tests, per pytest.ini's own `fast` marker
description) this would flood every CI job's log with thousands of near-zero
lines, a real regression from today's single extra line. Pairing `--durations=0`
with `--durations-min=1.0` avoids this: the `fast`/`unit` tier is sub-second by
definition and mostly disappears from the report entirely, while `tests/e2e`
and `tests/performance` (which do real subprocess/git work, well above 1s per
phase for the slower tests) still show a handful of lines — bounded, not a
flood. This is a **more accurate and lower-risk repo-wide mechanism** than the
original `--durations=1` draft, not a trade-off against it.

**Reading the evidence — sum, don't eyeball.** Because this prints potentially
more than one line for the golden path's nodeid
(`tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path`),
whoever reads the Actions log for closure evidence must locate **every** line
matching that nodeid (there will normally be two: `setup` and `call`; `teardown`
is expected to be absent, filtered by the 1.0s floor — if a future change ever
pushes teardown above 1.0s, include that line too, do not assume exactly two)
and **sum them with an actual calculation**, not by eye. `spec.md`'s own
"Evidence carried into this spec" section (see finding B1) already shows what
goes wrong when a three-number sum is done by eye: 73.58 + 29.36 + 0.03 was
recorded as 127.55 instead of the correct 102.97 — a ~24.6s arithmetic error in
exactly the kind of manual summation this WP now requires the evidence-reader
to do again. Use a real calculator step (e.g. `python3 -c "print(73.58 +
29.36)"`), not mental arithmetic, when producing the final summed number for
the PR description / `## Actions Evidence Log` entry.

### Subtask T024: Add `--durations=0 --durations-min=1.0` to `pytest.ini`'s `addopts` line

**Purpose**: Make the golden path's own full setup+call wall-clock cost visible
in every pytest run's terminal summary, without a workflow-file change, and
without the truncation flaw A1 found in the original `--durations=1` draft.

**Steps**:
1. Open `pytest.ini` and locate its `addopts` line (currently
   `addopts = --tb=short` — confirm the current exact value yourself, it may
   have drifted).
2. Append `--durations=0 --durations-min=1.0` to the existing `addopts` value
   (do not replace or remove `--tb=short` or any other existing flag on that
   line).
3. Do not touch any other line in `pytest.ini` — this WP's `owned_files` is
   confined to this single file, and the change itself should be a single
   flag addition to a single existing line.

**Files**: `pytest.ini` (1-line change: append two flags to the existing
`addopts` value).
**Validation**: `git diff pytest.ini` shows exactly one line changed, with
`--durations=0 --durations-min=1.0` appended and every pre-existing flag on
that line preserved.

### Subtask T025: Verify the durations summary captures BOTH material phases, not just one

**Purpose**: Confirm the flag combination actually produces the full
setup+call picture for the golden path, not just that some output changed.

**Steps**:
1. Run a scoped pytest invocation that will pick up `pytest.ini`'s `addopts`
   automatically (do not pass `--durations`/`--durations-min` explicitly on the
   command line — the whole point is confirming the config-file default takes
   effect):
   ```bash
   .venv/bin/python -m pytest tests/e2e/test_charter_epic_golden_path.py -q
   ```
2. Confirm the terminal output's "slowest durations" section (written
   regardless of `-q`, not subject to per-test stdout capture) includes **both**
   a `setup` line and a `call` line for
   `tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path`
   — not only one of the two. This is the concrete proof A1's flaw is fixed:
   the setup phase must be visibly present, not silently dropped.
3. Sum the two (or more, if `teardown` also appears) printed values with an
   actual calculation and record the total in your WP completion notes as a
   sanity check of the mechanism (this is a local dry run, not the real Actions
   evidence — the real evidence is gathered by the orchestrator per `plan.md`'s
   Actions evidence path once a real GitHub Actions run exists).
4. Run one of the baseline-method commands from `plan.md`
   (`.venv/bin/python -m pytest tests/unit tests/status tests/cli
   tests/specify_cli/runtime -q -m "(fast or unit)"`) and confirm the durations
   summary either shows nothing (if every fast/unit test's phases are under the
   1.0s floor, the expected common case) or only a small, bounded number of
   lines — not a flood — confirming the `--durations-min=1.0` noise-reduction
   design holds for the largest, most test-dense baseline command.
5. Run the always-on architectural gates cheap enough to sanity-check locally
   per `plan.md`'s Baseline method step 3: `terminology`
   (`tests/architectural/test_no_legacy_terminology.py`), `layer-rules`
   (`tests/architectural/test_layer_rules.py`,
   `tests/architectural/test_pyproject_shape.py`), and
   `tests/architectural/test_marker_registry_single_source.py` (the gate that
   specifically enforces `pytest.ini` as the canonical pytest-config home —
   this WP's own change must not trip it).

**Files**: none further changed (verification only).
**Validation**: both the `setup` and `call` lines for the golden path's own
nodeid are observed in the `tests/e2e` invocation's durations summary (not just
one), the fast/unit baseline command shows no flood of near-zero lines, and
`test_marker_registry_single_source.py` still passes.

## Definition of Done

- `pytest.ini`'s `addopts` line has `--durations=0 --durations-min=1.0`
  appended, with every pre-existing flag preserved.
- No `.github/workflows/*.yml` file is touched by this WP.
- A local dry run of `tests/e2e/test_charter_epic_golden_path.py` shows BOTH
  the `setup` and `call` duration lines for the golden path's own nodeid —
  proof the A1 phase-omission flaw is fixed, not just that some output
  changed.
- The fast/unit baseline command shows no flood of near-zero-duration lines
  (confirming `--durations-min=1.0` bounds the repo-wide noise).
- `tests/architectural/test_marker_registry_single_source.py` still passes.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T024–T025.

## Risks

- **Repo-wide blast radius**: this single-line change affects the terminal
  output of every pytest invocation in the repository, including CI jobs this
  mission does not otherwise touch. The risk is informational-output noise, not
  a behavior change — bounded by the `--durations-min=1.0` floor (see Context
  above for why this stays low-noise even repo-wide). Reviewers should still
  confirm no downstream tooling parses pytest's stdout in a way that a new
  trailing summary section could break (e.g. a script grepping for an exact
  final line).
  **Verified during design/analyze (no code change needed, recorded so a future
  implementer does not have to re-derive it):** a repo-wide grep for
  pytest-stdout consumers found `scripts/ci/capture_shard_timings.py` uses a
  report-hook (`pytest_runtest_logreport`), not stdout parsing — unaffected;
  `scripts/verify_shard_3115.sh` passes an explicit `--durations=50` on its own
  command line, which overrides `pytest.ini`'s `addopts` default entirely (CLI
  flag wins over ini `addopts`, verified live against this repo's installed
  pytest) — unaffected; collect-only invocations (`--collect-only`) never
  execute tests, so no durations block ever prints for them — unaffected. This
  finding was originally raised (and verified) against the earlier
  `--durations=1` draft (finding C4); it applies unmodified to this revised
  `--durations=0 --durations-min=1.0` form too — none of the three findings
  above depend on the specific N/min values chosen, only on the flag family
  (`--durations`) and the CLI-override/collect-only mechanics, which are
  unchanged by this revision.
- **Wrong flag form**: using a `-k`-scoped form, or reverting to a bare
  `--durations=N` count limit, would either silently filter every other pytest
  invocation across the repo down to one test name (the `-k` case — a severe,
  silent regression) or reintroduce A1's phase-omission flaw (the bare-`N`
  case). Use exactly `--durations=0 --durations-min=1.0` as specified above.
- **Manual-sum arithmetic errors**: because this mechanism prints multiple
  lines that must be summed by whoever reads the Actions log, a hand-eyeballed
  sum can be wrong — see this WP's Context section above, which cites `spec.md`'s
  own 127.55s-vs-102.97s arithmetic slip (finding B1) as a concrete example of
  exactly this failure mode. Always compute the sum with a real calculation
  step, never by eye.

## Reviewer Guidance

Confirm the diff is a two-flag append (`--durations=0 --durations-min=1.0`) to
the existing `addopts` value (not a `-k`-scoped form, not a bare `--durations=N`
count limit baked into the repo-wide config), confirm no
`.github/workflows/*.yml` file changed, confirm the local dry run shows BOTH
the golden path's `setup` and `call` lines (not just one), and confirm
`test_marker_registry_single_source.py` still passes.

Implementation command: `spec-kitty agent action implement WP07 --agent claude`
