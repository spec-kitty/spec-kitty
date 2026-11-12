# Implementation Plan: Approval honesty: no fabricated reviewer or review cycle

**Branch**: `kitty/mission-approval-honesty-01M78J9S` → lands on `fix/3044-approval-honesty` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/approval-honesty-01M78J9S/spec.md`

## Summary

`move-task --to approved|done` fills in an approval's reviewer and reference itself. The reviewer
comes from `git config user.name`, and the reference is a minted `auto-approval:` token. The
command also writes a second review cycle when the reviewer already wrote one, accepts citations of
cycles that do not exist, and lets any `--agent` approve a review that another identity claimed.

The fix gives the approval path **one reviewer-of-record resolver** and threads its result into
every identity field. It deletes the git-user and auto-approval fallbacks; that deletion closes the
defect class by construction. It adds two refusals, approver-not-claimant and cited-cycle-missing.
The approval adopts the review cycle the reviewer wrote after the claim instead of allocating
another. `approved -> done` and arbiter overrides carry forward the approval's own reviewer and
reference.

## Technical Context

**Language/Version**: Python 3.11+ (CLI, `src/specify_cli`)
**Primary Dependencies**: typer, rich, ruamel.yaml; `spec_kitty_events` (consumed, unchanged)
**Storage**: Files: `status.events.jsonl` (append-only event log) and `tasks/<WP>/review-cycle-N.md` (YAML frontmatter + body)
**Testing**: pytest; CliRunner end-to-end against a real temporary git repo (the `test_verdict_attribution_4670.py` seam), plus unit tests of the resolver and adoption helpers; mypy, ruff
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single
**Performance Goals**: `move-task --to approved` no more than 10% slower (NFR-001). The adoption probe reads only the files of one work package.
**Constraints**: No events-schema change (C-001); append-only history (C-002); stay out of `workflow*.py` and the consolidation verdict logic (C-003, C-004); complexity ≤ 15, and `_do_move_task` is already at 15, so it must not grow
**Scale/Scope**: ~6 source modules, ~10 test files re-pinned, 1 skill doc, 1 runtime hint, 1 ADR amendment

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | **Pass, by design.** Today there are three identity sources: `_mt_approval_facts`, `_mt_resolve_reviewer_identity` and the cycle writer's own chain. After the fix there is one resolver, and every field reads it. |
| ATDD / red-first (SO #4, C-011) | Each concern starts with a failing test through `move-task` in a real git repo, committed before the fix. |
| Architectural gate discipline (SO #5) | The defect class is closed by **deleting** `_detect_reviewer_name` and the approval-path mint of `synthetic_auto_approval_ref`, so no allowlist is needed. A non-vacuous end-to-end test pins the absence of a distinctive git name. No new size or ratchet gate (C-006). |
| Campsite / tidy-first (SO #2) | The tidy-first enabler comes before the behaviour changes. It extracts the resolver as a pure function, routes the three existing sources through it with behaviour preserved, and applies #6709's rename. |
| Review independence and approval-stamp bound (ADR `2026-10-04-5`) | Unchanged. This mission only adds refusals. An ADR amendment records the reviewer-of-record rule and the new codes. |
| Pack tiers | The core skill `src/charter/offering/skills/spk-run-verdict-capture/SKILL.md` is edited here. The open-packs prompt is filed upstream (C-005). |
| Terminology | Mission, never "feature"; "review claimant" is defined in the spec glossary. |
| Overlap | `prompt_builder.py` (#7596 touches it) is left alone. Its APPROVE line already carries the caller's `--agent` suffix. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/approval-honesty-01M78J9S/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/move-task-approval.md   # CLI contract: recorded fields + refusals
├── research/                         # pre-spec squad output (code grounding, folds)
├── traces/                           # tracer files (SO #3)
└── checklists/requirements.md
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── tasks_move_task.py            # _mt_approval_facts, resolver, claimant/identity refusals; delete _detect_reviewer_name
├── tasks_move_task_hops.py       # review_result + policy_metadata.tool read the reviewer of record
├── tasks_move_task_executor.py   # evidence overwrite reads the reviewer of record (no durability split)
├── tasks_verdict_persistence.py  # approval cycle write: adopt post-claim cycle; no synthetic body ref
├── tasks_transition_core.py      # _approval_evidence: reference never a minted token
└── tasks.py                      # --reviewer help text (no "auto-detected from git")
src/specify_cli/review/cycle.py   # rename create_rejected_review_cycle -> create_review_cycle (+alias); adoption probe helper; citation parse
src/runtime/next/runtime_bridge_decision_mapping.py  # approval hint carries --agent
src/charter/offering/skills/spk-run-verdict-capture/SKILL.md
docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md  # amendment
docs/changelog/unreleased/<id>.fixed.md
```

