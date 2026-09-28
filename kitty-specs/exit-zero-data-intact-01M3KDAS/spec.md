# Mission Specification: Exit 0 means your data is intact

**Mission Branch**: `claude/milestone-11-research-0rnnr4` (lanes topology; lands on `main` via PR)
**Created**: 2026-09-28
**Status**: Draft (revised after the post-spec adversarial squad)
**Input**: Operator-approved milestone-11 slice "Exit 0 means your data is intact" covering #4919, #4900, #4933, #4940, #4998 and #4964. The confirmed intent and failure policies are recorded in discovery Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`.

## Intent Summary (confirmed)

Six Spec Kitty commands can report success (exit 0) while they destroy, corrupt or mis-record data that belongs to the person using them. After this mission, each of those commands either keeps the data intact or stops with a non-zero exit and a message naming the affected data and a next step. Each fix is proven red-first through the real command entry point. Installs already damaged by the old behaviour are recovered by the existing repair commands.

- **Primary actor:** a developer using Spec Kitty in their own repository, on Linux, macOS or Windows.
- **Trigger:** running one of the affected commands in the situation it mishandles today.
- **Rule that must always hold:** a mutating command never exits 0 while destroying, corrupting or mis-recording user data.
- **Confirmed policies (operator):**
  1. **Dirty user-owned file:** when a file shares Spec Kitty's metadata filename and has uncommitted edits, local lane consolidation refuses.
  2. **Agent settings file:** a settings file whose encoding can be proven is decoded and merged. Proven means UTF-8, or a byte-order mark for UTF-8 or UTF-16. Any other file is left untouched and the command fails. The command never guesses an encoding. This matches the "refuse and leave it untouched" behaviour `init`, `upgrade` and `doctor` already apply to the same bytes.
  3. **Migrate group flags:** a group-level migrate flag is honoured by the subcommand when the subcommand has the same option, and refused otherwise.

## Domain Language

