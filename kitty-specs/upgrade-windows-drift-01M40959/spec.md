# Mission Specification: Upgrade and Windows drift

**Mission Branch**: `kitty/upgrade-windows-drift`
**Created**: 2026-10-03
**Status**: Draft
**Input**: Milestone 11 close-out for #5574, #5575, and #5576. An operator on the current release candidate cannot finish an unattended upgrade when installed commands already match the product, has no way to consent to replace a command they actually edited, and on Windows can be blocked from starting work by planning files Git itself considers clean.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unattended upgrade of already-current commands (Priority: P1)

An operator runs an unattended project upgrade. The installed commands on disk already match what this version of the product would write. The recorded install fingerprint is older. Upgrade finishes successfully and does not ask the operator to repair those commands.

**Why this priority**: Unattended upgrade is how operators and automation move to the current release. A false drift report stops that with exit failure even though nothing the operator wrote is at risk.

**Independent Test**: Install commands that byte-match the current rendering, record an older fingerprint, run unattended project upgrade, and observe success with those files left unchanged.

**Acceptance Scenarios**:

1. **Given** a command file whose contents match the current product rendering and whose recorded fingerprint is older, **When** the operator runs an unattended project upgrade, **Then** upgrade succeeds and does not list that file as drifted.
2. **Given** the same file, **When** the operator asks for a surface health check, **Then** the file is reported present, not drifted.

---

### User Story 2 - Consent before replacing an edited command (Priority: P1)

An operator has edited an installed command. Upgrade and health checks notice the edit and leave the file alone. When the operator explicitly asks to repair, the edited command is replaced with the current product rendering, the same way an edited agent profile is replaced today. An unattended upgrade never performs that replacement.

**Why this priority**: Keeping hand-edited files is deliberate. The defect is that asking to repair does not actually repair command edits, so the operator is told to run a check that cannot fix the problem.

**Independent Test**: Edit one command so it matches neither the recorded fingerprint nor the current rendering. Unattended upgrade leaves the bytes in place and fails. An explicit repair then replaces that file and a follow-up check no longer reports it drifted.

**Acceptance Scenarios**:

1. **Given** a command the operator edited, **When** they run an unattended project upgrade, **Then** the edited bytes are unchanged and upgrade does not succeed.
2. **Given** that same edited command, **When** they run the health check that offers repair, **Then** the check tells them a repair they can run, and until they ask to repair it writes nothing.
3. **Given** that same edited command, **When** they explicitly ask to repair, **Then** the file is replaced with the current rendering and a second check reports it present.
4. **Given** an edited agent profile in the same project, **When** they ask to repair, **Then** that profile is still replaced as it is today.

---

### User Story 3 - Start work when Git says the planning files are clean (Priority: P1)

An operator on a checkout that stores text one way and checks it out another way (the usual Windows setup) starts implementation with auto-commit turned off. Planning files that Git reports as clean do not block that start, and they are not committed again as an empty commit. A planning file they actually changed is still treated as uncommitted.

**Why this priority**: The block stops implementation on a clean tree. The same false reading is what the empty-commit guard is there to prevent, so the auto-commit path is wrong for the same files.

**Independent Test**: On a repository Git reports clean, including planning files whose working copy differs from the stored copy only by line endings, start implementation with auto-commit off and observe that it is not refused for those files. Change one word in one planning file and observe that only that file is still outstanding.

**Acceptance Scenarios**:

1. **Given** a clean checkout whose planning files differ from the stored copy only by line endings, **When** the operator starts implementation with auto-commit off, **Then** start is not refused because of those files.
2. **Given** that same clean checkout, **When** implementation would otherwise commit planning files, **Then** it does not create an empty commit for the line-ending-only files.
3. **Given** one planning file with a real text change as well as different line endings, **When** the operator starts implementation with auto-commit off, **Then** that file is still reported as needing a commit, and the line-ending-only files are not.

---

### Edge Cases