**Structure Decision**: Single project. All behaviour changes stay on the `move-task` approval path and the review-cycle module it calls.

## Design

### Reviewer of record (FR-001, FR-002, FR-006, FR-007)

One function `resolve_reviewer_of_record(st) -> ReviewerOfRecord` lives in
`tasks_move_task.py`, next to `_mt_resolve_active_reviewer_identity`, and is computed once in
`_mt_gather_late_facts`. Resolution order:

1. **Forced move** (`--force`, including arbiter override): the forcing actor's asserted identity
   (`--agent`, else the claimant, else the recorded placeholder `user`). Reference:
   `force-override`; for an arbiter override it is the arbiter decision's own `arb_review_ref`.
   Kind: `forced`.
2. **`approved -> done`** (approval already recorded): the reviewer and reference of the recorded
   approval, read through `event_sourced_review_result`. Kind: `carried`.
3. **Unforced approval**: the asserted identity, else the claimant. `--reviewer` is an assertion,
   not a fallback, and must agree (see the refusals below). Kind: `review`.

The resolved value feeds every identity field:
- `evidence.review.reviewer`;
- `review_result.reviewer`;
- `policy_metadata.tool`;
- the cycle's `reviewer_agent`;
- the reproduction command.

The `durably_persisted` overwrite in the executor then only swaps the **reference** to the
verified pointer. The reviewer is already the same on both paths, so `--no-auto-commit` and a
damaged slot record the same identity.

The resolver is pure over a small fact bundle: asserted identities, claimant, forced flag,
recorded approval and arbiter reference. It is unit-testable without git.

### Refusals (FR-004, FR-005, FR-010; C-008)

| Condition (unforced only) | Code | Remedy in message |
|---|---|---|
| No asserted identity and no claim | `REVIEW_NOT_INDEPENDENT` (**existing** placeholder refusal; ratchet, no new code) | `--agent <identity>` |
| Approval out of `in_review` whose `--agent` / `--reviewer` is not the claimant (segment-wise equality via the existing identity helpers) | **`APPROVER_NOT_CLAIMANT`** *(new; see decision D-P2)* | `spec-kitty agent action review <WP> --mission <m> --agent <id>` to re-claim |
| `--reviewer` and `--agent` both given and different | **`APPROVER_NOT_CLAIMANT`** (same rule: one reviewer of record) | pass one identity |
| `--approval-ref review-cycle://…`, or reference/note text that cites `cycle N`, where the cycle's file is missing, invalid, or the reference of a recorded rejection | **`REVIEW_CYCLE_CITATION_MISSING`** *(new)* | names the expected path; write the review via `--review-feedback-file`, or cite an existing cycle |

All refusals run in the pre-mutation decision pass (`_mt_run_decision`), before any persist, so
NFR-003 (byte-identical on refusal) follows from placement. The new checks live in
`tasks_move_task_gates.py`, keeping `_do_move_task` at complexity 15.

### One review, one cycle (FR-008, FR-009, FR-012)

The approval write gains an adoption probe. It looks for a `review-cycle-N.md` in the work
package's cycle directory that meets all of:
- it is **valid** (`validate_review_artifact_file`);
- its `reviewed_at` is at or after the latest claim's `at`;
- its `reviewer_agent` equals the reviewer of record;
- no recorded rejection references it.

If one exists, the approval references it and writes nothing. If none exists, it writes one, as
today. Cycles written before the claim are never adopted (FR-009). This is what makes the #6709
"repeat approval reuses an older cycle" case honest. `approved -> done` writes no cycle, which is
unchanged and now pinned (FR-012).

### Shipped guidance (FR-011)

- **`SKILL.md`:** the approve line gains `--agent <your identity>`.
- **`runtime_bridge_decision_mapping.py:318`:** the hint gains `--agent <identity>`.
- **`--reviewer` help text:** drops "auto-detected from git".

## Decisions to escalate (plan point-cut)

