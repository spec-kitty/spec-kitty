# Mission Specification: Skill surface and upgrade integrity

**Mission Branch**: `ccr-11788f1f-qu75jg`
**Created**: 2026-10-06
**Status**: Draft
**Input**: Remediation of GitHub issues #4275 and #5801 (research squad findings, operator discovery answer DM `01M482ZZ73BDZYM0K2R1CD0SE3`).

## Intent Summary (confirmed)

A project operator runs `spec-kitty upgrade` or `spec-kitty doctor skills` to get the
commands their team shares (pack skills) onto their machine and to learn whether the
skill surface is healthy. Today both lie or fail: `upgrade` aborts with "Owner effect
conflict" when a configured tool's folder (e.g. `.claude/`) does not exist yet, and still
leaves the new version stamped; `doctor skills` reports healthy while in-force pack skills
were never installed, and `--fix` does not install them. After this mission, upgrade
succeeds on such a project and only records the new version once it has finished;
`doctor skills` reports every missing pack skill and fails, `--fix` installs it, and the
doctor also fails when no configured tool folder exists locally at all (one is enough).

**Invariant:** a health or upgrade command never reports success while the work it is
responsible for is absent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade a project that has no tool folder yet (Priority: P1)

An operator clones a kittified project whose configuration lists `claude`, but `.claude/`
does not exist. They run `spec-kitty upgrade --project --yes`.

