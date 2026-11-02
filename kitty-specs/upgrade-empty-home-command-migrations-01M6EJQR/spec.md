# Mission Specification: upgrade — three migrations read the operator's home directly

**Mission Branch**: `kitty/mission-upgrade-empty-home-command-migrations-01M6EJQR`
**Created**: 2026-11-02
**Status**: Draft
**Input**: GitHub issue #6954 — "upgrade: three more migrations read ~/.kittify directly and were not covered by the #6551 fix"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second machine answers `upgrade` the same as the first (Priority: P1)

An operator runs `spec-kitty upgrade --project` on a project that is already converged,
on a machine where `upgrade` is the first spec-kitty command and `~/.kittify` has never
been bootstrapped. The upgrade must reach the same decision about the project's
project-local generated command files as it would on the original machine: it must not
keep or delete them because of *who* ran it or *which* machine it ran on.

**Why this priority**: this is the whole point of #6954 and the continuation of #6551.
A migration that answers from the operator's home lets the same commit produce two
different project states, which breaks the ledger's `skipped`-is-re-evaluated
idempotency (ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` §3).

**Independent Test**: build a project stamped at the running CLI version, carrying one
generated project-local command file (version marker present) and a ledger whose
`3.1.2_globalize_commands` record is `skipped`; run the real `upgrade` command with
`SPEC_KITTY_HOME` pointed at an empty directory; assert the file is removed and the
upgrade auto-commits the removal.

**Acceptance Scenarios**:

1. **Given** a project stamped at or above the migration's target version **When** the
   migration classifies a version-marked project-local command file **Then** it decides
   from the project's stamp alone and does not consult the operator's home.
2. **Given** the same project, same commit, one run with an empty `SPEC_KITTY_HOME` and
   one with a bootstrapped home **When** both upgrades finish **Then** both leave the
   same tracked state.
3. **Given** a project **without** a readable `metadata.yaml` stamp (or stamped below the
   migration's target version) **When** the migration classifies a file **Then** the
   historical home check still applies — the legacy repair path is unchanged.

---

### User Story 2 - A converged project's upgrade is a no-op on a fresh machine (Priority: P1)

An operator takes a converged project (a bootstrapped home, then a pass that changes
nothing) to a fresh machine and runs `upgrade --project` there with an empty
`SPEC_KITTY_HOME`. No tracked change and no auto-commit: the head does not move.

**Why this priority**: this is the regression shape #6954 asks for, applied to the three
migrations that read the home directly rather than through `uses_centralized_runtime()`.

**Independent Test**: converge a project, un-bootstrap the home, run `upgrade --project`,
and assert `git status --porcelain` is empty and `HEAD` is unchanged, with the three
migrations actually re-evaluated rather than settled.

**Acceptance Scenarios**:

1. **Given** a converged project whose `2.1.3_restore_prompt_commands`,
   `2.1.4_enforce_command_file_state` and `3.1.2_globalize_commands` records are
   `skipped` (the only state in which the ledger re-evaluates them) **When** the upgrade
   runs under an empty home **Then** no tracked file changes and the head does not move.
2. **Given** the same fixture **When** the same project-local command file is present
   **Then** a probe can still observe a file being removed, so "nothing changed" is not a
   probe that cannot see anything.

---

### User Story 3 - The command-template source does not depend on the home (Priority: P2)

The two command-file migrations resolve their templates from the packaged doctrine tree
first. On a machine whose home is empty they resolve the same templates, so the rendered
command files are byte-identical.

**Why this priority**: it is the other half of the issue. If the answer is "these two
never reach the home fallback", that must be pinned by a test rather than assumed.

**Independent Test**: call the template-source resolver with `SPEC_KITTY_HOME` pointed at
an empty directory and assert it returns the packaged doctrine `mission-steps` directory,
not a path below `SPEC_KITTY_HOME`.

**Acceptance Scenarios**:

1. **Given** an empty `SPEC_KITTY_HOME` **When** the resolver runs **Then** it returns a
   directory inside the installed package, and a bootstrap of the home does not change
   the answer.

---

### Edge Cases

- `metadata.yaml` present but unparseable, dated below 2.0.0, or numeric (YAML float):
  the migration keeps the legacy answer rather than treating the project as modern.
- A project-local command file with no version marker: still `hold`ed for manual review —
  the user-authored safety rule is unchanged.
- A stamped project whose global copies are genuinely absent (a CI runner that only ever
  runs `upgrade`): the migration removes the generated project-local copies anyway,
  because the CLI installs the global copies at the next command; the marker proves the
  file is ours. This trade-off is stated in the changelog.
- The legacy `.codex/prompts` root has no agent key: the exact-global-file check keeps its
  historical shape rather than guessing.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Project-stamped classification | As an operator, I want the command-globalization decision to come from the project's own stamp so that the same commit gives the same answer on every machine. | High | Open | [build] | no |
| FR-002 | Home kept for unstamped shapes | As an operator, I want a project with no readable stamp (or one below the migration's target version) to keep the historical home check so that legacy repair is unchanged. | High | Open | [ratchet] | no |
| FR-003 | Empty-home regression test | As a maintainer, I want a regression test at the real `upgrade` entry point so that a converged project on a fresh machine produces no tracked change and no auto-commit. | High | Open | [build] | no |
| FR-004 | Home-equivalence assertion | As a maintainer, I want the two homes compared on one commit so that a home-dependent outcome is caught even when the empty-home run happens to match. | High | Open | [build] | no |
| FR-005 | Template-source pin | As a maintainer, I want the 2.1.3/2.1.4 template resolver pinned as home-independent so that its "packaged doctrine wins" order is not assumed. | Medium | Open | [ratchet] | no |
| FR-006 | Canonical global-command path | As a maintainer, I want the exact-global-file check to ask the canonical owner where global agent commands live rather than re-deriving it, so that no second source of truth appears. | Medium | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic re-evaluation | For a project with a readable stamp, `detect()`/`apply()` return the same result with `SPEC_KITTY_HOME` set to an empty directory and to a bootstrapped home: 0 differing outcomes across the two runs of the new tests. | Reliability | High | Open |
| NFR-002 | Bounded test cost | The new regression module runs in under 180 seconds for the whole file on the standard shard, and adds no session-scoped fixture. | Performance | Medium | Open |
| NFR-003 | No weakened gate | The user-authored `hold` rule (no version marker) and the "only generated files are removed" invariant remain asserted by a test; no test is skipped, xfailed or loosened to pass. | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Independent of #6946 | This mission must not depend on unmerged PR #6946: the tests and fix stand alone, and no file that #6946 creates is claimed here. | Technical | High | Open |
| C-002 | Issue scope | One regression test plus the fix it proves; no speculative refactor of the migration framework, the ledger, or `uses_centralized_runtime()` (owned by #6946). | Business | High | Open |
| C-003 | Changelog fragments | The user-facing note lands in a per-PR fragment under `docs/changelog/unreleased/`, never as an `[Unreleased]` entry in `CHANGELOG.md` (since #6988). | Regulatory | High | Open |

### Key Entities

- **Project stamp**: `.kittify/metadata.yaml` `spec_kitty.version` — the only project-local
  evidence of which CLI generation last touched the project.
- **Migration record**: a row in `.kittify/migration-ledger.jsonl`; `skipped` is
  re-evaluated on every run, `success` settles the migration.
- **Generated project-local command file**: `spec-kitty.<command>.<ext>` under an agent
  command directory, carrying a `<!-- spec-kitty-command-version: … -->` marker in its head.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With `SPEC_KITTY_HOME` empty, a stamped project's generated project-local command file is removed by the upgrade and the removal is auto-committed (0 files kept on the stamped path). — [build] · no-op passable: no
- **SC-002**: The bootstrapped-home and empty-home runs of the same commit leave identical `git status --porcelain` output and identical `HEAD` (2 of 2 runs agree). — [build] · no-op passable: no
- **SC-003**: `tests/upgrade/` unit tests for the touched modules pass, including the new home-equivalence and hold-rule tests. — [ratchet] · no-op passable: no
- **SC-004**: No regression in the existing upgrade suite: the modules covering `m_2_1_3`, `m_2_1_4`, `m_3_1_2` and `compat` stay green. — [ratchet] · no-op passable: no
