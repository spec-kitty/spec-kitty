# Contract: collection store and reuse evidence

## `collect_universe(repo_root: Path | None = None) -> list[TestRecord]`

The signature and return value are unchanged. For identical inputs the returned list is equal, element for element, to what a fresh collection returns.

| Situation | Store read | Store written | Report `outcome` / `reason` |
|---|---|---|---|
| `repo_root` passed | no | no | `bypassed` / `root-override` |
| checkout has uncommitted changes | no | no | `bypassed` / `dirty-checkout` |
| platform or store unusable | no | no | `bypassed` / `unsupported-platform` |
| git cannot describe the checkout | no | no | `bypassed` / `git-unavailable` |
| lock or store error | no | no | `bypassed` / `unsupported-platform`, with `detail` |
| operator env file exists but cannot be read | no | no | `bypassed` / `env-file-unreadable`, with `detail` |
| valid record, matching key and origin | yes | no | `reused` |
| no record for key | yes | yes, after a successful collection | `collected` / `no-record` |
| record unreadable, wrong schema, empty, below the 1,000-record sanity floor, count mismatch | yes | yes, replaced after a successful collection | `collected` / `invalid-record` |
| record key matches, commit or tree differs | yes | yes, replaced | `collected` / `origin-mismatch` |
| collection fails | — | no | none; the existing `RuntimeError` is raised unchanged |

Concurrency: for one key, at most one collection runs at a time on a machine; other callers block on the lock and then reuse.

## `python -m scripts.ci.collect_universe_prestep <command>`

| Command | Behaviour | Exit |
|---|---|---|
| `key` | prints the collection key for the current checkout and environment (used as the CI cache key) | 0; 2 when the checkout is dirty |
| `collect` | calls `collect_universe()` once; prints the report line | 0 only when its line is `reused`, or `collected` with the record stored, or `bypassed` / `unsupported-platform` with no `detail`; non-zero otherwise (dirty checkout, git unavailable, lock or store failure, record not stored, collection failure, no report line) |
| `check` | reads the report file, writes a table to the job summary, and compares with the pre-test step's outcome | 1 when the pre-test step's own line is anything other than `reused`, a stored `collected`, or `bypassed` / `unsupported-platform` with no `detail`; 1 when the pre-test step stored or reused a record and any later line is `collected`, or `bypassed` for a reason other than `root-override`; 1 on a malformed line; 0 otherwise. Fallback mode (exit 0 with a note) applies only when there is no report file, an empty report, or no `prestep` line |
| `compare` | performs one fresh collection with the store bypassed and diffs it against the stored record | 1 on any difference or when no stored record exists; 0 when equal |

## Workflow shape (pinned by test)

In each consuming job, in this order: compute key → restore store (guarded on a non-empty key) → `collect` → save store → pytest (unchanged command) → `check` with `if: always()`. The save does not depend on pytest's outcome. The pytest command line of each job is byte-identical to today's.
