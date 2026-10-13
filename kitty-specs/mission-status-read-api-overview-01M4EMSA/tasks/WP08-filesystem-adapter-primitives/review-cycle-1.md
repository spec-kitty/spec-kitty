---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T06:56:50Z'
reviewer_agent: reviewer-renata
wp_id: WP08
---

# WP08 review cycle 1: returned for fixes (reviewer-renata + operator ruling)

The full evidence is in wp08-review-verdict.md (orchestrator scratchpad). The build, scope, security plants (L2, L6, L7, L9, L11, no path in any message), allowlist coverage and listing all pass. The reviewer ran 56 layouts × 2 trees against the oracle, and only the items below differ. The ruling is at the end of reviews/analyze.ruling.md (2026-10-12), and DD-100 records these decisions.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | medium | ReadDirResolver.java:75-77, :133 | Stored `coord` or `lanes_with_coord`, with `coordination_branch` absent or empty and a coordination Mission dir present: the oracle (`resolve_read_dir`) reads OWN, Java reads COORD. The operator ruled to match the oracle. | Route to COORD only when `coordination_branch` is a non-blank string. Add the reviewer's layouts L33, L34 and L36 to your inline resolver table, with oracle results from running `resolve_read_dir` (registered and husk). Add a revert row. Do not edit `resolver-cases.json`: it is WP07's, and WP09 adds the row. |
| F3 | low | ReadDirResolver.java:104, :124-137 | A non-string truthy `mid8` or `coordination_branch` makes Java read COORD, where the oracle reads OWN. | Treat a non-string `mid8` as absent and a non-string truthy `coordination_branch` as read-OWN. Add oracle-backed cases. |
| F4 | low | ReadDirResolver.java:69, Listing.java:62 | `resolve("..")` reads `<root>/meta.json`, and `a/../b` is accepted. | Reuse `safeSegment` and refuse a bad Mission name with `PATH_REFUSED` (L9) in both places. Add tests and a revert row. |
| F5 | low | Allowlist.java, classifier `\.git/.+/HEAD` | It allows READ of in-root `.git/refs/remotes/origin/HEAD` and `.git/worktrees/*/HEAD`, which FR-010 forbids, so AC-10a would not flag them. | Drop the in-root pattern; the `<gitdir>/HEAD` pattern for pointer files covers linked checkouts. Add tests that both paths are violations, and update `Allowlist.PATTERNS` / `ENTRIES` if the text changes. |

Not in this round: F2 (DD wording, corrected by the orchestrator), F6 (accepted, recorded), F7 (WP19's README threat note) and F8. On F8: do every mutation in a scratch worktree (`git worktree add --detach <scratchpad>/...`), never in the shared lane worktree.