- A command that matches the current rendering is not treated as an operator edit, even when the recorded fingerprint is stale.
- An operator edit that also happens to share line endings with the product rendering is still an edit if any other content differs.
- Repair of one drifted command does not rewrite an unrelated edited file the operator did not include.
- A file declared as binary, or otherwise excluded from text conversion, still counts as changed when its bytes differ, including a carriage-return-only difference.
- A missing planning file on the comparison baseline still counts as needing a commit.
- If the comparison against Git cannot be completed, the file stays in the "needs a commit" set rather than being treated as clean.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Current commands are not drift | As an operator, I want an installed command that already matches the current product to count as present, so that an unattended upgrade is not stopped by a stale fingerprint. | High | Open | [build] | no |
| FR-002 | Edited commands stay until repair | As an operator, I want a command I edited to be left in place until I ask to repair it, so that my edits are not discarded by an unattended upgrade. | High | Open | [build] | no |
| FR-003 | Repair replaces an edited command | As an operator, I want an explicit repair to replace an edited command with the current product rendering, so that the health check I am sent to can actually clear the drift. | High | Open | [build] | no |
| FR-004 | Clean planning files do not block start | As an operator, I want planning files Git considers clean to be ignored when I start implementation, so that a line-ending-only checkout does not block me or create an empty commit. | High | Open | [build] | no |
| FR-005 | A real planning edit is still outstanding | As an operator, I want a planning file I actually changed to remain outstanding, so that a line-ending-tolerant check cannot hide a real edit. | High | Open | [ratchet] | yes — paired with FR-004 on the same checkout; the real edit must remain the only outstanding file |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Red then green | Each of FR-001, FR-003, and FR-004 has one test through the existing product entry point that fails on the current release and passes after the change. Three such proofs, zero new harnesses. | Reliability | High | Open |
| NFR-002 | Unattended upgrade writes nothing on a real edit | During an unattended upgrade, an edited command's bytes are identical before and after (zero bytes rewritten) while upgrade exits unsuccessfully. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Three issues only | This mission closes #5574, #5575, and #5576. It does not take on the open doctrine-skill drift issue or the broader skill-drift programme. | Business | High | Open |
| C-002 | No new public flag | Do not add a new public command flag. Consent to replace an edited command is the repair request operators already use for agent profiles. | Business | High | Open |
| C-003 | Keep user edits | Unattended upgrade and a health check that is not asked to repair must not overwrite operator-edited commands. | Business | High | Open |
| C-004 | Do not hide a real edit | Treating line-ending differences as clean must not treat a real text change as clean, including when the text change is saved with the checkout's line endings. | Technical | High | Open |
| C-005 | Evidence before the fix | The failing test for each bug is written and observed failing before the product change that makes it pass. | Technical | High | Open |

### Key Entities

- **Installed command**: A product command file the project owns, with a recorded fingerprint from when it was installed and a current rendering the product would write today.
- **Operator edit**: Installed-command contents that match neither the recorded fingerprint nor the current rendering.
- **Repair request**: The operator's explicit ask to replace drifted managed files. It already replaces edited agent profiles.
- **Planning file**: A specification or plan file implementation expects to commit before work starts.
- **Clean checkout**: A working tree Git reports as having nothing to commit. Line-ending differences that Git itself would not record are clean.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator whose installed commands already match the current product can finish an unattended project upgrade without a drift failure. — [build] · no-op passable: no
- **SC-002**: An operator who edited a command can point to one repair they were told to run, and after they run it that command matches the product and is no longer reported as drifted. — [build] · no-op passable: no
- **SC-003**: An operator on a checkout Git reports as clean can start implementation with auto-commit off without being asked to commit planning files. — [build] · no-op passable: no
- **SC-004**: An operator who changed the text of one planning file on that same checkout is still asked to commit that file, and only that file. — [ratchet] · no-op passable: yes — paired with SC-003

## Assumptions

- The kick-off brief is the discovery record. The operator asked for an autonomous run and to stop only for a new public flag, a forced widening into the skill-drift programme, or a line-ending fix that would hide a real edit. None of those is required.
- "Ask to repair" means the existing repair on the tool-surface health check, not a newly named flag.
- Mission type is software-dev. Topology is lanes with a coordination branch. Planning and the later merge of this mission stay on `kitty/upgrade-windows-drift`.
- File-level evidence for plan and tasks is in `research-memo.md` beside this specification.
