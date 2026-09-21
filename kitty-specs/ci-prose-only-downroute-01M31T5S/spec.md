# Mission Specification: CI down-route of prose-only .py diffs

**Mission Branch**: `feat/ci-prose-only-downroute`
**Created**: 2026-09-21
**Status**: Draft
**Input**: Issue #4842 (under CI-honesty epic #4437) — "CI: down-route comment/docstring-only .py diffs off the code test matrix (path router is content-blind)".

## Intent Summary *(confirmed)*

**Primary actor**: the CI path-routing seam (`ci-modules.yml` / `ci-router.yml`, driven by `scripts/ci/gate_selection.py`) acting on behalf of a maintainer who opens a pull request.

**Trigger**: a pull request whose entire Python diff changes only comments and/or
docstrings (no executable code, no type-affecting comments), optionally alongside
already-documentation paths (`docs/**`, `*.md`).

**Desired outcome**: such a PR is *down-routed* — it does **not** run the runtime
module-test matrix or the heavy architectural battery (which no comment/docstring
edit can affect), and it **does** run the documentation-facing lanes
(docs/help-drift + doctest) that a docstring edit *can* affect. Every other PR
routes exactly as it does today.

**Load-bearing invariant**: the classifier is **fail-closed**. It skips the code
matrix only on *proof* of prose-only; on any uncertainty — parse error, unfetchable
base blob, an unfamiliar construct, or a change to a semantically-live comment
(`# type:`, `# noqa`, `# pragma`) — it routes as a full code change. A false
"prose-only" that skipped tests on real code would let a bug merge; that must be
impossible.

**Confirmed assumptions** (operator directed autonomous execution; recorded here in
lieu of a full interview):
- The behavior is defined by #4842's Acceptance section; this mission implements it
  verbatim, including the docs-lane fix (the inversion where a docstring change ran
  the code suite and skipped the docs lane).
