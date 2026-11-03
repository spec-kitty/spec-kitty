# Contract: evidence verdict codes (addition)

A backward-compatible addition to the evidence code family that `accept`, `consolidate` and `orchestrator-api` (`PREFLIGHT_FAILED` / `data.preflight_error_codes`) already report.

| Code | Alias of | Meaning | Liftable by `--attest-no-implementation` |
|---|---|---|---|
| `OWNERSHIP_UNRESOLVED` | - | An approved work package's `owned_files` could not be read (the task file is absent or unreadable, or `tasks/` is missing); the line names the directory read | no |
| `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED` | `OWNERSHIP_UNRESOLVED` | Same, on a single_branch Mission | no |

Line shape (one per work package, like the sibling codes): `OWNERSHIP_UNRESOLVED: <WP> <detail naming the tasks/ path>`.
Recovery line (once per refusal when the code is present): restore or commit the work package's task file with its `owned_files`, or run the command from the checkout that owns the Mission (`--owned-checkout <path>`).

No envelope field changes; consumers that branch on `data.preflight_error_codes` see one more possible value.
