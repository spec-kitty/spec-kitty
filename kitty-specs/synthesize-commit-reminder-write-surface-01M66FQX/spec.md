# Mission Specification: Synthesize Commit Reminder Names the Whole Write Surface

**Mission**: synthesize-commit-reminder-write-surface-01M66FQX
**Created**: 2026-10-30
**Status**: Draft
**Target branch**: issue-6631-synthesize-reminder-write-surface
**Input**: Issue spec-kitty/spec-kitty#6631 — `charter synthesize`'s safe-commit reminder omits `.kittify/charter/synthesized-artifacts.yaml`.

## Summary

`charter synthesize` prints a `spec-kitty safe-commit` recipe naming three paths
(`synthesis-manifest.yaml`, `provenance/`, `.kittify/charter-packs/`), but the
same run also writes `.kittify/charter/synthesized-artifacts.yaml` — the
per-kind created-artifact record that makes an operator's artifact removal stick
(#6404, #6442) — and, on a project with explicit `activated_<kind>s` lists, the
activation write target (`.kittify/charter/activation.yaml`, or the pointed-at
`charter.yaml` on a legacy project). An operator who runs the printed command as
given leaves the record out of git, so no other clone has it and the
"removal sticks" guarantee is lost there. The governance skill's step 7 and the
`charter-artifact-structure.md` tables have the same gap, so the same omission
is copied by hand.

The fix makes the reminder **derived from the write surface**: the activation
append step reports the paths it wrote, and the reminder names the always-written
synthesis paths plus exactly those. The skill and doc text are updated to name
the record, and an end-to-end regression test pins the invariant generically —
run `synthesize`, run the printed command, assert `.kittify/` is clean in git —
so the next record-like file cannot be silently dropped from the reminder again.

No behavior change to synthesis itself: what is written, when, and with what
content is untouched; only the printed reminder and the docs change.

## User Scenarios & Testing

### User Story 1 - The printed command commits everything the run wrote (Priority: P1)

An operator runs `spec-kitty charter synthesize` on a project whose interview
creates at least one reach-only artifact (a `how-we-apply-*` tactic or a
directive-sourced styleguide). The run writes the manifest, provenance, the
project pack, and the created-artifacts record. The operator copies the printed
`safe-commit` command verbatim and runs it. Everything the run wrote under
`.kittify/` is now committed; `git status --porcelain .kittify/` is empty.

**Why this priority**: this is the reported defect — the record is the
"removal sticks" guarantee and today it stays uncommitted.

**Independent Test**: end-to-end regression test on the canonical fixture
(`FixtureAdapter`, explicit `activated_tactics` list): run synthesize, parse the
printed safe-commit line, execute it in the test repo, assert
`git status --porcelain .kittify/` is empty. Red before the fix (the record
remains `??` untracked), green after.

**Acceptance Scenarios**:

1. **Given** a project where synthesis creates one tactic and holds an explicit
   `activated_tactics` list, **When** the operator runs the printed safe-commit
   command, **Then** `git status --porcelain .kittify/` is empty — the record
   `.kittify/charter/synthesized-artifacts.yaml` and the rewritten activation
   target are both committed.
2. **Given** a project with no explicit activation list (absent key stays
   absent, C-001), **When** synthesis creates a tactic, **Then** the reminder
   names the record (the run wrote it) but names no activation file (the run
   wrote none) — the command still succeeds and leaves `.kittify/` clean.
3. **Given** a run that creates no new artifact and changes no record entry,
   **When** the reminder prints, **Then** it names only paths the run actually
   touched — it never names a path the run did not write.

### User Story 2 - The reminder cannot drift from the write surface again (Priority: P2)

A future change adds another file to the synthesis write surface. The
regression test fails the moment that file is written but missing from the
reminder, because the test asserts cleanliness of `.kittify/` after running the
printed command, not a fixed path list.

**Why this priority**: the issue asks for a single authority so the reminder,
the skill and the docs cannot drift apart again; the path list is derived, not
restated.

**Independent Test**: the same end-to-end test as story 1 (its assertion is
generic over written files, not a substring check); plus the activation-append
seam test asserting the returned written-paths set matches the files the call
changed on disk.

**Acceptance Scenarios**:

1. **Given** the activation append writes the record, **When** it returns,
   **Then** its result reports the record's repo-relative path among the
   written paths, and the reminder renders that path.
2. **Given** the activation append writes the activation target (explicit list
   present), **When** it returns, **Then** the target's repo-relative path is
   reported and rendered likewise.
3. **Given** the append writes nothing (no participating kinds, or no change to
   the record), **When** the reminder prints, **Then** no activation-surface
   path is named.

### User Story 3 - The governance skill and artifact-structure doc name the record (Priority: P3)

An agent following `spk-charter-governance` step 7, or reading
`charter-artifact-structure.md`, commits the record with the rest of the
synthesis state instead of leaving it out.

**Why this priority**: the skill text drifted with the reminder; fixing only
the CLI would leave the second copy of the omission.

**Independent Test**: doc-assertion test (or doc text review) that step 7 and
the Git-tracking / authority tables name `synthesized-artifacts.yaml`.

**Acceptance Scenarios**:

1. **Given** the skill's step 7, **When** an agent commits promoted synthesis
   state, **Then** the command names the record alongside the three existing
   paths.
2. **Given** `charter-artifact-structure.md`, **When** a reader looks up the
   record, **Then** it is listed as **Tracked** in the Git-tracking table and as
   **Derived** ("written by `charter synthesize`; do not edit") in the authority
   table, so it is not mistaken for local runtime state.

### Edge Cases

- **Record exists but this run changed nothing in it**: the append reports no
  written path for it; the reminder omits it. The file is unchanged, so the
  operator's tree is not made dirty by the omission (unchanged files need no
  commit).
