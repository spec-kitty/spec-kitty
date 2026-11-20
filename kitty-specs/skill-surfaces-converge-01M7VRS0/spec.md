# Mission Specification: Skill surfaces converge

**Mission Branch**: `kitty/mission-skill-surfaces-converge-01M7VRS0` (lands on `issue-7700-skill-surfaces-converge`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: Operator brief (orchestrator session), closing #7700, #5983, #7722, #7723, #2460, #5281, #7725, and #2527 if it reproduces. #7724 is already closed.

## Intent Summary

- **Primary actor**: a Spec Kitty user who upgraded the CLI and whose machine still holds skill and command copies written by older releases.
- **Trigger**: any Spec Kitty command (the startup sync), `spec-kitty upgrade`, or `spec-kitty doctor {tool-surfaces,skills,command-files} [--fix]`.
- **Desired outcome**: a skill file that is byte-identical to something Spec Kitty itself shipped is refreshed to today's render; anything Spec Kitty cannot prove it wrote is kept and *reported*, never silently kept and never certified as current. The three repair entry points reach the same verdict.
- **Invariant**: unproven content is never deleted or overwritten without consent (charter, User Customization Preservation). Proof is byte equality with a shipped render or an ownership record, never a name heuristic.
- **Boundary**: core-shipped skills (`src/charter/offering/skills/`) and their install surfaces only. No pack contract, no packs pin change.

Operator rulings already given (binding for this spec):

- #7700 (a): a frozen digest list of historically shipped renders per skill path; byte-matching files count as proven generated and are refreshed.
- #7700 (b): preserved-stale global skills are reported by `doctor tool-surfaces`; the user-global skill version stamp is not written as current while any canonical destination is preserved.
- #5983 is folded in: content matching no shipped render stays under the consent rule and is reported, never kept silently.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stale shipped global skills are refreshed (Priority: P1)

A user's `~/.claude/skills/` holds files an older release wrote, before any ownership record existed. After the upgrade, the next Spec Kitty command refreshes every file whose bytes equal a historically shipped render of that same skill path.

**Why this priority**: agents keep loading superseded doctrine today (#7700); this is the user-visible defect.

**Independent Test**: seed a global skill root with a historical render of one skill file and no ownership record; run the global skill assessment; the file is planned for refresh and the version stamp is written.

**Acceptance Scenarios**:

1. **Given** a global skill file byte-equal to a historical shipped render of the same path and no ownership record, **When** the startup sync runs, **Then** the file is refreshed to today's render and the version stamp is written as current.
2. **Given** a global skill file that matches no shipped render, **When** the startup sync runs, **Then** the file is kept unchanged, the version stamp is not written as current, and `doctor tool-surfaces` reports the file as kept with the reason and a remedy.

---

### User Story 2 - Kept and retired copies are reported, never silent (Priority: P1)

A user edited a skill that has since been retired. The sync keeps it (it is theirs now) and `doctor tool-surfaces` names it as an edited retired skill.

**Why this priority**: #5983; user edits must not disappear or linger without notice.

**Independent Test**: seed an edited copy of a retired skill in a global root; run the doctor; the copy is listed and nothing is deleted.

**Acceptance Scenarios**:

1. **Given** an edited copy of a retired skill in a global root, **When** `doctor tool-surfaces` runs, **Then** it is reported as kept-edited-retired and remains on disk byte-for-byte.
2. **Given** an unedited retired copy that is byte-equal to a shipped render, **When** the sync runs, **Then** it is retired (removed) as proven generated.

---

### User Story 3 - The repair commands agree (Priority: P2)

`doctor skills --fix` repairs a command skill whose ownership record captured corrupted bytes, the same way `doctor tool-surfaces --kind command-skill --fix` and `upgrade` already do (#5281). A copy-mode retired skill whose recorded hash still matches is detected by verification, so the retirement drain runs (#2460).

**Independent Test**: seed a self-consistent corrupted command skill; `doctor skills --fix` converges it. Seed a hash-clean retired managed-skill entry; verification reports it and the repair drains it.

**Acceptance Scenarios**:

1. **Given** a command skill whose on-disk bytes match the recorded hash but differ from today's canonical render, **When** `doctor skills --fix` runs, **Then** the file is re-rendered and the next `doctor skills` reports no issue.
2. **Given** a managed project skill entry of a retired skill whose file still matches its recorded hash, **When** `doctor tool-surfaces --fix` runs, **Then** verification reports it, the retirement drain removes it, and its record leaves the manifest.

---

### User Story 4 - Moving one agent root does not orphan the others (Priority: P2)

A user sets `CLAUDE_CONFIG_DIR` (or `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME`) to a directory outside their home. Files the CLI recorded under `~/.agents/skills` stay proven and keep refreshing (#7722).

**Independent Test**: record an inventory with every root under home, then move one root outside home and re-assess; files under the unmoved roots are still owned.

**Acceptance Scenarios**:

1. **Given** an ownership record written while every root was under home, **When** one root moves outside home, **Then** previously recorded files under the other roots are still proven (refreshed or retired as before), with no "Unproven existing asset" disposition for them.
2. **Given** an ownership record written in the old format, **When** the next assessment runs, **Then** its entries keep resolving and the record is rewritten once in the new format.

---

### User Story 5 - Leftover copies under the old root are reported (Priority: P3)

With `CLAUDE_CONFIG_DIR` set, Spec Kitty-owned copies an earlier release left in `~/.claude/commands` and `~/.claude/skills` are listed by `doctor command-files` and `doctor skills` with a cleanup hint (#7723).

**Acceptance Scenarios**:

1. **Given** `CLAUDE_CONFIG_DIR` set and proven Spec Kitty copies under `~/.claude/{commands,skills}`, **When** either doctor command runs, **Then** the proven copies are listed with a cleanup hint and nothing is written or deleted.
2. **Given** an unproven file in the same place, **When** the doctor runs, **Then** it is not listed as a Spec Kitty leftover.
3. **Given** `CLAUDE_CONFIG_DIR` unset, **When** either doctor command runs, **Then** its output is unchanged.

---

### User Story 6 - The first-mission skill says Mission (Priority: P3)

The public skill `spk-start-first-feature` is renamed `spk-start-first-mission` (#7725). Old unedited copies retire through the normal retired-skill path.

**Acceptance Scenarios**:

1. **Given** the shipped skills, **When** `git grep spk-start-first-feature -- src docs` runs, **Then** it returns only retired-name entries and changelog text.
2. **Given** an unedited installed `spk-start-first-feature` copy, **When** the sync runs, **Then** it is retired.

### Edge Cases

- A file byte-equal to a historical render of a *different* skill path is not proven for this path.
- A symlink, a directory or an unreadable node at a skill path is never treated as proven.
- A historical render list that is missing or malformed fails closed: nothing is refreshed on its authority, and the existing consent rule applies.
- Several roots resolve to the same directory: no duplicate reports.
- A preserved file in a *non-canonical* name (a user's own skill) does not block the version stamp and is not reported as stale.
- Windows paths: ownership records must survive drive-letter roots.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Historical-render proof source | As a user, I want a file byte-equal to a historically shipped render of the same skill path to count as proven generated, so that it is refreshed instead of kept forever. | High | Open | [build] | no — paired with the non-matching file on the same fixture (FR-002) |
| FR-002 | No current stamp while canonical destinations are preserved | As a user, I want the user-global skill version stamp not to be written as current while any canonical destination is kept, so that a stale install is never certified. | High | Open | [build] | no — same fixture as FR-001 with one non-matching file |
| FR-003 | Doctor reports preserved-stale global skills | As a user, I want `doctor tool-surfaces` to list each kept canonical global skill file with its reason and a remedy, so that nothing stale is silent. | High | Open | [build] | no |
| FR-004 | Doctor reports edited retired global skills | As a user, I want an edited copy of a retired skill in a global root reported as kept and mine, never deleted, so that my edits are visible and safe (#5983). | High | Open | [build] | no — paired with the unedited retired copy that is retired |
| FR-005 | `doctor skills --fix` verifies against the canonical render | As a user, I want `doctor skills --fix` to repair a command skill whose recorded hash matches corrupted bytes, so that it agrees with `doctor tool-surfaces` and `upgrade` (#5281). | High | Open | [build] | no — the existing strict-xfail test flips |
| FR-006 | Verify-side retired-orphan detection | As a user, I want verification to report a managed skill entry of a retired skill whose file still matches its recorded hash, so that the retirement drain runs (#2460). | Medium | Open | [build] | no |
| FR-007 | Ownership records survive a moved root | As a user, I want ownership records of the user-global assets to stay valid when one agent root moves outside home, so that the other roots' files stay proven (#7722). | High | Open | [build] | no — the same files are unproven on the base |
| FR-008 | Old-format ownership records keep resolving | As a user, I want ownership records written by earlier releases to keep resolving and be rewritten once in the new format, so that upgrading does not orphan them. | High | Open | [build] | no |
| FR-009 | Leftover old-root copies are reported | As a user with `CLAUDE_CONFIG_DIR` set, I want `doctor command-files` and `doctor skills` to list proven Spec Kitty copies under `~/.claude/{commands,skills}` with a cleanup hint, writing nothing (#7723). | Medium | Open | [build] | no — paired with the unset-variable fixture (unchanged output) |
| FR-010 | Rename the first-mission skill | As a user, I want the skill named `spk-start-first-mission`, with the old id retired and every reference repointed, including the "New feature" wording (#7725). | Medium | Open | [build] | no |
| FR-011 | One verdict across entry points | As a user, I want the startup sync, `upgrade` and `doctor --fix` to reach the same refresh/keep verdict for the same file, so that no command certifies what another would keep (DIRECTIVE_044, #5215). | High | Open | [build] | no |
| FR-012 | #2527 disposition | As a maintainer, I want #2527 reproduced on `a053b674` first: folded in if it reproduces, otherwise closed as stale with the evidence. | Medium | Open | [folded] | no — decided by a recorded reproduction |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Startup cost | The historical-render lookup adds no more than one file read per assessment and no git invocation at runtime; the startup sync's wall time on the existing fixture stays within 10% of the base. | Performance | Medium | Open |
| NFR-002 | No data loss | Zero unproven bytes are deleted or overwritten across every new test fixture (asserted byte-for-byte). | Reliability | High | Open |
| NFR-003 | Quality gates | ruff, ruff format (`--force-exclude`) and mypy report zero issues on changed files; no new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Frozen, reviewed proof data | The historical digest list is generated from git history by a committed tool, frozen in the repository and reviewed; it is never computed at runtime. | Technical | High | Open |
| C-002 | Never delete unproven content | No flow added or changed here deletes or overwrites content it cannot prove it wrote. Doctor reporting writes nothing. | Technical | High | Open |
| C-003 | Scope | Core-shipped skills and their install surfaces only; no pack contract and no packs pin change. Non-goals: #6471, #6472, #2904, #5993 (overlaps noted, not fixed). | Business | High | Open |
| C-004 | Generated index untouched | `docs/development/docs-retrieval-index.yaml` is never hand-edited. | Technical | High | Open |
| C-005 | Red-first | Every FR lands with a test that fails on `a053b674` and passes on the final commit, committed before the fix. | Technical | High | Open |

### Key Entities

- **Historical render list**: per skill path, the set of digests of every render Spec Kitty shipped for that path.
- **Ownership record (global asset inventory)**: what the CLI wrote under the user-global roots, with the digest it wrote.
- **Kept file report**: a file the sync or a repair kept, with its reason (unproven, edited, edited retired, old-root leftover) and a remedy.

## Success Criteria *(mandatory)*

- **SC-001**: On a machine seeded with the six #7700 files (historical renders), one startup sync leaves 0 of them stale. — [build] · no-op passable: no
- **SC-002**: For a seeded non-matching file, the doctor names it in 100% of runs and the version stamp stays not-current. — [build] · no-op passable: no
- **SC-003**: `doctor skills --fix`, `doctor tool-surfaces --fix` and `upgrade` leave the same seeded corrupted command skill in the same converged state. — [build] · no-op passable: no
- **SC-004**: `git grep spk-start-first-feature -- src docs` returns only retired-name entries and changelog text. — [build] · no-op passable: no

## Decisions

- **Historical digest list home** (decision `01M7VRSCZZPMQHPVF9HP5T4HM9`, operator ruling 2026-11-20): a reviewed package-data JSON file plus a committed generator that reads git history. The list is append-only; a test fails when a digest is dropped or a current render is missing, so a PR that edits a shipped skill re-runs the generator. `RELEASE_CHECKLIST.md` gains a step.
- **Old-root leftovers** (decision `01M7VRSF1T1ENCAMW2SACF5MS3`, operator ruling 2026-11-20): report only in this Mission: list proven files with a removal hint, delete nothing. A P3 follow-up issue for opt-in `--fix` removal of byte-proven files under the old root is filed and linked to #7723.

## Assumptions

- Historical renders are the raw shipped bytes of each skill file, plus today's frontmatter projection applied to each historical `SKILL.md`; older builds' own projection output that differs from both stays under the consent rule and is reported.
- The source roots for history are `src/doctrine/skills/` and `src/charter/offering/skills/`.
- `pr:pause-ci` and the PR process are owned by the orchestrator; this spec does not change CI.