- The prior design review on #4842 (F1–F4) is binding architectural guidance:
  content-detection lives in a **new pure module + workflow wiring**, not inside the
  path-pure `gate_selection.py` (F1/F2); the classifier must catch `# type:` /
  `# noqa` / `# pragma` deltas that a bare AST compare misses (F3); and the
  down-route must *positively enable* the docs/help-drift/doctest lane rather than
  merely subtract the code path (F4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prose-only PR stops burning the code matrix (Priority: P1)

A maintainer opens a PR that fixes a stale docstring in `src/specify_cli/**` (the
#4841 shape). CI recognizes the entire diff as prose-only and runs the fast
always-on lanes plus the docs/help-drift/doctest lanes, but not the per-module test
matrix and not the heavy architectural battery.

**Why this priority**: this is the whole point of the mission — the ~2 hrs of
aggregate shard compute that #4841 wasted is the motivating defect. Delivering just
this story (with its fail-closed guarantee) is a viable MVP.

**Independent Test**: feed a real docstring-only base→head `.py` blob pair through
the classifier and assert the resulting selected-lane set excludes the module matrix
and the arch battery and includes the docs lane; assert the always-on lanes are
untouched.

**Acceptance Scenarios**:

1. **Given** a PR whose only change is a docstring edit in one `src/**.py` file,
   **When** the router classifies the diff, **Then** the module-test matrix and the
   architectural battery are not selected.
2. **Given** that same PR, **When** the router classifies the diff, **Then** the
   documentation/help-drift and doctest lanes **are** selected (the inversion is
   fixed), and lint/format/terminology (always-on) still run.
3. **Given** a PR that edits only `#` comments in a `tests/**.py` file, **When** the
   router classifies the diff, **Then** it is treated identically to the docstring
   case (down-routed).

---

### User Story 2 - Any real code change routes exactly as today (Priority: P1)

A maintainer opens a PR that flips a default, adds a branch, or edits a non-docstring
string literal (error text, `--help` string). CI must route it through the full code
matrix and arch battery unchanged — the refinement is invisible to every non-prose PR.

**Why this priority**: co-equal P1 with Story 1. The mission's safety rests entirely
on this story: the refinement must never narrow routing for a PR that carries real
code. Without it, Story 1 is a liability, not a feature.

**Independent Test**: feed base→head blob pairs representing (a) a changed default,
(b) an added branch, (c) a changed non-docstring string literal, and (d) a mixed
docstring+code diff, and assert each classifies as **not** prose-only, yielding
today's full routing.

**Acceptance Scenarios**:

1. **Given** a `.py` diff that changes a default value or adds a statement, **When**
   classified, **Then** the file is *not* prose-only and the PR routes fully.
2. **Given** a PR that mixes a docstring edit and a one-line code change (same or
   different files), **When** classified, **Then** the PR routes fully (all-or-nothing
   per PR).
3. **Given** a `.py` diff that changes only a `# type:`, `# noqa`, or `# pragma`
   comment, **When** classified, **Then** the file is *not* prose-only (fail-closed on
   semantically-live comments) and the PR routes fully.

---

### User Story 3 - Uncertainty always fails closed (Priority: P1)

Whenever the classifier cannot *prove* prose-only — a base blob cannot be fetched, a
file does not parse on one side, an unfamiliar construct appears — it must default to
"code" so the PR routes fully. The safe failure mode is "run everything," identical to
today.

**Why this priority**: co-equal P1 — this is the invariant that makes Story 1 safe to
ship. It is separated from Story 2 because it covers *tooling* failure (not code
content) and needs its own explicit tests.

**Independent Test**: feed inputs that raise `SyntaxError`, a `None`/empty base blob,
and a construct the normalizer does not recognize; assert each returns not-prose-only
and the aggregate routes fully.

**Acceptance Scenarios**:

1. **Given** a `.py` file that fails to parse on the head side, **When** classified,
   **Then** it is not prose-only and the PR routes fully.
2. **Given** a changed `.py` path whose base blob cannot be retrieved (new file, or a
   degenerate/force-push base), **When** classified, **Then** it is not prose-only and
   the PR routes fully.
3. **Given** the aggregate decision, **When** *any* changed file cannot be proven
   prose-only, **Then** the whole PR routes as a full code change (all-or-nothing).

### Edge Cases

- A docstring that contains an executable doctest (`>>> …`) is prose-only by AST but
  can change doctest behavior → the doctest lane must run (covered by FR-005), so
  down-routing must not suppress it.
- A docstring feeds `--help`/CLI reference output (Typer uses `__doc__`) → the
  help-drift lane must run for a docstring-only change (FR-005).
- A file added or deleted wholesale (no base or no head) → cannot be proven
  prose-only → fail closed (FR-006).
- A diff that only adds/removes blank lines or reformats whitespace inside code →
  out of scope for the "prose-only" claim; if the normalized code is identical it may
  down-route, but a whitespace change that alters tokens must not. The classifier
  keys on normalized-code identity, not on the textual diff.
- A PR touching CI infra itself (`scripts/ci/**`, `.github/workflows/**`) is not a
  `.py`-under-`src`/`tests` prose case and routes by its existing group.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Prose-only classifier | As the routing seam, I want a pure predicate over a (base source, head source) pair that returns true only when the two are identical after removing comments and docstrings, so that a prose-only `.py` change can be proven without side effects. | High | Open |
| FR-002 | Semantically-live content guard | As the routing seam, I want the classifier to treat as a code change (not prose): a change to any tool directive comment (`type:`, `noqa`, `pragma`, `ruff:`, `fmt:`, `mypy:`, `pyright:`, `isort:` — matched whitespace/`#`-spacing insensitively so `#type:` is caught), a change to a line-1/2 encoding cookie or shebang, or a change to a docstring containing a `>>>` doctest prompt — so that a bare AST compare cannot skip a tool gate on a live directive (#4842 F3, squad HIGH-4/MEDIUM-1) or skip a doctest that runs inside the down-routed module matrix (research R4). | High | Open |
| FR-003 | Aggregate all-or-nothing decision | As the routing seam, I want a PR down-routed only when *every* changed file is either an existing documentation path or a proven prose-only `.py`, so that any real code change anywhere forces today's full routing. | High | Open |
| FR-004 | Down-route target set | As the routing seam, I want a proven-prose-only PR to skip the runtime module-test matrix, the per-group code shards (tests-merge/status/cli/…), and the heavy architectural battery, while the always-on lanes (lint/format/terminology) still run, so that inert compute is not spent. | High | Open |
| FR-005 | Positive docs/help-drift enablement | As the routing seam, I want a proven-prose-only-`.py` PR to positively select the documentation/help-drift lane (`tests/docs`), so that the current inversion (docstring change skipped the docs lane) is corrected rather than reproduced (#4842 F4). Doctests are not a separate lane — they are protected by treating a changed `>>>`-bearing docstring as code (FR-002/R4). | High | Open |
| FR-006 | Fail-closed default | As the routing seam, I want any classification uncertainty (parse error, unfetchable base, unfamiliar construct) to yield a "code" verdict, so that the code matrix is never skipped without proof of prose-only. | High | Open |
| FR-007 | Path purity of the existing authority | As a maintainer, I want `scripts/ci/gate_selection.py` to remain a pure function of a path list (no git/blob IO), so that its reuse by the WP17 completeness oracle and WP18 local parity is preserved and the #2476 single-authority invariant holds (#4842 F1/F2). | High | Open |
| FR-008 | Workflow wiring across all three surfaces | As the routing seam, I want the down-route wired into all THREE content-blind surfaces: (a) `ci-modules.yml` changed-files reduces the path list before `select_modules` (skips the module matrix); (b) `ci-router.yml` computes `prose_only` in a SEPARATE job (so `gate_selection.py`'s group-regex never treats it as a routing group — squad F2) and its output gates the arch battery + code shards off and forces the docs lane on; (c) `ci-aggregate.yml` excludes prose-only `.py` from the diff-cover diff patch (FR-009). Path classification (doc/corpus/mapped) stays in the wiring behind `gate_selection`, not in the pure classifier (research R9). | High | Open |
| FR-009 | Coverage-gate honesty | As the routing seam, I want a proven-prose-only `.py` excluded from the `ci-aggregate.yml` diff-cover diff patch, so that skipping its module shard does not leave the coverage gate scoring the changed docstring lines against stale backfilled coverage and false-failing the PR (squad F1, epic #4437 honesty). | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Classifier isolation | The classifier module performs no filesystem, git, or network IO and imports neither `yaml` nor `fnmatch`; it is a pure function of two source strings, unit-testable with in-memory inputs (no fixtures on disk). | Maintainability | High | Open |
| NFR-002 | Fail-closed provability | 100% of the enumerated uncertainty inputs (parse error, absent base, unknown construct, live-comment delta) return not-prose-only; there is no input for which the classifier returns prose-only without structural proof. | Safety | High | Open |
| NFR-003 | Type and lint cleanliness | New code passes `ruff check`, `ruff format --check`, and `mypy` with zero issues and zero new suppressions. | Quality | High | Open |
| NFR-004 | No product-code change | The change is confined to CI surfaces (`scripts/ci/**`, `.github/workflows/**`) and their tests (`tests/ci/**`, `tests/architectural/**`); no `src/**` product code is modified. | Locality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single routing authority (#2476) | The path→group routing map must not be re-encoded; `gate_selection.py` stays the sole parser of `ci-router.yml`, and the classifier introduces no second path map. | Technical | High | Open |
| C-002 | AST normalization mechanics | Comparison uses `ast.dump(..., include_attributes=False)` (position-insensitive) with docstring string-expression nodes stripped on both sides, parsed with `type_comments=True` so type comments participate in the compare — the mechanism #4842 F3 requires. | Technical | High | Open |
| C-003 | Terminology canon | All new identifiers, comments, and docs use canonical Mission vocabulary; no `feature*` aliases are introduced. | Regulatory | Medium | Open |
| C-004 | Operator merges | The mission consolidates into the local `feat/ci-prose-only-downroute` branch; publication is a PR to `skupstream/main` that the operator merges. No push to `main`, no `merge --push`. | Business | High | Open |

### Key Entities

- **Prose-only verdict**: the boolean result of classifying one `.py` file's
  (base source, head source) pair — true only on proven comment/docstring-only change.
- **Changed-path set**: the flat list of files a PR touches, reduced by dropping
  proven-prose-only `.py` paths before it reaches `select_modules`.
- **Down-route lane set**: the lanes a proven-prose-only PR selects — always-on lanes
  + docs/help-drift + doctest, minus the module matrix and arch battery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A comment/docstring-only `.py` PR (no other code change) selects zero
  module-test-matrix shards, does not select the architectural battery or the
  per-group code shards, has its `.py` excluded from the diff-cover diff patch (so
  the coverage gate does not false-red), while the documentation/help-drift lane is
  selected — verified by a golden test pinning the down-routed lane set (hand-pinned,
  not reverse-engineered from the `if:` expressions — squad F4).
- **SC-002**: Every PR containing a real code change, a mixed diff, or any file the
  classifier cannot prove prose-only routes to the identical lane set it selects today
  (zero regressions against the current routing for non-prose PRs).
- **SC-003**: 100% of the enumerated fail-closed inputs (parse error, absent base,
  live-comment delta, unknown construct, mixed diff) are covered by unit tests and
  each yields full routing.
- **SC-004**: The existing single-authority and local-parity architectural guards
  (`tests/architectural/test_gate_selection_authority.py`,
  `test_local_gate_parity.py`, `test_ci_integrity_oracle_nonvacuous.py`) remain green,
  confirming `gate_selection.py` stayed path-pure.