- **A previous run left the record uncommitted (pre-fix omission carried
  forward)**: this run that does not rewrite the record will not name it; the
  operator sees it in `git status`. The reminder is a per-run hint, not a
  git-status replacement. Out of scope (no reconciliation logic, C-002).
- **`--json` output**: the reminder is human-branch-only today and stays so;
  the JSON envelope's contracted fields are unchanged (C-003).
- **Fresh-project seed path**: it does not call the activation append; its
  reminder keeps today's base paths unchanged.
- **Unreadable record**: the append returns its existing warning and writes
  nothing; the reminder names no record path. No new failure mode.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | The activation-append seam reports the paths it wrote | US2 | High | Open | [build] | no — the record path must appear in the result when the record is written |
| FR-002 | The synthesize reminder is derived from the write surface | US1, US2 | High | Open | [build] | no — the printed command must name the record on a run that wrote it |
| FR-003 | End-to-end regression: the printed command leaves `.kittify/` clean | US1, US2 | High | Open | [build] | no — red on main today |
| FR-004 | Governance skill step 7 and artifact-structure tables name the record | US3 | Medium | Open | [build] | no — doc text must name the path |
| FR-005 | Changelog entry under [Unreleased] | US1 | Medium | Open | [build] | no — user-facing surface change |

FR-001: `append_synthesized_activations` (reach_only.py) returns a structured
result — the existing warnings plus the repo-relative paths the call wrote (the
created-artifacts record when its content changed; the activation write target
when a promote fired). The list is produced by the writer itself, in the same
lock, so there is exactly one authority for "what did this step write".

FR-002: `_print_synthesis_commit_reminder` takes the run's activation-written
paths and renders the base synthesis paths (`synthesis-manifest.yaml`,
`provenance/`, the project pack root) plus those, deduplicated in stable order.
The two production callers (`charter synthesize`'s real-run report;
`resynthesize` consumes only the warnings) are adapted. The base-path tuple
stays the CLI's statement of what the synthesis pipeline always writes.

