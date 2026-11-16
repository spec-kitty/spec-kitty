---
description: "Work package task list for the context-docs-refresh Mission"
---

# Work Packages: Context docs refresh (audience profiles first)

**Inputs**: Design documents from `kitty-specs/context-docs-refresh-01M7AN3N/`
**Prerequisites**: plan.md, spec.md, gap-analysis.md

**Tests**: No new tests are requested. Each work package runs the existing docs gates listed in
plan.md ("Per-WP checks"); any new gate would be written red-first in its own commit.

**Organization**: Subtasks (`Txxx`) roll up into three work packages in #7522's order. Each work
package is independently deliverable: it leaves its pages checked, reader-named and gate-clean.

**Prompt Files**: Each work package has a prompt in `tasks/`. Record subtask completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

**Shared mission logs**: `corrections-log.md` and `operator-flags.md` are mission-level logs owned
by no work package. Each work package appends its own rows in its own commits (a recorded
out-of-map edit: the logs are the evidence trail FR-004 and FR-005 ask for).

---

## Work Package WP01: Audience profiles (Priority: P1) 🎯 MVP

**Goal**: The ten audience profiles and three hub pages match how Spec Kitty 4.x is used today, name their own reader, and tell an author how to pick a reader.
**Independent Test**: For each profile, a reviewer can trace each goal, vocabulary item and reader question to a current CLI command or concept; the regenerated `context/audience/` audit rows show a reader and a verified `updated`; docs gates pass.
**Prompt**: `tasks/WP01-audience-profiles.md`

### Included Subtasks

T001 Load the writer profile and doctrine; record the gate baseline (WP01)
T002 Refresh the four external profiles and the external hub (WP01)
T003 Refresh the three human internal profiles: system-architect, lead-developer, maintainer (WP01)
T004 Refresh the agent and system profiles: ai-collaboration-agent, spec-kitty-cli-runtime, project-codebase, and the internal hub (WP01)
T005 Rewrite the audience hub: what profiles are for and how to name one (WP01)
T006 Frontmatter, corrections log and operator flags for WP01 (WP01)
T007 Run the gates and write the self-review (WP01)

### Implementation Notes

- Keep the canonical persona template shape (plan.md Decision 3). Change only what the code or the Terminology Canon proves wrong, and log each factual change.
- Readers of these pages: `internal/maintainer` and `internal/ai-collaboration-agent` (Decision 2).

### Parallel Opportunities

- T002, T003 and T004 touch different files and can run in any order.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Rewriting persona content beyond what is proven → edits stay minimal; a wider change becomes a proposal in `operator-flags.md`.

---

## Work Package WP02: Footgun and concept pages, plus identity (Priority: P2)

**Goal**: `orchestration.md`, `execution.md`, `topology.md`, `team-kitty.md` and `identity.md` are checked against the code, keep every linked anchor, name their reader, name no retired surface, and drain all 11 `context/` burn-down pairs.
**Independent Test**: The strict link check passes; every heading slug linked from `CLAUDE.md`, `AGENTS.md` or another doc still exists; `grep -c "page: context/" scripts/docs/retired_surface_burndown.yaml` returns 0 and `test_retired_surface_gate.burn_down` is 70.
**Prompt**: `tasks/WP02-footgun-and-concept-pages.md`

### Included Subtasks

T008 Snapshot the linked anchors and the gate baseline (WP02)
T009 Check `orchestration.md`: definitions, commands, paths; remove the retired names (WP02)
T010 Check `execution.md` and `topology.md` (WP02)
T011 Rewrite `team-kitty.md` to the #6164 state (WP02)
T012 Check `identity.md`; remove the retired names (WP02)
T013 Drain the burn-down and lower the baseline; frontmatter, logs, gates and self-review (WP02)

### Implementation Notes

- Anchor freeze (plan.md Decision 5). Drain each pair in the same commit as its page fix (Decision 6).

### Parallel Opportunities

- T009 to T012 touch different pages; T013 runs last.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Renaming a linked anchor → slug snapshot before and after, plus the strict link check.

---

## Work Package WP03: Remaining context pages (Priority: P3)

**Goal**: The other 22 pages under `docs/context/` are checked against the code, name their reader, keep one Divio type, and lose their text-drawn diagram and dead references.
**Independent Test**: The regenerated `context/` audit shows a reader on every row, no missing path or command (except the recorded illustrative placeholder), no text diagram; docs gates pass.
**Prompt**: `tasks/WP03-remaining-context-pages.md`

### Included Subtasks

T014 Governance and charter pages: `charter`, `charter-overview`, `governance`, `governance-files` (WP03)
T015 Identity fields, configuration and records: `identity-fields`, `configuration-project-structure`, `dossier`, `system-events` (WP03)
T016 Glossary tooling: `contextive-glossaries` (Mermaid diagram), `glossary-conventions`, `lexical`, `historical-terms` (WP03)
T017 Method pages: `spec-driven`, `practices-principles`, `testing-taxonomy`, `technology-foundations`, `naming-decision-tool-vs-agent` (WP03)
T018 Product and work model: `product-lines`, `ops-vs-missions`, `mission-types`, `planning-and-tracking` (WP03)
T019 Section index `context/README.md` (WP03)
T020 Frontmatter, logs, regenerated audit, gates and self-review (WP03)

### Implementation Notes

- Readers per plan.md Decision 4. Resolve the mixed-type pages by moving or trimming the off-type part, never by inventing content.

### Parallel Opportunities

- T014 to T019 touch different pages.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Size (22 pages, about 3,000 lines) → one commit per subtask; stop and split the WP if a subtask cannot be finished in one session.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → (WP02, WP03).
- **Parallelization**: WP02 and WP03 share no file (WP02 alone owns the burn-down and its baseline).
- **MVP Scope**: WP01, since every other page names a profile as its reader.

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Load profile and doctrine; gate baseline | WP01 | P1 | No |
| T002 | External profiles and hub | WP01 | P1 | [P] |
| T003 | Human internal profiles | WP01 | P1 | [P] |
| T004 | Agent and system profiles, internal hub | WP01 | P1 | [P] |
| T005 | Audience hub | WP01 | P1 | No |
| T006 | WP01 frontmatter and logs | WP01 | P1 | No |
| T007 | WP01 gates and self-review | WP01 | P1 | No |
| T008 | Anchor and baseline snapshot | WP02 | P2 | No |
| T009 | `orchestration.md` | WP02 | P2 | [P] |
| T010 | `execution.md`, `topology.md` | WP02 | P2 | [P] |
| T011 | `team-kitty.md` | WP02 | P2 | [P] |
| T012 | `identity.md` | WP02 | P2 | [P] |
| T013 | Burn-down drain, logs, gates, self-review | WP02 | P2 | No |
| T014 | Governance and charter pages | WP03 | P3 | [P] |
| T015 | Identity fields, configuration, records | WP03 | P3 | [P] |
| T016 | Glossary tooling pages | WP03 | P3 | [P] |
| T017 | Method pages | WP03 | P3 | [P] |
| T018 | Product and work model pages | WP03 | P3 | [P] |
| T019 | Section index | WP03 | P3 | No |
| T020 | WP03 logs, audit, gates, self-review | WP03 | P3 | No |
