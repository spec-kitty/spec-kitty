---
title: 'CI and Architectural Gate Mechanics'
description: 'What trips each spec-kitty CI gate — marker gates, the architectural battery, docs-freshness registration, and accept-to-consolidate close-out — with symptom and repro.'
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/development/reference/known-friction-points.md
- docs/development/reference/red-main-and-release-readiness.md
- docs/development/testing/testing-parallel.md
- docs/development/how-to/pr-landing.md
---

# CI and Architectural Gate Mechanics

Many spec-kitty gates pass a naive local run and only go red ~40 minutes into
CI, because they live in shards a fast local run never selects. This page maps
the durable, repeatable ones: **what trips each gate, the symptom it produces,
and the command that reproduces it locally** so you can catch it before pushing.

It is a mechanics reference, not a status page — for the *current* red list and
fast-drifting toggles see [Known Current Friction
Points](known-friction-points.md); for what a red `main` means see [Red Main and
Release Readiness](red-main-and-release-readiness.md).

## How CI is wired (so a local run can mirror it)

CI runs as a lean modular pipeline: a path router (`ci-router.yml`) decides which
module and data shards are affected, per-module test jobs run
(`module-tests.yml` / `ci-modules.yml`), and results aggregate with a coverage
and diff-cover gate (`ci-aggregate.yml`); a nightly full run (`ci-nightly.yml`)
and a fork-safe Sonar scan (`sonar.yml`) sit alongside. The trap is structural:
**a passing `pytest <file>` locally does not mean a gate will be green**, because
the gate that fails may run in a different shard, under a different marker
selection, or only over paths your diff happened to touch.

Two habits defuse most of this class:

- Reproduce a gate by running its **exact selection**, not just the test file —
  e.g. a marker-scoped shard runs `-m "fast and not windows_ci"`, so a test
  missing the `fast` marker is silently deselected there even though it passes
  when you name it directly.
- Before declaring a branch green, run the architectural gate files your change
  implicates over the **rebased tip**. Do not sweep the whole
  `tests/architectural/` directory in mission work ([`NO_FULL_HEAVY_SUITES_IN_MISSION`](../../../packs/internal/directives/no-full-heavy-suites-in-mission.directive.yaml)); CI runs
  the whole battery for you: the always-on `architectural-fast` job plus the two
  `architectural-heavy` legs on code and CI-config PRs.