**Why this priority**: It blocks the only command that installs pack skills, for every
fresh clone (#4275, #5801 "Related").

**Independent Test**: Kittify a temp project with `claude` configured, remove `.claude/`,
run upgrade; it exits 0 and recreates the tool surfaces.

**Acceptance Scenarios**:

1. **Given** a project with `claude` configured and no `.claude/`, **When** the operator runs upgrade, **Then** it completes and `.claude/` holds its skills, profiles and commands.
2. **Given** two surface contributors that want genuinely different results at one path, **When** upgrade plans them, **Then** it still refuses, and the message names both contributors.

---

### User Story 2 - A failed upgrade does not claim success (Priority: P1)

An upgrade fails after migrations or during the final surface repair.

**Why this priority**: A wrong stamp makes the next run report "already up to date" and
skip the work (#4275 second finding).

**Independent Test**: Force the final repair step to fail; the project's recorded version
and last-upgraded time are unchanged afterwards.

**Acceptance Scenarios**:

1. **Given** an upgrade whose final repair fails, **When** it exits, **Then** the recorded project version is the one from before the run.
2. **Given** an upgrade that succeeds, **When** it exits, **Then** the recorded version is the target version (unchanged behaviour), including the existing schema-stamp repair.

---

### User Story 3 - Doctor reports and installs missing pack skills (Priority: P1)

An operator's project has pack skills in force (an org pack's required skills, or an
activated skill) that were never installed for a configured tool. They run
`spec-kitty doctor skills`, then `--fix`.

**Why this priority**: A health command reporting success over absent work is a false
success (#5801).

**Independent Test**: Put a pack skill in force with an empty install record; doctor exits
1 with a `missing` finding; `--fix` installs it and a re-run exits 0.

**Acceptance Scenarios**:

1. **Given** an in-force pack skill not installed for a configured tool that accepts skills, **When** doctor runs, **Then** it reports one `missing` finding per skill and tool and exits 1.
2. **Given** an install record whose installed file was deleted, **When** doctor runs, **Then** it reports `missing`.
3. **Given** missing findings, **When** doctor runs with `--fix`, **Then** the skills are installed, the record updated, and the re-check is healthy.
4. **Given** an installed copy the user edited (drift), **When** doctor runs with `--fix`, **Then** that copy is not overwritten and the drift finding remains.
5. **Given** no pack skill in force, **When** doctor runs, **Then** it reports no pack-skill finding (unchanged).

---

### User Story 4 - Doctor fails when no configured tool folder exists (Priority: P2)

An operator's configuration lists tools, but none of their folders exist locally.

**Why this priority**: Operator-requested (discovery answer); the skill surface cannot be
healthy with no tool surface at all.

**Independent Test**: Configure `claude` and `codex`, remove both folders; doctor exits 1
with a finding naming them. Restore one; the finding disappears.

**Acceptance Scenarios**:

1. **Given** no configured tool folder exists, **When** doctor skills runs, **Then** it reports a finding and exits 1.
2. **Given** at least one configured tool folder exists, **When** doctor skills runs, **Then** no such finding is reported (not every tool is required).

### Edge Cases

- Tools that do not accept skill files are never reported as `missing`.
- A project with no pack skills in force and an empty install record stays silent.
- An unresolvable skill catalog keeps its existing `unresolvable` finding.
- `--fix` removing copies of skills no longer in force is reported in its output.
- An upgrade failing before any migration leaves no stamp change; the same holds for the no-migration path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Identical folder creation merges | As an operator, I want surface contributors that create the same absent folder in the same phase with the same resulting kind and mode to be planned as one step that keeps every contributor's claim, so that upgrade succeeds without the folder pre-existing. Covers both a tool folder shared by profiles, commands and skills, and the skills folder shared by several Agent Skills tools. | High | Open | [build] | no |
| FR-002 | Real conflicts still refuse, naming both | As an operator, I want a genuine conflict at one path (different mode, phase, action or content) to keep failing, and the message to name the path, both contributors and the aspect that differs, so that I can act on it. | High | Open | [build] | no — paired with FR-001 on the same fixture |
| FR-003 | Failed upgrade restores the recorded version | As an operator, I want the project's recorded version, last-upgraded time and schema version restored to their pre-run values whenever the upgrade fails, including a failure in its final surface repair, on both the migration and the no-migration path, so that a failed run is retried next time. | High | Open | [build] | no |
| FR-004 | Missing pack skill finding | As an operator, I want doctor skills to report each in-force pack skill not installed for a configured tool that accepts skills, and each recorded copy whose file is absent, as `missing`, and to exit 1, so that the doctor never reports a false healthy. | High | Open | [build] | no |
| FR-005 | --fix installs missing pack skills | As an operator, I want doctor skills --fix to install missing pack skills through the same canonical pack-skill installation that `charter activate skill` uses, re-check, and report (never overwrite) a copy whose content differs from its record, so that one command repairs the surface. | High | Open | [build] | no |
| FR-006 | No tool folder at all fails | As an operator, I want doctor skills to fail with a finding when none of the configured tools' folders exist locally, while one existing folder suffices, so that an absent surface is never healthy. | Medium | Open | [build] | no — paired with the one-folder-present case |
| FR-007 | Documentation lists the new kinds | As a pack author, I want the pack-skill how-to, the pack-skills ADR (amendment) and the changelog to list the `missing` kind and the no-tool-folder finding so that the doctor's output is explained. | Medium | Open | [build] | yes — reviewed, not tested |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Red-first proof | Each of FR-001..FR-006 has a regression test that fails on the planning base and passes at the work package's final commit. | Reliability | High | Open |
| NFR-002 | Coverage | New and changed lines reach at least 90% diff coverage. | Maintainability | High | Open |
| NFR-003 | Complexity | No touched function exceeds cyclomatic complexity 15. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One authority | The folder-merge rule lives in one place; an existing narrower merge either delegates to it or is documented as kept. No second "missing skill" predicate is invented if an existing one can be reused. | Technical | High | Open |
| C-002 | User-owned files | Fixes never overwrite or delete a user-owned or edited file that is not manifest-tracked as package-owned. | Technical | High | Open |
| C-003 | Out of scope | The skill verifier's and the upgrade pre-check's own blind spot to never-installed skills is not fixed here (follow-up). | Business | Medium | Open |
| C-004 | Keep schema-stamp repair | The existing schema-version repair on already-current projects keeps working under the restore design. | Technical | High | Open |
| C-005 | Configured tools come from configuration | The tool set is the project's agent configuration. A configured tool whose folder is absent is still configured: upgrade's surface repair recreates it and the doctor treats it as configured; removing a tool goes through `agent config remove`. Migrations keep skipping absent agent folders (ADR #6). | Technical | High | Open |
| C-006 | Additive doctor contract | The `doctor skills --json` payload keeps every existing field; `missing` and the no-tool-folder finding are additive. The in-force skill set comes from the existing charter resolver; no second in-force rule is added. | Technical | High | Open |

### Key Entities

- **Surface effect**: one planned change at one path, with an owner, phase, action and before/after state.
- **Pack skill finding**: a doctor result for a pack skill; kinds drift, stale, orphaned, unresolvable, and new `missing`.
- **Configured tool**: a tool listed in the project's agent configuration, with a local folder.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Upgrade succeeds on 100% of tested projects whose configured tool folder is absent — [build] · no-op passable: no
- **SC-002**: After a forced failure in the final surface repair (not only in a migration), the recorded version equals the pre-run version in 100% of tested cases — [build] · no-op passable: no
- **SC-003**: Doctor reports zero false-healthy results across the tested missing-skill and no-folder scenarios — [build] · no-op passable: no
- **SC-004**: One `doctor skills --fix` run brings a project with missing pack skills to a healthy re-check — [build] · no-op passable: no

## Assumptions

- "Charter-supported harness folders" means the folders of the tools configured in `.kittify/config.yaml`.
- `--fix` installs with the same automatic consent as `charter activate skill`.
