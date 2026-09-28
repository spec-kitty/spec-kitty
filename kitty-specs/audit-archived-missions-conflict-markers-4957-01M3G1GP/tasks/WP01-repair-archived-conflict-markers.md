---
work_package_id: WP01
title: Repair WP01 conflict-marker corruption (archived, planning-artifact-confined)
dependencies: []
requirement_refs:
- FR-001
- C-002
- C-003
planning_base_branch: issue-4957-archived-conflict-markers
merge_target_branch: issue-4957-archived-conflict-markers
branch_strategy: Planning artifacts for this mission were generated on issue-4957-archived-conflict-markers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4957-archived-conflict-markers unless the human explicitly redirects the landing branch.
subtasks:
- T001
history: []
agent_profile: implementer-ivan
authoritative_surface: kitty-specs/025-cli-event-log-integration/tasks/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-4-6
owned_files:
- kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md
role: implementer
tags: []
tracker_refs: []
---

# WP01: Repair WP01 conflict-marker corruption (archived, planning-artifact-confined)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Resolve the botched-merge conflict-marker block at lines 758–773 of
`kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
to the `HEAD` side, so the archived mission artifact is valid, coherent Markdown
with no residual `<<<<<<<`/`=======`/`>>>>>>>` marker text and no orphaned-lineage
content (FR-001).

## Context

**Why this WP exists**: This is the one confirmed real conflict-marker
corruption in the archived mission corpus (issue #4957, escalated from
#4936/#4880's precedent). `git grep -nE '^(<<<<<<<|>>>>>>>) ' -- kitty-specs/`
currently hits exactly this file at lines 758 and 773 — the sole repair target
outside the test-fixture exemption (`tests/git_ops/test_git.py`, out of this
WP's scope).

**Why this WP is confined to exactly one `kitty-specs/` file**: this repo's
`tasks-finalize` ownership validation bans a `code_change` WP from owning any
`kitty-specs/` path (`INVALID_WP_OWNED_FILES_KITTY_SPECS`), and only exempts a
`planning_artifact` WP whose *every* `owned_files` entry is confined to
`kitty-specs/` or `docs/`. The carve-out registration this repair also requires
(`_OPERATOR_SANCTIONED_CORRECTIONS` in `tests/architectural/test_archive_root_byte_identical.py`)
therefore cannot live in this same WP — it is a `tests/` path, not a planning
surface. That registration, and the new conflict-marker guard, are handled by
**WP02**, which **depends on this WP**.

**Landing-order coupling (read before starting)**: plan.md Section D reasoned
that the repair (this WP) and the carve-out registration (WP02) are safest
landed in the *same commit*, because an intermediate state where the file is
repaired but not yet registered would red the always-on `archive-freeze` CI job
(`test_no_preexisting_archived_file_was_modified`), and the reverse order
(registered-but-uncorrupted) is semantically premature. The two-WP split
forced by the `kitty-specs/` ownership ban above makes a literal single commit
impossible across WP boundaries, so this coupling is instead expressed as a
tight `dependencies: [WP01]` edge on WP02 — **not** a shared lane. WP01 and
WP02 are in two distinct lanes (`lane-planning` and `lane-a` respectively, per
`lanes.json`), joined only by `depends_on_lanes` — dependency edges never
collapse lanes in this codebase. `lane-planning` (this WP) resolves to the
repo-root checkout, which is the mission's actual PR-source branch
(`issue-4957-archived-conflict-markers`), so this WP's repair commit lands
directly on that branch with no merge/consolidation step of its own. The
`depends_on_lanes` edge only controls **when WP02 can be claimed** — it
cannot be claimed until this WP reaches `approved`/`done` — it is not a
merge-and-gate checkpoint over this WP's own commit. The only code-level
gate, `_assert_mission_terminal_ready` (`src/specify_cli/merge/executor.py:461-521`),
is a **mission-wide** precondition — it is evaluated once over
`run.all_wp_ids` (every WP in the mission, WP01 and WP02 together, not just
WP02/lane-a) early in a single `spec-kitty merge` invocation (after the
review-artifact consistency gate and merge-state setup/load, but strictly
before `_phase_merge_lanes`, the first lane-consolidating phase). It gates
local lane consolidation only — it never runs against, and
never gates, a `git push origin` or `gh pr create` from this checkout. That
is a separate action from pushing this WP's already-resident commit to
origin or opening/updating a PR, and nothing in the tooling stops that push
from happening the instant this WP alone lands — which would reproduce the
transiently-red `archive-freeze` state Section D wanted to avoid. **Operative discipline (binding, since no
gate enforces it): do NOT push the mission branch
(`issue-4957-archived-conflict-markers`) to origin, and do NOT open or update
a pull request from it, until BOTH this WP and WP02 have reached
`approved`/`done`.** Only the branch tip after WP02 also lands should ever be
published, per the mission's single-PR convention (plan.md Section G). **Do
not treat a red `test_no_preexisting_archived_file_was_modified` as a problem
to fix within this WP** — that is expected and resolved by WP02, not by this
WP reaching into `tests/architectural/` (which this WP does not own).

**Which side to keep**: independently re-verified per spec.md Clarification
(c): `git merge-base --is-ancestor df2dac046 main` returns true (the `HEAD`
side, "chore: Move WP01 to done on spec 025 [claude-reviewer]", shipped to
`main`); `git merge-base --is-ancestor 5eda48f7 main` returns false (the
losing side, "chore: Start WP01 implementation [claude-planner]", is an
orphaned lineage). Keep the `HEAD` side; delete the marker lines and the
losing side entirely.

**Chokepoint callout**: the file this WP touches is not itself a shared
chokepoint, but the change is a modification to a *frozen archive root*
(`kitty-specs/`) enforced by the always-on `archive-freeze` CI job every PR in
this repository goes through — see WP02's Context for the shared-chokepoint
detail on that job's file.

**Do NOT spawn sub-agents.** Implement this WP's single subtask yourself,
directly. (This mission previously incurred an incident class where forked
sub-agents inherited an entire WP brief and raced commits against each other —
do not repeat that pattern here.)

## Subtask T001: Resolve the conflict-marker block to the HEAD side

**Purpose**: Make
`kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
valid, corruption-free Markdown by resolving lines 758–773 (FR-001).

