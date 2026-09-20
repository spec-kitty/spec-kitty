---
title: 'CI and Architectural Gate Mechanics'
description: 'What trips each spec-kitty CI gate — testing and marker gates, the architectural battery, docs-freshness registration, and accept-to-merge close-out — with symptom and repro.'
doc_status: active
updated: '2026-09-20'
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
- Before declaring a branch green, run the relevant architectural tests over the
  **rebased tip**. The `tests/architectural/` suite is the whole safety net;
  running the targeted gate file first is faster, and the full suite is the final
  check.

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

- **Trips it:** the corpus shard (`tests-corpus`, driven by
  `ci-router.yml`) runs `tests/contract/test_example_round_trip.py`, which walks
  **every** `kitty-specs/*/contracts/*.md` and collects each fenced ` ```yaml `
  block as a contract-example case. A block in a non-legacy file that is neither
  executable nor marked as an illustration fails.
- **Symptom:** `test_contract_example_round_trip[...MISSING_FRONTMATTER]` fails,
  reddening the corpus shard. A local run of `tests/ci` + `tests/architectural`
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
gates that each pass in isolation but only surface together on CI's
architectural shards (a long-running job whose failure short-circuits the router
gate). Pre-run the targeted gate files before pushing. A useful invocation base
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

### Renaming a symbol whose body is allowlisted

Renaming or editing a symbol tracked in the dead-symbol allowlist stales its
content hash (the allowlist keys entries by a body hash). Refresh it with the
project's dead-symbol hash-refresh tool, which is fail-closed — it only refreshes
entries that are still genuinely dead and never adds new ones. Never weaken the
gate to get past it.

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

## Docs-freshness and registration gates

Adding or moving a `docs/**` page trips several documentation gates that draw
from separate committed catalogs; fixing one leaves the others red.

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
  2. **Page inventory** — regenerate `docs/development/3-2-page-inventory.yaml`
     via `scripts/docs/inventory_lockfile.py`. Its `--write` guard refuses a path
     under `docs/`, so write to a temp file and copy it over.
  3. **Retrieval index** — regenerate
     `docs/development/3-2-docs-retrieval-index.yaml` via
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

### Touching any docs path can surface a pre-existing docs-test flake

- **Trips it:** touching any `docs/**` path flips the docs-test path filter,
  which can run a `tests/docs/` test that never ran on your branch before.
- **Symptom:** a docs test you did not write reds — often a fragile
  single-cold-measurement performance assertion on a contended runner. Do not
  misattribute it to your diff.
- **Fix / repro:** classify it as pre-existing (reproduce on the merge base),
  then fix perf flakes at the root with warm-run discipline (discard the cold
  pass, assert the fastest of several warm runs); never retry-to-green.

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

## Accept-to-merge consolidation gates

The `accept` → `merge` close-out has several gates that block silently until fed
exactly what they expect.

### The issue-matrix verdict gate fires on every WP approval

- **Trips it:** `move-task <WP> --to approved` — on *every* WP, including one with
  no issue references — requires a verdict for **every `#NNN`** referenced
  anywhere in the mission's `spec.md` **and** `research.md` (including
  out-of-scope, deferred, and already-closed references).
- **Symptom:** the approval is blocked, and the error lists the missing rows.
- **Fix:** this is orchestrator-level bookkeeping — seed the whole matrix up
  front. Set verdicts with `spec-kitty agent issue-verdict --mission <m> --issue
  "#NNN" --verdict <v> --actor <a> [--wp WP##] --evidence-ref "..."`. Verdict
  values:
  - `in-mission` — the issue is owned and being fixed by a WP in this mission
    (the honest interim state while WPs are in progress; not fabrication).
  - `deferred-with-followup` — out of scope; the evidence-ref **must** contain a
    `#NNN` or `Follow-up:` handle or the gate rejects it.
  - `verified-already-fixed` — a closed root-cause issue the mission relies on.
  - `fixed` — completed in-mission, set at accept once the WP is done.

  The per-WP reviewer should **refuse to fabricate** verdicts for unfixed issues
  — that is correct behavior, not a blocker; the orchestrator fills them honestly.
  At accept, flip the `in-mission` rows to `fixed` / `verified-already-fixed`. The
  matrix is a dict keyed by `#NNN` under `rows` in `issue-matrix.json` on the
  coordination partition (the `.md` form is legacy — do not create it).

### The other close-out gates

- **Lane branches reject any `kitty-specs/` change** ("kitty-specs/ changes are
  not allowed on lane branches"). Before moving a task to `for_review` or
  `approved`, restore the planning artifacts from the planning branch and commit.
  The review-claim step can re-dirty them, so re-clean between claim and approve.
- **`acceptance-matrix.json` has no CLI** — edit it directly in the coordination
  worktree: set each criterion's `pass_fail` to `"pass"` with `evidence`,
  `verified_by`, and `verified_at`, and set `overall_verdict` to `"pass"`.
  `accept` also fails on a dirty tree, so commit or clean the dossier state
  first.
- **`spec-kitty merge` refuses a dirty coordination worktree** — commit the
  status files and clear ignored `.kittify/` state in the coordination worktree,
  then `--resume`.
- **The graph-manifest check verifies the pack manifest, not just the graph
  files.** Regenerating the reference graph alone leaves the manifest stale; run
  the full `spec-kitty doctrine regenerate-graph`, which regenerates both.
- **The post-merge stale-assertion analyzer** flags test string-literals tied to
  removed code even when the test still passes. Confirm the test is green, then
  refresh the docstring or literal.

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
