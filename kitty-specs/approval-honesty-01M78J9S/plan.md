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

### Two pieces: one fact, one combiner

- **Claimant, the fact.** It is a pure `latest_review_claim_identity(events, wp_id)` in
  `status/review_roles.py`, the declared role leaf, next to `latest_implementer_identity`. It
  returns the newest **unforced**, non-migration entry into `in_review` whose actor is not in
  `GENERIC_IMPLEMENTATION_ACTORS`. This is the same rule as consolidation's
  `approved_bound._entered_review_by_claim` (decision `claimant_definition`). It is imported as a
  submodule (`from specify_cli.status.review_roles import …`), so `status/__init__.py`, which
  #7596 touches, stays untouched. `_mt_resolve_active_reviewer_identity` delegates to it.
- **Reviewer of record, the combiner.** A pure `resolve_reviewer_of_record(facts)` in
  `tasks_move_task.py` combines `--agent`, `--reviewer`, the claimant, the forced flag, the
  recorded approval (for `approved -> done`) and, as a late input, the arbiter reference. It
  returns `ReviewerOfRecord(identity, reference, kind ∈ {review, forced, carried})`.

Today six sources each pick an identity. Every one of them reads the combiner instead:
1. `_mt_approval_facts`;
2. `_mt_resolve_reviewer_identity`;
3. the cycle writer chain;
4. `_mt_hop_actor` and `_mt_approval_actor`;
5. `_mt_approval_policy_metadata.tool`;
6. the executor's `st.actor`.

The fields that carry the identity are the event `actor`, `review_result`, `evidence.review`,
`policy_metadata.tool`, the cycle's `reviewer_agent`, the cycle body and its reproduction command.

The resolution order:

1. **Forced** (`--force`, including arbiter override). The reviewer is the forcing actor
   (`--agent`/`--reviewer`, else the claimant, else the recorded placeholder `user`). The reference
   is `force-override`, or the arbiter's `arb_review_ref`, which is resolved after
   `_mt_fire_arbiter_persist`.
2. **`approved -> done`.** The recorded approval's reviewer and reference are copied **verbatim**
   (`event_sourced_review_result`; decision `carry_forward`). With no readable approval, the
   asserted identity with `force-override`, else the existing `REVIEW_NOT_INDEPENDENT` placeholder
   refusal.
3. **Unforced review.** `--agent`, else `--reviewer`, else the claimant. `--reviewer` is an
   assertion: it sets the actor when `--agent` is absent, and it must agree with `--agent` and the
   claimant (decision `codes_and_reviewer`).

`_detect_reviewer_name` (with its `tasks.py:408` re-export) and the approval-path mints of
`synthetic_auto_approval_ref`, `synthetic_approval_ref` and the `auto-forward:` arm are deleted.
The executor's durable overwrite then swaps only the **reference** to the verified pointer, which
makes `--no-auto-commit` honest too. Historical tokens stay readable (C-002); the grammar module
keeps its classifiers.

### Refusals and where they run (FR-004, FR-005, FR-010, FR-014; NFR-003)

| Check | Code | Home | Runs |
|---|---|---|---|
| No identity and no claim | `REVIEW_NOT_INDEPENDENT` (existing; ratchet) | `_mt_require_independent_approval` | unchanged |
| Unforced `in_review -> approved/done` whose identity is not identity-equal to the claimant; `--agent` and `--reviewer` disagree | `APPROVER_NOT_CLAIMANT` | **pure guard** `_guard_review_claimant`, added to `_GUARDS` right after `_guard_agent_ownership` (`tasks_transition_core.py`). It is a sibling of the existing ownership authority, not a second authority. | decision pass 1 |
| Cited cycle (a `review-cycle://` ref, or `cycle N` / `cycle-N` / `review-cycle-N` in ref or note) is missing, invalid, a rejection's cycle, or not after the latest claim | `REVIEW_CYCLE_CITATION_MISSING` | helper called from `_mt_require_independent_approval` (no new branch in `_do_move_task`) | before any cycle write |
| A post-claim `review-cycle-N.md` that is invalid or attributed to another identity | `REVIEW_CYCLE_NOT_ADOPTABLE` | same helper | before any cycle write |

