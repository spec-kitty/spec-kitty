---
work_package_id: WP01
title: ADR - one status read contract and restated ruling 3
dependencies: []
requirement_refs:
- FR-007
- FR-046
- FR-061
- C-016
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Governing ADRs
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/
create_intent:
- docs/adr/4.x/2026-11-06-2-one-status-read-contract.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-11-06-2-one-status-read-contract.md
- docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md
- docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md
role: implementer
tags: []
task_type: plan
tracker_refs: []
---

# Work Package Prompt: WP01 - ADR: one status read contract and restated ruling 3

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission lane-worktree-model-hardening-01M6QY1M`).
- Address every feedback item before marking the work complete. Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP01 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

Use the workspace path the command prints. Never reconstruct it.

## Objectives & Success Criteria

Record, before any code changes behaviour, the S1 status read contract (#7277) and the restated ruling 3 for lane checkouts (#7281):

1. A new Proposed ADR `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md` that declares exactly one read source per topology and Mission state (FR-007).
2. The ADR explicitly reverses `coord-artifact-single-home-01M3V4BE#FR-017` and `coord-artifact-single-home-01M3V4BE#C-002` (the loud repository-root fallback for an empty coordination surface), and an amendment section appended to `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md` points at the new ADR.
3. The ADR records the FR-061 placement contract change (DM `01M6R0QJVPVZG2QT8MWQD4NXJR`): for `topology_source: default` the PRIMARY partition resolves to the Mission topic branch until `consolidate`; explicit `--topology` Missions keep PRIMARY on `target_branch`.
4. An amendment section appended to `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md` states the restated ruling 3 for every lane topology and keeps Assert A' (FR-046).
5. Each record names its confirmation tests (WP05 matrix test, WP07 single-door gate, WP09 every-route exclusion test).

Done means: a reviewer can map every topology x coordination state (materialized, empty, unmaterialized, deleted, consolidated) to exactly one declared source, and every rule in spec "Rules and Invariants" 1 and 2 is stated.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`; Mission `spec.md` (User Story 1, User Story 5, FR-001 to FR-007, FR-040 to FR-046, FR-061, Rules 1 and 2); `research.md` R-1, R-2, R-4, R-6 (PRIMARY placement paragraph); `data-model.md` §2; `decisions/` (DM `01M6QY3S1H6G5N853PJAPJS7CE` status source of truth, DM `01M6QY3XQJ5NAYVF3GMZ7ZPPRE` ruling 3 restated, DM `01M6R0QJVPVZG2QT8MWQD4NXJR` PRIMARY placement).
- ADR template: `docs/architecture/adr-template.md`. Copy the frontmatter shape of a recent 4.x ADR (e.g. `docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md`): `title`, `description` (<= 180 chars), `status: Proposed`, `doc_status`, `kind: ADR`, `date: '2026-11-06'`.
- C-016: Proposed until the operator accepts; amendments are appended sections (`## Amendment 2026-11-06: ...`), never edits of earlier text. Do NOT add index rows (the bot does it).
- ADR number: `2026-11-06-1` is the S4 ADR on #7275. This WP uses `2026-11-06-2` exactly. WP02 holds `-3`, WP03 holds `-4`, `-5`, `-6`.
- C-001 terminology: "Mission" never "feature"; `consolidate` for lane consolidation; name the sense of "primary" (repository root checkout vs PRIMARY partition) every time.
- This WP writes no code. It is a planning artifact; every owned file is under `docs/`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

> Populated by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T001 - Draft the read-contract ADR

- **Purpose**: one governed statement of where status is read from.
- **Steps**:
  1. Create `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md` from the template. Title: "One status read contract".
  2. **Context**: nine adapters give four answers for an unmaterialized coordination state (research R-1, brief A table A1); #6466 and #7198 symptoms; short-lived checkouts (ruling 5) and the S9 write service make the unmaterialized state normal.
  3. **Decision**: the door `resolve_status_read(repo_root, mission, *, owned=None) -> StatusReadSurface` with sources:
     - `WRITE_CHECKOUT` for `single_branch`, `lanes` and provisional Missions (never a ref: appends there are uncommitted);
     - `COORD_WORKTREE` for `coord` / `lanes_with_coord` when the coordination worktree is materialized;
     - `COORD_BRANCH_REF` when that worktree is empty or unmaterialized (`git cat-file --batch` of `refs/heads/<coord>:kitty-specs/<dir>/status.events.jsonl`);
     - the declared pre-seed `WRITE_CHECKOUT` fallback (stamped `fallback_reason`) when the coordination branch exists but holds no log yet;
     - `CoordinationBranchDeleted` raised when the branch is gone (unchanged);
     - `CONSOLIDATED_TARGET` after consolidation.
  4. Root normalization: every input root is normalized; a lane root re-anchors to the main repository root through the #6884 registry classifier; a registry that cannot be read **fails closed with a typed error** (tightening #6884's fail-open choice; record this explicitly).
  5. Ref reader: absent file on a readable ref = empty history; missing/unreadable ref or git failure = `StatusSurfaceRefUnreadable` (`STATUS_SURFACE_REF_UNREADABLE`).
  6. NFR-001: at most one batched object-read subprocess per Mission per command.
  7. Invariants: never a lane path, never a path that does not exist, never a silent fallback.
  8. **Considered options** (from R-1): keep the loud root fallback (rejected), materialize on read (rejected), raise on unmaterialized (rejected).
