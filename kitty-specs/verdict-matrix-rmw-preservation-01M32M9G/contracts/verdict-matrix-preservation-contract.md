# Contract — Verdict-matrix write preservation

Behavioural + internal-function contracts the implementation must satisfy. No external CLI/API
surface changes; these are internal seam contracts.

## Behavioural contract (both matrices)

- **C-PRES-1**: A verdict-recording command commits a matrix that contains every row present on
  the authoritative read surface at write time, plus/updating only the row the invocation owns.
- **C-PRES-2**: The command never lowers the honesty of the overall outcome — a committed failing
  row is never dropped, and an overall verdict never flips fail→pass as a side effect of an
  unrelated write.

## #4858 — acceptance concurrency

- **C-4858-lock**: The re-read → single-row merge → write+commit critical section is held under
  `feature_status_lock(repo_root, matrix_dir.name)`. `matrix_dir` is resolved once and reused for
  both the re-read and the write. (Asserted by a spy: acquired with `lock_key == matrix_dir.name`,
  lock path under the git common dir.)
- **C-4858-order**: The slow custom check (`enforce_negative_invariants`) is invoked BEFORE the
  lock is acquired. (Asserted by call-order.)
- **C-4858-atomic**: `write_acceptance_matrix` writes via `kernel.atomic.atomic_write`. (Asserted
  by a spy on the atomic-write door.)
- **C-4858-modes**: Both `_run_negative_invariant_mode` and `_run_criterion_mode` splice a single
  owned row into the freshly re-read matrix (insert-if-absent). Criterion mode recomputes
  `index_by_id`/unknown-criterion from the re-read; NI mode uses a *replace-or-append the
  already-judged row* helper (NOT `_register_negative_invariant`, which resets to `pending`).
- **C-4858-reread-in-lock**: The re-read (`read_acceptance_matrix`) AND the write both happen
  while `feature_status_lock` is held. Asserted by strict call-order
  `lock.__enter__ → read → write → lock.__exit__`. (Kills the "re-read outside the lock" mutant
  the serial harness cannot catch.)
- **C-4858-fail-closed**: The lock uses a bounded timeout; on `FeatureStatusLockTimeoutError` the
  command performs NO write and exits non-zero with a structured error — never an unlocked
  fallback write. Asserted by patching the lock to raise and spying that
  `write_acceptance_matrix`/`atomic_write` is not called.
- **C-4858-honest-report**: The command emits `overall_verdict` computed from the re-read+spliced
  matrix (the committed content), not the pre-lock in-memory snapshot. Asserted emitted == disk.
- **C-4858-surface**: `matrix_dir` (re-read surface) equals `commit_for_mission`'s resolved
  placement surface; the coord worktree is materialized BEFORE the lock is acquired so racers +
  commit agree on the coord surface. Precondition: worktree materialized (normal post-finalize).

## #4868 — issue migration

- **C-4868-source**: `migrate_issue_matrix_to_json(feature_dir, *, read_dir=None, ...)` reads the
  legacy matrix from `source_dir = read_dir or feature_dir` for the existence check and the
  Markdown parse. `_migrate_if_needed` passes `read_dir=read_dir`.
- **C-4868-write-staging (C-011)**: The write remains `write_issue_matrix(feature_dir=feature_dir)`
  (primary staging → write-seam materializes coord + cleans residue). The fix MUST NOT pass
  `read_dir` as the write `feature_dir`. **Asserted by a spy that the migration's
  `write_issue_matrix` received `feature_dir == primary`** (a "no primary residue" check is
  INSUFFICIENT — the untouched main write cleans residue for the wrong fix too). Mutation-tested:
  RED against both base and the `read_dir`-as-write-`feature_dir` variant.
- **C-4868-malformed**: A malformed authoritative `.md` is translated into a structured
  `IssueVerdictError`/result (caught by the command), not a raw traceback.
- **C-4868-idempotent**: A subsequent verdict once the coord JSON exists reports `migrated=False`,
  preserves all prior rows, and leaves no primary residue.
- **C-4868-compat**: Adding `read_dir` is keyword-only and defaulted; existing callers
  (`_migrate_one_mission`, unit callers) are unaffected.
- **C-4868-precondition**: The coord-aware read only helps once the coord worktree is
  materialized (normal post-`finalize-tasks` state); the degradation-to-primary path when the
  worktree is unmaterialized is documented, not silently assumed away.

## Non-goals (contract exclusions)

- No serialization of non-verdict acceptance-matrix writers (finalize/accept/gate/post-consol) —
  C-010.
- No atomic-write door on the issue-matrix writer (deferred, separate hardening).
- No issue-matrix concurrency work. No #2482 restage-clobber fix.
