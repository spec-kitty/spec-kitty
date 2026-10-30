# Research — bound failed-synthesis staging retention (#6723)

Mission: `bound-failed-staging-retention-01M66YJ3`
Issue: [spec-kitty/spec-kitty#6723](https://github.com/spec-kitty/spec-kitty/issues/6723)
Base: `main` @ `512567eee71e31bb39f580c4f7acf8b865e9d1b2` (clean, fast-forwarded, nothing pushed)
Agent: python-pedro (implementer profile), planning profiles loaded (planner-priti)

## Problem statement (from the issue, verbatim scope)

Every refused `charter synthesize` / `charter resynthesize` leaves
`.kittify/charter/.staging/<run_id>.failed/` behind. Nothing prunes them, so a
project that keeps getting refused — exactly what happens while an agent follows
the implement gate's "run `spec-kitty charter synthesize`" remedy — accumulates
one directory per attempt. #4226 counted 15, then 16, on one repository.

**Expected (issue):** keep failed staging directories bounded, for example by
keeping the most recent N, or by replacing an older directory that has the same
cause, while still keeping the latest failure for diagnosis.

Follow-up split out of #4226 by Mission `resynthesis-after-activation` (M9,
#6510). M9 fixed the self-collision that caused the repeated refusals; it did
not change staging retention. So this Mission is *only* the retention bound:
no synthesis, promotion, or collision-remedy behaviour changes.

## Code map (surveyed before specifying)

| Surface | Location | Role |
| --- | --- | --- |
| `StagingDir.create` | `src/charter/activation/synthesizer/staging.py:88` | makes `.kittify/charter/.staging/<run_id>/` |
| `StagingDir.commit_to_failed` | `staging.py:171` | renames the dir to `<run_id>.failed/` and writes `cause.yaml` |
| `StagingDir.__exit__` | `staging.py:240` | routes unhandled exceptions to `commit_to_failed` |
| `write_pipeline.stage_and_validate` / `promote` | `write_pipeline.py:522`, `:722` | call `commit_to_failed` on validation refusal |
| `PathGuard` | `src/charter/activation/synthesizer/path_guard.py` | the only write seam; owns `rmtree` |
| CLI failure hint | `src/specify_cli/cli/commands/charter/synthesize.py:616` | prints "Staging directory preserved at: …" |
| Stale-dir warning | `src/charter/bundle.py:418` (`_check_stale_failed_dirs`) | warns per stale `.failed` dir; no deletion |
| Run directories | `orchestrator.py:324`, `resynthesize_pipeline.py:400`, `_synthesis.py:388`, `:424` | every caller uses the same `StagingDir` context manager |

The `.staging/` tree is inside `.kittify/charter/`, which is gitignored and is in
`PathGuard`'s default allowlist (`path_guard.py:_DEFAULT_ALLOWLIST`). Deletion is
therefore possible through the existing seam (`PathGuard.rmtree`) with no
allowlist change — the ADR (`docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`)
explicitly promises `PathGuard` as the only mutation seam, so a bare
`shutil.rmtree` at the call site would break that invariant and the
`tests/charter/synthesizer/test_path_guard.py` lint-style guard.

## Reproduction on current `main`

Direct exercise of the pre-existing lifecycle seam (`StagingDir.create` +
`commit_to_failed`, six refused runs, in a scratch temp directory):

```text
$ uv run --frozen python - <<'PY'   # create + commit_to_failed six times
...
PY
['01M66YJ3TESTRUN0000000000.failed', ..., '01M66YJ3TESTRUN0000000005.failed']
failed dirs: 6
```

One directory per refusal, no bound — the issue reproduces on `512567ee`.

The refusal path is the same one the CLI uses: `spec-kitty charter synthesize`
wraps the pipeline in `with StagingDir.create(...) as staging_dir:`, so every
`SynthesisError` / `NeutralityGateViolation` / validation refusal reaches
`__exit__` → `commit_to_failed`. Confirmed against the existing CLI refusal
tests in `tests/charter/synthesizer/test_collision_refusal_6510.py` and
`test_staging_atomicity.py`.

Not superseded: `git log -S"commit_to_failed"` shows only the original
Phase-3 synthesizer pipeline commit and a complexity refactor; no retention was
ever added, and no changelog entry mentions staging retention.

## Decisions

1. **Prune on the failure path, right after preserving the current run.**
   `commit_to_failed` renames to `<run_id>.failed/`, writes `cause.yaml`, then
   prunes. Doing it there keeps the bound on the only code path that creates
   failed dirs, so no new command, cron or doctor pass is needed.
2. **Keep the newest `3` failed runs (`DEFAULT_KEEP_FAILED_RUNS = 3`).**
   One directory is enough to read the latest refusal; three lets an operator
   compare the *latest* refusal against the two before it (the repeated-refusal
   case the issue describes, where the cause changes as the operator iterates).
   The issue explicitly allows "the most recent N" as long as N is stated; the
   number will be stated in the module constant, the CLI hint, the changelog and
   the governance-files doc.
3. **Never delete the current run or a live staging directory.**
   The pruner only considers entries whose name ends in `.failed`; an
   in-progress `.staging/<run_id>/` (another process, or this run before its
   rename) is out of scope by construction. The current `<run_id>.failed` is
   passed as `preserve` and is exempt even if ordering would drop it.
4. **Order by directory mtime, newest first, with the name as tiebreak.**
   Run ids are ULIDs so name order is usually time order, but mtime is the
   property that survives a copied/restored tree and mixed-name fixtures; the
   name tiebreak keeps the result deterministic when several dirs share an
   mtime (as they do in tests that write them in one tick).
5. **Delete through `PathGuard.rmtree` only.** No new allowlist entry, no bare
   `shutil.rmtree`, no shell-out.
6. **Pruning never raises.** An `OSError` while listing or removing must not
   mask the original synthesis failure — the whole prune is best-effort and
   suppressed, matching `commit_to_failed`'s existing "must not mask the
   original error" contract.
7. **Rejected alternative — replace an older directory with the same cause.**
   The issue offers it, but it needs the old `cause.yaml` read and compared on
   every failure, and it silently destroys the history an operator uses to see
   whether a remedy changed anything. A count bound is simpler, predictable, and
   testable. Rejected: a config knob (`charter.staging.keep_failed`) — there is
   no second consumer for it, and a config typo would gate a deletion path
   (the `ledger.retention` precedent is heavier than this surface needs).

## Open questions (resolved during specify/plan)

- Should the CLI hint name the retention? → Yes, one short clause: the operator
  who just got the refusal is the person who needs to know older copies are
  pruned, and that the number is three.
- Should `bundle validate`'s stale-dir warning change? → No behaviour change; it
  now warns at most three times, which the existing message already handles.
- Should there be an opt-out/env var? → No (decision 7).

## Evidence and references

- Issue #6723 body and its `#4226` follow-up context (comments of 2026-09-11).
- `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md` (§ staging,
  R-7 retention risk, `cause.yaml` contract).
- `docs/context/governance-files.md:40` — `.kittify/charter/.staging/` row.
- `src/charter/bundle.py:418` — the existing accumulation signal.
- `docs/changelog/CHANGELOG.md` — no prior staging-retention entry.