**Steps**:
1. Open `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
   and locate the Activity Log section (starts at line 753, "## Activity Log").
   Confirm the corrupted block is still at lines 758–773 before editing — a
   line-number drift means something else touched this file since planning;
   stop and re-read the live content rather than editing blind.
2. The corrupted block currently reads (line numbers as of this WP's
   planning-phase read; re-confirm before editing):
   ```
   758: <<<<<<< HEAD
   759-770: (twelve HEAD-side Activity Log lines, verbatim, in order)
   771: =======
   772: - 2026-01-28T04:40:48Z – claude-planner – shell_pid=22944 – lane=doing – Started implementation via workflow command
   773: >>>>>>> 5eda48f7 (chore: Start WP01 implementation [claude-planner])
   ```
3. Remove exactly three things: the `<<<<<<< HEAD` marker line (758), the
   `=======` marker line (771), and the `>>>>>>> 5eda48f7 (...)` marker line
   plus the one losing-side Activity Log line immediately above it (772–773).
4. Keep every line that sat between the `<<<<<<< HEAD` marker and the
   `=======` marker (the twelve lines from 759–770) **verbatim and in the same
   order** — do not reformat, reword, reorder, or drop any of them. These are
   the real Activity Log entries for the lineage that shipped to `main`.
5. Confirm the result reads as one continuous Activity Log list with no gap,
   no marker text, and no `5eda48f7`-side content — the line immediately
   following the last preserved HEAD-side entry should be the file's next
   existing section (`## Implementation Command`), separated by the same
   blank-line spacing the file already uses elsewhere in this section.
6. Do not touch any other line in the file. This WP's `owned_files` is exactly
   this one path — stay inside it (a small, well-justified out-of-map edit
   would need a one-line rationale per doctrine, but none should be needed
   here).

**Files**: `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
(content edit only, net 4 lines removed, 0 lines added — 3 marker lines plus
the 1 losing-side line).

**Validation**:
- `git grep -nE '^(<<<<<<<|>>>>>>>) ' -- kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
  returns zero hits.
