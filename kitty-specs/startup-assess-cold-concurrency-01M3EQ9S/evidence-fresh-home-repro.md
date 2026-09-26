---
title: 'Evidence: fresh-home concurrency reproducer (#3998)'
doc_status: active
updated: '2026-09-26'
---

# Evidence: fresh-home concurrency reproducer

Mission `startup-assess-cold-concurrency-01M3EQ9S`, WP02/T011. Covers NFR-001 and SC-001. This is
live reproducer evidence, not a substitute for the deterministic test suite added in WP01 (which
is the actual gate).

## Host

- Linux, x86_64, 32 logical CPUs (`nproc` = 32).
- Kernel `6.8.0-136-generic`.

## Method

- The lane worktree (`<lane>`, tip `6b005a1c71`, WP01 approved) is not resolvable by either the
  global `spec-kitty` or `.venv/bin/spec-kitty` — both resolve `src` via the main checkout's
  editable install regardless of `cwd`. A thin wrapper was built to force the lane's code:

  ```bash
  #!/usr/bin/env bash
  PYTHONPATH=<lane>/src exec <main-checkout>/.venv/bin/python -c \
    'import sys; from specify_cli import main; sys.exit(main())' "$@"
  ```

  Verified before use:

  ```
  $ PYTHONPATH=<lane>/src python -c \
      "import specify_cli.runtime.asset_preparation as m; print(m.__file__, hasattr(m, 'build_serialized'))"
  <lane>/src/specify_cli/runtime/asset_preparation.py True
  ```

  i.e. the module resolved is the lane's, and it carries the WP01 fix symbol.

- The reproducer itself is the script from the #3998 issue comment (copied to `<scratch>/repro.sh`,
  `SK=` repointed at the wrapper above): for each of `N` concurrent processes it launches
  `spec-kitty events --help` against a brand-new `HOME`/`XDG_*` (the "fresh" phase, one process
  actually does the cold install and the rest race it), then repeats once more against the now-warm
  same `HOME` (the "warm" phase, a regression guard on NFR-002). It tallies exit codes and greps for
  `Traceback`/`Error` in each process's output.
- Baseline contrast: a detached scratch worktree (`git worktree add --detach <scratch>/base-worktree
  81b835441b`, the mission's planning base — verified pre-fix: `hasattr(build_serialized)` is
  `False`, `hasattr(retry_torn_read)` is `True`) with a second wrapper pointed at it, run through the
  same reproducer. This shows whether the reproducer still hits the race window on the pre-fix code
  under this host's timing, since the bug is intermittent.

## Results — lane (`6b005a1c71`, WP01 fix applied)

| # | N | Pinned? | Fresh exit tally | Fresh tracebacks | Warm exit tally |
|---|----|---------|-------------------|-------------------|-------------------|
| 1 | 16 | no | 16×0 | 0 | 16×0 |
| 2 | 16 | no | 16×0 | 0 | 16×0 |
| 3 | 16 | no | 16×0 | 0 | 16×0 |
| 4 | 16 | no | 16×0 | 0 | 16×0 |
| 5 | 16 | **yes** (`taskset -c 0-3`) | 16×0 | 0 | 16×0 |
| 6 | 32 | no | 32×0 | 0 | 32×0 |
| 7 | 32 | no | 32×0 | 0 | 32×0 |
| 8 | 32 | no | 32×0 | 0 | 32×0 |
| 9 | 32 | no | 32×0 | 0 | 32×0 |
| 10 | 32 | no | 32×0 | 0 | 32×0 |

**Total across all 10 lane runs: 0 non-zero exits, 0 tracebacks**, fresh and warm alike, across
(5×16) + (5×32) = 240 fresh-phase process launches and 240 warm-phase launches.

## Results — baseline contrast (planning base `81b835441b`, pre-fix)

| # | N | Fresh exit tally | Fresh tracebacks | Warm exit tally |
|---|----|-------------------|-------------------|-------------------|
| 1 | 32 | 32×0 | 0 | 32×0 |
| 2 | 32 | **30×0, 2×1** | **2** | 32×0 |
| 3 | 32 | 32×0 | 0 | 32×0 |

Run 2's failing processes both raised the pre-fix, unwaited crash:

```
RuntimeError: Asset changed during preparation: …
```
(traceback present; the reproducer's `Traceback|Error` grep tagged both). The remaining 30 of that
run's 32 fresh-phase processes, and both other base runs in full, did not hit the race window —
consistent with the spec's own framing that this is intermittent, "up to 5/32 crash per run," not
every run.

## Verdict

- The lane (WP01's fix) shows 0 failures across all 10 prescribed runs (5×N=16 including one
  CPU-pinned run, 5×N=32) — SC-001 and NFR-001 are met by this evidence.
- The baseline contrast confirms the reproducer still exercises the real race window on this host:
  1 of 3 base runs at N=32 reproduced the original crash (2/32 processes), with the exact pre-fix
  traceback. This is not a claim that the base always fails — it is intermittent by design — only
  that the reproducer is capable of triggering it here, which makes the lane's clean 10/10 result
  meaningful rather than a reproducer that never exercised the race.
- No lane run raised a non-zero exit or a traceback in either phase. Per the WP02 risk guidance, had
  any lane run failed this would have been stopped and reported as a WP01 defect rather than
  retried; that did not occur.
- This is supplementary, non-gating evidence (per NFR-001); the gate is WP01's deterministic test
  suite (`tests/runtime/test_build_serialized.py`,
  `tests/runtime/test_startup_torn_read_escalation.py`), which is green.

## Cleanup

The scratch base-worktree used for the baseline contrast was removed after this evidence was
recorded (`git worktree remove <scratch>/base-worktree`); no scratch artifacts remain in the repo.
