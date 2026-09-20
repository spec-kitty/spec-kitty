# Mission Specification: Charter Activation Catalog Coherence

**Mission Branch**: `issue-4785-charter-catalog-coherence`
**Created**: 2026-09-19
**Status**: Draft
**Input**: GitHub issue #4785 — "Charter activation tooling: no clean, worktree-safe, minimal way to keep catalog.references coherent when activating one built-in directive"

## Context

`.kittify/charter/charter.yaml` carries a compiled, **derived** `catalog.references`
section that must stay in sync with the activation lists in the same file
(`activated_directives`, etc.). Maintainers activate built-in doctrine (e.g. a new
directive) as a routine governance action. Four independent tooling gaps — all
reproduced on current `main` by the grounding squad — make it impossible to keep
that catalog coherent cleanly:

1. `charter activate <directive>` is a config-only write and never recompiles the
   catalog, so the coherence guard reds (the #2524 "dangler" class).
2. The tool's own suggested repair (`charter synthesize` / `activate --resynthesize`)
   points at a command that **structurally cannot** recompile the catalog, and on an
   established store it takes a fresh-project short-circuit.
3. Charter write commands resolve the project root to the **primary checkout**, so
   running from a linked worktree silently writes into the primary repo.
4. The one command that does recompile (`charter generate`) re-renders the **entire**
   catalog and still leaves directive entries as `Definition unavailable in bundled
   doctrine.` placeholders.

This mission closes all four so charter activation is coherent, worktree-safe, and
complete **by construction**, honouring the charter's single-canonical-authority
principle (no second or "minimal" catalog writer).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Activating a directive keeps the catalog coherent (Priority: P1)

A maintainer activates a single built-in charter directive. The compiled
`catalog.references` stays coherent automatically — no hand-edit, no red coherence
guard.

**Why this priority**: This is the reported blocker's core. Every built-in directive
activation today produces an incoherent charter store that only a manual surgical edit
(as done for PR #4784) can fix. It partially discharges parent epic #2519's reconciler
scope.

**Independent Test**: On an established charter store, run `charter activate` for a
built-in directive absent from the baseline catalog, then run the coherence guard
(`tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent`).
It passes with zero manual edits.

**Acceptance Scenarios**:

1. **Given** an established charter store whose coherence guard passes, **When** the
   maintainer activates a built-in directive not yet in `catalog.references`, **Then**
   `catalog.references` gains the matching entry and the coherence guard still passes.
2. **Given** a directive that was just deactivated, **When** deactivation completes,
   **Then** its `catalog.references` entry is removed and the coherence guard passes.
3. **Given** a maintainer who wants the historical fast config-only write, **When** they
   pass the explicit opt-out flag, **Then** activation writes config only and the
   command clearly reports the catalog was not recompiled.

---

### User Story 2 - The tool's guidance points at a repair that works (Priority: P1)

When catalog coherence drifts, the guidance the tool prints (coherence-guard remediation
text and `--resynthesize` help) names a command that actually recompiles the catalog on
an established store — not a dead-end.

**Why this priority**: Finding 1 and Finding 2 are a coupled trap — the guard's own
suggestion sends the operator to `synthesize`, which cannot recompile the catalog and,
on this store shape, short-circuits to a fresh-project seed. Fixing the guidance is what
makes the drift recoverable at all.

**Independent Test**: Introduce a catalog divergence on an established store, run the
command named in the remediation text; the divergence clears. Separately, run
`charter synthesize` on an established store and confirm it is no longer misclassified as
a fresh project.

**Acceptance Scenarios**:

1. **Given** a drifted catalog on an established store, **When** the maintainer runs the
   command named in the coherence-guard remediation message, **Then** `catalog.references`
   is recompiled and the divergence is cleared.
2. **Given** an established charter store that has no `.kittify/charter/generated/`
   directory, **When** `charter synthesize` runs, **Then** it does **not** report
   "fresh project" and does not short-circuit to seeding minimal doctrine.
3. **Given** the remediation and help text, **When** a maintainer reads them, **Then**
   they never recommend `charter synthesize` as the way to recompile `catalog.references`.

---

### User Story 3 - Charter authoring is worktree-safe (Priority: P2)

A maintainer running a charter write command from inside a linked git worktree never has
their write silently land in the primary checkout. It either targets the invoking
checkout or fails closed with a clear, actionable message.

**Why this priority**: Silent cross-checkout writes are dangerous when another session
owns the primary checkout (the exact landing-session hazard the issue records). This
folds the CLI-charter-write half of duplicate issue #4250.

**Independent Test**: From a linked worktree, run a charter write command (e.g.
`generate`); confirm the primary checkout's charter store is untouched — the command
either wrote the worktree's store or exited non-zero with guidance.

**Acceptance Scenarios**:

1. **Given** a maintainer inside a linked worktree, **When** they run a charter write
   command, **Then** the primary checkout's `.kittify/charter/` is not modified.
2. **Given** the same situation with fail-closed policy, **When** the command refuses,
   **Then** it exits non-zero and tells the maintainer to use a dedicated clone for
   charter authoring.
3. **Given** `activate --resynthesize` run from a worktree, **When** it completes,
   **Then** the activation flag and the catalog recompile land in the **same** checkout
   (no split-brain between worktree and primary).

---

### User Story 4 - The compiled catalog is complete and stable (Priority: P2)

Recompiling the catalog produces real directive summaries — no silent
"Definition unavailable" placeholders for directives that do have a bundled definition —
and a second recompile of an unchanged store is a no-op.

**Why this priority**: Once activation recompiles by default (US1), the output must be
complete, or activation would re-introduce placeholder gaps. The over-render itself is
by design (the catalog is derived); the defect is the silent placeholders and the churn
from prior hand-edits.

**Independent Test**: Recompile the catalog and assert zero directive entries read
`Definition unavailable in bundled doctrine.` for directives present in the authoritative
bundled-doctrine enumeration; run the recompile a second time and assert a zero-line diff
**of the `catalog.references` section** (the `metadata.generated_at` stamp is preserved when
the compiled catalog is byte-unchanged, so it does not count as churn).

**Acceptance Scenarios**:

1. **Given** a full catalog recompile, **When** it finishes, **Then** every activated or
   transitively-reachable directive that has a bundled definition resolves to its real
   summary.
2. **Given** a directive id that genuinely has no bundled definition, **When** the catalog
   is recompiled, **Then** it surfaces as a diagnostic / unresolved reference, not a
   silent placeholder catalog row.
3. **Given** an unchanged charter store, **When** the catalog is recompiled twice in a
   row, **Then** the second recompile produces a zero-line diff of the `catalog.references`
   section (entries emitted in a canonical, deterministic order).

### Edge Cases

- Activating a directive that is **already** in the catalog → no duplicate entry, guard
  still passes, idempotent.
- Recompile invoked when git is absent/unavailable → worktree detection degrades safely
  (does not crash; treated as not-a-linked-worktree).
- A transient global-asset-cache race (`#2627` "Global asset input changed") during
  recompile → out of scope to fix, but the recompile path must not be newly fragile to it.
- Authored (non-derived) charter sections (`governance`, `directives`, activation lists,
  overrides) must never be rewritten by a catalog recompile.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Activate recompiles catalog | As a maintainer, I want activating a built-in directive to update `catalog.references` so the coherence guard passes without a manual edit. | High | Open |
| FR-002 | Deactivate recompiles catalog | As a maintainer, I want deactivating a directive to remove its `catalog.references` entry so the store stays coherent. | High | Open |
| FR-003 | Config-only opt-out | As a maintainer, I want an explicit flag to keep the fast config-only write when I intend to defer recompilation, with a clear notice that the catalog was not recompiled. | Medium | Open |
| FR-004 | Correct remediation guidance | As a maintainer, I want the coherence-guard message and `--resynthesize` help to name a command that actually recompiles `catalog.references` (never `charter synthesize`); the guard's own suggestion-substring assertions are updated to the corrected guidance. | High | Open |
| FR-005 | Fresh-project gate fix | As a maintainer, I want `synthesize` to classify an established store (compiled catalog present) as non-fresh so it does not short-circuit to a minimal-doctrine seed. | High | Open |
| FR-006 | Worktree-safe charter writes | As a maintainer, I want every charter write command that touches the charter store (`activate`, `deactivate`, `generate`, `synthesize`, `activate --resynthesize`) to **fail closed** with a non-zero exit and actionable "use a repository-root checkout or dedicated clone" guidance when invoked from a linked worktree, never silently writing the primary checkout. | High | Open |
| FR-007 | Complete directive summaries | As a maintainer, I want a catalog recompile to resolve real summaries for every directive present in the authoritative bundled-doctrine enumeration (the typed doctrine repository listing), and to surface genuinely-missing definitions as diagnostics rather than silent placeholders. | High | Open |
| FR-008 | Stable, deterministic recompile | As a maintainer, I want a second recompile of an unchanged store to produce a zero-line diff of the `catalog.references` section (canonical entry order; `generated_at` preserved when the catalog is byte-unchanged) so the derived catalog does not churn. | Medium | Open |
| FR-009 | Retire dead reference builder | As a maintainer, I want the dead, uncalled second reference-builder removed so future edits cannot patch the wrong copy. | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Activation stays fast | Recompile-on-activate for a typical project completes within the CLI performance budget; the red-first work records the **measured** end-to-end recompile time and the budget is set to that measurement (target < 2 s; if the measured value exceeds it, that is surfaced as a risk, not silently accepted). | Performance | High | Open |
| NFR-002 | Authored sections preserved | A catalog recompile changes only derived content (`catalog.references`, and the `metadata.generated_at` stamp only when the catalog itself changed); authored sections (`governance`, `directives`, activation lists, `overrides`) and `charter.md` remain byte-identical. | Correctness | High | Open |
| NFR-003 | Cross-platform worktree detection | Linked-vs-primary checkout detection works on Linux/macOS/Windows via git topology (git-dir vs git-common-dir), not by matching a `.worktrees/` path substring. | Portability | High | Open |
| NFR-004 | Red-first regression proof | Every finding lands an issue-pinned regression test that is RED through the pre-existing entry point before the fix and GREEN after. | Testability | High | Open |
| NFR-005 | Deterministic catalog order | `catalog.references` entries are emitted in a canonical, deterministic order (e.g. sorted by id) so a recompile of an unchanged store is diff-stable regardless of graph-walk or dict iteration order. | Correctness | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single catalog authority | All `catalog.references` writes route through the one canonical compiler (`compile_charter` / `write_compiled_charter`). No second or "minimal one-entry" writer is introduced — the whole-derived-section recompile is canonical. | Technical | High | Open |
| C-002 | Do not alter shared root resolver | The shared `find_repo_root` / `get_main_repo_root` follow-to-primary behavior (used far beyond charter) must not change; the worktree-safety policy lives at the charter-write command boundary only. | Technical | High | Open |
| C-003 | Reuse kernel git topology | Reuse the kernel `git_topology` probe for checkout detection; do not add a fourth root-resolution authority. | Technical | High | Open |
| C-004 | Reject minimal-writer design | An incremental "add one directive → one entry" append path is explicitly out of scope and rejected on single-authority grounds (it would be a competing authority the charter forbids). | Technical | High | Open |
| C-005 | Scope boundary | Out of scope: #4250's hosted-binding-recovery half + saas#1713; the synthesize-family recovery bugs #4042 / #4226; the generate-honesty siblings #4618 / #4615 / #4614. These are cross-referenced, not folded. | Business | High | Open |
| C-006 | Reconcile behavior-change tests | Pre-existing tests that assert `activate`/`deactivate` is a config-only write (parity-refresh, boundary-heal, activate-CLI, resynthesize-hotpath, activation-parity-guard) must be **deliberately enumerated and reconciled** to the new recompile-by-default behavior — never silently edited to green. | Technical | High | Open |

### Key Entities

- **`catalog.references`**: The compiled, derived reference set inside `charter.yaml`. Not
  authored by hand; recomputed from the activation lists + doctrine graph on each compile.
- **Charter store**: The `.kittify/charter/` tree. "Established" = a compiled `charter.yaml`
  exists; "fresh" = no compiled catalog yet.
- **Coherence guard / dangler**: The suite-tier check that fails when an activated artefact
  does not resolve in `catalog.references` (the #2524 dangler class).
- **Primary checkout vs linked worktree**: The repository-root checkout that owns the
  charter store, vs a linked git worktree that must not silently write into it.
- **Single compiler authority**: `compile_charter` / `write_compiled_charter` — the one
  code path that writes the derived catalog.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After activating one built-in directive on an established store, the coherence
  guard passes with **zero** manual edits (today it reds).
- **SC-002**: The command named in the coherence-guard remediation, run on an established
  store with a drifted catalog, clears the divergence in one invocation; `charter synthesize`
  on an established store no longer reports "fresh project".
- **SC-003**: A charter write command invoked from a linked worktree causes **zero**
  modifications to the primary checkout's charter store (it writes the invoking checkout or
  exits non-zero with actionable guidance).
- **SC-004**: A full catalog recompile leaves **zero** directive entries reading
  "Definition unavailable in bundled doctrine." for directives present in the authoritative
  bundled-doctrine enumeration, and a second consecutive recompile produces a **zero-line**
  diff of the `catalog.references` section (`metadata.generated_at` preserved when the catalog
  is byte-unchanged).

## Assumptions

- The grounding squad's reproductions on `main` @ `ba4e590142` are the current baseline;
  all four findings are still real and none is superseded (confirmed by the related-tickets
  lens).
- "Activate recompiles by default" (Decision `01M2XQRXWVK1DHVMYEBJNYDQMC`, resolved under
  delegated mission autonomy) is the chosen behavior; a config-only opt-out flag preserves the
  fast path.
- The exact F4b mechanism (DRG-closure ↔ typed-repository key/loader mismatch) will be pinned
  by a red-first repro at implement time; the spec requires the observable outcome
  (no silent placeholders), not a specific internal mechanism.
- The recompile-on-activate path runs the compiler with `from_interview=False` (the
  `charter pack apply --compile` pattern), so it needs no `CharterInterview`/`answers.yaml` —
  it recomputes only the derived catalog from the activation lists + doctrine graph.
- Worktree policy (FR-006) is **fail-closed** rather than honour-the-worktree: the issue's
  own finding is that a dedicated clone (not a git worktree) is required for safe charter
  authoring, so refusing from a linked worktree with a clear message is the decided, uniform
  behavior across all charter write commands.