- Manually diff the file against its pre-repair blob (`git show
  HEAD:kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
  or equivalent) and confirm: only the three marker lines and the one
  losing-side line are removed; all twelve HEAD-side lines are present,
  verbatim, in original order; nothing else in the file changed.
- Do **not** run `tests/architectural/test_archive_root_byte_identical.py`
  expecting it to pass in isolation after this WP alone — see the
  landing-order coupling note in Context above. WP02's guard tests are the
  ones that assert this repair's correctness end-to-end once both WPs have
  landed.

## Definition of Done

- [ ] `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
  contains no line matching `^(<<<<<<<|>>>>>>>) ` (FR-001, SC-001 partial —
  the full SC-001 grep also covers the other three archive roots, which this
  mission does not otherwise touch).
- [ ] All twelve `HEAD`-side Activity Log lines (originally lines 759–770) are
  present, verbatim and in order, with no gap.
- [ ] No `5eda48f7`-side content survives anywhere in the file.
- [ ] No other line in the file was modified.
- [ ] Per-subtask completion is recorded via `spec-kitty agent tasks
  mark-status T001 --status done` (event-sourced — not a hand-ticked
  checkbox above).

**Gate set** (carried verbatim-consistent from plan.md Section C — this WP's
diff is covered by the "trivially yes" rows; the two rows worth naming
explicitly for this WP):

| Gate | Applies? | Why |
|---|---|---|
| `tests (corpus)` (`tests-corpus` job, marker-selected) | Yes | Its path filter includes `kitty-specs/**/tasks/**`, which this WP's file matches exactly. |
| **archive-freeze** (`test_archive_root_byte_identical.py -q`) | Yes — central, but not green from this WP alone | This is the job whose invoked file gains the carve-out entry in **WP02**; per the landing-order coupling note above, this test is expected to be red immediately after this WP lands alone and only goes green once WP02's carve-out entry also lands. Do not attempt to make it pass from within this WP. |
| ruff lint + `ruff format --check`, `uv lock --check`, import-linter, `spec-kitty regen --check`, terminology guard, layer rules/pyproject shape, `architectural-heavy`, diff-cover, `packs.yml`, wheel build | Yes (trivially, or not applicable) | Same reasoning as plan.md Section C — this is a content-only Markdown edit with no code, dependency, or workflow change. |

## Risks

- **Line-number drift**: if the corrupted block has moved from lines 758–773
  by the time this WP is implemented (e.g., another change touched this file
  in the interim), re-read the live file rather than trusting the line numbers
  in this prompt — the *content* pattern (`<<<<<<< HEAD` … twelve lines …
  `=======` … one losing line … `>>>>>>> 5eda48f7 (...)`) is the authoritative
  target, not the line numbers.
- **Transient red on `test_no_preexisting_archived_file_was_modified`**: expected
  and resolved by WP02, not a defect in this WP — see Context. Do not "fix" it
  by adding a carve-out entry from within this WP (that file is out of this
  WP's `owned_files`).
- **Reformatting temptation**: resist reformatting or "cleaning up" the
  preserved HEAD-side lines while resolving the conflict — FR-001 requires
  verbatim preservation, not stylistic improvement.
- **Mission-wide issue-matrix gate may block this WP's own approval first**:
  `issue-matrix.json` carries six rows (#4928, #4936, #4954, #4956, #4957,
  #4972) at the gating `unknown` placeholder for the whole mission, and the
  approval/done-transition validator hard-blocks on any `unknown` row. This
  WP has no lane dependency and could be submitted for approval before WP02
  even exists — and hit that same mission-wide block. That is expected and
  tracked, **not** a defect in this WP's own repair: WP02's Subtask T008 is
  where all six rows get resolved via `spec-kitty agent issue-verdict`. If
  this WP's approval stalls on an issue-matrix check, treat it as
  pending-on-WP02, not a reason to reject the repair itself.

## Reviewer Guidance

- Confirm the diff against the pre-repair blob touches *only* the marker lines
  and the losing-side line — nothing else changed, and nothing was
  reformatted.
- Confirm all twelve HEAD-side lines survive verbatim and in order.
- Do **not** reject this WP for a red `test_no_preexisting_archived_file_was_modified`
  taken in isolation — that is expected until WP02's carve-out entry also
  lands (a separate lane, gated only by `depends_on_lanes` — see Context).
  Reject only if the *content* of the repair itself is wrong (wrong side
  kept, lines dropped/reordered/reworded, or other lines touched).
- Run `git grep -nE '^(<<<<<<<|>>>>>>>) ' -- kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
  and confirm zero hits.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude
```
