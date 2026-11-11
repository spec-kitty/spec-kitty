# Contract: CLI-observable behaviour changed by this Mission

| Command | Before | After |
|---|---|---|
| `agent mission record-analysis` | refuses `DIRTY_WORKTREE` on any non-bookkeeping dirt | refuses `DIRTY_WORKTREE` only on this Mission's own paths and on dirty material inputs (charter, config); JSON success payload gains `foreign_dirty_paths` (list, omitted when empty); human output prints one warning line per path |
| `implement` (single_branch claim) | `WRITE_CHECKOUT_DIRTY` on any non-owned dirt | another Mission's paths no longer refuse; they are logged as a warning (stderr in human mode, silent under `--json`) |
| `next` and `orchestrator-api answer-decision` (coordination Mission) | leaves `kitty-specs/<m>/mission-events.jsonl` untracked in the coordination worktree | commits it there (`chore(next): record next invocation for <m>`); a refused commit is a warning (stderr, or `answer-decision`'s `warnings`), never a failure; the lane `kitty-specs/` guard tolerates the inherited log |
| `agent mission setup-plan` | commits `plan.md` only; lifecycle events stay dirty | commits `plan.md` and this Mission's `status.events.jsonl` in one commit; `commit_hash` names that commit |
| `agent tasks mark-status` | commits only on single_branch | commits on every topology with auto-commit on |
| `init` | commits nothing | at the top of a git repository with at least one commit, one commit `chore: initialize spec-kitty project` with the files it wrote; `--no-commit` opts out; on a repository with no commit yet it prints the first commit to make |

Error codes are unchanged; no code is added or removed.
