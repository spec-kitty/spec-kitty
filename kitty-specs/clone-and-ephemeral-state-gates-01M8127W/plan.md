# Implementation Plan: Gates that work in teammate clones and ephemeral reviewers

**Branch**: `kitty/mission-clone-and-ephemeral-state-gates-01M8127W` (topic) → target `issue-7809-clone-ephemeral-state-gates` (stacked on PR #7804) | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

## Summary

Five gates assume the state they need is local, pushed and anchored on the target branch. This plan fixes them in five independent concerns:

- **Docs work packages in a lane topology:** `finalize-tasks` normalises the kind of a docs work package to `code_change` when the Mission is in a lane topology, and counts it in the size-based topology settlement. A mixed docs + `kitty-specs/` work package is refused with a split remedy.
- **Remote-only lane branches:** review creates a local lane branch from the owning remote's tracking ref. It goes through one kernel helper, generalised from PR #7804.
- **Approval stamps:** an approval records the lane tip from before the review's own sync merge, and the approval bound accepts whichever recorded stamp the lane contains.
- **Hex colours:** issue discovery rejects hash-numbers with a leading zero and CSS hex colour declarations.
- **Planning-lane review range:** a range made only of bookkeeping commits is reported as unavailable.

Research, squad findings and operator rulings: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, git (subprocess through `kernel.git.run_git`)
**Storage**: git refs, `status.events.jsonl`, WP frontmatter, `lanes.json`
**Testing**: pytest. Red-first acceptance tests run through the real CLI with real bare-origin + clone fixtures where the defect is cross-clone. In-process unit tests cover each new branch.
**Target Platform**: Linux, macOS, Windows 10+
**Project Type**: single project (CLI)
**Performance Goals**: no added remote contact; at most one extra local git call per lane or work package on the common path (NFR-002)
**Constraints**:
- no push (C-002);
- reuse PR #7804's resolver (C-001);
- `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` layer rules;
- remote-contact owner gate (`tests/architectural/test_remote_contact_owner.py`);
- lane-checkout single seam gate (`tests/architectural/test_lane_checkout_single_seam.py`);
- `__all__` and the dead-symbol gate for `src/kernel/`.

**Scale/Scope**: about 15 source modules, 3 ADR amendments, 5 changelog fragments.

## Charter Check

- **Single canonical authority:**
  - One owning-remote materialisation helper replaces three copies: PR #7804's coordination helpers, `resolve_lane_base_ref`, and the new lane case.
  - One effective-stamp helper is read by every approval-stamp consumer.
  - The work package's kind stays the one authority for lane placement. Normalising it avoids a second, lane-based authority.
- **Architectural alignment:** the materialisation helper lives in `kernel/git/` (refs only, no remote contact, so it is not in `kernel/git/remote.py`, the remote-contact owner). The status pipeline stays git-free: the pre-sync tip comes through the injected lane-head reader.
- **ATDD-first:** every work package starts with a failing acceptance test through the pre-existing entry point (CLI or the public function the issue names), committed before the fix.
- **Terminology:** Mission, work package, lane, approval stamp. No `feature` in new prose or identifiers.
- **Testing policy:** targeted tests plus the owning subsystem directories and the named architectural gates. No full `tests/architectural/` or `make test-full` runs (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Out-of-matrix test directories are disclosed (C-005).
- **Sonar:** complexity ≤ 15, constants for repeated literals, no empty handlers, tests for every new branch.

No violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/clone-and-ephemeral-state-gates-01M8127W/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── approval-stamp-presync.md
│   └── finalize-kind-normalisation.md
├── checklists/requirements.md
└── tasks.md / tasks/   (created by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/kernel/git/tracking_branch.py               # NEW: owning tracking ref + create tracking local branch
src/specify_cli/coordination/surface_resolver.py  # PR #7804 helpers delegate to the kernel helper
src/specify_cli/workspace/context.py            # resolve_lane_base_ref uses the kernel probe
src/specify_cli/cli/commands/agent/workflow.py  # _reconcile_review_lane creates a remote-only lane branch
src/specify_cli/lanes/auto_rebase.py | lifecycle_sync.py   # record the pre-sync lane tip
src/specify_cli/status/lane_head.py             # reading carries the pre-sync tip
src/specify_cli/status/transition_pipeline.py   # stamps lane_head_presync on approval
src/specify_cli/consolidation/approved_bound.py | write_branch_bound.py | approved_attestation.py | git_probes.py
src/specify_cli/ownership/ (or lanes/)          # pure kind-normalisation rule
src/specify_cli/cli/commands/agent/mission_finalize*.py   # apply normalisation, settlement count, notice, mixed refusal
src/specify_cli/tasks/issue_matrix.py | issue_reference_discovery.py
src/specify_cli/review/wp_range.py              # bookkeeping-only planning range → unavailable
docs/adr/4.x/2026-10-04-5-*.md | 2026-11-06-3-*.md | 2026-11-08-2-*.md   # amendments
docs/changelog/unreleased/<issue>.fixed.md      # one per issue
```

**Structure Decision**: single project; changes stay inside the owning modules listed above.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Hex colours are not issue references

- **Purpose:** stop hash-number literals with a leading zero, and CSS hex colour declarations, from becoming issue-matrix rows.
- **Relevant requirements:** FR-012.
- **Affected surfaces:**
  - `src/specify_cli/tasks/issue_matrix.py`: `_GH_ISSUE_PATTERN` hash arm becomes `#([1-9]\d{1,5})`, and `_matched_issue_number` gets the colour filter (a declaration form such as `color:`, `background:`, `fill:` or `stroke:`, followed by a hash and 3, 4 or 6 hex digits).
  - `src/specify_cli/tasks/issue_reference_discovery.py`: `_SOURCE_DESCRIPTION_LEAD_PATTERN` and `_CLOSING_KEYWORD_PATTERN` get the same no-leading-zero rule.
  - Tests: `tests/specify_cli/tasks/`, `tests/tasks/`.
- **Sequencing/depends-on:** none.
- **Risks:**
  - The colour filter must not drop a real reference on a line that only mentions a CSS word. It matches the declaration form only, not a keyword anywhere on the line.
  - `#abc123` must stay unmatched (`test_issue_matrix_scaffold.py:237`).

### IC-02 — One owning-remote branch materialisation; review creates a remote-only lane

- **Purpose:** a teammate's review proceeds when the lane branch exists only as a remote-tracking ref.
- **Relevant requirements:** FR-006, FR-007, FR-008.
- **Affected surfaces:**
  - New `src/kernel/git/tracking_branch.py`:
    - `owning_tracking_ref(repo, branch) -> str | None`: `resolve_remote` + `tracking_ref` + a local `rev-parse --verify ^{commit}` probe.
    - `ensure_local_tracking_branch(repo, branch) -> bool`: `git branch --track --end-of-options <b> <ref>`; tolerates a concurrent creation; writes nothing without a ref.
  - `coordination/surface_resolver.py`: `coord_branch_tracking_ref` / `ensure_coord_branch_local_head` (PR #7804) become thin delegates.
  - `workspace/context.py:1228 resolve_lane_base_ref`: uses `owning_tracking_ref`. Its documented fallback is unchanged: `origin` when no owner resolves.
  - `cli/commands/agent/workflow.py _reconcile_review_lane` (`:2463-2486`): on `CREATE_FROM`, or when the origin check is off, unreachable or ambiguous and the lane has no local head:
    - refuse `DESTROYED_LANE` if `refs/spec-kitty/lane-tip/<lane>` exists and is not an ancestor of the tracking ref;
    - otherwise create the branch before the claim, so the claim's lane sync and `_create_review_worktree` both see a local head.
  - `_create_review_worktree` keeps its `-b` cut for any remaining path.
  - `lifecycle_sync` stays fail-closed.
- **Sequencing/depends-on:** none.
- **Risks:**
  - The kernel helper must stay refs-only: no remote contact (NFR-001), no `worktree add` (single-seam gate).
  - An ambiguous owner never picks a remote.
  - With the origin check off, a stale tracking ref seeds an older tip. Print a warning naming that.

### IC-03 — Approval stamp survives the review's own sync merge

- **Purpose:** an approval no longer depends on a commit only the reviewer's clone has.
- **Relevant requirements:** FR-009, FR-010, FR-011.
- **Affected surfaces:**
  - **Recording.** The lane sync (`lanes/auto_rebase.py attempt_auto_rebase`, called from `lifecycle_sync`) records the pre-sync lane tip in the local ref `refs/spec-kitty/review-presync/<lane-branch>`, only when it actually creates a merge.
  - **Reading.** `status/lane_head.py` `_read_lane_head` returns the pre-sync tip on the reading (a new optional field). It does so only when that tip is a first-parent ancestor of the lane head, reached through merge commits only. Otherwise the field is absent.
  - **Stamping.** `status/transition_pipeline.py _stamped_policy_metadata` writes `policy_metadata.lane_head_presync` next to `lane_head` when the field is present and differs from it.
  - **Bound.** One helper in `consolidation/approved_bound.py` (`effective_stamp`) returns the newest recorded stamp the lane contains (`lane_head`, else `lane_head_presync`), and every consumer binds on it: `stamp_refusal`, `check_lane`, `write_branch_bound` tier 2, `approved_attestation`.
  - **Absent-object refusal.** When neither stamp is on the lane, `git_probes.commit_in_clone` distinguishes "absent from this clone" (new remedy text) from "not on lane" (rewritten lane). The code stays `APPROVAL_STAMP_NOT_ON_LANE`; only the text and detail differ.
  - **ADR.** Amendment to ADR `2026-10-04-5`.
- **Sequencing/depends-on:** none. It touches no file IC-02 touches.
- **Risks:**
  - The bound must not weaken. A non-merge commit after the pre-sync tip still refuses when the bound is on the pre-sync tip. Both bound tiers drop merges already, so the sync merge itself never refuses.
  - The `policy_metadata` key classification: `lane_head` is `BRANCH_RELATIVE`, and the new key must be registered the same way.
  - Attestation rules (FR-012 of ADR `2026-09-29-1`) treat the new key like `lane_head`.

### IC-04 — Docs work packages get a lane in lane topologies

- **Purpose:** a docs work package in a lane Mission is implemented, reviewed, stamped and consolidated like a code work package.
- **Relevant requirements:** FR-001, FR-002, FR-003, FR-004, FR-005.
- **Affected surfaces:**
  - **Pure rule.** A new pure rule, `normalise_kinds_for_lane_topology(manifests, started_wp_ids)`, returns the rewritten manifests plus the list of rewritten WP ids.
    - A `planning_artifact` manifest with any owned path outside `kitty-specs/` becomes `code_change`.
    - A started work package is never rewritten.
    - Mixed `kitty-specs/` + other paths becomes `code_change` too, so the existing kitty-specs ownership refusal (`INVALID_WP_OWNED_FILES_KITTY_SPECS`) fires. Its remedy text gains the split instruction for this case.
  - **finalize-tasks (`mission_finalize.py`, `mission_finalize_lanes.py`, `mission_finalize_bootstrap.py`):**
    - **Settlement.** The settlement count (`_count_code_lanes_for_settlement`) uses the normalised manifests (FR-004, operator ruling "Count it").
    - **Persistence.** When the effective topology is a lane topology (settled this run, or explicit), the rewritten `execution_mode` is persisted to WP frontmatter (not in `--validate-only`).
    - **Notice.** A notice names each rewritten WP, on stderr and in JSON (`kind_normalised`).
    - **single_branch.** Kinds are not touched.
  - **ADR.** Amendment to ADR `2026-11-06-3`.
  - **Follow-up.** File an upstream issue in `spec-kitty-open-packs` for the template guidance (C-004).
- **Sequencing/depends-on:** none.
- **Risks:**
  - Frozen lane membership (ADR `2026-10-04-2`): re-finalizing an existing Mission must not move a started work package.
  - Settlement outcomes change for Missions with docs work packages, as ruled.
  - Interaction with `lanes.json` `planning_artifact_wps`: the kind view follows the persisted kind.

### IC-05 — Honest planning-lane review range

- **Purpose:** never present a bookkeeping-only range as the work of a planning-lane work package.
- **Relevant requirements:** FR-013.
- **Affected surfaces:**
  - `src/specify_cli/review/wp_range.py`: after deriving a planning-lane range from committed status events, if every commit in it touches only bookkeeping paths, return the unavailable outcome with a reason naming the shape.
  - `review/context_block.py`: renders it as other unavailable ranges.
  - ADR `2026-11-08-2`: cross-reference.
- **Sequencing/depends-on:** none. Mostly mooted by IC-04 for docs work packages.
- **Risks:** the bookkeeping definition must be the gate's own (`_is_bookkeeping`, or the status-only excluded prefixes), not a third one.
