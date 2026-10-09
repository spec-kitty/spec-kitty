---
title: 'Review Gates: Pre-PR Hygiene, Review-Cycle Mechanics, and the Consolidation Gate'
description: Review-cycle-artifact and consolidation-gate mechanics, the --skip-review-artifact-check override, and issue-matrix discovery, so review focuses on substance.
doc_status: active
updated: '2026-10-08'
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
satisfy to reach `approved`/`done`. The issue-matrix verdict vocabulary and
the rule for which references need a row are owned by the
[Issue-Matrix Verdict Reference](../reference/issue-matrix-verdicts.md); review
error codes live in
[`ERROR_CODES.md`](../../../src/specify_cli/cli/commands/review/ERROR_CODES.md).
This page cites them rather than restating them.

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
  [`tasks_move_task_hops.py`](../../../src/specify_cli/cli/commands/agent/tasks_move_task_hops.py))
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
not-ready. Use the GitHub **draft** flag for the same purpose: keep the PR in
draft until it is ready, and drop any `WIP` / `[WIP]` prefix before you mark it
ready for review. A non-draft PR that still carries a WIP prefix is a
contradiction — reviewers will send it back.

No CI job currently gates on the draft flag or the WIP title: the modular CI
(`ci-router.yml`, `ci-modules.yml`, `ci-aggregate.yml`) and `ci-quality.yml`'s
`quality-gate` run the same way on draft and ready PRs. The earlier
draft-gated suites (`integration-tests-core-misc`, `e2e-cross-cutting`) no
longer exist.

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
understands — e.g. "`spec-kitty research` now finds its templates through
the same resolver as every other mission template" — not an
internal-mechanism summary. Add it
under the relevant `[Unreleased]` category in
[`docs/changelog/CHANGELOG.md`](../../changelog/CHANGELOG.md).