| Canonical term | Meaning here | Avoid |
|---|---|---|
| **Local lane consolidation** (`spec-kitty consolidate`) | Folding a mission's lanes into its target branch on the local machine. | Bare "merge" (it could also mean branch integration or publishing to origin). |
| **Target branch** | The branch a mission consolidates into (from the mission's `target_branch`). | "main" / "primary" as synonyms. |
| **Spec Kitty-owned mission metadata** | A mission's own `meta.json` directly inside a `kitty-specs/<mission>/` directory, plus the legacy `.kittify/meta.json`. | "any `meta.json`". |
| **Mission** | The canonical unit of work. | "Feature". |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A deferred decision survives repair (Priority: P1)

A developer opens a Decision Moment, defers it, then resolves it later, which is the documented flow. Later the decisions index goes missing or out of date, as happens after a checkout, a merge or a manual clean-up. The developer runs the decisions health check with repair. Today the repair removes the decision from the index and exits 0, and the read-only check reports "clean" beforehand.

**Why this priority**: A governance record is silently lost on a documented flow.

**Independent Test**: In a scratch repository, run open → defer → resolve through the CLI, then delete the decisions index. Run the read-only health check, then the repair. Assert that the decision is rebuilt as resolved with its final answer.

**Acceptance Scenarios**:

1. **Given** a decision that was deferred and then resolved, and a missing decisions index, **When** the user runs the decisions repair, **Then** the rebuilt index lists the decision as resolved with its final answer.
2. **Given** an event log already written by today's code, containing the deferred-then-resolved pair for one decision, **When** the user runs the repair, **Then** that decision is rebuilt as resolved.
3. **Given** a decision whose event history cannot be reconciled (for example, opened twice), **When** the user runs the read-only health check, **Then** it reports the decision as a problem instead of "clean". **When** the user runs the repair, **Then** the decision is not removed, the command exits non-zero, and the message names the decision.

---

### User Story 2 - Every consolidated mission gets a real, persisted number (Priority: P1)

A developer consolidates several missions into their target branch one after another. Today each consolidation prints "Assigned mission_number=1" and the recorded number stays empty.

**Why this priority**: Every consolidation is affected, and the output states something untrue.

**Independent Test**: In a scratch repository, consolidate two missions in sequence. Assert that the printed numbers are 1 and 2, and that the target branch records the same numbers.

**Acceptance Scenarios**:

1. **Given** a target branch with no numbered missions, **When** the user consolidates mission A and then mission B, **Then** the target branch records A as 1 and B as 2, matching the printed lines.
2. **Given** a target branch that already has missions numbered up to 7, including a hand-numbered one, **When** the user consolidates a new mission, **Then** it is recorded as 8.
3. **Given** the recorded number read back from the target branch does not match the number being announced, **When** consolidation finishes, **Then** the command exits non-zero and does not print the false number.
4. **Given** the mission-metadata merge driver is asked to combine a target side whose number is empty with a mission side that has a number, **When** it runs, **Then** the number survives. **Given** instead that the target side already has a number, **Then** the target's number is kept.

---

### User Story 3 - Local lane consolidation never throws away the user's uncommitted edits (Priority: P1)

A developer has uncommitted edits to a tracked file of their own that happens to be named `meta.json` (for example `src/app/meta.json`). The edit may be in the repository root checkout or in a lane worktree that consolidation will remove. They run `spec-kitty consolidate`. Today the safety check treats every file with that name as Spec Kitty bookkeeping, and consolidation then discards the edit and exits 0.

**Why this priority**: The user's work is silently destroyed on the default consolidation path.

**Independent Test**: For each of the two locations, create a tracked user-owned `meta.json` outside the Spec Kitty-owned locations and edit it without committing. Run `spec-kitty consolidate`. Assert that it refuses with a non-zero exit, names the file, and that the edit is still present.

**Acceptance Scenarios**:

1. **Given** an uncommitted edit to a user-owned `meta.json` in the repository root checkout, **When** the user consolidates, **Then** consolidation stops before changing anything, exits non-zero, and names the file with a commit-or-stash remedy.
2. **Given** the same kind of edit in a lane worktree that consolidation would remove, **When** the user consolidates, **Then** consolidation stops, exits non-zero, and names the file and the worktree.
3. **Given** only Spec Kitty-owned mission metadata is dirty, **When** the user consolidates, **Then** consolidation proceeds as today.
4. **Given** several dirty user files at once, some named `meta.json`, **When** the user consolidates, **Then** a single refusal lists all of them.

---

### User Story 4 - Syncing agent hooks never wipes the user's agent settings (Priority: P1)

A developer, often on Windows, has an agent settings file (`.claude/settings.json`) that holds their permissions (including deny rules), environment, their own hooks and Spec Kitty's session hooks. An editor may have saved it as UTF-16, with a byte-order mark, or in a Windows code page such as cp1252. They run `spec-kitty agent config sync --sync-hooks` or `spec-kitty live-work install`. Today a file that isn't UTF-8 is replaced with a nearly empty one, no backup is kept, and the command reports success.

**Why this priority**: Security-relevant configuration is destroyed silently with no backup.

**Independent Test**: Build a settings file with user permissions, an env value containing a non-ASCII character, a user hook and Spec Kitty's session hooks. Encode it as (a) UTF-8 with a byte-order mark, (b) UTF-16 with a byte-order mark, and (c) cp1252 (the issue's bytes). Run the hook sync on each. Assert that (a) and (b) are merged with every entry preserved, and that (c) is left byte-identical with a non-zero exit.

**Acceptance Scenarios**:

