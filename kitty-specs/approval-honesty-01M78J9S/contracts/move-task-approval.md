---
type: reference
updated: 2026-11-12
audience: agents and orchestrators calling move-task
---

# Contract: `spec-kitty agent tasks move-task <WP> --to approved|done`

## Inputs that name the reviewer

| Flag | Meaning after this mission |
|---|---|
| `--agent <id>` | The approver's identity. On an unforced exit from `in_review` it must equal the review claimant. |
| `--reviewer <id>` | An identity assertion. It sets the approver when `--agent` is absent, and it must equal `--agent` and the claimant. It is **no longer free text**. |
| neither | The review claimant is used. With no claimant, the approval refuses with `REVIEW_NOT_INDEPENDENT` (existing). |
| `--approval-ref <ref>` | If it is a `review-cycle://` pointer, or its text cites `cycle N`, that cycle must exist, be valid, not be a rejection's cycle, and post-date the latest claim. |
| `--note <text>` | Prose, kept in `reason`. A `cycle N` citation in it is verified as above. |

## Recorded output (success)

Every identity field equals the reviewer of record (see `data-model.md`). The reference is:
- a `review-cycle://` pointer to the adopted or written cycle (unforced review);
- `force-override`, or the arbiter decision's reference (forced);
- the recorded approval's reference (`approved -> done`).

No `auto-approval:`, `approval:` or `auto-forward:` token is minted. One review produces exactly
one review cycle.

## Refusals (exit 1, nothing written by this mission's paths)

| Code | When | Remedy printed |
|---|---|---|
| `APPROVER_NOT_CLAIMANT` | unforced `in_review -> approved/done` by an identity that is not the claimant (tool, model and profile compared); `--agent` and `--reviewer` disagree; or the dispatch binding (`--profile` / `--invocation-id`) would override a model or profile that `--agent`/`--reviewer` itself names (any approval lane, including a direct approval from `for_review`; a binding that only fills an empty segment passes) | have the claimant record the verdict (`--agent <claimant>`), or, as an operator override, `--force` (recorded as a forced move) |
| `REVIEW_SLOT_DAMAGED` | unforced review approval when the event log's review verdict cannot be read, so no cycle can be written | repair the event log, or pass `--approval-ref <ref>`, or `--force` |
| `REVIEW_CYCLE_CITATION_MISSING` | a cited cycle that is missing, invalid, a rejection's cycle, or from before the latest claim | names the expected path; cite an existing current cycle or write the review via `--review-feedback-file` |
| `REVIEW_CYCLE_NOT_ADOPTABLE` | a `review-cycle-N.md` written after the claim that is invalid or attributed to another identity | rename it to `review-feedback-N.md` and pass `--review-feedback-file`, or remove it |
| `REVIEW_NOT_INDEPENDENT` (existing) | no identity and no claim, or the approver is the implementer | `--agent <identity>` |

Under `--json`, `APPROVER_NOT_CLAIMANT` is a move-task diagnostic with a `code` field (plus `review_claimant` and `requesting_agent`). `REVIEW_CYCLE_CITATION_MISSING`, `REVIEW_CYCLE_NOT_ADOPTABLE`, `REVIEW_SLOT_DAMAGED` and `REVIEW_NOT_INDEPENDENT` print `{"error": "<CODE>: ..."}`: the code is the prefix of the `error` text, with no separate `code` field. With `--owned-checkout`, the owned refusal envelope carries `error.code`.
