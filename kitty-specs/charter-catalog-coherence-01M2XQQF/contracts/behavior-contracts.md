# Behavior Contracts: Charter Activation Catalog Coherence (#4785)

Executable-intent contracts, one per finding. Each is the observable contract a red-first
regression test pins (RED through the pre-existing entry point before the fix, GREEN after).
No YAML frontmatter blocks here by design (prose contracts; the round-trip corpus does not
apply).

## Contract C1 — Activation is coherent-by-construction (WP03 / FR-001, FR-002, FR-003)

- **Given** an established charter store whose coherence guard passes,
- **When** `charter activate directive <built-in-directive-not-in-catalog>` runs (default, no flags),
- **Then** `catalog.references` gains the matching `DIRECTIVE:<id>` entry AND
  `tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent`
  passes with no manual edit.
- **And** `charter deactivate directive <id>` removes the entry and keeps the guard green.
- **And** `charter activate directive <id> --no-compile` writes only the activation list and
  prints an explicit notice that the catalog was not recompiled.
- **Recompile source**: `compile_charter(..., from_interview=False)` — no `CharterInterview`/
  `answers.yaml` required.

## Contract C2 — Remediation guidance names a command that works (WP03 strings + WP04 fresh-gate / FR-004, FR-005)

- **Given** a catalog divergence on an established store,
- **When** the coherence guard emits its remediation suggestion,
- **Then** the suggestion names `charter generate` (or `activate --resynthesize`) — **never**
  `charter synthesize` — and `RESYNTHESIZE_HELP` text agrees.
- **And Given** an established store with `charter.yaml` present but no `.kittify/charter/generated/`,
- **When** `charter synthesize` runs,
- **Then** it does NOT report "fresh project" and does NOT short-circuit to a minimal-doctrine seed
  (the fresh-project predicate keys on actual catalog emptiness, not `generated/` absence).

## Contract C3 — Charter writes are worktree-safe (WP02 helper + WP03/WP04 wiring / FR-006, NFR-003)

- **Given** a maintainer inside a linked git worktree,
- **When** they run any charter write command (`activate`, `deactivate`, `generate`,
  `synthesize`, `activate --resynthesize`),
- **Then** the command exits non-zero with an actionable message
  ("use a repository-root checkout or dedicated clone for charter authoring") and the PRIMARY
  checkout's `.kittify/charter/` is **not modified** (zero cross-checkout writes).
- **And** the same command run from the repository-root checkout / a dedicated clone succeeds.
- **And** `activate --resynthesize` never lands the activation flag and the catalog recompile in
  different checkouts (no split-brain).
- **Detection**: kernel `git_topology` (git-dir vs git-common-dir); git-absent degrades safely
  (treated as not-a-linked-worktree); no `.worktrees/` path-substring matching.
- **Non-goal**: the shared `find_repo_root`/`get_main_repo_root` follow-to-primary behavior is
  unchanged.

## Contract C4 — Recompiled catalog is complete and stable (WP01 / FR-007, FR-008, FR-009, NFR-002, NFR-005)

- **Given** a full catalog recompile,
- **When** it completes,
- **Then** every directive present in the authoritative typed-doctrine enumeration resolves to
  its real `summary` — **zero** entries read `Definition unavailable in bundled doctrine.` for a
  directive that has a bundled definition.
- **And Given** a directive id with genuinely no bundled definition,
- **Then** it surfaces through the `graph.unresolved` diagnostics channel, not as a silent
  placeholder `catalog.references` row.
- **And Given** an unchanged charter store,
- **When** the catalog is recompiled twice consecutively,
- **Then** the second recompile produces a **zero-line diff of the `catalog.references` section**
  (entries in canonical, deterministic order; `metadata.generated_at` preserved because the
  catalog content is byte-unchanged).
- **And** authored sections (`governance`, `directives`, activation lists, `overrides`) and
  `charter.md` remain byte-identical (NFR-002).
- **And** the dead, uncalled `_build_references_from_yaml` reference-builder is removed (FR-009).
