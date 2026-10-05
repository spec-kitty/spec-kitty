---
work_package_id: WP04
title: Decision record and operator docs for frozen lane membership
dependencies:
- WP02
- WP03
requirement_refs:
- FR-006
- C-008
planning_base_branch: issue-5573-frozen-started-lanes
merge_target_branch: issue-5573-frozen-started-lanes
branch_strategy: Planning artifacts for this mission were generated on issue-5573-frozen-started-lanes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5573-frozen-started-lanes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-frozen-started-lanes-01M444FM
base_commit: 56c3ef9b8eb7b0f0aaca0ca85fa5ca0451ef57f2
created_at: '2026-10-04T21:46:29.771848+00:00'
subtasks:
- T015
- T016
- T017
history: []
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md
- docs/adr/4.x/index.md
- docs/architecture/execution-lanes.md
- docs/api/finalize-tasks-internals.md
- docs/context/topology.md
- CHANGELOG.md
role: documentarian
tags: []
tracker_refs: []
---

# WP04 — Decision record and operator docs for frozen lane membership

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's
`task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP04 --agent claude`

## Post-tasks squad folds (binding — these override any conflicting text below)

- **Dependencies:** this WP depends on **WP03** too, because it documents the preflight position, validate-only and
  the JSON envelope.
- **CHANGELOG style test:** a live test bans bare requirement ids (FR-/C-/SC-) in `CHANGELOG.md`. Find it with
  `grep -rln "CHANGELOG" tests/ | xargs grep -ln "FR-"` and keep the entry free of them.
- Add the ADR to `docs/adr/4.x/index.md` exactly in its format, and run any ADR index test.

## Objective

Record the new invariant as a 4.x ADR, and update the operator and maintainer docs. The audience is software
engineers operating or maintaining Spec Kitty missions (persona `software-engineer`; charter "Audience-oriented
writing"). This makes "started work packages keep their lane on re-finalize" and the `LANE_MEMBERSHIP_FROZEN` refusal
discoverable where people look.

## Context

- **Spec:** the whole spec, especially the Intent Summary, FR-001–FR-010 and Domain Language.
- **Plan:** "Design".
- **Contract:** `contracts/lane-membership-frozen.md`.
- **Research:** `research/code-grounding.md` §4 ("Governing decisions" ADRs) and §7 (D1–D8).
- **Charter doc rules:**
  - one Divio quadrant per document;
  - an `updated: YYYY-MM-DD` freshness date where the page carries frontmatter;
  - docs mirror shipped behaviour (code is the source of truth);
  - terminology canon: Mission and work package, never "feature"; `--mission` in commands.
- **Dependency:** this WP depends on WP02 (the semantics). Before marking it done, reconcile the text against WP02's
  merged names: `FrozenLaneMembership`, `LaneMembershipFrozenError`, the reason strings, and the `frozen_lane_membership`
  collapse rule. If WP03 lands later, re-check the CLI-facing behaviour at accept time.
- Run `pytest tests/architectural/test_no_legacy_terminology.py -q` before handing off. Also run any docs gates the repo
  has (e.g. `tests/docs` or ADR-index tests). Find them with `grep -rl "adr/4.x" tests/`.

### Subtask T015: ADR `docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md`

**Steps**:
1. Read two or three recent 4.x ADRs (e.g. `docs/adr/4.x/2026-10-04-1-*.md`, `2026-10-03-1-*.md`) and copy their exact
   structure and frontmatter conventions. The index is `docs/adr/4.x/index.md`.
2. **Content:**
   - **Context.** #5573 is the third recurrence of a lane-identity defect (#3311, then #4945, then #5573). Lane ids are
     bound to their branch, per terminus-merge-integrity FR-010, but started WP ↔ lane membership was a heuristic
     output. Also cite the attribution reason: `lane_head` stamps feed the #5046 per-WP attribution.
   - **Decision.** Started work packages' recorded lane membership is a constraint of lane computation:
     - "started" is history-based, with the lane-work-tip fallback;
     - preserve by construction; refuse only the unsatisfiable cases with `LANE_MEMBERSHIP_FROZEN`;
     - the refusal fires before any write;
     - an absent log means nothing started, and a malformed log refuses;
     - the tie-break for unpinned groups is documented;
     - lane ids that held started work are reserved from minting.
   - **Consequences:**
     - removing a started WP's task file now refuses (an intentional behaviour change);
     - the validate-only preview uses the prior manifest;
     - the collapse report gains the `frozen_lane_membership` rule.
   - **Alternatives rejected:** a post-hoc diff, freezing all lanes, and compute reading status/git.
   - **Related:**
     - ADR 3.x `2026-07-29-1` (finalize-tasks is the single writer of `lanes.json`);
     - ADR 3.x `2026-09-26-2` (refuse, never rescue);
     - #5080 (sibling invariant);
     - follow-ups #5701, #5702, #5703.
3. Add the ADR to `docs/adr/4.x/index.md` in its existing format.

### Subtask T016: `docs/architecture/execution-lanes.md` + `docs/api/finalize-tasks-internals.md`

**Steps**:
1. `execution-lanes.md`: add or extend a "Re-finalizing an active mission" section (Explanation quadrant):
   - what a started work package is;
   - the lane-id rule:
     - pinned groups keep their recorded id;
     - unpinned groups read back by most shared members, then the lowest prior lane id;
     - new lanes get the next free id, skipping reserved ids;
   - started lane-mates stay together;
   - the refusal cases.

   Link the ADR and the glossary. Keep the page's existing style and freshness date.
2. `finalize-tasks-internals.md` (Reference): next to §3, which covers the #3311 planning-pin preservation, document:
   - the preflight's position (after the ownership gates, before the first status write);
   - the evidence sources;
   - the `--validate-only` behaviour;
   - the JSON refusal envelope (copy the key set from the contract);
   - the reason/remedy table.

   State explicitly that the planning-pin "execution has begun" probe and the started-WP predicate answer different
   questions, and cite #5702.

### Subtask T017: Glossary + CHANGELOG

**Steps**:
1. `docs/context/topology.md` (glossary): add rows in the existing table format for:
   - **Started work package**: the definition from the spec's Domain Language, with "Do NOT use when" guards matching
     the page's style (e.g. not a synonym of "in_progress");
   - **`LANE_MEMBERSHIP_FROZEN`**: what triggers it, and a pointer to the remedy table.
2. `CHANGELOG.md`: add an entry under the current unreleased section, following the file's existing headings and
   style, under Fixed or Changed:
   - re-running `finalize-tasks` no longer moves a started work package to another lane (#5573);
   - unsatisfiable amendments refuse with `LANE_MEMBERSHIP_FROZEN` before writing;
   - note the intentional behaviour change (removing a started WP's task file refuses) and the validate-only preview
     change;
   - reference #3311 and #4945 as context.

## Definition of Done

- The ADR exists, follows the 4.x template, and is listed in the index.
- All three docs pages and the CHANGELOG are updated and mirror the shipped names and behaviour.
- `pytest tests/architectural/test_no_legacy_terminology.py -q` passes, and any ADR/docs index tests pass.
- Prose uses Mission / work package canon, with no new "feature".
- Each subtask is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.

## Risks

- **Docs drifting from code:** names and reason strings must match WP02/WP03 exactly. Grep the source before
  finalizing.
- **CHANGELOG merge conflicts** with main moving fast: keep the entry small and self-contained.

## Reviewer Guidance

- The ADR is a decision record, not a design dump.
- The glossary rows follow the "Do NOT use when" convention.
- The remedies quoted in the docs are non-destructive and match the contract.
