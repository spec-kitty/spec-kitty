# Contracts: lane auto-commit exact-path seam (#6750)

This mission adds no new external contract. It changes two existing seams:

1. **`specify_cli.git.commit_helpers.safe_commit` / `preflight_commit`** — a new
   typed pre-mutation refusal, `SafeCommitDirectoryArgument`
   (`error_code = "SAFE_COMMIT_DIRECTORY_ARGUMENT"`), raised when a requested path
   is a directory that is not a submodule gitlink. `SafeCommitError` subclass, so
   it is still a `RuntimeError` for callers that flatten the error type. Every
   pre-existing error class, code and message contract is unchanged (spec C-002).
2. **`move-task --to for_review` auto-commit output** — the collector now reads
   untracked entries expanded, and renders a `SafeCommitRecoveryFailed` carrying a
   `commit_sha` as "landed ... as <sha>", keeping "could not auto-commit" for
   failures before the commit. Console wording only; `--json` output is unchanged.

No `contracts/` schema is owed: no API schema, no wire format and no persisted
artifact shape changes. See `../spec.md` (FR-001..FR-004, C-002) and
`../plan.md` for the requirement-level detail.