FR-003: an issue-pinned regression test (marker `regression`, #6631) drives the
real `charter synthesize` on the canonical fixture (explicit
`activated_tactics` list, `FixtureAdapter`), extracts the printed safe-commit
line, executes it in the initialized test repo, and asserts
`git status --porcelain .kittify/` is empty. The assertion is over the whole
`.kittify/` tree, not a fixed path list, so any future written-but-unnamed
artifact fails it.

FR-004: `src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md`
step 7 adds `.kittify/charter/synthesized-artifacts.yaml` (with a note that
synthesis prints the exact command); `charter-artifact-structure.md` adds the
record to the authority table (**Derived**) and the Git-tracking table
(**Tracked**, the removal-sticks record shared across clones).

FR-005: `docs/changelog/CHANGELOG.md` `[Unreleased]` entry, bold impact-first
lead with `(#6631)`, before/after, under 1,200 characters.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | No synthesis behavior change | What the run writes, and when, is byte-identical to today; only the returned reporting shape and the printed reminder change. All existing synthesize/resynthesize/reach-only tests stay green apart from mechanical adaptation to the new result shape. | Compatibility | High | Open |
| NFR-002 | No new CLI flag or command | The reminder is extended in place; no new command, flag, env var or JSON envelope field. | Surface stability | High | Open |
| NFR-003 | Single authority for activation-surface paths | The reminder never hard-codes the record or activation paths; they reach it only through the append step's reported written paths. A grep for the record path in the CLI layer finds no literal restatement of it in the reminder construction. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Absent activation keys stay absent | The append's write behavior (including "an absent `activated_<kind>s` key is left absent") is untouched; only reporting is added. | Technical | High | Open |
| C-002 | Forward-only, no reconciliation | No logic tries to detect or repair a record left uncommitted by an earlier run. | Technical | High | Open |
| C-003 | JSON envelope contract unchanged | `--json` output fields for synthesize/resynthesize keep their current shape; the reminder remains human-branch-only. | Technical | High | Open |
| C-004 | Skill/doc edits land in the committed source | The skill references under `src/charter/offering/skills/spk-charter-governance/` are the committed source of the rendered skill; edit them there (no pack pin bump needed — the references are not in the fetched pack trees). | Process | Medium | Open |
| C-005 | Proportionate scope | No change to `safe-commit` itself, to the bundle manifest, or to `charter bundle validate` scope; those are named in the issue as separate concerns. | Scope | Medium | Open |

### Key Entities

- **Created-artifacts record** — `.kittify/charter/synthesized-artifacts.yaml`;
  per-kind ids synthesis has created; a listed id is never re-appended, so a
  removal sticks. Written by the activation append step.
- **Activation write target** — the file holding explicit
  `activated_<kind>s` lists (ledger: `.kittify/charter/activation.yaml`;
  legacy: the pointed-at `charter.yaml`, or `.kittify/config.yaml`). Written by
  the append's promote when a first-time slug joins an explicit list.
- **Synthesis commit reminder** — the `spec-kitty safe-commit ...` recipe
  printed after a successful real-run synthesize; names the paths the run wrote.

## Success Criteria

- **SC-001**: On a project whose synthesize run creates a reach-only artifact
  and holds an explicit activation list, running the printed safe-commit
  command leaves `git status --porcelain .kittify/` empty. — [build] · no-op passable: no
- **SC-002**: The activation-append result's written-paths list, and only that
  list, supplies the activation-surface paths in the reminder; a run that
  writes neither the record nor the activation target prints a reminder naming
  neither. — [build] · no-op passable: no
- **SC-003**: The governance skill's step 7 and both `charter-artifact-structure.md`
  tables name the record; the changelog carries the user-facing entry. — [build] · no-op passable: no

## Issues

| Issue | Verdict |
|-------|---------|
| spec-kitty/spec-kitty#6631 | fixed (pending) |
