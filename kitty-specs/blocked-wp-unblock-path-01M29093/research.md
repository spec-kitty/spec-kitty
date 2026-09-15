# Research: Blocked-WP unblock path (#3937)

Consolidated from the pre-spec research squad (debugger-debbie root-cause, researcher-robbie cluster, Explore code-seams) and the pre-spec review squad (paula-patterns cleanup-safety, reviewer-renata adversarial scope/ATDD). Raw lens outputs archived under the session scratchpad `research-3937/`.

## Decision 1 — F-50: leave the WP `planned` on allocation failure (do not manufacture `blocked`)
- **Decision**: On a workspace-allocation failure in `implement`, cease emitting `planned → blocked`; leave the WP `planned` and print the exception's actionable `next_step`.
- **Rationale**: `create_lane_workspace` runs before the claim transition, so the WP is still `planned` when allocation raises; the error handler `_emit_blocked_on_alloc_failure` *creates* an unrecoverable state (`blocked → planned` is illegal; `start_implementation_status` has no `BLOCKED` branch). The allocator self-cleans (abort + `reset --hard`, no `lanes.json` write), so the persisted worktree is the allocator's reentrancy vehicle — leaving `planned` strands nothing. Confirms parity with the orchestrator-api path, which never emits `blocked`.
- **Alternatives considered**: (a) add a `blocked → planned` recovery edge — rejected: adds a new semantic and the fake-review "Fix mode" trap (`workflow_executor.py`) still looms; (b) add a `blocked → in_progress` recovery driver — rejected: that is the #1711 class, skips the CLAIMED slot (`lifecycle.py:158-193`), larger blast radius (C-001).
- **Sourced**: debbie root-cause §1; paula F1/F2/F6; explore §3.

## Decision 2 — F-51: single-stage, honest transition refusal
- **Decision**: `_guard_planned_rollback` early-returns when the source lane is not a review-family lane, so `blocked → planned` falls through to FSM legality; enumerate `allowed_targets()` on the CLI/emit refusal path only.
- **Rationale**: The guard is source-blind (keys only on `target == PLANNED`) and runs before legality, producing a two-stage refusal that coerces a fabricated review artifact. A source-scoped early-return fixes it without reordering `_GUARDS` (which would shift persist-signal prefixes) — C-002.
- **Alternatives considered**: head-insert a legality guard — rejected (widens persist-signal prefixes at ~:716/:733); enrich the FSM-core illegal string — rejected (detonates ~1500 `fsm_parity_baseline.jsonl` rows, NFR-002).
- **Sourced**: debbie §3; explore §2; renata finding [HIGH] golden-fixture + guard-reorder hazard.

## Decision 3 — Non-fakeable ATDD (NFR-001)
- **Decision**: Acceptance tests pin observable STATE, not message substrings. F-50: assert NO `planned→blocked` event emitted + a clean re-run leaves no `review-cycle://` pointer (Fix mode off). F-51: assert refusal IDENTITY is illegal-transition (not feedback-demand) AND a fake `--review-feedback-file` cannot flip the verdict.
- **Rationale**: renata showed both findings are fakeable by cosmetic message edits if tests assert substrings only.

## Adversarial Evidence (plan point-cut) — dispositions
Per `contracts/adversarial-evidence-contract.md`. The pre-spec review squad's contested findings and their dispositions:
| Finding (lens) | Disposition | Note |
|---|---|---|
| Golden-fixture detonation if enrichment touches FSM-core string (renata, HIGH) | **accepted** | NFR-002 + Decision 2: enumerate on CLI/emit path only. |
| Remediation must surface `exc.next_step`, not generic "re-run" (paula, HIGH) | **accepted** | FR-002. |
| Both conflict codepaths must be covered (paula, MED) | **accepted** | FR-003. |
| Partial-workspace strand risk (paula open risk) | **accepted (discharged)** | Allocator self-cleans; no disk cleanup added (recorded assumption). |
| Guard-reorder shifts persist-signal prefixes (renata, MED) | **accepted** | C-002: source-scoped early-return, no tuple reorder. |
| `blocked→in_progress` recovery driver would skip CLAIMED slot (paula/renata, MED) | **accepted (defer)** | C-001: out of scope → #1711 class. |
| One bug-encoding test asserts `[("planned","blocked")]` (renata, LOW) | **accepted** | Rewrite `tests/integration/test_status_emit_on_alloc_failure.py:189/192` as the F-50 AC test. |

No contested finding was silently dropped. No dependency change → supply-chain N/A.

## Cluster boundary (robbie)
- Same-root closed sibling **#2512** (fix `749768c0a9` released the claim slot but left the blocked-exit gap = this residual) — precedent mined, not reopened.
- Co-sequence **#3938** (F-52 resume-claim / prompt regen) — deferred-with-followup (C-003).
- Leave separate: #2555, #2066, #1711, and other epic #2017 children (#2513, #3941, #3944, #3956, #2742, #3468, #3466, #3477, #3226).
