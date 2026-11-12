# Contract: pre-review gate evidence tree and refusal

## Recorded evidence
`status.events.jsonl` → transition `policy_metadata.pre_review_gate.evidence_tree`, present
whenever the gate reached a test-running tier (a declared test command or an override
scope) and built and probed an invocation; absent on the skip path, on an undeclared gate,
an empty diff, planning lanes and verdicts synthesized before inputs resolved. Paths under
the repository root (`path`, probe `origins`, `interpreter`, `reason`) are recorded
repository-relative in posix form:

```json
{"path": ".worktrees/<slug>-lane-a", "head": "<40-hex>", "dirty": false,
 "probe": {"status": "verified", "origins": {...}, "foreign": [], "reason": null, "interpreter": "..."}}
```

`outcome` may now be `foreign_tree`. Every other key and outcome is unchanged.

## Refusal
`move-task <WP> --to for_review` without `--force`, when the probe is `foreign`:
- exit code 1, transition not applied;
- human: `Pre-review gate refused (EVIDENCE_TREE_MISMATCH): …` naming package, origin, lane
  and the remedy;
- JSON diagnostic: `{"result": "error", "error_code": "EVIDENCE_TREE_MISMATCH", "error": …,
  "transition_applied": false, "pre_review_gate": {…, "outcome": "foreign_tree", "evidence_tree": {…}}}`.

With `--force` (whether or not `review.fail_on_pre_review_regression` is on): the
transition proceeds; `pre_review_gate.force_bypassed` is `true`,
`bypassed_refusal` is `"EVIDENCE_TREE_MISMATCH"`, and no test run happened (outcome stays
`foreign_tree`).
`unverified` never refuses.