1. **Given** a settings file encoded as UTF-8 with a byte-order mark, or as UTF-16 with a byte-order mark, **When** the user syncs hooks, **Then** every user entry and Spec Kitty's own session hooks are preserved and the new hook is added. **And** before the file is rewritten in a different encoding, the original bytes are kept in a sibling backup file.
2. **Given** a settings file whose encoding cannot be proven (for example cp1252 with an accented character), **When** the user syncs hooks or installs live-work, **Then** the file is left byte-identical, the command exits non-zero, and the message names the file and says to re-save it as UTF-8.
3. **Given** a normal UTF-8 settings file, **When** the user syncs hooks, **Then** behaviour is unchanged from today.

---

### User Story 5 - Skills install cleanly from a Windows-style checkout (Priority: P1)

A developer installs or upgrades Spec Kitty from a source checkout with Windows (CRLF) line endings. Today every installed doctrine skill and command skill gets a second, bogus frontmatter block. The skills health check then reports hundreds of drifts that the repair commands cannot fix.

**Why this priority**: Every installed skill is corrupted for Windows users installing from source, and the documented repair path can't recover them.

**Independent Test**: Render and install skills and command skills from CRLF sources. Assert that the output is byte-identical to installing from LF sources. Separately, take an install corrupted by the old behaviour and assert that the repair restores it.

**Acceptance Scenarios**:

1. **Given** doctrine skill sources with CRLF line endings, **When** the user installs or upgrades, **Then** each installed skill has exactly one frontmatter block and matches an LF-source install.
2. **Given** command templates with CRLF line endings, **When** the user installs command skills, **Then** each installed command skill has exactly one frontmatter block and matches an LF-source install.
3. **Given** an install already corrupted with doubled frontmatter, whose files still match what the install manifest recorded, **When** the user runs `spec-kitty upgrade` or the skills repair (`doctor --fix`), **Then** every such file is restored to the clean content, and a second run reports nothing to repair.
4. **Given** a corrupted file the user has edited since installation, so it no longer matches the manifest, **When** the user runs repair, **Then** it is not overwritten silently; it is reported as needing the user's consent, as happens today.
5. **Given** a fresh clone of the Spec Kitty repository on any platform, **When** it is checked out, **Then** shipped skill sources and command templates arrive with LF line endings.

---

### User Story 6 - A requested dry run never runs the real migration (Priority: P2)

A developer runs `spec-kitty migrate --dry-run <subcommand>`, putting the flag before the subcommand as the group help suggests. Today the flag is silently dropped: the real migration runs, files change, and the command exits 0.

**Why this priority**: The user asked for a preview and got real writes. It's P2 because the writes are uncommitted and recoverable with git.

**Independent Test**: For every registered migrate subcommand, run the group-level dry-run form in a scratch repository with a mission that needs migrating. Assert that nothing on disk changes and the exit code matches the policy.

**Acceptance Scenarios**:

1. **Given** a subcommand that has its own dry-run option, **When** the user passes `--dry-run` before it, **Then** it runs in dry-run mode and nothing on disk changes.
2. **Given** a subcommand without a dry-run option, **When** the user passes `--dry-run` before it, **Then** the command fails with a usage error and nothing on disk changes.
3. **Given** a group-level `--force` or `--verbose` before a subcommand that lacks that option (none has it today), **When** the user runs it, **Then** the command fails with a usage error and nothing on disk changes.
4. **Given** the flag placed after the subcommand, or no subcommand at all, **When** the user runs it, **Then** behaviour is unchanged from today.

---

### Edge Cases

