# Contract: finalize-tasks pin decisions (single_branch)

| Run | Recorded pin state | Result | Code / reason |
|-----|--------------------|--------|---------------|
| explicit `--refresh-planning-commit --allow-orphaned` | orphaned, one patch-id match, window keeps owned work | re-pin to the match, exit 0 | `action=repinned`, `matched_by=patch_id` |
| same | orphaned, no match | refuse before write, exit 1 | `PLANNING_PIN_NO_PATCH_ID_MATCH` |
| same | orphaned, several matches | refuse before write, exit 1 | `PLANNING_PIN_PATCH_ID_AMBIGUOUS` |
| same | orphaned, empty-diff pin | refuse before write, exit 1 | `PLANNING_PIN_NO_PATCH_ID_MATCH` (message says empty diff) |
| explicit refresh or re-pin | candidate drops committed owned work | refuse before write, exit 1 | `PLANNING_PIN_WOULD_EMPTY_WINDOW` |
| plain finalize | derived pin | preserved, exit 0 | `action=preserved` |
| plain finalize | advanced, planning changed, candidate drops owned work | kept, warning, exit 0 | `kept_with_warning`, `reason=window_would_empty` |
| plain finalize | no pin, tip resolved, nothing derivable | kept (None), warning, exit 0 | `kept_with_warning`, `reason=no_pin_underivable` |

Lane topologies: the rows above marked "orphaned" keep the #4827 behaviour (re-pin to the tip).
The error envelope is `{"error": <message>, "error_code": <code>}` in `--json`; the message leads with the code in human mode.