- **D-P1: a non-adoptable reviewer-written cycle file.** Covers a post-claim `review-cycle-N.md`
  that is invalid (for example no frontmatter, as in `stale-coord-lane-base-01M67HRA` WP01) or
  attributed to another identity. `review-cycle-N.md` is a **tool-owned** filename
  (`review_feedback_source_path` docstring). The canonical route for a reviewer's text is
  `review-feedback-N.md` + `--review-feedback-file`.
  - *Recommend*: refuse with `REVIEW_CYCLE_NOT_ADOPTABLE`, naming the file and the canonical
    route.
  - *Alternative*: write N+1 as today and warn. That leaves part of #7571 open, because the
    reviewer's render and the tool render still count as two cycles.
- **D-P2: the new codes.** Names `APPROVER_NOT_CLAIMANT` and `REVIEW_CYCLE_CITATION_MISSING`
  (plus `REVIEW_CYCLE_NOT_ADOPTABLE` if D-P1 is accepted), exit 1, the move-task refusal shape,
  and recorded in an ADR `2026-10-04-5` amendment. Are they also aliased under `SINGLE_BRANCH_*`
  like `REVIEW_NOT_INDEPENDENT`? *Recommend*: no alias. They are not topology-specific.
- **D-P3: `--reviewer` semantics.** It becomes an identity assertion that must equal the approver;
  it is never a display name. *Recommend*: yes. An alternative that keeps it as free text would
  re-open #7569, because a caller could pass any human name.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Reviewer-of-record resolver (tidy-first enabler)

- **Purpose**: Extract one pure resolver and route today's three identity sources through it with no behaviour change. This is the enabler step; it also applies #6709's rename with an alias.
- **Relevant requirements**: FR-001 (structure), FR-013
- **Affected surfaces**: `tasks_move_task.py`, `tasks_move_task_hops.py`, `tasks_verdict_persistence.py`, `review/cycle.py`
- **Sequencing/depends-on**: none
- **Risks**: Source-text call-site counters (`test_verdict_attribution_4670.py:434-462`) and the arch gates listed in research §6 may pin names. Run them in this step.

### IC-02 — Honest identity and reference on approval

- **Purpose**: The resolver stops falling back to the git user and stops minting `auto-approval:`. All five fields read it, and `approved -> done` and the arbiter path carry the approval forward.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, FR-011
- **Affected surfaces**: `tasks_move_task.py` (delete `_detect_reviewer_name`), `tasks_transition_core.py`, `tasks_move_task_hops.py`, `tasks_move_task_executor.py`, `tasks.py` help, `runtime_bridge_decision_mapping.py`, `SKILL.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: Re-pins ~10 test files that assert the git fallback or the token. `DoneEvidence` requires a non-empty reference, which the carried or `force-override` reference satisfies.

### IC-03 — Approver must be the claimant

- **Purpose**: Refuse an unforced approval out of `in_review` by a non-claimant, or with a conflicting `--reviewer`.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `tasks_move_task_gates.py` (new check), `tasks_move_task.py` (registration in the decision pass)
- **Sequencing/depends-on**: IC-01
- **Risks**: An existing test that approves with a different `--agent` than its claim would now refuse; re-pin it after checking intent. The claimant comparison must reuse the segment-wise identity helpers, never string equality.

### IC-04 — One review, one cycle; cited cycles exist

- **Purpose**: Adopt the reviewer's post-claim cycle instead of allocating another, and refuse citations of missing or rejected cycles.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-012
- **Affected surfaces**: `tasks_verdict_persistence.py`, `review/cycle.py` (adoption probe and citation parser), `tasks_move_task_gates.py`
- **Sequencing/depends-on**: IC-01; it can follow IC-02
- **Risks**: The cycle directory placement is shared with #7546, so read through the existing `_review_cycle_read_candidate_dirs` and never add a new join. Citation regex false positives are limited to the explicit `cycle N` forms.

### IC-05 — Documentation, ADR amendment, changelog, follow-ups

- **Purpose**: Record the reviewer-of-record rule and the new codes in an amendment to ADR `2026-10-04-5`, add the changelog fragment, file the follow-up issues named in the spec Scope, and file the #3451 disposition.
- **Relevant requirements**: C-008, SC-005
- **Affected surfaces**: `docs/adr/4.x/2026-10-04-5-…md`, `docs/changelog/unreleased/`, the CLAUDE.md approval-stamp paragraph (one sentence; check the charter-vs-CLAUDE.md drift rule)
- **Sequencing/depends-on**: IC-02, IC-03, IC-04
- **Risks**: none
