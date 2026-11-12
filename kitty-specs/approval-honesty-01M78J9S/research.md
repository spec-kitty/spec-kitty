---
type: explanation
updated: 2026-11-12
audience: mission implementers and reviewers
---

# Research: approval honesty

Pre-spec grounding is in `research/code-grounding.md` and `research/foldable-issues.md`. This file
records the planning decisions and how each finding of the plan point-cut squad was handled.

## Decisions

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| R1 | Reviewer identity is asserted (`--agent`/`--reviewer`) or the claimant. Otherwise refuse. Never the git user, never a token. | Operator ruling `reviewer_identity`. A null reviewer needs a `spec-kitty-events` release. | Explicit "unreviewed" marker; null reviewer with a schema change |
| R2 | Claimant = newest unforced, non-migration, non-placeholder `-> in_review`, in `status/review_roles.py` | One authority shared with consolidation (`approved_bound._entered_review_by_claim`) | Keep `_mt_resolve_active_reviewer_identity`, which also counts forced entries (second definition) |
| R3 | `APPROVER_NOT_CLAIMANT` as a pure guard beside `_guard_agent_ownership` | That guard already compares `--agent` with the claim slot, but only on the bare tool. A sibling with full identity closes the same-tool supervisor case without a second authority. | A separate check in `tasks_move_task_gates.py`, which is the pre-review test-gate module, the wrong home |
| R4 | Remedy is "claimant records the verdict, or `--force`" | Operator ruling `claimant_remedy`. Re-claiming is refused as a collision, and `in_review -> for_review` does not exist. | New review handoff path (scope growth; overlaps #7596) |
| R5 | Adoption is keyed on event references and cycle numbers, not `reviewed_at` | `reviewed_at` is reviewer-written and can be backdated. The frontmatter has no verdict field (`artifacts.py:218`). A rejection's cycle is always referenced by its event. | Timestamp comparison; frontmatter verdict, which does not exist |
| R6 | Non-adoptable post-claim cycle refuses (`REVIEW_CYCLE_NOT_ADOPTABLE`) | Operator ruling `non_adoptable_cycle` | Write N+1 and warn (leaves #7571 open) |
| R7 | Citations must also be post-claim | Squad: citing an old approved cycle after a later rejection would otherwise pass | Existence check only |
| R8 | `approved -> done` carries the recorded approval verbatim | Append-only history (C-002). A fabrication in an old record is not re-made here. | Refuse done on old records (blocks every legacy Mission) |
| R9 | Codes live in `tasks_transition_core.py`, with no `SINGLE_BRANCH_*` alias | Move-task only; `wp_evidence` codes are shared with accept and consolidate (C-004) | Put them in `wp_evidence` |

## Plan squad findings and dispositions

| Finding (lens) | Disposition |
|---|---|
| Second "who may approve" authority (architect, BLOCKER) | **Fixed in plan:** R3 |
| NFR-003 does not follow from placement; override and arbiter persists precede guards (architect + tester, BLOCKER) | **Fixed:** refusals placed in pass 1 and in the pre-write helper. The pre-existing override persist is scoped out of NFR-003 as a residual with a follow-up issue. |
| Six identity sources, not three; event `actor` missing from FR-001 (architect, tester) | **Fixed:** all six routed; FR-001 widened (actor, body, reproduction command) |
| Arbiter reference not yet available when facts are gathered (architect) | **Fixed:** late input after `_mt_fire_arbiter_persist` |
| FR-006 over-promises given consolidation (architect) | **Fixed:** FR-006 scoped to recorded fields; residual documented (#5721) |
| Done carry-forward fallback undefined (architect) | **Fixed:** R8 order |
| Adoption clock, rejection test, #6652 interaction, revert hazard, auto-walk (architect) | **Fixed:** R5; the frontmatter-verdict suggestion was **rejected** because the field does not exist |
| Re-claim remedy does not work (tester, BLOCKER) | **Escalated:** ruling R4 |
| Claimant definition drift, forced claims (tester) | **Fixed:** R2. The 4670 fixture is re-pinned to an unforced claim. |
| Equality via `not actor_identities_independent` is too loose (tester) | **Fixed:** strict equality on the recorded tool, model and profile; bare tool is not equal to a profiled claimant |
| Other synthetic tokens (`approval:`, `auto-forward:`) (tester) | **Fixed:** FR-003 and SC-002 widened |
| Stale-cycle citation bypass (tester) | **Fixed:** R7 |
| Reviewer-written frontmatter trust (tester) | **Partly:** R5 removes the reliance on timestamps. Identity impersonation stays a documented residual. |
| `--reviewer` alone gives actor `user` and is refused (tester) | **Fixed:** `--reviewer` sets the actor (ruling `codes_and_reviewer`) |
| #3451 reproduction (tester) | **Reproduced:** +1 cycle with no reviewer cycle; +2 when the reviewer wrote `review-cycle-1.md`. Same cause as #7571, so it folds (closed by this PR). |
| Red-test inventory (tester) | Carried into the IC-02 and IC-03 risks. Fixture identities are re-pinned only after checking each test's intent. |

## Supply chain

No dependency is added, upgraded or removed.