**Identity equality.** Drop the role segment and require tool, model and profile to be equal
where both are recorded. Bare `claude` against `claude:sonnet:reviewer-renata` is **not** equal.
The rule is never derived from `not actor_identities_independent`.

**Codes.** Defined as constants in `tasks_transition_core.py` (not in `wp_evidence`, C-004), with
exit 1, the move-task refusal shape, and the code in the JSON diagnostic.

**NFR-003.** The new refusals all run before any write *this mission adds*. The pre-existing
`_mt_fire_override_persist` (`--skip-review-artifact-check` over a rejection) still runs before
pass 1. That ordering is pinned by an earlier mission's partial-write rule and is listed as a
residual with a follow-up issue. A test combines it with a non-claimant to document the boundary.

### One review, one cycle (FR-008, FR-009, FR-012, FR-014; decision `adoption_rule`)

The probe lives in `review/cycle.py` and reads through `_review_cycle_read_candidate_dirs`, with
no new path join (#7546). A file is **adoptable** when all of these hold:
- it is valid;
- **no status event references it** (a rejection's cycle is always referenced by its rejection);
- its N is greater than every cycle number referenced in the event log;
- its `reviewer_agent` is identity-equal to the reviewer of record.

**Outcomes:**
- Adoptable: the approval references it and writes nothing.
- A post-claim file that fails validity or identity: `REVIEW_CYCLE_NOT_ADOPTABLE` (unforced).
- `--review-feedback-file` given: no adoption; the #6652 leg writes as today.
- `approved -> done`: no cycle written (pinned).
- An adopted file is never undone by `revert_committed_verdict_write`.
- A pointer to an adopted file that is not committed is treated as local-only, exactly like a
  local-only write today.

The frontmatter has no verdict field (verified, `artifacts.py:218`), so verdicts are never read
from it.

### Shipped guidance (FR-011)

- **`SKILL.md`:** the approve line gains `--agent <your identity>`.
- **`runtime_bridge_decision_mapping.py:318`:** the hint gains `--agent <identity>` (outside
  #7596's files).
- **`--reviewer` help text:** "identity of the reviewer; must match --agent and the review
  claimant".
- **`prompt_builder.py`:** untouched (#7596).

## Operator rulings applied (plan point-cut)

| Decision | Ruling |
|---|---|
| `claimant_remedy` | `APPROVER_NOT_CLAIMANT` remedy is: the claimant records the verdict, or the operator uses `--force` (recorded as forced). No handoff path. Supersedes the re-claim remedy. |
| `non_adoptable_cycle` | Refuse with `REVIEW_CYCLE_NOT_ADOPTABLE`. |
| `codes_and_reviewer` | Three codes, no `SINGLE_BRANCH_*` alias, ADR amendment. `--reviewer` is a strict identity assertion. |
| `closure` | Close the four core issues on the recording side. The residuals below are documented and followed up. |

Agent design calls (recorded): `claimant_definition`, `carry_forward`, `adoption_rule`.

**Residuals (documented, not fixed):**
- `--force` bypasses the new refusals, and consolidation counts a forced approval after a claim as
  a review (#5721 route (a)).
- An auto-walk claims and approves in one move.
- `--agent <claimant>` impersonation cannot be detected.
- The override-persist ordering.
- `agent status emit` and `orchestrator-api transition` accept any reviewer.
- Consolidation's done bookkeeping uses the git user.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Claimant fact and reviewer-of-record combiner (tidy-first enabler)

- **Purpose**: Add `latest_review_claim_identity` and the pure combiner. Route all six identity sources through them with **behaviour preserved**: the git fallback and the tokens stay for now, but behind the combiner. Apply #6709's rename `create_rejected_review_cycle` → `create_review_cycle`, keeping the old name as an alias, with callers kept on the alias the existing patches intercept.
- **Relevant requirements**: FR-001 (structure), FR-013
- **Affected surfaces**: `status/review_roles.py`, `tasks_move_task.py`, `tasks_move_task_hops.py`, `tasks_move_task_executor.py`, `tasks_verdict_persistence.py`, `review/cycle.py`
- **Sequencing/depends-on**: none
- **Risks**: `test_verdict_attribution_4670.py:434-462` counts call sites in source text. The patches on `create_rejected_review_cycle` (seam, durability and materialization tests) must keep intercepting. Run the arch gates listed in research §6.

### IC-02 — Honest identity and reference

- **Purpose**: Remove the git-user and synthetic-token fallbacks, so the combiner's resolution order becomes real. Add the forced, carried and arbiter paths, and update the guidance (skill, hint, `--reviewer` help).
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, FR-011
- **Affected surfaces**: `tasks_move_task.py`, `tasks.py`, `tasks_transition_core.py` (`_approval_evidence`), `tasks_move_task_hops.py`, `tasks_move_task_executor.py`, `tasks_verdict_persistence.py`, `runtime/next/runtime_bridge_decision_mapping.py`, `src/charter/offering/skills/spk-run-verdict-capture/SKILL.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: Re-pin these stale tests (research table): `test_tasks_helpers.py` and `test_review_feedback_pointer_2x_unit.py` (import), `test_tasks_move_task_seam.py:302`, `test_review_durability_matrix.py:526`, plus the fixtures whose claimant identity differs from the approver.

### IC-03 — Approver must be the claimant

- **Purpose**: Add the pure `_guard_review_claimant` with the identity-equality rule and the `APPROVER_NOT_CLAIMANT` code, and the `--agent`/`--reviewer` conflict check.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `tasks_transition_core.py`, `MoveTaskRequest` (claimant fact)
- **Sequencing/depends-on**: IC-01
- **Risks**: `test_move_task_structured_actor_6400` (bare `codex` against `codex::reviewer-renata`), `test_ac5_hash_guard.py:229`, `test_verdict_save_performance.py`, `test_move_task_approval_evidence.py`, `test_move_task_approval_body_collision.py` and `test_move_task_done_issue_matrix_orchestrator.py` all seed a claimant that differs from the approver. Re-pin each one's fixture identity after checking its intent. The 4670 fixture seeds a forced claim, so it gets an unforced one.

### IC-04 — One review, one cycle; cited cycles exist

- **Purpose**: Add the adoption probe, the citation parser and verification, the `REVIEW_CYCLE_CITATION_MISSING` and `REVIEW_CYCLE_NOT_ADOPTABLE` refusals, and pin #6709's edge semantics.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-012, FR-014
- **Affected surfaces**: `review/cycle.py`, `tasks_verdict_persistence.py`, `tasks_move_task.py` (helper inside `_mt_require_independent_approval`)
- **Sequencing/depends-on**: IC-02
- **Risks**: `tests/architectural/test_untrusted_path_containment.py` needs a sink row if N from user text builds a path. Resolve through `build_review_cycle_pointer` and `resolve_review_cycle_pointer` instead of a new join. `_do_move_task` must stay at complexity 15.

### IC-05 — ADR amendment, changelog, follow-ups

- **Purpose**: Amend ADR `2026-10-04-5` with the reviewer-of-record rule, the three codes and the residuals. Add the changelog fragment, including the `--reviewer` behaviour change. File the follow-ups: done bookkeeping; the status emit and orchestrator-api doors; the open-packs prompt; the override-persist ordering; a doctor report for historical fabricated approvals; lane-tip citations. Record #3451 as reproduced with the same cause (+2 per review when the reviewer wrote the cycle).
- **Relevant requirements**: C-008, SC-005
- **Affected surfaces**: `docs/adr/4.x/2026-10-04-5-…md`, `docs/changelog/unreleased/`
- **Sequencing/depends-on**: IC-02, IC-03, IC-04
- **Risks**: CLAUDE.md quotes the ADR. Add one sentence to its approval-stamp paragraph, or flag the drift instead.