Since mission `ci-runtime-stabilisation` ([#5510](https://github.com/spec-kitty/spec-kitty/issues/5510)),
five things about that pipeline are worth knowing before you read a red check:

- **The battery has three parts.** `architectural-fast` is always on (docs-only PRs
  included). Its roster of deterministic ratchet and census gates is held in
  `.github/ci-module-registry.yml` under `special_tiers.architectural.fast_gate`,
  with a per-file budget. `architectural-heavy` is one job key with a two-leg
  matrix (`--battery-part 1/2` and `2/2`). The three parts are file-disjoint and
  together cover the base selection exactly, which
  `tests/architectural/test_battery_partition_proof.py` proves statically.
- **CI-config changes select the heavy battery.** The router path group
  `ci_config` (workflows, composite actions, `scripts/ci/**`, `pytest.ini`,
  `pyproject.toml`, `Makefile`, the registry and the shard timings file) gates the
  heavy battery and no other job.
- **Corpus tests have one advisory owner.** `packs.yml` runs the `-m corpus`
  suite as the advisory job `built-in / -m corpus suite (advisory)`. The corpus
  tests that have no other blocking per-PR home run blocking in two router jobs:
  `tests (corpus-blocking)` (the modules that read the committed corpus) and
  `tests (contract tools)` (the contract tool unit tests). The router jobs `tests (cli)`,
  `tests (status)`, `tests (consolidation)` and `tests (corpus)` no longer exist;
  the `cli`, `status` and `consolidation` module rows in `ci-modules.yml` are now
  their only homes.
- **A nightly backstop runs the whole battery.** `ci-nightly.yml` job
  `architectural-backstop` executes the full base selection with no partition
  plugin, so a green nightly means the battery ran (see the amendment to
  [ADR 2026-09-26-1](../../adr/3.x/2026-09-26-1-ci-coverage-honesty.md)).
- **A `ready_for_review` run can skip on prior evidence.** When the same workflow
  already went green for the identical tested key, the selection step is
  suppressed and the required gates post success. A re-run always executes. See
  [Skip-if-green on ready-for-review](#skip-if-green-on-ready-for-review) below
  and the amendment to
  [ADR 2026-09-23-1](../../adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md).

The rest of this page groups gates by the change that trips them.

## Testing and marker gates

These fire when a test file's markers, or the coverage a test contributes, do
not line up with the shard that is supposed to run it.

### A test with the wrong marker contributes zero CI coverage

- **Trips it:** a new test carries the wrong (or too few) `pytestmark` markers,
  so the shard meant to run it deselects it. Example: a test marked only `unit`
  when its shard selects `-m "fast and ..."` never runs in CI.
- **Symptom:** the diff-coverage gate (`ci-aggregate.yml`) goes red on a source
  file that *has* a passing test — because that test never executed in CI. Named
  directly (`pytest <file> --cov`) it shows full coverage locally, which hides
  the problem.
- **Fix / repro:** give the new test the same speed + domain markers its
  siblings use (typically `fast` plus the module's domain marker). Reproduce the
  shard's real selection locally — run `pytest <dir> -m "fast and not
  windows_ci"` — not just `pytest <file>`.

### A file with two markers can fall between two shards

- **Trips it:** a test file carries two markers whose CI jobs *mutually exclude*
  it (e.g. both `distribution` and `e2e`, where the e2e shard runs `-m "not
  distribution"` and the other shard ignores the e2e directory). The file
  reaches no gate at all.
- **Symptom:** `tests/architectural/test_marker_job_completeness.py` goes red —
  each routed marker gained a carrier that no job selects. This runs in an
  architectural shard, so it only surfaces on CI.
- **Fix / repro:** make sure the file is positively selected by at least one job.
  The minimal fix is a complementary pytest step in an existing job (e.g. add a
  `-m "distribution and e2e and not windows_ci"` pass over the e2e directory);
  the completeness gate auto-discovers it. Run
  `pytest tests/architectural/test_marker_job_completeness.py` before pushing.

### A new test file must declare a marker

- **Trips it:** a new `tests/**/test_*.py` file lands without a module-level
  `pytestmark`.
- **Symptom:** an architectural marker-convention gate reds, insisting every test
  file declare *some* marker. It is distinct from the completeness gate above —
  and distinct from the marker-baseline gate below — so one can be green while
  another is red.
- **Fix / repro:** add `pytestmark = [pytest.mark.unit, pytest.mark.fast]` (or
  the markers the file's siblings use) at module scope. When a fold adds or moves
  a test file, run the marker-related tests in `tests/architectural/`, not just
  one of them.

### Moving a slow / stress / quarantine test can red the marker baseline

- **Trips it:** relocating or renaming a test that carries a budget marker
  (`slow`, `stress`, `quarantine`). Its node-id changes, so the pinned baseline
  set gains a "new" node and loses the old one, and the growth check reads that
  as new slow surface.
- **Symptom:** the marker-baseline architectural gate reds even though it is the
  same test with the same marker.
- **Fix / repro:** do a documented one-for-one swap in the baseline — remove the
  old node-id, add the new one, and add a dated comment noting it is the same
  node relocated (no net-new slow surface). This is legitimate; a blanket
  baseline "update" that hides a genuinely new slow test is not. This gate is
  easy to miss because it is not in the fast shard.

### New `contracts/*.md` YAML blocks need a round-trip skip marker

- **Trips it:** the router job `tests (corpus-blocking)` (job key
  `tests-corpus-blocking` in `ci-router.yml`) runs
  `tests/contract/test_example_round_trip.py`, which walks
  **every** `kitty-specs/*/contracts/*.md` and collects each fenced ` ```yaml `
  block as a contract-example case. A block in a non-legacy file that is neither
  executable nor marked as an illustration fails.
- **Symptom:** `test_contract_example_round_trip[...MISSING_FRONTMATTER]` fails,
  reddening `tests (corpus-blocking)`. The Packs advisory corpus job deselects
  this file, so a red here is blocking, not advisory. A local run of `tests/ci` + `tests/architectural`
  (the obvious blast radius for a CI change) does **not** cover
  `tests/contract/`, so illustrative YAML passes locally and only reds on CI.
- **Fix / repro:** tag each YAML block with one of, as its first line inside the
  fence:
  - `# pydantic_model: <Model>` — executed against that model, or
  - `# round-trip: skip: <reason>` — non-executable illustration; the reason is
    mandatory (a bare marker still fails).

  Run `pytest tests/contract/test_example_round_trip.py` locally before pushing.

### The pre-review gate can run the full suite and hang

- **Trips it:** `spec-kitty agent action implement WP##` (and `review`, and
  `move-task --to for_review`) trigger the auto-scoped pre-review regression gate
  (`src/specify_cli/review/pre_review_gate.py`, baseline capture in
  `review/baseline.py`). When the auto-scope resolves broadly it runs
  effectively the whole suite with no path arguments.
- **Symptom:** the CLI hangs with no output for a very long time, blocked waiting
  on the pytest child; parallel workers each doing this pin every core.
- **Fix / repro:** set `SPEC_KITTY_SKIP_PRE_REVIEW_GATE=1` on the lifecycle
  command (this is the canonical opt-out; it no longer reads the retired
  sync-disable vocabulary). The claim still succeeds — the WP moves to
  `in_progress` and the worktree is created — even if baseline capture times out.
  To make the baseline itself cheap, declare a fast `review.test_command` in
  `.kittify/config.yaml` (a local, uncommitted no-op command is legitimate;
  revert it at mission end). If a killed gate leaves a stale run-lock or orphaned
  pytest children, remove them before retrying. Rely on targeted per-WP tests
  plus CI for breadth, never the full suite in-session.

## The architectural gate battery

Adding new `src/` symbols and new test files trips a battery of architectural
gates that each pass in isolation but only surface together in CI's
architectural jobs: the always-on `architectural-fast` job and the two legs of
`architectural-heavy` (a code-scoped job whose failure reds the router gate).
Pre-run the targeted gate files before pushing. A useful invocation base
for these is `PYTHONPATH=src -o addopts=""` so collection matches CI.

- **Dead-symbol gate** (`tests/architectural/test_no_dead_symbols.py`): a new
  public symbol in a module's `__all__` that no other `src/` file imports fails.
  Fix by trimming `__all__` to genuinely public symbols — test-only helpers stay
  importable but out of `__all__`.
- **Dead-module gate** (`tests/architectural/test_no_dead_modules.py`): a new
  module with zero non-test `src/` importer fails — even a `python -m` entry
  point launched by an argv string, because that is not a static import. Fix by
  *wiring* it: have the launcher reference the module by name
  (`from . import _server_main; MODULE = _server_main.__name__`) rather than a
  string literal, so it is statically reachable and rename-safe.
- **Clock call-ban** (`tests/architectural/test_clock_call_ban.py`):
  `time.time()` / `.now()` / `.utcnow()` / `.today()` anywhere (including tests)
  outside `src/kernel/clock.py` fails. Import from `kernel.clock` instead.
- **Clock import-ban** (`tests/architectural/test_clock_import_ban.py`, distinct
  from the call-ban): a raw `import datetime` / `from datetime import ...`
  anywhere outside `src/kernel/clock.py` fails. Import from `kernel.clock`, or
  add an exemption line under `tests/architectural/_exemptions/`.
- **Charter facade table** (`tests/architectural/test_charter_facades_reexport_doctrine.py`):
  this self-discovers every `src/charter/*.py`, so a new charter facade that
  re-exports a `doctrine.*` symbol in its `__all__` must be registered in the
  facade table. It runs in an architectural shard, invisible to fast-shard local
  runs.
- **Environment-fragile absolute counts:** integration jobs run
  `uv sync --frozen --all-extras`, which installs and imports more optional
  dependencies than a local checkout. An absolute module-count or import-count
  assertion (`len(modules) <= N`) passes locally and false-reds on CI. Assert a
  specific module's presence or absence, never an absolute count.

### Fast roster, shard legs, and the partition proof

The battery base selection is `tests/architectural` with the marker expression
`not performance and not stress and not timing`, minus the four files that other
always-on lanes own (`test_no_legacy_terminology.py`, `test_layer_rules.py`,
`test_pyproject_shape.py`, `test_archive_root_byte_identical.py`). It runs as:

| Part | Job (display name) | Selection | When |
| --- | --- | --- | --- |
| Fast | `architectural fast gates (ratchet/census, always-on)` | `--battery-part fast`: the registry roster | every PR shape |
| Heavy leg 1 | `architectural battery (heavy, code-scoped) 1/2` | `--battery-part 1/2` | code, `ci_config` or `architectural` path changes, not prose-only |
| Heavy leg 2 | `architectural battery (heavy, code-scoped) 2/2` | `--battery-part 2/2` | same as leg 1 |
| Backstop | `Architectural battery backstop (nightly-only, #5510)` | the base, no partition flag | nightly |

- **The roster is registry-held.** Each entry in
  `special_tiers.architectural.fast_gate.roster` carries a path, a
  `budget_seconds` and a reason. A file earns a roster slot only if it is a
  deterministic static gate, so a new slow or CLI-round-trip file belongs in the
  heavy legs. The budgets are checked statically against the committed timings by
  `tests/ci/test_battery_roster_budgets.py`, never against wall-clock time.
- **Adding or moving a battery test file** needs no workflow edit: the plugin
  `scripts/ci/battery_partition_plugin.py` assigns each file to exactly one part
  from the per-file timings in `.github/ci-shard-timings.json`. A file with no
  timing gets the median weight, and a timing-set mismatch prints a `::warning::`
  rather than silently using uniform weights.
- **A partition-proof red** means a file is in two parts or in none. The proof
  (`tests/architectural/test_battery_partition_proof.py`) evaluates the three
  literal `--battery-part` commands, so fix the roster or the timings, not the
  proof.
- **Worker count** is a literal `-n 4` in every CI battery command; see
  [CI worker policy](../testing/testing-parallel.md#ci-worker-policy-and-the-nightly-architectural-backstop).

### Skip-if-green on ready-for-review

When a draft PR is marked ready for review, the head SHA has usually already been
tested. The selection jobs (router `changes`, CI Modules `generate-matrix`, Packs
`changes`) therefore run `scripts/ci/green_match.py decide` first. It suppresses
the path-filter step, and so every path-gated job, only when all of these hold:

- the event is a `pull_request` with the action `ready_for_review`, on the first
  attempt of the run;
- a completed, successful run of the same workflow exists for the same head SHA;
- that run carries a non-expired marker artifact `ci-tested-key-pr<N>-base-<sha>`
  for the identical tested key `(workflow file, PR, head SHA, first parent of the
  merge commit the run tested)`.

The required contexts `router gate` and `CI Modules gate` still post success. On a
skip run the always-on lanes and `prose-scan` still run, and `tests (docs)` still
runs on a prose-only PR.

- **Symptom of a surprise skip:** a `ready_for_review` run finished with every path-gated
  shard skipped, and the step summary names a matched run.
- **Escape hatch:** re-run the workflow. Attempt 2 always executes.
- **Never suppressed:** push, `workflow_dispatch`, `workflow_call`, schedule, any
  other `pull_request` action, a failed, cancelled or in-progress prior run, a
  moved base, and any lookup error (the helper runs normally and warns).
- **CI Aggregate** re-points to the matched CI Modules run after re-verifying it,
  and fails with "re-run CI Modules to execute" if it cannot. Re-run CI Modules,
  not Aggregate.

### Moving or renaming a symbol that is dead-symbol allowlisted

The dead-symbol allowlist lives in `tests/architectural/dead_symbol_allowlist.yaml`
and is keyed by `(module, name)`: `module` is the module whose `__all__` declares
the name. No body hash is stored
([ADR 2026-10-01-1](../../adr/4.x/2026-10-01-1-dead-symbol-allowlist-module-name-identity.md)).

- **Editing the body** of an allowlisted symbol costs nothing: no allowlist edit.
- **Renaming or moving** one makes the gate report the old entry `GONE` (for a
  move, with a "probably moved to `X`" hint) and the new location as an
  offender. Update `module:` or `name:` of that entry in the YAML file.
- **Adding an entry** needs a declared `category_*`, a rationale (its own or
  inherited from the category -- see
  [declaring a new category](../how-to/add-architectural-gate-exemption.md#declaring-a-new-category)),
  an `issue` where the category sets `requires_issue: true`, and a raised
  `test_no_dead_symbols` leaf in `tests/architectural/_baselines.yaml`
  (`allowlist_entries`, or `widened_grandfathered_470` for the widened section).
  Both leaves are shrink-only caps. Try wiring the symbol, dropping it from
  `__all__` or deleting it first.

Never weaken the gate to get past it.

### The `ruff format` exclude ratchet has a twin

`[tool.ruff.format].exclude` in `pyproject.toml` is a large, shrink-only
formatter-debt allowlist (that is why a whole-repo `ruff format --check .` passes
on `main` — excluded files are skipped). Two distinct architectural tests guard
it, and checking only one misses failures:

- `tests/architectural/test_ruff_format_enforcement.py` — asserts
  `ruff format --check .` exits 0 and every exclude entry names a live file.
- `tests/architectural/test_ruff_format_exclude_ratchet.py` — asserts every
  exclude entry **still genuinely reformats**, and that the entry count stays
  under a shrink-only ceiling.

Two changes trip the ratchet, and both are caught only at the integration/merge
gate, not by a per-WP subset run:

1. You run `ruff format` on an excluded file (making it clean) → its entry no
   longer reformats → red.
2. You delete an excluded file's source → its entry names a missing file → red.

Fix both by **removing** the now-dead entries (this only shrinks the list, so no
ceiling bump is needed). Remove entries only for files your branch actually
formats or deletes.

### A scanner that swallows a parse failure reds the parse fail-closed gate

`tests/architectural/test_scanner_parse_fail_closed.py` scans every module under
`tests/` for a construct that can swallow a failure to parse source: an
`except` catching `SyntaxError` (or a subclass) that does not always re-raise,
a bare, `Exception`, `BaseException`, `AssertionError` or aliased handler around
a parse call, `contextlib.suppress(...)` around one, or `finally: return`. A
scanner that skips a file it cannot parse drops it from its census, so the gate
it feeds passes over code it never read.

It trips on harmless-looking code too — for example
`try: parse_file(p) except AssertionError: continue`. Repro:
`pytest tests/architectural/test_scanner_parse_fail_closed.py`. Fix it by
reading and parsing through `tests/architectural/_ast_scan.py`
(`read_and_parse` / `parse_file` / `parse_source` / `read_source`, which fail
closed naming the file). Only when the input is *deliberately* allowed to be
unparseable, add a rationale row to its `_ALLOWED_SWALLOWS` ledger; the ledger
is checked for exact equality, so remove the row when the handler goes.

### Router path filters are the tail of a guarded SSOT chain

The `ci-router.yml` path-filter globs are not a free-standing authority — they
are the verbatim tail of a three-link single-source-of-truth chain:
`tests/release/ci_retirement_scrub.json` (the SSOT) → `.github/ci-module-registry.yml`
→ `ci-router.yml` filters. Each link is pinned by an architectural transcription
guard (`tests/architectural/test_module_shard_registry.py`,
`tests/architectural/test_ci_router_transcription_guards.py`).

- **Trips it:** adding a glob to a router filter group alone.
- **Symptom:** the router-transcription guard reds; cascading the glob to satisfy
  it then reds the registry-verbatim guard unless the registry roots change too —
  and the registry roots drive the per-module test matrix, so this is a real
  CI-matrix change, not a config tweak.
- **Fix:** to change what a module *owns* for routing, edit the scrub SSOT and
  cascade verbatim through all three links. To route test directories to modules
  *without* touching the chain, derive the mapping from the registry inventory in
  the gate-selection logic (`scripts/ci/gate_selection.py`) rather than
  hand-authoring a second map.

## Stored test-universe collection

Several architectural gates need the full list of collected tests with their
markers (the "test universe"). One real `pytest --collect-only` of the tree takes
tens of seconds, and before this change the first test that needed the list
collected it inside its own setup while four xdist workers competed for the same
CPUs. The list is now collected once per job, in a step before pytest, and stored on
disk; the tests read the stored copy.

**What it does and does not do.** A first run of a checkout still collects once
in each job that consumes the list, so twice per pull-request update (architectural
battery leg 1/2 and the `ci` module shard; leg 2/2 holds no collecting test and skips
the step). The change moves that
collection out of test setup and out of worker contention. A re-run of the same
checkout restores the stored list from the CI cache instead of collecting. On one
developer machine a collection took 62.5 s and reading the stored copy 0.33 s. On CI
the pre-test step took 89 to 233 s on a first run and 0.3 to 0.6 s when restored from
the Actions cache; the three runs are in
`kitty-specs/shared-collection-and-shard-recapture-01M42V58/evidence/ci-measurements.md`.

### Where it lives and what it is keyed on

- The code is `tests/architectural/_universe_store.py`. `collect_universe()` in
  `tests/architectural/_gate_coverage.py` calls it; its signature and return value are
  unchanged.
- The store is `.pytest_cache/universe-store/`, which git ignores. It holds one
  record file, `<key>.json`, plus a lock file. Writing a record deletes every other
  record file.
- The key is a digest of the committed tree (not the commit), the interpreter,
  the platform, every installed distribution with its version, and the environment
  variables named `SPEC_KITTY_*` plus `PYTEST_ADDOPTS`. The variables the test
  session sets for itself are listed in `ENV_EXCLUDED_NAMES` and left out, so a
  pre-test step and a test compute the same key. The key also overlays the
  operator env file (`.kitty.env`) through the product's own loader. A machine whose
  home-level `.kitty.env` sets `SPEC_KITTY_*` variables may therefore see local reuse
  not happen, because pytest isolates `HOME`; CI is unaffected.
- A record is stored only when the checkout is still the one the key was computed
  for after the collection: if a commit, a branch switch or an edit happened
  meanwhile, the caller still gets the universe it collected, the report line says
  `not stored: the checkout changed during the collection`, and the pre-test step
  fails on that line.
- A record is read only when its schema, key, record count and origin (commit and
  tree) all match and it holds at least 1,000 records (a corruption guard, not a
  ratchet). Anything else is treated as absent and replaced after a fresh
  collection.
- For one key, one collection runs at a time on a machine. Other callers wait on
  the lock and then read the stored copy.

### When the store is bypassed

The store is not read or written, and the caller collects for itself, when:

| Reason in the report | Condition |
| --- | --- |
| `dirty-checkout` | `git status --porcelain` is not empty. Untracked files count, because an untracked test file changes what is collected. |
| `root-override` | the caller passed a `repo_root` (a patched root). |
| `unsupported-platform` | the platform is not Linux or macOS. The same reason, with a `detail`, is reported when the store directory or its lock cannot be used. |
| `git-unavailable` | git cannot describe the checkout. |
| `env-file-unreadable` | an operator `.kitty.env` exists but cannot be read, so the environment variables of the key are unknown. |

### The report line

When `SK_GATE_REUSE_REPORT` names a file, each call of `collect_universe()` appends
one JSON line to it: `outcome` (`reused`, `collected` or `bypassed`), `reason`
(`no-record`, `invalid-record`, `origin-mismatch` or a bypass reason from the table),
`key`, `caller` (the pre-step is `prestep`, a test is its file path), `seconds`, and
when present `detail` and `dirty_paths`. A `detail` starting with `not stored` on a
`collected` line means the fresh collection could not be written back.

### The pre-test step and the post-test check

`python -m scripts.ci.collect_universe_prestep <command>` runs from the repository
root checkout:

| Command | What it does | Exit status |
| --- | --- | --- |
| `key [--with-commit]` | Prints the collection key. With `--with-commit` it prints `<key>-<commit>`, which is the CI cache key. | 0; 2 when the checkout is dirty or git cannot describe it |
| `collect` | Calls `collect_universe()` once and prints the report line. | 0 only when the line is `reused`, `collected` with the record stored, or an unsupported-platform bypass without a `detail`; 1 for anything else, including a record that could not be stored |
| `check` | Reads the report file and writes a table to the job summary. | 1 when the pre-test line is not acceptable, when a later request in the job collected or was bypassed (other than `root-override`) after the pre-test step stored or reused a record, or when a report line is malformed; 0 otherwise |
| `consumers --battery-part <part>` | Prints `true` when the battery partition holds a test file that calls `collect_universe()` (found by scanning `tests/architectural/test_*.py`), `false` otherwise. | 0 with an answer; 1 and no answer for an unknown part |
| `compare` | Collects once with the store bypassed and diffs the result against the stored record. | 1 on any difference or when no usable record exists |

`collect` and `check` fail when the pre-test step could not store a collection.
Only an unsupported platform is a legitimate fallback: the job then collects for
itself, `check` prints a fallback note and exits 0.

### Where it runs

- **`ci-router.yml`, job `architectural-heavy`** (a leg runs these steps only when its
  partition holds a collecting test; the battery partition moves with the timings, so
  each leg first runs `consumers --battery-part <leg>` in a step with id `select`, and
  a failed answer fails the job). Steps in order: compute the key, restore the store,
  `collect`, save the store, run the battery (the pytest command line is unchanged),
  `check` with `if: always()`.
- **`module-tests.yml`, job `test`.** The same steps, but only in per-PR mode and
  only on the shard whose selected test list contains
  `tests/ci/test_corpus_blocking_home.py::test_every_corpus_test_has_a_blocking_per_pr_home`,
  the test that takes the `live_universe` fixture. The `ci` module runs as one shard
  (`shard_count: 1` in `.github/ci-module-registry.yml`), so that shard holds the test.
  `tests/ci/test_ci_workflow_prestep_shape.py` pins that the test still exists.
  Full-mode warm-up may rewrite `uv.lock` and leave the checkout dirty, so it
  skips the step.
- **The cache key is `universe-<key>-<commit>`.** It includes the commit because a
  stored record is valid for one commit only and a CI cache key never changes once
  saved; a key without the commit could keep a record that a later commit rejects,
  and the save step is skipped after a restore hit. Only an exact key restores
  (there are no `restore-keys`), and the save runs before pytest, so a leg that goes
  red on a test can still be re-run warm.
- **The shard list lives in the runner's temp directory**, not in the checkout. An
  untracked file there would make the checkout dirty for the rest of the job.
- **None of the collect, check or compare steps sets `continue-on-error`.** The
  shape test pins that, because it would turn the check into a summary.

### Nightly equivalence job

`ci-nightly.yml` job `universe-equivalence` runs `collect` and then `compare` in
one job. It shows that collection is deterministic and that a stored record
round-trips to the same list as a fresh collection. It does not show that a record
restored from the CI cache on another runner equals a fresh one. It is part of
`nightly-summary`.

### Run it locally

```bash
# The key of a clean checkout, and the CI cache key (commit appended)
python -m scripts.ci.collect_universe_prestep key
python -m scripts.ci.collect_universe_prestep key --with-commit

# Collect once and store it, then run a gate against the stored copy
export SK_GATE_REUSE_REPORT=/tmp/universe-reuse.jsonl
python -m scripts.ci.collect_universe_prestep collect
PYTHONPATH=src python -m pytest tests/architectural/test_fast_tier_marker_completeness.py -q
python -m scripts.ci.collect_universe_prestep check

# Prove the stored copy equals a fresh collection
python -m scripts.ci.collect_universe_prestep compare
```

A dirty checkout (including an untracked file) is bypassed on purpose; commit or
stash first to see a `reused` line. To force a fresh collection, run
`rm -rf .pytest_cache/universe-store`; there is no bypass environment variable, and
`pytest --cache-clear` does not remove that directory.

## Scheduled shard-timings recapture

`.github/ci-shard-timings.json` records, for each registry module, how many tests
its shard collects and how long each took. The count drifts whenever tests are
added or removed. The workflow `ci-shard-recapture.yml` (schedule 04:41 UTC daily,
plus `workflow_dispatch`, and only on the primary branch (`main`)) refreshes the drifted entries for
**every** registry module and proposes the change as a pull request. The code is
`scripts/ci/recapture_shard_timings.py`.

The job `recapture-shard-timings` runs the script in three steps:

| Phase | Holds the token | What it does |
| --- | --- | --- |
| `detect` | yes | Asks `gh` whether a recapture pull request is open on the proposal branch. |
| `capture` | no | Finds drifted modules, captures them, and writes the result (`drifted`, `captured`, `failed`, `deferred`) as a step output and a job-summary table. |
| `publish` | yes | Pushes the refreshed file and opens or refreshes the pull request. |

The `capture` phase runs test code for a long time, so it refuses to run when
`CHARTER_SHARD_RECAPTURE_TOKEN` is in its environment and starts every subprocess
without any token variable.

**Finding drift.** A count-only pass (`pytest --collect-only`, over the same
directories and marker expression the producer uses) counts each module whose
committed provenance is valid. A module is drifted when its count differs from the
committed `module_test_count`, or its provenance record is missing or not valid.

**Capturing.** Each drifted module is captured by
`python -m scripts.ci.capture_shard_timings --module <m> --write` in its own
subprocess, longest-untouched first.

**Time budget.** The workflow passes `--budget-seconds 4200`, counted from the start
of the `capture` phase, so the count-only passes are inside it. No count pass and no
capture starts once the budget is spent; the modules left over are reported as
`deferred`, never as clean, and the next run recomputes drift (no state is kept).
A count pass is capped at 300 s per module, a capture at 2,100 s, and the job at
120 minutes.

**The valid-capture rule.** A capture is kept when its provenance record carries
the run id the script passed in, the pytest exit status was 0 or 1, and at least one
test was measured. Anything else (a crash, a collection error, a timeout, an
unreadable file) puts the committed file back byte for byte and reports the module
as `failed`; the other modules still run. A count pass that fails or times out also
reports its module as `failed`. The script exits 1 when any module failed.

**Proposal.** The branch is `ci/recapture-shard-timings`, and GitHub allows one open
pull request per head branch.

- With no open pull request, `publish` force-pushes the branch and opens one.
- With an open pull request, `capture` starts from the proposal's timings for the
  modules it already refreshed, so each run continues the work, and `publish` adds
  a follow-up commit with a plain push. It never forces.
- A push the token is not allowed to make (HTTP 403) fails the step with a message
  naming the secret. That is a token problem code cannot fix; see #5624.

**The red window.** Per pull request, a drifted count is a non-blocking
`ShardTimingsDriftWarning`. The job `strict-shard-timings-check` in the same
workflow runs `tests/architectural/test_module_length_agreement.py` with
`SPEC_KITTY_STRICT_SHARD_TIMINGS=1` and has no `needs` edge to the recapture job. So
from the first scheduled run that sees a drift until the proposal merges, the strict
check is red on each scheduled run. That window is accepted: the red is the alarm
and the proposal is the fix.

To run it by hand, `capture` without `--write` only reports drift:

```bash
python -m scripts.ci.recapture_shard_timings capture --module charter
```

## Docs-freshness and registration gates

Adding or moving a `docs/**` page trips several documentation gates that draw
from separate committed catalogs; fixing one leaves the others red.

The prose of those pages is linted by a separate, always-on job: see
[`docs-lint`](#docs-lint).

### A new docs page needs triple registration plus a description band

- **Trips it:** a new `docs/**/*.md` page that is not registered everywhere.
- **Symptom:** the docs build and docs-freshness checks red with a mix of
  `DOCS-INDEX-DRIFT`, `INVENTORY-INCOMPLETE` / `INVENTORY-LOCKFILE-DRIFT` /
  `LEAK-MISSING-INVENTORY`, and a description-length failure. The "committed
  index" in a drift error is the machine-generated *retrieval* index, not the
  curated `index.md`, which is why updating only `index.md` is not enough.
- **Fix / repro:** register the page in three places and satisfy the frontmatter
  band:
  1. **Curated section index** — hand-add the page to its section's `index.md`
     (satisfies the index-completeness rule).
  2. **Page inventory** — regenerate `docs/development/page-inventory.yaml`
     in place with `scripts/docs/inventory_lockfile.py --write <that path>` (run
     with `PYTHONPATH=.`). The script does not refuse a
     path under `docs/` (its `--help` text and module docstring still say it
     never writes there; the code does not enforce that), so no temp-file copy
     is needed.
  3. **Retrieval index** — regenerate
     `docs/development/docs-retrieval-index.yaml` via
     `scripts/docs/docs_index.py --write` (this one writes in place).
  4. **Frontmatter `description`** — a hard **50–180 character** band, enforced by
     `scripts/docs/description_length_check.py` and the docs SEO tests. Both
     inventories derive from frontmatter and headings, so regenerate them *after*
     the frontmatter and headings are final.

  Verify with `PYTHONPATH=. python scripts/docs/check_docs_freshness.py --ci`
  (expect `errors=0`; external-URL link-health *warnings* are fine).

  **ADRs** are tracked in all three surfaces too, and have a dedicated helper,
  `scripts/docs/freshen_adr_inventory.py`, that adds the ADR index-table row and
  regenerates the page inventory in one step; then run the retrieval-index
  regeneration. An ADR's frontmatter needs `date:`, `updated:`, and a 50–180
  character `description`.

### `docs-lint`

- **Trips it:** a typo or British spelling in docs prose, or a changelog
  `[Unreleased]` entry that breaks the house style. Any PR can trip it, because
  the job has no path filter.
- **Job:** `docs-lint` in `.github/workflows/ci-router.yml` (display name "docs
  lint (spelling + changelog style, always-on)"). It is listed in the
  `router-gate` job's `needs`, so a red `docs-lint` blocks the merge. It is
  **blocking**: neither command's exit code is masked.
- **Why always-on:** its inputs span `docs/**`, `README.md`,
  `packs/built-in/**/*.md`, `pyproject.toml` (the `[tool.codespell]` table and
  the pinned `codespell`) and `uv.lock`. No single router path group covers all
  of them, so a path filter would let some edits skip the check.
- **What it runs:** `uv sync --frozen`, then
  `python -m scripts.docs.check_spelling` (typo, US-spelling and Unreleased
  passes) and `python -m scripts.docs.check_changelog_style`. It runs **no
  pytest**. The planted-violation and live-tree tests for the two scripts
  (`tests/docs/test_check_spelling.py`, `tests/docs/test_changelog_style.py`,
  `tests/docs/test_docs_spelling_live.py`) run in the `tests-docs` job.
- **Exit codes:** `0` clean; `1` findings; `2` the check could not run or could
  not prove it looked at anything: a usage error, `codespell` missing, no
  `[tool.codespell]` table in `pyproject.toml`, an unreadable changelog (both
  scripts), a `typo` or `us` pass that scanned 0 files, or an `unreleased`
  scratch file that a `[tool.codespell]` `skip` glob would drop. A changelog with
  no `[Unreleased]` section is `0` (nothing to check). The changelog guard also
  exits `0` on warnings alone.
- **Scope:** Markdown only. `docs/archive/`, `docs/reports/`, `docs/plans/` and
  the generated CLI reference (`docs/api/cli-commands.md`) are skipped through
  the `[tool.codespell]` `skip` list, so a finding never comes from them. A
  relative `--changelog` resolves against the repository root in both scripts
  (against `--repo-root` for the spelling check), not the current directory.
- **Symptom:** the job log lists one finding per line as
  `path:line: [rule] ... — fix`, ending in a summary line. It is not one of the
  docs-freshness or registration errors above. The guard's rules include
  `bullet-marker` (a column-0 `* ` or `+ ` bullet) and banned-token checks on
  prose between a `###`/`####` heading and its first bullet; the how-to lists
  every rule and the false-positive shapes (`WP-D-1`, `SC-2086`,
  `DEFAULT-branch`) to put in backticks.
- **Fix / repro:** `make docs-lint` from the repository root reproduces the job
  (it runs the same two commands). The how-to has the steps: [run the checks,
  allow a word, exempt a quoted literal, and read a
  failure](../how-to/review-gates.md#changelog-update-and-style). Never run bare
  `codespell`, which scans the whole repository.
- **Owning files:** `scripts/docs/check_spelling.py`,
  `scripts/docs/check_changelog_style.py`, and the `[tool.codespell]` table
  (`skip`, `ignore-words-list`) plus the exact `codespell==2.4.3` pin in
  `pyproject.toml`. The pin is exact on purpose: a new `codespell` release
  changes its dictionary, so bump it deliberately, together with the docs it
  newly flags.

### Touching any docs path can surface a pre-existing docs-test flake

- **Trips it:** touching any `docs/**` path flips the docs-test path filter,
  which can run a `tests/docs/` test that never ran on your branch before.
- **Symptom:** a docs test you did not write reds — often a fragile
  single-cold-measurement performance assertion on a contended runner. Do not
  misattribute it to your diff.
- **Fix / repro:** classify it as pre-existing (reproduce on the merge base),
  then fix perf flakes at the root with warm-run discipline (discard the cold
  pass, assert the fastest of several warm runs); never retry-to-green.

### Where the docs site deploys from

`docs.spec-kitty.ai` is deployed by `.github/workflows/docs-pages.yml` from
this repository's `main`. The workflow runs on pushes to `main` that touch
`docs/**` (and a few docs-tooling paths) or on manual dispatch. It first probes
whether GitHub Pages is configured and skips cleanly if not; the deploy job
itself runs only for `spec-kitty/spec-kitty` on `refs/heads/main`. A
`workflow_dispatch` on another branch builds but does not deploy.

### The GitHub Pages docsite build needs `PYTHONPATH`

- **Trips it:** the docsite deploy (`docs-pages.yml`) runs Python post-processing
  steps that import `from kernel.clock import ...`. `kernel` is a src-layout
  package, so a step that runs raw `python3` with no `PYTHONPATH` and no installed
  package raises `ModuleNotFoundError: No module named 'kernel'`.
- **Symptom:** the DocFX render succeeds but the Python post-step fails, the
  deploy job is skipped, and merged `docs/` changes never go live. **Footgun:**
  `docs-pages.yml` has no `pull_request` trigger, so a PR that changes it is not
  exercised by PR CI.
- **Fix / repro:** ensure the build job exports `PYTHONPATH: .:src` at job scope
  (job, not step — several post-process modules import each other and the
  `scripts.docs.*` package). Verify a change to this workflow via
  `workflow_dispatch` on the branch, where the build runs and the deploy stays
  skipped off `main`.

## Accept-to-consolidate gates

The `accept` → `consolidate` close-out has several gates that block silently until fed
exactly what they expect.

### The issue-matrix verdict gate blocks WP approval

- **Trips it:** `move-task <WP> --to approved` when a gating `#NNN` reference in
  the mission's artifacts has no verdict row in `issue-matrix.json`. Not every
  reference gates: context-only and PR/commit references are recorded but do
  not block.
- **Symptom:** the approval is blocked, and the error lists the missing rows.
- **Fix:** seed the matrix up front with `spec-kitty agent issue-verdict`. The
  verdict values, which references gate, and the evidence-token rule for
  `deferred-with-followup` are documented once, in the
  [Issue-Matrix Verdict Reference](issue-matrix-verdicts.md). The per-WP
  reviewer should **refuse to fabricate** verdicts for unfixed issues; the
  orchestrator fills them honestly and flips `in-mission` rows to a terminal
  verdict at accept.

### The other close-out gates

- **Lane branches reject any `kitty-specs/` change** ("kitty-specs/ changes are
  not allowed on lane branches"). Before moving a task to `for_review` or
  `approved`, restore the planning artifacts from the planning branch and commit.
  The review-claim step can re-dirty them, so re-clean between claim and approve.
- **Record `acceptance-matrix.json` verdicts with `spec-kitty agent
  acceptance-verdict`; do not hand-edit the file.** `spec-kitty agent
  acceptance-verdict --mission <m> --criterion FR-001 --result pass --evidence
  <ref>` writes the criterion through the matrix seam, commits it, and
  recomputes `overall_verdict`. Its negative-invariant mode (`--negative-invariant
  <id> --description ... --verification-method grep_absence|route_check|custom_command
  --verification-command ...`) registers an invariant through the same seam and
  runs it at once (`--no-execute` registers only). `accept` also fails on a
  dirty tree, so commit or clean the dossier state first.
- **`spec-kitty consolidate` refuses a dirty coordination worktree** — commit the
  status files and clear ignored `.kittify/` state in the coordination worktree,
  then `--resume`.
- **The graph-manifest check verifies the pack manifest, not just the graph
  files.** Regenerating the reference graph alone leaves the manifest stale; run
  the full `spec-kitty doctrine regenerate-graph`, which regenerates both.
- **The post-merge stale-assertion analyzer** flags test string-literals tied to
  removed code even when the test still passes. Confirm the test is green, then
  refresh the docstring or literal.

## Contracts gates

The top-level `contracts/` tree (the machine-readable contracts, today the
`mission-status` module) is checked by two groups of gates that run in different
places. The conventions themselves are in [`contracts/README.md`](../../../contracts/README.md).

### What runs where

- **The Contracts workflow** (`contracts.yml`) has nine jobs: `verify-pins`,
  `python-checks`, `validate-bundle`, `resolver-parity`, `lint`, `breaking-change`,
  `release-dry-run`, `negative-tests` and the terminal `contracts-gate`, which fails
  unless the other eight succeeded. It is path-filtered: the ten paths under
  `on.pull_request.paths` and `on.push.paths` in the file (`contracts/**`,
  `tests/contract/**`, the CODEOWNERS file, the two contract workflow files, `uv.lock`,
  `pyproject.toml`, `pytest.ini`, `tests/conftest.py` and
  `src/specify_cli/status/lifecycle_events.py`), so a change outside them never starts
  it. No pytest runs in it; every check is a script under `contracts/tools/`.
  Pushes to `main` get one concurrency group per commit, so a burst of merges does not
  cancel the Contracts run that the release workflow looks up.
- **The contract tool tests** (the `tests/contract/test_*` modules for each tool, for
  example `test_lint_ruleset.py` and `test_run_negative_cases.py`) run in the router job
  `tests (contract tools)` (`tests-contract-tools` in `ci-router.yml`), a required check
  through `router-gate`: `pytest -m "corpus and not windows_ci" tests/contract` minus
  three `--ignore` modules, so a new corpus-marked tool test is picked up without a
  workflow edit. The job runs when the `corpus` filter group matches (`contracts/**`) or
  the `contract_tools` group matches (`tests/contract/**`, the two contract workflow
  files, the lock and pytest configuration, `tests/conftest.py`,
  `status/lifecycle_events.py` and the `src/` modules the mission-status reference reader
  imports, spelled `**/<module path>` so the group stays non-src). They read no corpus; keeping them out of
  `tests (corpus-blocking)` keeps that job inside its timeout. Unmarked
  `tests/contract` modules run in the module matrix.
- **The reality check and its payload helper** (`tests/contract/test_mission_status_reality.py`
  and `tests/contract/test_mission_status_payloads.py`) read the committed corpus and run
  in the router job `tests (corpus-blocking)` (`tests-corpus-blocking`), together with the
  example round trip, `tests/integration/test_mission_review_contract_gate.py`,
  `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` and one performance
  class. The `contracts/**` glob is in the router's `corpus` group, so a contracts-only
  change selects both router jobs and no module shard. The modules of both router jobs
  are deselected from the Packs advisory corpus run, so each runs once.
  `tests/ci/test_contracts_workflows.py` fails when a `tests/contract` module that
  carries the corpus marker is run by neither router job, or by both.
- **Tiers.** Tier 1 is the Python tooling over the split tree and the written bundle.
  It needs only the locked Python environment: layout, citation, provisional,
  example, event-mapping, enum-pin, leak, structure, CODEOWNERS and no-pytest checks,
  plus the resolver and `resolver-parity`. Tier 2 is the pinned JVM toolchain
  (the openapi-generator Gradle plugin 7.25.0 under Gradle 8.14.5 with strict
  dependency verification), which validates the split root and the bundle and
  generates a TypeScript client as a consumer check. Tier 3 is two prebuilt
  binaries, `vacuum` 0.30.6 for lint and `oasdiff` 1.32.1 for the breaking-change
  comparison. Tiers 2 and 3 run in CI only, and every download is checked against a
  sha256 pinned in `contracts/tools/pins.json`.
- **Lint plants name their own rule.** The `lint` job's planted-proof step reads the
  rule a plant must fail with from the `# rule: <id>` header on the plant's first
  line, so a variant plant (`<rule>-<variant>.yaml`) is proved against its own rule.
  A plant without the header fails the step, and `tests/ci/test_contracts_workflows.py`
  runs the workflow's own derivation over every plant.
- **Release.** `contracts-release.yml` runs on a pushed tag
  `contract-<module>-v<semver>` (for example `contract-mission-status-v1.0.0`) and
  publishes `openapi.yaml` and `openapi.yaml.sha256`. Only a tag push publishes. It has
  two jobs. The `build` job holds a read-only token: it runs every check and builds the
  assets. The `publish` job (`needs: build`) is the only one with a write token; it
  confirms the tag still resolves to the commit that was built, then runs the argument
  list that `release_check.py --args-file` wrote (module, version, `--latest=false`,
  `--prerelease` only for a prerelease semver) and derives nothing itself.
  The `release-dry-run` job of the Contracts workflow runs the same checks on a pull
  request and cannot publish. Until a release tag exists, `breaking-change` has no
  baseline and prints `NO_BASELINE_INITIAL_VERSION`. An unreleased version is
  `1.0.0-SNAPSHOT`: `release_check.py` refuses a `-SNAPSHOT` tag with
  `SNAPSHOT_RELEASE_REFUSED`, and the dry run of a snapshot module prints
  `SNAPSHOT_DRY_RUN` instead of a release command.
- **Closed response schemas.** A response-shape change is a new schema version, so
  `breaking-change` treats an added response property as breaking (a major move), even
  though `oasdiff` calls it compatible. Also breaking: a new `default` or range
  (`4XX`/`5XX`) response (`response-key-added`, found by `breaking_check.py` itself, not
  by `oasdiff`), a write-only property that becomes readable, and added
  `patternProperties`. A request-side optional addition stays additive. The baseline is
  the latest release tag reachable from the commit under test, ordered by semver 2.0
  precedence.
- **`verify-pins` hashes real artefacts.** `verify_pins.py` exits 2 with
  `CHECKSUMS_UNVERIFIED` when it hashed nothing, so the job runs it with `--fetch` (a
  job that already downloaded the tools would pass `--artifacts DIR`); a bare call or
  `--pins-only` fails `tests/ci/test_contracts_workflows.py`. It also refuses a pin
  that has no `url`.

### A reader or test-only change selects no corpus job

- **Trips it:** a pull request that edits a status reader the reality check imports
  (anything under `src/specify_cli/status/**`), the reality check's own test files or
  fixture, or a Mission's `meta.json` or `status.events.jsonl`. The router's `corpus`
  group matches `contracts/**` but none of those, so `tests (corpus-blocking)`, the job
  that runs the reality check, is not selected. An edit under `tests/contract/**`
  selects `tests (contract tools)` through the `contract_tools` group, which does not
  run the reality check. The Packs run on a push to `main` does not help: `packs.yml`
  passes `--deselect` for every `tests/contract` module that runs in a router job, so
  the `built-in-corpus-suite` never runs them.
- **Symptom:** a green pull request. The drift is first seen by the nightly run
  (`ci-nightly.yml`, job `interpreter-matrix-shard-4`, which runs `tests/contract`,
  scheduled daily at 03:17 UTC), up to a day later. This is an accepted risk, tracked
  in issue #5623: status-reader drift is caught by the nightly run, not on the
  pull request. It was seen on a real pull request, which needed a manual router run.
- **Fix / repro:** run the check before pushing:
  `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py`,
  and dispatch the router in full mode on the branch:
  `gh workflow run ci-router.yml -f mode=full --ref <branch>`.

### What only a merge can confirm

- The fleet-verdict job is triggered by `workflow_run`, and GitHub runs the copy of
  such a workflow that is on the default branch. A change to how it treats the
  Contracts workflow cannot be tested from a pull request; confirm it on the first
  run after the merge.
- The Packs `built-in-corpus-suite` does **not** run the reality check or the tool
  tests on a push to `main`: it deselects them, because the router job
  `tests (corpus-blocking)` owns the reality check and the router job
  `tests (contract tools)` owns the tool tests. The runs after the merge that execute
  them are the router on `main` (each job runs only for a change that selects it) and
  the nightly shard 4. The Contracts workflow on `main` runs no pytest.
- A release tag is a maintainer act and is never pushed from a pull request.

## See also

- [Known Current Friction Points](known-friction-points.md) — the fast-drifting,
  time-stamped list of what is red *today*.
- [Red Main and Release Readiness](red-main-and-release-readiness.md) — what a red
  `main` means and why CI is the release authority.
- [Parallel testing](../testing/testing-parallel.md) — why the make targets are
  shaped the way they are.
- [Landing contributor PRs](../how-to/pr-landing.md) — the maintainer landing
  runbook and red-classification step.
</content>
</invoke>
