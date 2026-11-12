# Contract: pre-review gate evidence tree and refusal

## Recorded evidence
`status.events.jsonl` → transition `policy_metadata.pre_review_gate.evidence_tree`, present
whenever the gate built an invocation (absent on the skip path and on planning lanes):

```json
{"path": "/abs/lane", "head": "<40-hex>", "dirty": false,
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

With `--force`: the transition proceeds; `pre_review_gate.force_bypassed` is `true`.
`unverified` never refuses.
