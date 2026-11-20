# Mission Specification: Keep a project-local Codex home ignored after agent-gitignore narrowing (#7729)

**Mission Branch**: `fix/7729-codex-home-gitignore`
**Created**: 2026-11-20
**Status**: Draft
**Input**: Operator brief (scheduled run) for P0 #7729: "`4.0.0rc8_narrow_agent_gitignore` un-ignores most of a project-local CODEX_HOME, and only the clone running the upgrade is warned."
**Mission kind**: bugfix (Charter Standing Order 4; `test-first-bug-fixing`, `disciplined-defect-diagnosis`)

## Intent Summary

- **Primary actor**: a developer whose project folder `.codex/` is also their Codex home (`CODEX_HOME=<project>/.codex`, advice Spec Kitty itself gave in 2025), working in any clone of a project upgraded to 4.0.0rc8 or later.
- **Trigger**: `spec-kitty upgrade` in that clone, or `git pull` of a commit in which another clone's upgrade narrowed the agent ignore rules.
- **Desired outcome**: personal Codex state (databases, logs, caches, approval rules, scratch folders, and the personal `config.toml`) stays out of `git status`, so `git add -A` cannot commit it; and every clone that receives the narrowed rules is told which agent-folder files git now shows.
- **Rule that must always hold**: the committed agent-files block is the same in every clone on one CLI version, and team files in a plain project `.codex/` (notably `config.toml`) stay committable.
- **Confirmed design** (Decision Moment `01M7X1KW5TB3PMABWHBDK0407Y`, operator brief: proceed with the recommendation, ratification requested on the PR and #7729): widen the committed Codex block with Codex home state that is never team configuration, and add a clone-local upgrade step that keeps a Codex-home-shaped `.codex/` wholly ignored for that clone only and lists newly visible agent-folder files in every clone.

## Design options considered

| Option | What it does | Verdict |
|---|---|---|
| (a) Widen the committed Codex block | Adds Codex's home layout to the committed block | Needed, but not sufficient alone: `config.toml` is team config in a plain project folder and personal config in a Codex home, so the committed block cannot decide it |
| (b) Keep `.codex/` wholly ignored in the committed `.gitignore` when the local folder looks like a Codex home | Decides per clone, but writes the decision into a committed file | Rejected: the committed block would flip between clones with and without a Codex home on every upgrade, and a clone without one would re-expose the other clone's state |
| (c) Clone-local protection and warning | A clone-local upgrade step writes `.codex/` to `.git/info/exclude` when the clone's `.codex/` is a Codex home, and lists the agent-folder files git now shows; it re-runs in every clone, including clones that pulled the narrowed rules | Recommended together with (a) |
| Edit the shipped rc8 migration | | Forbidden (DIRECTIVE_044) |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrading clone keeps its Codex home ignored (Priority: P1)

A developer with `CODEX_HOME=<project>/.codex` runs `spec-kitty upgrade` on a project last upgraded before 4.0.0rc8. After the upgrade no Codex home file is untracked.

**Why this priority**: this is the leak itself; `git add -A` would commit personal state, possibly credentials.

**Independent Test**: the #7729 reproduction, driven through the real migration runner on a real repository.

**Acceptance Scenarios**:

1. **Given** a pre-rc8 project whose `.gitignore` has the whole-folder `.codex/` line and whose `.codex/` holds the issue's 13 Codex home files, **When** the upgrade migrations run, **Then** `git status` shows none of them as untracked.
2. **Given** a plain project `.codex/` holding only `config.toml`, **When** the upgrade runs, **Then** `config.toml` stays visible (team config) and `.git/info/exclude` gains no `.codex/` rule.

### User Story 2 - A pulled clone is protected and told (Priority: P1)

A second clone with a project-local Codex home pulls the commit that narrowed the rules. When it next runs `spec-kitty upgrade` (or `--dry-run`), its Codex home is excluded for that clone and the upgrade lists the agent-folder files git now shows.

**Why this priority**: the issue's real-world loss happened in a pulled clone.

**Independent Test**: two real clones; clone A upgrades and commits; clone B pulls and runs the migration runner.

**Acceptance Scenarios**:

1. **Given** clone B pulled clone A's narrowed `.gitignore` and ledger, **When** clone B runs the upgrade, **Then** no Codex home file in clone B is untracked and the run warns about the files the narrowing exposed (for example `.cursor/rules/x.md`).
2. **Given** the same clone B, **When** it runs the upgrade as a dry run, **Then** the pending clone-local step is listed and nothing is written.

### User Story 3 - Clones that do not upgrade still hide the worst state (Priority: P2)

After the upgrading clone refreshes the committed block, a clone that only pulls (and never runs `upgrade`) no longer sees Codex databases, logs, caches, approval rules or scratch folders.

**Acceptance Scenarios**:

1. **Given** a block written by this CLI, **When** a clone holds Codex home files under `.codex/`, **Then** every Codex home path except `config.toml` is ignored by the committed block alone.

### Edge Cases

- `.codex/` exists but is a plain project folder (only `config.toml`, `rules/team.rules`): no exclusion, team files stay visible.
- `CODEX_HOME` points at the project's `.codex/` but the folder holds no marker yet: treated as a Codex home.
- The operator restored `.codex/` in `.gitignore` by hand (the issue's workaround): nothing is exposed, so nothing is written.
- Not a git repository, or no `info/exclude` writable: the step does nothing and the upgrade still succeeds.
- Files already committed under `.codex/` are not touched (ignore rules never untrack); the step does not run `git rm`.
- Re-running the upgrade: the exclusion is written once; a settled record is not re-applied.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Committed block covers Codex home state | As a developer with a Codex home in `.codex/`, I want the committed agent-files block to ignore Codex's databases, logs, caches, version file, approval-rules file and scratch, memory, snapshot and system-skill folders so that a clone that never upgrades does not expose them. | High | Open | [build] | no — the same fixture asserts `.codex/config.toml` stays visible |
| FR-002 | Codex-home detection | As a developer, I want Spec Kitty to recognise a `.codex/` folder as a Codex home when it holds Codex home markers or when `CODEX_HOME` points at it, so that a plain project `.codex/` is not treated as one. | High | Open | [build] | no — paired plain-folder fixture must stay undetected |
| FR-003 | Clone-local exclusion of a Codex home | As a developer, I want the upgrade to add `.codex/` to this clone's `.git/info/exclude` when the clone's `.codex/` is a Codex home that git shows files from, so that `config.toml` and any future Codex file stay out of `git status` in this clone only. | High | Open | [build] | no — the #7729 reproduction is red before |
| FR-004 | Runs in every clone | As a developer in a clone that pulled the narrowed rules, I want the protection step to be pending in my clone until it runs there, so that the protection does not depend on which clone upgraded first. | High | Open | [build] | no — two-clone test is red before |
| FR-005 | Newly visible files are listed in every clone | As a developer, I want the upgrade in each clone to list the untracked files git shows inside agent folders the old whole-folder rules hid, so that I can review them before committing. | High | Open | [build] | no — two-clone test asserts the listed path |
| FR-006 | Reproduction becomes a per-PR guard | As a maintainer, I want the #7729 reproduction to lose its `p0_repro` marker and run through the real upgrade runner so that the defect cannot return unnoticed. | High | Open | [ratchet] | no — red on pre-fix sources with `SPEC_KITTY_RUN_P0_REPRO=1` |
| FR-007 | Ledger shows the new step | As a maintainer, I want `spec-kitty migrate ledger` to list the new step in manifest order in the clone-local partition. | Medium | Open | [build] | no — the order-manifest gate fails without the entry |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Idempotent | Running the new step twice changes `.git/info/exclude` at most once (0 duplicate lines). | Reliability | High | Open |
| NFR-002 | Cheap | The step adds at most 2 git invocations to an upgrade of a project with no `.codex/` folder (0 when the folder is absent). | Performance | Medium | Open |
| NFR-003 | Quality gates | New code: 0 ruff findings, 0 mypy errors, every function at complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Shipped migration untouched | `m_4_0_0rc8_narrow_agent_gitignore.py` stays byte-identical (DIRECTIVE_044). | Governance | High | Open |
| C-002 | Deterministic committed block | The committed block never depends on files present in one clone. | Architecture | High | Open |
| C-003 | Nothing deleted or untracked | The step never deletes, moves or untracks a file; it only adds a local exclude rule and warns. | Safety | High | Open |
| C-004 | Ledger model | The new step has an order-manifest entry, `clone_local_effect = True`, and an idempotent `apply()`. | Governance | High | Open |

### Key Entities

- **Agent-files block**: the committed, auto-managed region of `.gitignore` listing Spec Kitty's generated files and agent secrets.
- **Codex home**: a folder Codex uses as `CODEX_HOME`, holding personal state; here, a project `.codex/`.
- **Local exclusion**: a rule in the clone's `.git/info/exclude`, never committed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After upgrading a pre-rc8 project with the issue's 13 Codex home files, 0 of them are untracked. — [build] · no-op passable: no
- **SC-002**: In a second clone that pulled the narrowed rules, 0 Codex home files are untracked after its upgrade, and its upgrade output names every newly visible agent-folder file (up to the listing limit). — [build] · no-op passable: no
- **SC-003**: In a plain project `.codex/`, `config.toml` remains committable after the upgrade (1 of 1 team files visible). — [ratchet] · no-op passable: yes — paired with SC-001 on the same fixture shape
- **SC-004**: Without any upgrade in the receiving clone, all Codex home files other than `config.toml` are ignored by the committed block (12 of 12). — [build] · no-op passable: no

## Assumptions

- Codex's home layout is as the issue lists (observed on Codex as of 2026-11): `auth.json`, `history.jsonl`, `sessions/`, `archived_sessions/`, `log/`, `logs_*.sqlite*`, `state_*.sqlite*`, `models_cache.json`, `version.json`, `config.toml`, `rules/default.rules`, `tmp/`, `shell_snapshots/`, `memories/`, `skills/.system/`.
- `rules/default.rules` is Codex's own per-user approval record; team rules in a project use other file names.
- A pulled clone gets the protection when it next runs `spec-kitty upgrade`; a clone that never upgrades is covered by the committed block (FR-001) only. Surfacing pending clone-local steps without an upgrade is out of scope and tracked as a follow-up issue.
