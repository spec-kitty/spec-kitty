# Contract: what a completed `spec-kitty upgrade` reports

Applies to every run that reaches the finalizer. Planner and compatibility paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, agent-check flags) are outside this contract.

| Kind | Exit | JSON `status` | JSON `success` | JSON `outcome` | Text closing line |
|------|------|---------------|----------------|----------------|-------------------|
| applied | 0 | `success` | true | `applied` | `Upgrade complete! <from> -> <to>` |
| no-op | 0 | `up_to_date` | true | `no_op` | `Project is already up to date!` |
| drift-unresolved | 1 | `failed` | false | `drift_unresolved` | `Upgrade finished with unresolved tool-surface drift.` |
| failed | 1 | `failed` | false | `failed` | `Upgrade failed.` |
| applied or no-op, completed dry run | 0 | unchanged | true | `applied` / `no_op` | migrations path: `Dry run complete — no changes applied. (<from> -> <to> previewed)`; no-migrations path: `Project is already up to date!` |
| failed, incomplete dry-run preview | 1 | `failed` | false | `failed` | `Upgrade failed.` |

Precedence: any reason other than drift makes the kind `failed`; drift alone makes it `drift_unresolved`. All reasons are listed in `failure_reasons` and all messages in `errors`.

Rules:

1. Text and JSON exit codes are equal for the same project state.
2. On a non-zero exit, text mode prints every string in JSON `errors` and prints no success closing line.
3. JSON gains `outcome` and `failure_reasons`; no existing key is removed or renamed.
4. The drift error reads `Unresolved tool-surface drift in N file(s); run 'spec-kitty doctor tool-surfaces' to review.` with N ≥ 1. It never names an overwriting option.
5. A dry run that completes prints its dry-run closing line and exits 0; an incomplete preview is `failed` and its notice is printed once.
6. A non-zero exit always has at least one entry in `errors`.

7. A declined or failed mission-state repair never changes any column of the table; a failed one is listed in `warnings`.
