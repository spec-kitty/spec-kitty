---
title: 'Review Gates: Pre-PR Hygiene, Review-Cycle Mechanics, and the Consolidation Gate'
description: Review-cycle-artifact and consolidation-gate mechanics, the --skip-review-artifact-check override, and issue-matrix discovery, so review focuses on substance.
doc_status: active
updated: '2026-09-08'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
related:
- docs/development/how-to/local-overrides.md
- docs/development/how-to/pr-landing.md
- docs/development/contributing.md
---
# Review Gates: Pre-PR Hygiene, Review-Cycle Mechanics, and the Consolidation Gate

This page documents (1) the small set of hygiene steps a contributor should
run locally before requesting review or opening a PR, so the actual review
focuses on the substance of the change and not on confusing failures
unrelated to it; and (2) the mechanics of the review-cycle artifact / consolidation
gate and the issue-matrix discovery surface that a WP actually has to
satisfy to reach `approved`/`done`. The verdict vocabulary, JSON schema, and
`in-mission` semantics for the issue matrix are **already documented** in
[`ERROR_CODES.md`](../../../src/specify_cli/cli/commands/review/ERROR_CODES.md)
and
[`spec-kitty-mission-review/SKILL.md`](../../../src/charter/offering/skills/spec-kitty-mission-review/SKILL.md) —
this page cites them rather than restating them.

## Environment hygiene before review/PR

Run the documented sync command from the repository root **before**
running the test gates:

```bash
uv sync --frozen
```

### Why

The CLI consumes `spec-kitty-events` and `spec-kitty-tracker` from PyPI.
Compatibility ranges live in `pyproject.toml`; **exact pins** live in
`uv.lock`. If your installed copy of either shared package drifts away
from `uv.lock` (for example, after an ad-hoc `pip install` against a
sibling checkout, or after switching branches without re-syncing), the
review-gate test suite can fail in ways that look like real defects but
are actually pure environment drift.

### What `uv sync --frozen` does

It installs the **exact resolved versions from `uv.lock`** into your
active virtualenv without re-resolving the dependency graph. This is
the cheapest possible "snap me back to the lockfile" operation:

- It does not modify `pyproject.toml`.
- It does not modify `uv.lock`.
- It does not contact the resolver -- only the package index for the
  pinned wheels.

### When to run it

Run `uv sync --frozen` any time:

- You pull `main` (or any branch with new lock changes).
- You switch branches.
- You change `pyproject.toml` or `uv.lock`.
- You temporarily installed an editable / sibling-checkout copy of
  `spec-kitty-events` or `spec-kitty-tracker` for cross-package work
  (see [`local-overrides.md`](local-overrides.md) for the dev workflow).
- A review gate or local command reports dependency drift.

`uv sync --frozen` is the **only** documented sync command for this purpose. Do not
substitute `uv pip sync`, `uv pip install`, or any other variant -- they
either re-resolve the graph or skip the lockfile entirely, both of which
defeat the point.

## Typer/click version skew (`spec-kitty review` preflight)

`spec-kitty review` also checks that the active interpreter's `typer` and
`click` versions match the exact versions pinned in `uv.lock`. CI always
installs via `uv sync --frozen --all-extras`; a local `.venv` built without
`--frozen` can drift onto a newer release -- including a `typer>=0.26`
release that vendors `click` internally and stops re-exporting it (see the
TID251 Gap-5 ban in `pyproject.toml`) -- so local CLI-shard test runs can
silently diverge from CI without this check.