- A decision that the service already refuses to change (for example, resolving a decision that is already resolved) keeps being refused. This mission adds no new decision transitions.
- Two event logs combined by a git merge, so the decision events are no longer in append order. The repair must still rebuild the decision deterministically, or refuse non-zero. It never silently drops it.
- A Spec Kitty project in a subdirectory of the git repository (monorepo). Its mission metadata stays exempt, and a user-owned `meta.json` elsewhere still blocks consolidation.
- A user-owned `meta.json` nested deeper under `kitty-specs/`, for example `kitty-specs/<mission>/research/meta.json`, is not exempt.
- A settings file with a byte-order mark that is not valid JSON once decoded. The existing invalid-JSON handling applies: the original is preserved, and nothing is lost silently.
- A skill source file with mixed line endings (some CRLF, some LF) installs identically to an all-LF source.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Deferred-then-resolved decision rebuilds | As a developer, I want the decisions repair to rebuild a decision taken through defer-then-resolve as resolved with its final answer, even when the index is missing, so that my governance record survives. | High | Open | [build] | no — the repro deletes the index first and fails on today's code |
| FR-002 | Existing event logs rebuild too | As a developer, I want event logs written by earlier versions (containing the deferred-then-resolved pair) to rebuild correctly, so that my existing decisions are not lost. | High | Open | [build] | no — fixture is the issue's on-disk event shape |
| FR-003 | Health check reports unreconcilable history | As a developer, I want the read-only decisions health check to report a decision whose history cannot be reconciled as a problem, instead of "clean", so that I learn before I repair. | High | Open | [build] | no — the fixture is a genuinely unreconcilable history, and the healthy decision in the same log still reports clean |
| FR-004 | Repair refuses instead of erasing | As a developer, I want the repair to exit non-zero and name any decision it cannot reconcile, and keep it rather than remove it, so that no decision is lost with exit 0. | High | Open | [build] | no — asserts non-zero exit and the decision still present |
| FR-005 | Recorded number matches the announced number | As a developer, I want `spec-kitty consolidate` to record on the target branch the same mission number it announces, continuing from the highest existing number, so that numbering is truthful. | High | Open | [build] | no — two sequential consolidations must record 1 and 2 |
| FR-006 | Mismatch fails loudly | As a developer, I want consolidation to exit non-zero instead of announcing a number when the number read back from the target branch doesn't match, so that a false announcement can't pass. | Medium | Open | [build] | no — driven through a fault-injected write-back, paired with the FR-005 happy path |
| FR-007 | Merge driver keeps a real number | As a developer, I want the mission-metadata merge driver to keep a mission's number when the target side has none, while still preferring a number the target already has, so that the number isn't dropped during consolidation. | High | Open | [build] | no — the driver repro returns empty today |
| FR-008 | User-owned meta.json blocks consolidation (root checkout) | As a developer, I want `spec-kitty consolidate` to refuse, non-zero and naming the file, when a user-owned `meta.json` in the repository root checkout has uncommitted edits, so that my work is never reset away. | High | Open | [build] | no — asserts the edit survives |
| FR-009 | User-owned meta.json blocks consolidation (lane worktree) | As a developer, I want the same refusal when the edit is in a lane worktree that consolidation would remove, so that removing the worktree never destroys my edit. | High | Open | [build] | no — separate fixture through the worktree-removal gate (same predicate as FR-008, second gate) |
| FR-010 | Exemption limited to Spec Kitty-owned metadata | As a developer, I want only Spec Kitty-owned mission metadata to stay exempt from the dirty-tree check, including in a monorepo subdirectory, so that normal consolidations are not newly blocked and nothing else is exempt. | High | Open | [ratchet] | yes — paired with FR-008 on the same fixture |
| FR-011 | Provably-encoded settings are merged | As a developer, I want hook syncing to read a settings file that is UTF-8, or UTF-8/UTF-16 with a byte-order mark, and keep every user entry and Spec Kitty's session hooks, so that nothing I configured is lost. | High | Open | [build] | no — the UTF-16 fixture loses all entries today |
| FR-012 | Original bytes kept before re-encoding | As a developer, I want the original bytes of a settings file kept in a sibling backup before it is rewritten in a different encoding, so that I can always get my exact file back. | Medium | Open | [build] | no — asserts that the backup exists and is byte-identical to the original |
| FR-013 | Unprovable encodings are refused | As a developer, I want hook syncing and live-work install to leave a settings file byte-identical and exit non-zero, naming the file, when its encoding cannot be proven, so that my settings are never replaced. | High | Open | [build] | no — the issue's cp1252 bytes are wiped today |
| FR-014 | One shared decode rule | As a maintainer, I want every reader of the agent settings file in the hook registrar to use one shared rule for "provably decodable", reused from the existing encoding stack and never guessing, so that encoding behaviour cannot fork. | Medium | Open | [build] | no — a test asserts both readers use the shared rule and reject the cp1252 fixture |
| FR-015 | CRLF doctrine skills install identically | As a developer, I want doctrine skills installed from CRLF sources to be byte-identical to LF-source installs, with one frontmatter block, so that nothing is corrupted. | High | Open | [build] | no — CRLF vs LF comparison fails today |
| FR-016 | CRLF command skills install identically | As a developer, I want command skills rendered from CRLF command templates to be byte-identical to LF-template renders, so that the command-skill path is fixed too. | High | Open | [build] | no — separate fixture, red when only FR-015's fix is applied |
| FR-017 | Corrupted installs converge on repair | As a developer, I want `spec-kitty upgrade` and the skills repair to restore files corrupted by the doubled-frontmatter bug that still match the install manifest, with a second run reporting nothing, so that I can recover without reinstalling. | High | Open | [build] | no — seeded with a corrupted, manifest-matching install |
| FR-018 | User-edited corrupted files still need consent | As a developer, I want a corrupted file that I've edited since installation to keep today's consent-required treatment, so that repair never overwrites my changes. | Medium | Open | [ratchet] | yes — paired with FR-017 on the same fixture |
| FR-019 | Shipped sources pinned to LF | As a maintainer, I want the repository to pin shipped skill sources and command templates to LF line endings, so that a Windows clone can't reintroduce the bug. | Medium | Open | [build] | no — a test asserts the line-ending rule covers both source trees |
| FR-020 | Group-level dry run honoured | As a developer, I want `migrate --dry-run <subcommand>` to run a subcommand that supports dry run in dry-run mode, so that a requested preview never writes. | High | Open | [build] | no — parametrized over every registered subcommand |
| FR-021 | Unhonourable group flags refused | As a developer, I want a group-level `--dry-run`, `--force` or `--verbose` that the subcommand does not declare to cause a usage error with nothing written, so that no flag is silently dropped. | Medium | Open | [build] | no — asserts a usage-error exit and an unchanged tree |
| FR-022 | Trailing and no-subcommand forms unchanged | As a developer, I want the trailing-flag form and the no-subcommand form of `migrate` to behave exactly as today, so that existing scripts keep working. | Medium | Open | [ratchet] | yes — paired with FR-020 on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Red-first proof per issue | Each of the six issues has at least one regression test that fails on the pre-fix code and passes after. It runs through the CLI entry point the issue names: `agent decision` + `doctor decisions`, `consolidate`, `agent config sync --sync-hooks`, `upgrade` / `doctor --fix`, `migrate`. Coverage: 6 of 6 issues. | Reliability | High | Open |
| NFR-002 | Destructive-fixture invariant | For each of the six entry points above, a test over its destructive fixture asserts that the exit code is non-zero, or that the user's data is present and unchanged. Each such test carries a same-fixture positive control. | Reliability | High | Open |
| NFR-003 | Actionable failures | Every new non-zero exit (100%) prints the affected path or identifier and at least one concrete next action. | Usability | High | Open |
| NFR-004 | Code quality gates | New and changed code passes `ruff check`, `ruff format --check` and `mypy` with zero new findings. Each changed function stays at cyclomatic complexity ≤15, with no new suppressions. | Maintainability | High | Open |
| NFR-005 | Test coverage of changed lines | Changed lines reach ≥90% test coverage, meeting the CI diff-cover gate. | Maintainability | High | Open |
| NFR-006 | Platform-independent tests | The encoding and line-ending tests cover LF, CRLF, mixed, byte-order-mark and cp1252 inputs, and all of them run on Linux CI without Windows. | Portability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Fail loud, never fail silent | When a fix can't preserve the data, the command stops with a non-zero exit. Never add a silently-continuing fallback. | Technical | High | Open |
| C-002 | Respect the layer chain | Shared helpers respect the enforced import direction `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`. Any new kernel code is standard-library only. | Technical | High | Open |
| C-003 | Canonical sources only | Reuse the existing canonical seams (the charter encoding-recovery steps, the kernel metadata decode, the existing settings backup, the existing mission-number assignment and bookkeeping-commit path, the existing line-ending handling) instead of adding parallel implementations. | Technical | High | Open |
| C-004 | No cross-repo changes | No change to the `spec_kitty_events` package or any other repository. Upstream gaps are filed as follow-ups. | Technical | High | Open |
| C-005 | Scoped test runs | Mission work runs targeted test files, the named architectural gate files and the owning modules' fast tiers, never a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Process | Medium | Open |
| C-006 | Edit sources, not copies | Skill and template changes are made in the shipped sources (`src/charter/offering/skills/`, `packs/built-in/`), never in generated agent copies. | Technical | Medium | Open |
| C-007 | Documented contracts updated | Where a fix changes a documented behaviour (for example, the decisions health check "always exits 0"), the command help and docs change with it. | Process | Medium | Open |

