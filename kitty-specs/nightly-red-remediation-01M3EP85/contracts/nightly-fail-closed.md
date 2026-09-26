# Contract: nightly lanes fail closed (FR-010)

Applies to `.github/workflows/ci-nightly.yml`.

## Interpreter-matrix leg

- The pytest suite step carries a step-level `timeout-minutes` strictly below the job-level `timeout-minutes`. Today these are 60 and 75. Re-derive them with ceil(×1.5) from the first honest run.
- The pytest command passes `--timeout=<seconds>`, so a single deadlocked test fails that test instead of consuming the leg.
- The upload and fail-loud steps that follow are `if: always()`. The escalation step is `if: ${{ !cancelled() }}`: a step timeout marks that step Failed rather than Cancelled, so all three still run after an overrun. A manual cancel of the run does not file a false P0.
- A step that never wrote `INTERPRETER_EXIT` is treated as failure (`${INTERPRETER_EXIT:-1}`):
  - escalation files or refreshes the deduplicated P0 with conclusion `failure`;
  - the leg fails.

## `nightly-summary`

- Every `needs.<job>.result` reaches the script through `env:`. Nothing is interpolated into the script body with `${{ }}`.
- The script echoes every result, then exits `1` if any result is not `success`. That covers `failure`, `cancelled` and `skipped`.

**Pinned by**: `tests/ci/test_nightly_overrun_fail_closed.py` (parses the real workflow; runs the summary script under bash).