- **Files**: the new ADR (~150-220 lines).

### Subtask T002 - Reverse FR-017 / C-002 and amend ADR 2026-06-19-1

- **Steps**:
  1. In the new ADR add a "Reverses" subsection quoting `coord-artifact-single-home-01M3V4BE#FR-017` and `#C-002` by reference and stating the new behaviour (empty/unmaterialized coordination worktree reads the committed branch, not the repository root checkout copy).
  2. Append to `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md` a section `## Amendment 2026-11-06: superseded by the one status read contract` with 5-10 lines linking `../4.x/2026-11-06-2-one-status-read-contract.md`. Do not edit earlier text. Update its frontmatter `status` only if the repository's ADR conventions do that for partially superseded records (check two existing amended ADRs first; if unsure, leave it).

### Subtask T003 - Record the FR-061 PRIMARY placement change

- **Steps**: add a "Placement of the PRIMARY partition for default Missions" decision section:
  - PRIMARY partition kinds = `_PRIMARY_ARTIFACT_KINDS` (`src/mission_runtime/artifacts.py:180`): spec, plan, research, data-model, contracts, tasks, WP files, `lanes.json`, `meta.json`.
  - For `topology_source: default`, reads and writes resolve to `meta.mission_branch` (the topic branch; after a multi-lane settlement also the coordination branch) until `consolidate` lands it on `target_branch`.
  - Explicit `--topology` Missions keep PRIMARY on `target_branch`.
  - Consequence: after settlement the repository root checkout no longer shows planning files; readers go through the read door or the placement seam, never a root-checkout path. `spec-kitty agent context resolve --json` (`mission_dir`) and `check-prerequisites --paths-only` must report the PRIMARY-partition location (confirmed by tests in WP05 and WP14).
  - Name it a placement contract change carried by the read door (WP05) and the placement seam (WP14) as one change.

### Subtask T004 - Amend ADR 2026-07-29-1 with the restated ruling 3 [P]

- **Steps**: append `## Amendment 2026-11-06: lane checkouts carry no live status` to `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md`:
  - lane checkouts never show `status.events.jsonl` / `status.json` (sparse exclusion by the one lane-checkout helper, on every topology with code lanes, `lanes` included);
  - Spec Kitty never writes or commits them in a lane (write seam classifies targets through the worktree registry, not path shape);
  - no reader reads a lane copy;
  - the fork-time blob stays in lane history; no lane-side deletion commit (C-008); Assert A' is kept and why (deleting would carry a deletion onto the Mission/coordination branch at consolidation and trip `auto_rebase._refuse_preexisting_lane_status_deletions`);
  - existing lane worktrees: the clone-local migration and the `LANE_STATUS_AUTHORED` doctor probe (WP10).

### Subtask T005 - Confirmation tests, cross-links, validation

- **Steps**:
  1. Add a "Confirmation" section naming: `tests/status/test_read_surface_door.py` (WP05), `tests/status/test_status_readers_cross_cwd_parity.py` (WP06), `tests/architectural/test_status_read_single_door.py` (WP07), `tests/lanes/test_lane_checkout_helper.py` every-route exclusion (WP09).
  2. Cross-link #6884's contract (`status-read-root.md` on that branch) by PR reference, ADR `2026-10-01-2` (Mission Status Read API) and the WP03 ADRs C-1/C-3 as forward references.
  3. Run validation (below).

## Validation

```bash
cd /home/user/spec-kitty
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python -m scripts.docs.check_spelling --pass docs 2>/dev/null || true   # if the pass exists; otherwise skip
git diff --check
```

- If a docs frontmatter/link validator exists under `scripts/docs/` (list it), run it on the three files.
- Do NOT run `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Append friction and decisions to the Mission tracer files (this is a planning WP, so you may write them directly):

- `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/tooling-friction.md`
- `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/approach.md`
- `kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/design-decisions.md`

Format: `- **[YYYY-MM-DD][implement WP01] <finding>.** <detail>. Disposition: <...>.` If your workspace is a lane worktree where Mission files must not change, return the lines in your completion summary instead and the orchestrator appends them.

## Risks & Mitigations

- **Number collision**: re-list `docs/adr/4.x/` first; if `2026-11-06-2` is taken, stop and ask the orchestrator (WP02-WP03 and every code WP cite these paths).
- **Deciding beyond the rulings**: options the rulings leave open stay as options with a recommendation.
- **Edits to old text**: only append.

## Review Guidance

- Every topology x coordination state maps to one source; fail-closed registry recorded; FR-017/C-002 reversal explicit; FR-061 rule present with the explicit-topology exception; Assert A' kept; confirmation tests named; status Proposed; no index rows added.

## Definition of Done

- Three files changed as above, terminology guard green, no edits outside owned files (tracer appends excepted).

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "..."`
- `spec-kitty agent tasks move-task WP01 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks mark-status T001 T002 T003 T004 T005 --status done --mission lane-worktree-model-hardening-01M6QY1M`
