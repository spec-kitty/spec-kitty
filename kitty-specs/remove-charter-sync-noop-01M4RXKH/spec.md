# Mission Specification: Remove the charter sync no-op compatibility command

**Mission Branch**: `issue-5828-remove-charter-sync-noop`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #5828 — "Remove the `charter sync` no-op compatibility command". Per ADR `2026-10-06-2` §7 (full cutover: no aliases, no shims) and OD-3/OD-5 of the #3732 Mission spec.

## Context

`spec-kitty charter sync` does nothing and says so. Since #4679 it prints a "kept for
compatibility only … Nothing to do." line; the prose→triad extraction it once ran was
retired (IC-04 / #2773). A command that exists only to announce it does nothing is the
same residue ADR `2026-10-06-2` §7 removes. This mission deletes the command surface and
every reference/hint that points at it.

**Critical distinction (grounded):** the load-bearing `charter.activation.sync` **module**
(`load_governance_config`, `load_directives_config`, `ensure_charter_bundle_fresh`,
`require_canonical_governance`, `SyncResult`, and `sync()` — consumed by the resolver,
compiler, and `charter generate`) is **out of scope and must not be touched**. Only the
`spec-kitty charter sync` CLI surface is removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator/contributor sees one honest charter surface (Priority: P2)

An operator or contributor working with charter governance no longer encounters a command
that exists only to say it does nothing, nor any help text, status hint, skill reference,
doc, or emitted-file header that recommends running it. Running `spec-kitty charter sync`
now fails with the plain unknown-command error, like any other removed name.

**Why this priority**: P2 tidy-up (usability / domain:cli). It carries no behaviour change
for any real command; it removes contradictory residue ahead of the 4.0.0 GA so the breaking
removal rides the major version.

**Independent Test**: Invoke `spec-kitty charter sync` and assert Typer emits the standard
"No such command" error with a non-zero exit; grep the shipped source surfaces (CLI,
generated reference, skills, docs, emitted YAML header) and assert no live
`spec-kitty charter sync` reference or recovery hint remains.

**Acceptance Scenarios**:

1. **Given** a project on 4.0.0rc7+, **When** the operator runs `spec-kitty charter sync`, **Then** the CLI exits non-zero with the standard unknown-command error (no bespoke no-op banner).
2. **Given** the shipped CLI, **When** shell completion / `--help` / the generated CLI reference is produced, **Then** `charter sync` does not appear.
3. **Given** `charter status` reports a stale charter, **When** the human readout is rendered, **Then** it does not direct the operator to `spec-kitty charter sync` (the deeper STALE-verdict rework stays with #4042).
4. **Given** every other `charter` subcommand (`status`, `generate`, `synthesize`, `context`, `interview`, `lint`, `resynthesize`, `activate`, `preflight`, `bundle`, `pack`, `mission-type`), **When** it is invoked, **Then** its behaviour is byte-for-byte unchanged.

### Edge Cases

- A caller importing the `charter.activation.sync` **module** (e.g. `charter generate`) keeps working — the module is untouched.
- The `charter status` STALE display itself is unchanged (that verdict is #4042's scope); only the removed-command recommendation line is dropped.
- `charter sync --force` no longer has a fail-open path (its removal moots #2992).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Delete the `charter sync` command module | As a contributor, I want `src/specify_cli/cli/commands/charter/sync.py` and its registration (`charter/__init__.py` import + `__all__`) gone so the command no longer resolves. | High | Open | [build] | no — paired with FR-002's invoke-and-expect-unknown-command control |
| FR-002 | `charter sync` fails with the plain unknown-command error | As an operator, I want the removed name to behave like any other unknown command (non-zero exit, standard Typer error), not a bespoke banner. | High | Open | [build] | no — asserts a specific exit/stderr shape on the live app |
| FR-003 | Remove the command's dedicated tests; preserve module-level tests | As a contributor, I want the four `test_sync_command_*` CLI tests removed and the `charter status` tests' pointless `["sync"]` setup dropped, while the `charter.activation.sync` **module** tests stay green. | High | Open | [build] | no — module tests still execute real code |
| FR-004 | Update the architectural gates that enumerate the command | As a maintainer, I want `tests/architectural/test_no_retired_subsystems.py` (`_REQUIRED_CLI_PATHS`) and `test_json_contract_enumeration.py` to stop requiring/enumerating `charter sync`, so they reflect the real surface. | High | Open | [build] | no — gates re-run against the live tree + regenerated manifest |
| FR-005 | Regenerate the completion manifest and the generated CLI reference | As a user, I want `src/specify_cli/_completion_manifest.json` and `docs/api/cli-commands.md` regenerated so completion, `--help`, and the reference no longer list `charter sync`. | High | Open | [build] | no — freshness + parity gates compare against the live CLI |
| FR-006 | Remove every live `charter sync` recovery hint / reference | As an operator/agent, I want the `charter status` stale-hint, the preflight `--auto-refresh` help + `references_refresh` docstring, the governance-emit YAML header, the `spk-charter-governance` skill sources + command-map, the synthesize-doctrine how-to, the `charter-commands.md` section, and the two project-charter prose mentions to stop naming the removed command. | Medium | Open | [build] | no — offering-snippet parity gate + targeted greps assert absence |
| FR-007 | Preserve the `charter.activation.sync` module untouched | As a maintainer, I want the load-bearing module (loaders, bundle-freshness, `sync()`, `SyncResult`) unchanged so the resolver, compiler, and `charter generate` keep working. | High | Open | [build] | no — resolver/compiler/charter-generate tests exercise it |
| FR-008 | Changelog note for the breaking removal | As a user, I want an `[Unreleased]` CHANGELOG entry recording the removal with the `(#5828)` ref and the new unknown-command behaviour. | Medium | Open | [folded] | yes — documentation-only |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No gate suppressions | Zero new `# noqa`, `# type: ignore`, per-file ignores, or gate allowlist widenings are introduced to make gates pass; gates stay green honestly. | Maintainability | High | Open |
| NFR-002 | Terminology canon preserved | No `feature`-for-Mission regressions introduced; `test_no_legacy_terminology.py` stays green. | Correctness | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Edit canonical sources only | Edit canonical SOURCES (`src/charter/offering/skills/**`, `docs/**`, generators) — never generated agent copies (`.claude/`, `.agents/skills/`, …). | Technical | High | Open |
| C-002 | Behaviour-preserving for real commands | No change to any other `charter` subcommand's behaviour; no touching activation/context surfaces or the `charter.activation.sync` module. | Technical | High | Open |
| C-003 | Scope fence vs #4042 | Do not rework the `charter status` STALE verdict (that is open bug #4042); only neutralize the dangling `charter sync` recommendation. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `spec-kitty charter sync` is absent from the Typer command tree, `--help`, shell completion, and the regenerated `docs/api/cli-commands.md`; invoking it exits non-zero with the standard unknown-command error. — [build] · no-op passable: no
- **SC-002**: `make test-fast`, the charter/CLI test dirs covering the command, `tests/architectural/test_no_legacy_terminology.py`, the completion-manifest freshness gate, and the CLI-reference parity gate are all green with zero new suppressions. — [build] · no-op passable: no
- **SC-003**: No live `spec-kitty charter sync` reference or recovery hint remains in shipped source (CLI, generated reference, `src/charter/offering/skills/**`, `docs/**` guides, emitted YAML header, project charter prose); only historical/rationale comments that explain *why the sequence is no longer `charter sync`* may remain. — [build] · no-op passable: no
- **SC-004**: The `charter.activation.sync` module and every other `charter` subcommand are unchanged; their tests stay green. — [build] · no-op passable: no
