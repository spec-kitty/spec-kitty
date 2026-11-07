---
work_package_id: WP02
title: ADR - topology settled once at first finalize, and S8 approval windows
dependencies: []
requirement_refs:
- FR-050
- FR-061
- FR-077
- C-010
- C-011
- C-016
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Governing ADRs
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/
create_intent:
- docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md
- docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
role: implementer
tags: []
task_type: plan
tracker_refs: []
---

# Work Package Prompt: WP02 - ADR: topology settled once at first finalize, and S8 approval windows

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission lane-worktree-model-hardening-01M6QY1M`). Address every item; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP02 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

Govern S7 (#7282) and S8 (#7283) before any is built:

1. New Proposed ADR `docs/adr/4.x/2026-11-06-3-topology-is-settled-once-at-first-finalize.md` (FR-050) that supersedes #5100 item 2 (issue comment 5870360497; no ADR file holds that decision) and states: the size rule; the "lanes otherwise" mapping to `lanes_with_coord` on every target with the topic branch as the coordination branch (A-3, DM `01M6R0B954ZPQN5NV4R1ZRE7NY`); plain `lanes` / `coord` explicit-only; deferred materialization; the provisional representation; `topology_source`; `create_return_branch`; decide-once; compensation; the PRIMARY placement rule (FR-061, DM `01M6R0QJVPVZG2QT8MWQD4NXJR`); the `--pr-bound` fallback dropped (DM `01M6R0QQM5FCPY736008AD4W6V`); C-010 (S8 before or with S7).
2. An appended D2 amendment on `docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md`: Decision 2 becomes "stored at create, settled once at the first finalize, read thereafter".
3. An appended amendment on `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` (FR-077) narrowing the "planning lanes and `single_branch`" residual to per-WP windows, appended as a NEW dated section at the very END of the file.

## Context & Constraints

- Read: charter; `spec.md` User Stories 3 and 4, FR-050 to FR-061, FR-070 to FR-078, Assumptions A-1 to A-8, Edge Cases; `research.md` R-6, R-7, R-8; `data-model.md` §1 (meta keys and state machine) and §5 (approval window); `contracts/finalize-tasks-json.md`, `contracts/mission-create-json.md`, `contracts/error-codes.yaml`; decisions DM `01M6QY2SJ9ND1SKMH2230FS7JA`, `01M6QY46RJGFZN6WBVQQXCZSY6`, `01M6QY42BBA8GZ3R4FPGCYY3F5`, `01M6QZ02HDACM7A0VNYSAQ8MQB`, `01M6R0B954ZPQN5NV4R1ZRE7NY`, `01M6R0BDYC29D6XMDY72R22CP9`, `01M6R0QJVPVZG2QT8MWQD4NXJR`, `01M6R0QQM5FCPY736008AD4W6V`.
- **#7255 is NOT merged** (`issue-7210-finalize-derived-pin`) and adds "Amendment 2026-11-05" to ADR `2026-10-04-5`. Append your amendment as the LAST section of the file on the current topic branch, headed `## Amendment 2026-11-06: per-WP approval windows for single_branch (#7283)`. When #7255 lands, the rebase conflicts only at the end of the file; resolve by keeping both sections, 2026-11-05 first. Note this in your completion summary.
- ADR template `docs/architecture/adr-template.md`; frontmatter like other 4.x ADRs; `status: Proposed`; C-016 (append amendments, no index rows).
- ADR number `2026-11-06-3` exactly (`-1` is #7275's S4 ADR, `-2` is WP01).
- C-001: name the sense of "primary" and "merge" every time.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T006 - Topology ADR: size rule, mapping, deferred materialization

- **Steps**:
  1. Context: tracer evidence of scaffolds hand-removed after `specify` chose a coordination topology on a protected branch; operator rationale (shrinking lanes/coord into `single_branch` is the most expensive transition, growing from one topic branch is cheap).
  2. Decision 1 (create): without `--topology`, `create` mints exactly one Mission topic branch `kitty/mission-<slug>-<mid8>` (A-1) whatever the target's protection: no lane, no lane or coordination worktree, no coordination branch. `--topology` and `--owned-checkout` behave as today (`topology_source: explicit | owned_checkout`).
  3. Decision 2 (size rule): `single_branch` when <= 2 non-canceled WPs (planning-artifact WPs count; canceled do not) or <= 1 code lane (`lane-planning` excluded; 0 code lanes -> `single_branch`); otherwise `lanes_with_coord` on every target with the topic branch as the coordination branch under the same name. Tie: exactly 2 WPs with 2 code lanes -> `single_branch`.
  4. Decision 3 (materialization): settlement writes `lanes.json`; lane branches/checkouts appear only through implement-time allocation (A-7); lanes are cut from the topic branch, lane consolidation lands into it, it lands on the target at `consolidate`; nothing lands on the target at settlement; no fast-forward/merge step.
  5. The root checkout move: git forbids one branch in two worktrees, so settlement moves the repository root checkout to `create_return_branch` before the coordination worktree checks out the topic branch.
  6. Rejected alternatives (A-3, R-6 a-e).

### Subtask T007 - Provisional record, placement, decide-once, compensation, C-010

- **Steps**:
  1. Provisional representation (DM `01M6R0BDYC29D6XMDY72R22CP9`): `topology: single_branch`, `mission_branch: <topic>`, `topology_source: default`, `topology_settled: false`, `create_return_branch`; `create --json` reports `topology_provisional: true`. Legacy meta (no `topology_source`) = settled (FR-057). `topology_decision` object write-once (data-model §1).
  2. PRIMARY placement (FR-061): default Missions read/write PRIMARY on the topic branch until `consolidate`; explicit keeps `target_branch`. Reference WP01's ADR for the read side.
  3. Decide-once (FR-054, C-011): only at the first finalize, before finalize's first status write and before any WP is claimed; re-finalize, legacy `tasks-finalize` repair and doctor rebuilds never re-decide; growth keeps the settled topology.
  4. Compensation (FR-056, NFR-003): undo stack; any failure restores `meta.json` byte for byte, branch tips, absence of coordination worktree, root checkout on the topic branch; refusals `WRITE_CHECKOUT_OCCUPIED`, `WRITE_CHECKOUT_DIRTY` (#5676), `TOPOLOGY_SETTLEMENT_REFUSED`.
  5. `--pr-bound`: coordination-unreachable fallback to plain `lanes` dropped (A-5). `--commit-to-target` still requires explicit `--topology single_branch` (FR-060).
  6. C-010: no user-reachable settlement ships without the S8 bound.
  7. Contract: one orchestrator-api bump 1.23.0 -> 1.24.0 carries `topology_source`/`topology_provisional`/`topology_decision` (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).
  8. Risks: create from another provisional Mission's topic branch (R-6 risk; target resolution never picks another Mission's `mission_branch`/`coordination_branch`).

### Subtask T008 - Amend ADR 2026-06-22-1 Decision 2 [P]

- Append `## Amendment 2026-11-06: topology stored at create, settled once at the first finalize` to `docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md` (5-15 lines), linking the new ADR. Do not edit earlier text.

### Subtask T009 - Amend ADR 2026-10-04-5 with per-WP windows [P]

- **Steps**: append at the END of the file `## Amendment 2026-11-06: per-WP approval windows for single_branch (#7283)` covering:
  - stamp: every lifecycle transition of a WP in a Mission whose STORED topology is `single_branch` carries the Mission write branch head as `policy_metadata.lane_head` (never keyed on `is_planning_lane`); a `lanes` planning lane stays unstamped;
  - tier 1: `check_lane` on the Mission branch (content after the newest approval refuses `LANE_MOVED_AFTER_APPROVAL`);
  - tier 2: every content commit in `claim_base..mission_branch` (merges and bookkeeping excluded) lies in some approved `(O_k, S_k]`; else `LANE_MOVED_AFTER_APPROVAL` naming the commit and the preceding WP; overlapping windows accepted;
  - gate re-check reads the Mission branch through the claim's `lane_id -> branch` map, never `lane-planning`'s alias to the target;
  - back-compat refuse-plus-attest (`APPROVAL_STAMP_MISSING`, `--attest-approved-reviewed`), rebased branch `APPROVAL_STAMP_NOT_ON_LANE`; no marker key;
  - residuals: commit-to-target / direct-on-target unbounded (pinned by strict xfail, FR-078); missing `O_k` degrades to `(claim base, S_k]`, logged (A-8); commit during review; contested window;
  - no orchestrator-api code added (FR-076).

### Subtask T010 - Confirmation tests, cross-links, validation

- Name confirmation tests: WP12 `tests/integration/test_single_branch_approval_windows.py`, WP11 `tests/status/test_lane_head_single_branch.py`, WP13 `tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py`, WP14 `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py` and `tests/lanes/test_topology_settlement_compensation.py`.

## Validation

```bash
cd /home/user/spec-kitty
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
git diff --check
```

Run any docs frontmatter/link validator under `scripts/docs/` on the three files. Never a bare `tests/architectural/` sweep or `make test-full`.

## Tracer files

Append to `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/{tooling-friction,approach,design-decisions}.md` as `- **[YYYY-MM-DD][implement WP02] ...**`; if your workspace must not change Mission files, return the lines in your completion summary.

## Risks & Mitigations

- #7255 rebase conflict: appended last; documented.
- Over-deciding: open points stay options with a recommendation.

## Review Guidance

- All FR-050 elements present; FR-077 residuals listed; amendment is the last section of ADR 2026-10-04-5; #5100 item 2 superseded explicitly; status Proposed.

## Definition of Done

- Three owned files written; terminology guard green.

## Progress & Status

- `spec-kitty agent tasks move-task WP02 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks mark-status T006 T007 T008 T009 T010 --status done --mission lane-worktree-model-hardening-01M6QY1M`