### Key Entities

- **Decision Moment**: a recorded interview question and its lifecycle (opened, deferred, resolved, cancelled). Its event history is folded into the decisions index, which listing reads.
- **Mission number**: the display number a mission receives when it is consolidated into its target branch, recorded in the mission's metadata on that branch.
- **Spec Kitty-owned mission metadata**: see Domain Language. This is the only `meta.json` exempt from the dirty-tree safety check.
- **Agent settings file**: the user's agent configuration (`.claude/settings.json`) that hook syncing and live-work install merge Spec Kitty hooks into.
- **Installed skill**: a rendered doctrine skill or command-skill file with exactly one frontmatter block, tracked in an install manifest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: None of the six issues' reproduction scenarios, run against the finished mission, still exits 0 with lost or mis-recorded data (0 of 6). — [folded] → NFR-001, NFR-002 · no-op passable: no
- **SC-002**: A decision taken through defer-then-resolve is still listed after the index is lost and repaired, in 100% of runs. — [folded] → FR-001 · no-op passable: no
- **SC-003**: Consolidating N missions in sequence into a fresh target records numbers 1..N with no duplicates, matching the printed numbers exactly. — [folded] → FR-005 · no-op passable: no
- **SC-004**: An install from CRLF sources shows 0 drifts across every installed doctrine skill and command skill, and repairing a corrupted, manifest-matching install leaves 0 drifts after one run. — [folded] → FR-015, FR-016, FR-017 · no-op passable: no
- **SC-005**: For every provably-encoded settings file, 100% of user entries and Spec Kitty session hooks remain after hook syncing. — [folded] → FR-011 · no-op passable: no

## Assumptions

- The decisions fix lives entirely in Spec Kitty's own fold and health check. The squad confirmed that no change to the events package is needed. The events reducer's handling of a second resolved event is filed upstream as a follow-up (C-004).
- Writing a UTF-16 settings file back as UTF-8, with the original bytes kept in a backup, is acceptable. Agent hosts read UTF-8.
- A user editing a Spec Kitty-owned `meta.json` by hand is not a scenario this mission protects. That file stays exempt, as today.

## Out of Scope

- Take-theirs conflict resolution for any `*/meta.json` during consolidation. It is the same defect class and will get a follow-up issue filed under the #4915 epic.
- The CRLF never-verifies shape in the review-cycle retained-artifact path (see #4280), the Windows phantom-repair leftovers (see #4927), and the in-flight coordination clean-up (see #5264).
- The live-work capability probe crashing on undecodable settings. It is noisy but loses no data; see follow-up.
- The nightly/CI red burn-down the 4.0.0 release gate also requires (see #5044, #4916), the terminus follow-ups (see #5046, #5047), and lane work-tip persistence (see #5115).
