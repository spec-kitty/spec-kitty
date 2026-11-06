# Pre-PR adversarial squad: findings and dispositions

The squad ran on 2026-11-06 against
`docs/plans/engineering-notes/2026-11-06-lane-worktree-friction-research.md`. It had two
read-only delegates, each with its profile loaded: `analyst-annie` (evidence-quality lens) and
`architect-alphonso` (architecture lens). Both returned "ship with fixes".

## Evidence lens (analyst-annie)

**Reproduced exactly:** the tracer and issue shares, the cause-code counts, the domain shares,
the monthly trends, the PR figures, the topology table, the 10 `file:line` citations, the 11
quotes and the 7 issue claims.

| Severity | Finding | Disposition |
|---|---|---|
| MAJOR | The "costly cases" claim rests on the weak severity column, and the P0/P1 lane share (22.4%) is below the baseline (24.0%). | Accepted. Section 2.2 now reports the priority result and calls the claim unproven for issues. |
| MAJOR | "Largest single family" depends on grouping nine codes into one family. | Accepted. Section 2.2 states that it depends on the grouping, and that CT alone is smaller than tests/CI. |
| MAJOR | Cause-code agreement in the re-check is about 75%; CT absorbs SD cases. | Accepted. Section 1 reports it, and section 2.3 says SD is undercounted. |
| MAJOR | Validation samples are missing. | Partly fixed. The issue holdout and the agreement script are committed under `validation/`. The tracer hand check and the subject-bias Mission list were not recorded, so they are now reported as unverified ranges. |
| MINOR | "All P0 or P1" is false: #7198 is P2 and #6791 is unlabelled. | Accepted and corrected. |
| MINOR | The #7173 figures were merged, and a counterfactual was stated as fact. | Accepted and corrected (48 worktrees, about 36 GB; "would have committed" across 53 checkouts). |
| MINOR | 27 "lane" PRs carry `NL:*` codes. | Accepted. Section 2.4 gives the count with them excluded (139). |
| MINOR | Tracer false positives push the share up. | Accepted. The 32% figure is now labelled an upper estimate. |
| MINOR | "62 call sites" cannot be reproduced. | Accepted. Both counts are now given with their method. |

## Architecture lens (architect-alphonso)

**Verified against code by the orchestrator:** `lanes/for_review_gate.py:280`,
`cli/commands/agent/mission_create.py:386-449`, `runtime/next/committed_authority.py:8-20` and
`policy/lane_tip_recorder.py:67`.

| Severity | Finding | Disposition |
|---|---|---|
| BLOCKER | The for_review gate reads the lane checkout, which contradicts section 3.8 and option (b). | Accepted. Section 3.8 is re-scoped. Moving the gate onto the ref is now part of phase 1 and a precondition for (b). |
| BLOCKER | "Committed reads via the ref" would drop uncommitted rows from the flat shell. | Accepted. The phase 1 read contract is now defined per topology. |
| MAJOR | Option (c) misdescribed the code: the default is coord on the primary branch whether or not it is protected, and the change reverses the binding decision on #5100. | Accepted. Option (c) is restated, re-ranked to "operator decision only", and listed as decision 1. |
| MAJOR | The `single_branch` approval bound is not small. | Accepted. It is now rated medium (per-WP windows or an ADR amendment). |
| MAJOR | Option (e) conflicts with checked-out branches and the D-6 ADR set, breaks the `events tail` cursor, and does not fit inside step 4. | Accepted. (e) is restricted to coordination branches, re-sequenced as a step after step 4, framed as a git port and write-location change, and lists all four D-6 premises. |
| MAJOR | Option (b) has hidden costs: the lane-tip hook on a detached HEAD, re-entry through crash recovery, harness cwd, review worktrees, and the ADR `2026-04-03-1` amendment. | Accepted. These are added to (b) and to decision 5. |
| MINOR | Section 3.8 was overbroad. | Accepted. |
| MINOR | Option (g) was missing: lane branches stop carrying `status.events.jsonl`. | Accepted. Added as option (g), ranked second. |
| MINOR | Phase 1 exit criteria. | Accepted. They now include "the for_review gate passes with the lane checkout absent". |

## Divergence between lenses

No consequential divergence. Both lenses converge on two points:
- the verdict on the operator's observation is fair, or slightly generous to the lane share;
- the first slice is right in principle.
