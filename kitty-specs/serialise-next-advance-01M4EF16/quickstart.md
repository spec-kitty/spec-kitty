# Quickstart — verifying serialise-next-advance

How to reproduce the races and confirm the fix. All reproductions are
deterministic (injected interleaves or a `threading.Barrier`), never sleeps.

## Reproduce (red on the mission base)

Run the mission's red-first tests against the pre-fix code:

```bash
# per-PR deterministic repros (while the bug is open they carry p0_repro, so
# force the p0-repro lane on to see them):
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest \
  tests/next/test_next_concurrency_5682.py \
  tests/next/test_engine_stale_refusal_5854.py \
  tests/next/test_answer_vs_next_race.py -q

# true-concurrency lock proof (stress, serial):
.venv/bin/python -m pytest tests/runtime/test_next_advance_true_concurrency.py \
  -m stress -p no:xdist -q
```

Expected on the base: the composition-window and engine repros complete a step
the caller never evaluated (or re-apply success); the answer-vs-next test loses a
mutation; the true-concurrency test double-appends. All RED.

## Verify the fix (green on the final commit)

Re-run the same commands on the branch tip — all GREEN. Then prove non-vacuity
(SC-003), reverting each part in turn and confirming at least one test goes red:

- revert the expected-step CAS → composition/engine repros red;
- revert the engine-path refusal → the inverted pin red;
- revert the `provide_decision_answer` guard → the answer race red;
- revert the per-run lock (keep the CAS) → the held-lock-blocks test AND the
  barrier true-concurrency test red;
- revert the unique temp → the collision-pair test red.

## Blast-radius test commands (recorded in the PR)

```bash
make test-fast
.venv/bin/python -m pytest tests/runtime tests/next tests/specify_cli/next -q
.venv/bin/python -m pytest \
  tests/architectural/test_lock_primitive_ban.py \
  tests/architectural/test_layer_rules.py \
  tests/architectural/test_no_legacy_terminology.py -q
ruff check <changed>; ruff format --check --force-exclude <changed>; mypy <changed>
```

## Observe the shipped behavior

A refused advance prints the existing `next` blocked shape (no new kind/exit):

```bash
spec-kitty next --agent claude --mission <handle> --json --result success
# on a stale/contended advance: {"kind":"blocked","reason":"…changed after the advance was planned…"} ; exit 1
```
