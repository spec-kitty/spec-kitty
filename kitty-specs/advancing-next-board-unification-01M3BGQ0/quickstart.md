# Quickstart: reproduce & verify advancing-next board unification

## Reproduce the bug (pre-fix, current main)

The #4980 standalone reproduction (also captured in this mission's `tooling-friction`/`approach` tracers) drives a 1-WP `single_branch` mission to a review rejection and asserts the loop spins:

```bash
# From the source checkout:
SPK_QA_SOURCE="$PWD" bash <the #4980 repro script> /tmp/repro_out
# Expect (pre-fix):
#   bug advancing next [a1..a3] rc=0 kind=step state=review action=review wp=None
#   bug query next rc=0 kind=query state=implement action=None wp=WP01
#   CONFIRMED: after a review-step rejection the loop spins on a WP-less placeholder review step (exit 0); controls behave
```

For #4975, create a mission with `--topology coord` and advance the loop to implement:

```bash
# Expect (pre-fix):
#   coord advancing next 5 rc=1 blocked implement action=None wp=None reason=No action mapped for WP step 'implement'
#   coord query next: query implement wp=WP01
```

## Verify the fix (post-fix)

```bash
# Blast-radius test tier (NFR-004, ~<90s):
.venv/bin/python -m pytest tests/runtime/test_bridge_parity.py tests/next/test_finalized_task_routing.py tests/next/test_decision_unit.py -q
# Plus the advance-guard tests:
.venv/bin/python -m pytest tests/runtime/next/ -q
```

Post-fix expectations:
- `bug` arm of the #4980 repro re-dispatches `implement WP01` (no CONFIRMED spin); `approve`/`early` controls unchanged.
- `coord` advancing `next --result success` dispatches `implement WP01` (exit 0), matching query mode.
- Every parity-matrix cell (incl. combined coord×review) green; blocked floor returns `kind=blocked` + recovery.

## Dogfooding caveat

This mission is itself `coord` topology. Do **NOT** drive its own implement/review via the buggy autonomous `spec-kitty next --result success` loop (it would hit #4975/#4980). Use `spec-kitty implement WP01` directly and orchestrate review manually.