Two automated checks keep docs prose and that `[Unreleased]` section in shape:
a spelling check and a changelog style guard. Both run in CI as the always-on
`docs-lint` job (see [`docs-lint` in the CI gate
mechanics](../reference/ci-gate-mechanics.md#docs-lint)), so run them locally
first.

### Run the docs checks locally

From the repository root, after a one-time `uv sync --frozen` (it installs the
pinned `codespell` from the dev group):

```bash
make docs-lint        # both checks; stops at the first one that fails

# or one at a time (`make docs-lint` runs each of these through `uv run --frozen`):
uv run --frozen python -m scripts.docs.check_spelling                     # all three spelling passes
uv run --frozen python -m scripts.docs.check_spelling --pass typo         # typos in docs prose
uv run --frozen python -m scripts.docs.check_spelling --pass us           # US spelling in guides and context
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased   # US spelling in [Unreleased]
uv run --frozen python -m scripts.docs.check_changelog_style              # changelog entry style
```

Exit code `0` means clean, `1` means findings, and `2` means the tool could not
run or could not prove it looked at anything. Exit `2` covers:

- `codespell` is not installed, or `pyproject.toml` has no `[tool.codespell]`
  table (spelling check).
- The changelog cannot be read (both scripts).
- A `typo` or `us` pass scanned zero files (`the <pass> pass scanned 0 file(s)`).
- The `unreleased` pass would scan a scratch copy of the section that a
  `[tool.codespell]` `skip` glob drops, so nothing would be checked.

A changelog with no `[Unreleased]` section is not an error: the `unreleased`
pass scans `0` lines and the guard prints `nothing to check`, and both exit `0`.
The checks run no pytest.

Two options help when you test against another tree: `--repo-root PATH` on the
spelling check, and `--changelog PATH` on both. A relative `--changelog`
resolves against the repository root in both scripts (against `--repo-root` for
the spelling check), so the result does not depend on your current directory.

Do **not** run bare `codespell`. Without the script's scope roots it scans the
whole repository, including skipped trees (`docs/archive/`, `docs/reports/`,
`docs/plans/`) and generated files, and reports hundreds of hits that are not
yours.

### What gets checked

The spelling check runs three passes. Each covers Markdown only; the
`skip` list in `[tool.codespell]` in `pyproject.toml` excludes `docs/archive/`,
`docs/reports/` and `docs/plans/`, the generated CLI reference
(`docs/api/cli-commands.md`) and non-Markdown files. A page under those paths is
never spell-checked, so respell it by hand if you touch it.

| Pass | Looks for | Scope |
|---|---|---|
| `typo` | real typos | `docs/`, `packs/built-in/` and `README.md` |
| `us` | British spellings (`behaviour`, `colour`) | `docs/guides/` and `docs/context/` |
| `unreleased` | British spellings | the `[Unreleased]` section of the changelog only |

The two American-spelling passes ignore code spans, fenced blocks and
`<a id="…"></a>` heading anchors, and accept `dialogue`. The typo pass has no
such exemption.

The changelog guard reads the `[Unreleased]` section only; released sections are
never restyled. Both scripts find that section through one shared locator, which
ignores a release-looking heading inside a fenced block (fenced with ` ``` ` or
`~~~`) and accepts a heading written without a space (`##[Unreleased]`). The
guard enforces:

| Area | Rule (finding id) |
|---|---|
| Headings | Only `### Breaking`, `Upgrade Notes`, `Added`, `Changed`, `Fixed`, `Internal`, each at most once and in that order (`heading-unknown`, `heading-duplicate`, `heading-order`). A `####` heading is allowed only under `### Fixed` (`subheading-placement`). |
| Entry shape | Entries in every section except Internal start with a bold headline (`headline-missing`). Every entry is a `- ` bullet at column 0; a `* ` or `+ ` bullet fails (`bullet-marker`). Issue references go after the headline in parentheses, never inside the bold (`refs-in-bold`). Breaking, Changed and Fixed entries show the old behavior with `**Before:**` (or `**Why:**` plus `**After:**`), unless the body is short: at most two sentences and 300 characters (`contrast-missing`). |
| Internal entries | One physical line, with no nested items and no `**Before:**` (`internal-shape`). |
| Banned tokens | No requirement IDs such as `FR-012` outside backticks, no 26-character ULID (any one, not only a mission's), no `.kittify/evidence/` paths, no `planning#` references, no all-caps `DEFAULT`, `REFUSE` or `FAIL` outside backticks, no "Bug-fix; no CLI version bump" boilerplate, and no mention of the retired `merge` command (write `spec-kitty consolidate`; only an entry that also names `spec-kitty consolidate`, such as the rename entry, may name the old command). The same tokens are banned in the text above the first heading and in prose between a `###` or `####` heading and its first bullet (`banned-token`). |
| Length | Measured in characters. An entry over 900 warns (`length-warning`); over 1,200 fails (`length`). Each nested bullet is measured on its own. A warning does not change the exit code. |

A compliant entry looks like this (illustrative content; the guidance test runs
this exact block through the guard, so it stays valid):

<!-- docs-lint-example -->
```markdown
- **`spec-kitty consolidate` no longer deletes a lane branch that still holds unmerged commits** (#1234).
  **Before:** cleanup removed the branch as soon as its Work Package was approved, so late commits were lost. **After:** cleanup checks the branch tip first and refuses, naming the commit to restore.
```

### False positives

The banned-token rules match shapes, not meanings, so some legitimate text is
flagged. In an entry headline or body these all fail: `WP-D-1` (the shape `D-1`
reads as a requirement ID), `ISO C-3` (`C-3`), `SC-2086` (`SC-` plus digits),
`DEFAULT-branch` (the all-caps word `DEFAULT`), and `C#10` in a bold headline
(`refs-in-bold`, because of `#10`). Put the literal in backticks, for example
`` `SC-2086` ``. That clears requirement IDs and all-caps words. It does not
clear a ULID, which is matched even inside a code span.

### Read a failure

Each finding is one line. The spelling check prints
`path:line: [typo] word — fix: suggestion` (or `[us-spelling]`), then a summary:

```text
docs/guides/example.md:12: [us-spelling] colour — fix: color
1 finding(s) across 1 file(s); scanned: typo=665 file(s), us=134 file(s), unreleased=276 line(s)
```

The guard prints `path:line: [rule] [Section] headline excerpt — fix`, with
`warning:` in front of warnings, then an `N error(s), M warning(s)` summary:

```text
docs/changelog/CHANGELOG.md:57: [refs-in-bold] [Fixed] Stop duplicate events (#1234) — Move `(#1234)` out of the bold headline: `- **Headline** (#1234).`
```

The line number is the real line in the file, and the text after the dash says
what to do. Read the `scanned:` counts too: a pass that shows `0` looked at
nothing (a wrong `--repo-root`, for instance), which is not the same as a clean
pass. The check now refuses that case for the `typo` and `us` passes: it prints
`error: the <pass> pass scanned 0 file(s); a check that looks at nothing cannot
pass` and exits `2`. Only `unreleased=0 line(s)` can still be a clean result,
when the changelog has no `[Unreleased]` section.

### Allow a legitimate word

When `codespell` flags a word that is correct here (a domain term, a proper
noun), add it to `ignore-words-list` in the `[tool.codespell]` table of
`pyproject.toml`. Use lowercase, comma-separated, with no spaces:

```toml
ignore-words-list = "accreting,disjointness,yourword"
```

One lowercase entry covers every capitalization. The list is shared by all
three spelling passes, so add only words that are correct everywhere.

### Exempt a quoted literal

The two American-spelling passes flag British spellings inside quoted CLI
output, status values, config keys and identifiers, where you cannot change the
word. Put the literal in a code span (`` `like this` ``), or in a fenced block if
it spans several lines. A single-word heading anchor written as
`<a id="behaviour"></a>` is already exempt. This exemption does not apply to the
typo pass: a real typo inside a code span is still a typo.

### Known blind spots

- Hyphenated British tokens such as `organisation-tier` or `behaviour-driven`
  are never flagged, because `codespell` treats the hyphen as part of the word.
  Spell them the American way yourself.
- The `en-GB` to `en-US` dictionary is not complete; some words, for example
  `materialised`, slip through. Respell them by hand when you see them.

## Shippable doctrine: the built-in Charter Pack must work in a consumer repo

**The built-in Charter Pack (anything under `packs/built-in/`) MUST be valid
and actionable in a consumer repository that has activated the pack but has NO
access to the spec-kitty source tree, CI, or tooling.** A Charter Pack is
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
[`built-in-doctrine-repo-coupling-audit.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/built-in-doctrine-repo-coupling-audit.md).

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
