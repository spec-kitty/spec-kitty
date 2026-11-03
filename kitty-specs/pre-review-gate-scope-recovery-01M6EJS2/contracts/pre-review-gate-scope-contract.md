# Contract — pre-review gate scope and budget

Scope: the `in_progress → for_review` pre-review regression gate. This contract
covers only what this mission changes; outcome vocabulary, block policy and the
aggregation rules are owned elsewhere and are unchanged.

## 1. Work-package frontmatter

```yaml
---
work_package_id: "WP01"
pre_review_test_scope: "tests/review tests/status"   # optional, whitespace-separated pytest targets
# round-trip: skip: an illustrative fragment of the strict WPMetadata surface, not a complete document
---
```

- The key is part of the strict `WPMetadata` surface. It parses as
  `str | None`; `null`/absent means "no pinned scope".
- A WP carrying the key must resolve `authored_subtask_roster` (the roster guard
  validates the same file) and must remain readable by every other strict
  consumer.
- Unknown keys are still refused (`extra="forbid"`). This contract adds exactly
  one key.

## 2. Review budget resolution

`specify_cli.review.test_timeout.resolve_review_test_timeout(repo_root, override=None, *, whole_command=False)`

| Input | Output |
|---|---|
| `override` given | `validate_review_test_timeout(override)` |
| `review.test_timeout_seconds` declared | that value (validated) |
| not declared, `whole_command=True` | `WHOLE_COMMAND_TEST_TIMEOUT_SECONDS` (1 200) |
| not declared, `whole_command=False` | `DEFAULT_TEST_TIMEOUT_SECONDS` (300) |
| declared value invalid | `InvalidReviewTestTimeout` (refuses the transition) |

Callers **must** resolve once per transition and reuse the value for the
baseline capture, the baseline-receipt match and the head run
(`tasks_move_task_gates._mt_review_test_timeout`). `whole_command` is `True`
exactly when the resolved scope source contributes no per-file narrowing
(`not exposes_scope_breakdown(source)`).

## 3. Refusal reason text

`GateVerdict.reason` for `TIMED_OUT` (whole-command shape) contains:

1. the words `whole declared command`;
2. the declared command that ran, single-line and truncated (≤ 160 characters);
3. `review.test_timeout_seconds` and the resolved budget;
4. the policy-metadata location `review/gate_budget.py` and `_RULES`;
5. both recoveries: declare `review.test_timeout_seconds`, or pin a bounded
   `pre_review_test_scope`.

`GateVerdict.reason` for `TIMED_OUT` (bounded shape) contains the bounded shape
and its targets, and **never** the string `whole declared command`.

`GateVerdict.reason` for `SCOPE_OVERSIZED` names the bounded shape alongside the
targets it already lists.

All generated reasons are single-line, ≤ 800 characters, and JSON-safe.

## 4. Compatibility

| Surface | Guarantee |
|---|---|
| `review.test_command` | still the single test-command authority (unchanged) |
| `review.pre_review_test_command` | still a deprecated alias with its one-time warning (unchanged) |
| `review.test_timeout_seconds` | a declared value resolves to itself, before and after this change (C-003) |
| Baseline receipts | `test_timeout_seconds` stays the receipt identity; a receipt captured under a different budget is recaptured, not trusted |
| Gate outcomes | `TIMED_OUT`/`CANCELLED` stay terminal; the opt-in `NEW_FAILURES` block, the `--force` override and both skip paths are unchanged |
