---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T09:52:19Z'
reviewer_agent: reviewer-renata
wp_id: WP10
---

# WP10 review cycle 1: REJECT (reviewer-renata), with an operator ruling

The full evidence is in wp10-review-verdict.md (orchestrator scratchpad). Everything else passed:
- `check`, native and nativeSmoke;
- 35 golden route fixtures, byte-equal;
- all 12 ArchUnit rules;
- the three out-of-map changes, judged justified and minimal;
- every reviewer mutation went red.

The operator ruled on F2 (end of reviews/analyze.ruling.md, 2026-10-12): a non-integer `pageSize` is treated as absent.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | medium | ProblemAdvice (TypeMismatch handler); MissionsController.listMissions | An integer `pageSize` beyond 32 bits (`99999999999`, `-99999999999`) answers a codeless 400. The clamp ruling says no 400. | Bind `pageSize` as text, or catch the overflow. Saturate, then clamp: above 200 → 200, below 1 → 1. Add the rows 99999999999 → 200 and -99999999999 → 1, both on the JVM and in the native smoke if cheap. |
| F2 | medium | same handler; test `aPageSizeThatIsNotAnIntegerIsAProblem400` | `pageSize=abc` or `1.5` answers a 400 that is not valid against the contract's `/missions` 400 (`PageCursorRefusal`). | Operator ruling: a non-integer `pageSize` is treated as absent and serves the default 50. Replace the test with rows `abc`, `1.5`, `1e3`, ` 5` and `+5` → served per the rule (decide `+5` and ` 5` by what counts as an integer, and document it). Every response must validate against the contract. Add a revert row. |
| F4 | low | RefusalRowsTest (L11 row) | Only the `kitty-specs/` listing failure is covered over HTTP. A per-Mission directory failure (`mission_dir_unreadable`) has no HTTP row. | Add one HTTP row for a single Mission directory failure, using the recording seam's fault injection. |
| F5 | low | ContractDocumentTest (`assumeTrue` on python3/PyYAML) | The AC-11d fresh-bundle comparison skips silently without python3 or PyYAML. | Fail instead of skipping when the `CI` environment variable is set. |
| F6 | low | BindGuard (`spring.aot.processing` early return) | `-Dspring.aot.processing=true` skips the pre-start guard. | If Spring offers a reliable signal that you are inside its AOT processing (not a user-settable property), use it. Otherwise keep the property but also require that no web server is being started, or record the accepted risk in the BindGuard javadoc. Report which, and test it. |
| F3 | info | WP10 frontmatter | `application-test.properties` was never created. | No action: the orchestrator records it as unneeded. |
| F7 | info | BindGuardProcessTest (AC-9e) | The 10 s bound may be tight on a slow runner. | Raise only the AC-9e port-in-use bound to 30 s, with a comment citing the spec's provisional-bound clause. |

Run all mutations in a scratch worktree.