**Warn-loud by default**: a divergence prints a `MISSION_REVIEW_ENV_SKEW`
warning (see
[`ERROR_CODES.md`](../../../src/specify_cli/cli/commands/review/ERROR_CODES.md#env_skew))
and `spec-kitty review` proceeds.

**Fail-closed is opt-in**: set `SPEC_KITTY_ENV_SKEW_FAIL_CLOSED=1` to make
the preflight exit non-zero on divergence instead of warning. This is
intentionally opt-in -- a legitimately forward-compat dev loop (testing
against a newer `typer`/`click` ahead of the repo's pin bump) must not be
bricked by default.

Resolve a skew warning the same way as any other lock drift:

```bash
uv sync --frozen --all-extras
```

## Pre-review regression gate (`move-task --to for_review`)

When a work package moves to `for_review`, Spec Kitty runs a **doctrine-resolved**
transition gate. Rather than a hardcoded call into one repo-specific engine, the
hook resolves *which* named handlers the repo's active doctrine binds to the
current lane edge (`in_progress->for_review`), dispatches each, and aggregates
their verdicts (mission `doctrine-controlled-transition-gates`, epic #2535
half A). In the Spec-Kitty source tree the built-in `software-dev/review`
step-contract binds the `spec-kitty-pre-review` handler, which derives the CI
shards covering the WP's changed files and re-runs them — so a WP that broke a
shared contract pinned by a test *outside* its `owned_files` is caught at review
time instead of only at consolidation (#572, #1979). By default the gate is
**warn-only** -- it reports a new failure but the move still proceeds.

**How the impl is selected.** Activation, not repo shape, decides whether the
gate fires. A repo whose active doctrine binds no handler to the edge runs *no*
gate (a distinguishable `NO_COVERAGE` warn, never a silent skip); a repo that
activates a handler runs it. Toggling the binding's handler in doctrine flips
whether the gate fires with **no code change** between states.

**Fail-open and hard-stops.** Every handler *execution* error degrades to exactly
one visible unverified `NO_COVERAGE` warning — a faulting handler never removes
another's block from the computation. Exactly **two** hard-stops survive: a
terminal interruption (`TIMED_OUT`/`CANCELLED`) aborts the move with the
transition unapplied, and the opt-in `NEW_FAILURES` block (below) refuses the
move. Terminal is checked before the block. This is the closure of the
pre-review facet of #2534: a consumer repo never imports Spec-Kitty's internal
`_gate_coverage` authority, and even under *erroneous* activation of the
`spec-kitty-pre-review` handler the internal import is refused and degrades to a
`NO_COVERAGE` warn — the closure is structural, not configuration-dependent.

Configuration (`.kittify/config.yaml`, under `review:`):

- `review.fail_on_pre_review_regression` (bool, default `false`) -- opt in to
  **block** the move when the gate finds a new failure. `move-task --force`
  records an override and proceeds anyway.
- `review.test_command` -- selects which `ScopeSource` implementation the gate
  runs (`resolve_scope_source`, `scope_source.py`): when set, a portable
  `DeclaredCommandScopeSource` runs exactly this command; when unset --
  including in the Spec-Kitty source repo itself -- the gate falls back to the
  internal `GateCoverageScopeSource`, which derives its own scoped pytest
  invocation and ignores this key entirely. The block can only be *enforced*
  when a command is available (declared or derived); opting in to the block
  without one yields a loud warning (the gate cannot run a command it does not
  have).
- `review.pre_review_test_command` -- **deprecated** and aliased to
  `review.test_command`. A config that still sets it keeps working but earns a
  one-time deprecation warning; move the value to `review.test_command`.

> **Inherited limitation (#2741, P1 — inherited, NOT fixed by this mission).**
> The gate scopes off the WP worktree's *working-tree* diff rather than the WP
> commit range. The doctrine-controlled-transition-gates inversion is
> behaviour-preserving and therefore *preserves* this by design; it is tracked
> separately and must not be mistaken for a fix or flagged as a regression. Only
> the `for_review` pre-review facet of the repo-shape coupling is inverted here.

## Review-cycle artifacts and the consolidation gate

Every WP that reaches a terminal review lane (`approved` or `done` —
`TERMINAL_REVIEW_LANES` in
[`review/artifacts.py`](../../../src/specify_cli/review/artifacts.py)) is
checked against one invariant:
**`terminal_wp_latest_review_artifact_must_not_be_rejected`**. It is
implemented by `find_rejected_review_artifact_conflicts` in
[`post_merge/review_artifact_consistency.py`](../../../src/specify_cli/post_merge/review_artifact_consistency.py)
and is the **single shared implementation** behind three call sites:
`spec-kitty consolidate`
([`consolidation/preflight.py`](../../../src/specify_cli/consolidation/preflight.py)),
`spec-kitty consolidate --dry-run`
([`consolidation/forecast.py`](../../../src/specify_cli/consolidation/forecast.py)), and
`spec-kitty review`'s Gate 1 lane check
([`cli/commands/review/_lane_gate.py`](../../../src/specify_cli/cli/commands/review/_lane_gate.py))
— so the three surfaces cannot drift from one another.

**The gate is purely event-sourced.** It reads the reduced status
snapshot's `review_result` and `review` slots (via `materialize_snapshot`)
and never parses on-disk `review-cycle-N.md` frontmatter. A WP is blocked
only when the lane is terminal **and** the event-sourced verdict is
`changes_requested`; a `complete` override (see below) clears the gate
unconditionally and is checked first. An absent or damaged event slot is
treated as "no signal" — a safety gate that only detects rejections fails
open on missing data, never fabricates a block.

**No hand-authored artifact can satisfy the gate.** Because the gate never
reads the on-disk file, hand-editing a `review-cycle-N.md` to read
`verdict: approved` has no effect on whether consolidation or review passes — only
a genuine `move-task` transition can change the event-sourced verdict:

- An ordinary `move-task --to approved` (or `--to done`) out of `in_review`
  writes its own `approved` `ReviewResult` into the event log from the fact
  that the transition itself is happening
  (`_mt_plan_review_result` in
  [`tasks_move_task.py`](../../../src/specify_cli/cli/commands/agent/tasks_move_task.py))
  — no artifact content is read to decide this.
- When the WP's current event-sourced verdict was `changes_requested`,
  that same approval transition additionally synthesizes a durable
  `review-cycle-N.md` record on disk
  (`_persist_approved_review_cycle` in
  [`tasks_verdict_persistence.py`](../../../src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py)),
  with a machine-written body (`"Approved by {reviewer}: {reference}"`), so
  the on-disk history stays consistent with the event log. This is the
  CLI's own record of a genuine approval that already happened — never a
  hand-authored one — and it is a no-op when there was no prior rejection to
  close out. **Never instruct an agent to hand-write an `approved`
  review-cycle artifact to unblock a gate**; if the latest verdict is
  wrongly `changes_requested`, roll the WP back to `for_review` and run a
  real, independent review cycle.

**The `--skip-review-artifact-check` escape hatch.**
`move-task --to approved --skip-review-artifact-check --note "<reason>"` is
the arbiter-override path — `--note` is mandatory here; omitting it is
refused before the override can fire
(`_guard_rejected_verdict` in
[`tasks_transition_core.py`](../../../src/specify_cli/cli/commands/agent/tasks_transition_core.py)).
It records a `ReviewOverride {at, actor, wp_id, reason}`
([`status/models.py`](../../../src/specify_cli/status/models.py)) via a
single, topology-resolved `InnerStateChanged` event emit
(`_persist_review_artifact_override` in
[`tasks_materialization.py`](../../../src/specify_cli/cli/commands/agent/tasks_materialization.py))
— one write, not a **PRIMARY-partition-plus-coord** frontmatter mirror (that dual-write
is retired; the reduced `review` snapshot slot is the single authority both
partitions resolve). The gate only treats the override as clearing when
`ReviewOverride.complete` is true, i.e. all four fields are non-empty — a
partially-filled override still blocks. Use this only over a genuinely
superseded rejection, never as a substitute for a real re-review.

**`--review-feedback-file` provenance guard.** `move-task --to planned
--review-feedback-file <path>` reads `<path>` as the rejection body and
writes it into a freshly allocated, properly frontmattered
`review-cycle-N.md`
(`create_rejected_review_cycle` in
[`review/cycle.py`](../../../src/specify_cli/review/cycle.py); cycle
numbers are allocated under a lock as `max(existing) + 1`, never a file
count, so a numbering gap can't collide). The command refuses `<path>`
outright — by path identity **and** by content (does `<path>` itself parse
as a `ReviewCycleArtifact`?) — when it resolves to one of this WP's own
prior `review-cycle-N.md` files
(`_guard_feedback_source_provenance`, same module): a verdict record must
never be re-submitted as if it were new reviewer feedback. Plain reviewer
prose is always admissible, even when it is byte-identical to a prior
cycle's body (a reviewer re-reporting a recurring defect is not the attack
this guard exists to refuse).

## Issue-matrix discovery and `issue-verdict --actor`

Issue-matrix **verdict vocabulary** (`fixed`, `verified-already-fixed`,
`deferred-with-followup`, `in-mission`), the JSON **schema**, the
`.json`-canonical rule (a legacy `.md` matrix is read via failover, never
re-authored), and the `in-mission` semantics (accepted at per-WP `approved`,
**rejected on the mission `done` transition**) are already documented in
[`ERROR_CODES.md`](../../../src/specify_cli/cli/commands/review/ERROR_CODES.md)
and the Gate 4 section of
[`spec-kitty-mission-review/SKILL.md`](../../../src/charter/offering/skills/spec-kitty-mission-review/SKILL.md)
(C-008) — see those two for the full vocabulary and worked examples. This
section covers only the genuinely-absent operational half: how a reference
is *discovered*, and how a verdict is *recorded*.

**Discovery runs over every mission doc, not just `spec.md`.**
`discover_issue_references`
([`tasks/issue_reference_discovery.py`](../../../src/specify_cli/tasks/issue_reference_discovery.py))
scans `spec.md`, `plan.md`, `research.md`, `analysis-report.md` (each
optional), plus every `.md` file directly under `tasks/` and `contracts/`
(non-recursive, sorted by filename), in that fixed order. It reuses the one
canonical `#NNNN` detector
(`tasks.issue_matrix.detect_issue_references`) per file, so there remains
exactly one issue-reference pattern definition in the codebase. When the
same issue number appears in more than one file, the **first** file+line it
appears in (in scan order) wins both the context snippet and the recorded
`source_file` — never re-derived independently later.

**The consolidation-time completeness gate.**
`_evaluate_issue_matrix_completeness_gate`
([`policy/merge_gates.py`](../../../src/specify_cli/policy/merge_gates.py))
diffs `discover_issue_references`'s output against
`load_issue_matrix`'s rows and fails (blocking) when a discovered `#NNNN`
has no matrix row at all — it does not check verdicts (that is Gate 4's
job, cited above). A mission with **zero** discovered references is a
`PASS` — there is nothing to enforce, not a warning.

**`issue-verdict` requires `--actor`.**
`spec-kitty agent issue-verdict --mission <slug> --issue <#N> --verdict
<verdict> --actor <identity>`
([`cli/commands/agent/issue_verdict.py`](../../../src/specify_cli/cli/commands/agent/issue_verdict.py))
sets or upserts one issue-matrix row. `--actor` has no default and is
validated non-empty (`do_issue_verdict` raises `IssueVerdictError` /
`empty_actor` otherwise) — there is no anonymous or implicit-actor path for
recording a verdict.

## PR draft and WIP-title conventions

A `WIP` or `[WIP]` prefix on your PR title marks the PR as author-declared
not-ready. The two draft-gated CI suites (`integration-tests-core-misc`,
`e2e-cross-cutting`) **skip** on a WIP-titled PR, but the `quality-gate`
aggregator's exemption is draft-*flag*-only -- not title-based -- so a
**non-draft** PR that still carries a WIP prefix is a contradiction the gate
rejects by design: requesting review while WIP-titled must not pass. To land,
either drop the `WIP` / `[WIP]` prefix from the title, or keep the PR in draft
until it is ready. (See the `DRAFT_GATED_JOBS` note that used to live in
`.github/workflows/ci-quality.yml`, deleted per PROGRAM.md §2 / planning#57 —
this repo runs no GitHub Actions.)

## PR body style: consumer-focused BLUF

A PR description leads with **impact** — what changes for a user or operator
of Spec Kitty, stated plainly, in the first paragraph. Technical detail
(architecture, seams, test strategy) comes after, for the reviewer who wants
it. The first paragraph should make sense to someone who will *use* the
change, not only to someone who will *review* it — a PR body is not a
maintainer diary.

This is checked again at landing time; see
[Landing runbook, step 7](pr-landing.md#7-review-focus-areas-beyond-ci).

## Changelog update and style

Every user-facing change updates `docs/changelog/CHANGELOG.md` (the root
`CHANGELOG.md` is a symlink to it — there is one canonical file). The entry
mirrors the PR body's style: consumer-focused, impact-first, one line a user
understands — e.g. "Fixed: sync could deliver one project's events to
another project's workspace" — not an internal-mechanism summary. Add it
under the relevant `[Unreleased]` category in
[`docs/changelog/CHANGELOG.md`](../../changelog/CHANGELOG.md).

## Shippable doctrine: built-in doctrine must work in a consumer repo

**Built-in doctrine (anything under `packs/built-in/`) MUST be valid
and actionable in a consumer repository that has activated the pack but has NO
access to the spec-kitty source tree, CI, or tooling.** A doctrine pack is
installed/activated as a *pack* in an arbitrary customer repo — it does not ship
our `scripts/`, `.github/`, `src/`, or `tests/` directories, and never will.

When reviewing (or authoring) a directive, styleguide, tactic, procedure,
toolguide, or glossary pack, reject any of these:

- **A reference to a spec-kitty repo-local file as if the consumer has it** —
  e.g. naming `scripts/docs/<x>.py`, `.github/workflows/<y>.yml`,
  `src/specify_cli/...`, or a `tests/...` path as the enforcement mechanism or a
  resolvable artifact. The consumer repo has none of these. Mentioning our own
  CI or code-repo paths in shipped doctrine is an inconsistency waiting to
  happen (and, when the doctrine is activated in a customer repo, a dangling
  reference).
- **Consumer-facing logic (a lint, gate script, or other executable) that is
  not shipped as part of the pack.** The canonical way to ship executable logic
  or any blob to downstream repos is the **`asset` doctrine kind** (a sidecar
  `*.asset.yaml` manifest + the blob under the pack's `assets/` tree — see
  [`create-a-doctrine-artifact.md`](create-a-doctrine-artifact.md)
  and [`doctrine-kinds.md`](../../architecture/doctrine-kinds.md)). Do **not** force
  downstream customers to add executable scripts or CI to their own repos to
  satisfy our doctrine.

**Quick check** — run **both** patterns:

```bash
# repo-local tooling paths
grep -rEn 'scripts/|\.github/|src/specify_cli|tests/' packs/built-in/
# source-tree PREFIXES -- the content ships, the `src/` prefix does not
grep -rEn 'src/doctrine/|src/mission_runtime|src/charter/|src/runtime/|src/glossary/' \
  packs/built-in/
```

Neither should return anything a consumer is expected to *resolve or run*. The
second pattern matters as much as the first and is easy to forget: an installed
consumer has the pack in site-packages, never a `src/` tree prefix, so a
`guide_path:` or `references:` entry carrying the source-tree prefix is a
dangling reference downstream even though the artefact itself ships.

**Classify before you fix — a raw hit count is not a defect count.** Prose that
merely describes an internal practice ("maintained by periodic review") is fine,
as are generic conventions (`tests/**` globs, `ruff check src/ tests/`); a path
presented as a live gate or resolvable artifact is not. Measured 2026-07-28, the
first pattern returned **84 hits across 23 files of which 52 were real** — the
rest were permitted prose or a regex false positive. The worked classification,
the relocation order, and the gate that currently *requires* one of these
references live in
[`built-in-doctrine-repo-coupling-audit.md`](../../plans/doctrine/built-in-doctrine-repo-coupling-audit.md).

## See also

- [`local-overrides.md`](local-overrides.md) -- developer-only workflow
  for working across `spec-kitty-cli` / `spec-kitty-events` /
  `spec-kitty-tracker` checkouts without committing editable sources.
- [`tests/architectural/test_pyproject_shape.py`](../../../tests/architectural/test_pyproject_shape.py)
  -- TOML-shape assertions for the shared-package boundary
  (compatibility ranges, no committed editable sources, etc.).
- The CI job `clean-install-verification` in
  `.github/workflows/ci-quality.yml` performs the equivalent
  fresh-venv check on every PR.
