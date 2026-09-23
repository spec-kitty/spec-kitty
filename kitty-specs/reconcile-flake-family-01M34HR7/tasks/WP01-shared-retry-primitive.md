---
work_package_id: WP01
title: Shared bounded retry primitive (reconcile_retry.py)
dependencies: []
requirement_refs:
- NFR-001
- NFR-002
- C-004
- C-005
- FR-008
planning_base_branch: fix/reconcile-flake-family-4882
merge_target_branch: fix/reconcile-flake-family-4882
branch_strategy: Planning artifacts for this mission were generated on fix/reconcile-flake-family-4882. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/reconcile-flake-family-4882 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reconcile-flake-family-01M34HR7
base_commit: 8aadd9488ed78df3c609982c05a1b09ece5f3e6f
created_at: '2026-09-22T16:22:34.570407+00:00'
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/reconcile_retry.py
- tests/ci/test_reconcile_retry.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/reconcile_retry.py
- tests/ci/test_reconcile_retry.py
role: implementer
tags: []
tracker_refs: []
---

# WP01: Shared bounded retry primitive (reconcile_retry.py)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add one new, generic, stdlib-only bounded retry-with-backoff primitive
(`scripts/ci/reconcile_retry.py::retry_with_backoff`) with its own unit tests
(`tests/ci/test_reconcile_retry.py`). This primitive is the shared foundation WP02 and
WP03 will both import and wrap — it has no dependencies on this mission's other WPs, and
nothing else may import it until it lands, so it must merge first (or at minimum have a
fixed call signature) before WP02/WP03 can proceed.

## Context

This WP implements the plan's FR-008 shared-helper decision, generalized: instead of one
retry helper shared by only `fleet_verdict.py`/`fleet_main.py` (FR-008's literal framing),
plan.md deliberately generalizes it to a single primitive reused by all three retrying call
sites (`fleet_verdict.py`, `fleet_main.py`, and WP03's new `wait_for_artifacts.py`) — see
plan.md's "User Story 2" section and its "Deviations, Blockers, and Judgment Calls" item 1.
Read `kitty-specs/reconcile-flake-family-01M34HR7/plan.md` in full before starting,
especially: "User Story 2 — `fleet_verdict.py` / `fleet_main.py`: retry-then-skip" (the
primitive's exact signature and docstring), "Retry Budget Rationale (NFR-001)" (the two
call sites' concrete numbers, which this primitive must support generically), and
"Red-First Application Across All NFR-003 Test Surfaces". Also read
`kitty-specs/reconcile-flake-family-01M34HR7/spec.md`'s NFR-001, NFR-002, and FR-008 rows
in full.

**Exact required signature** (plan.md, verbatim — do not deviate):

```python
def retry_with_backoff(
    attempt: Callable[[], T | None],
    *,
    max_attempts: int,
    backoff_seconds: Callable[[int], float],
    sleep: Callable[[float], None] = time.sleep,
) -> T | None:
    """Call attempt() up to max_attempts times. attempt() returns None to mean
    "not yet stable/visible, retry"; anything else is returned immediately.
    Sleeps backoff_seconds(i) between attempts (never after the last). Returns
    None if every attempt returned None — the CALLER decides what None means
    (skip-and-defer vs. fail loudly); this primitive makes no such decision.
    """
```

**Compatibility contract, binding on this WP and on all future changes** (plan.md, verbatim
intent): `reconcile_retry.py` MUST remain fully caller-agnostic. No GitHub-specific
parameters (e.g. a PR-number or run-ID argument), no fleet-verdict-specific terminal-behavior
knobs (e.g. a flag that changes what `None` means), and no optional hooks added for one
caller's convenience. Any caller-specific need belongs in that caller's own `attempt()`
closure or a caller-side wrapper, never inside this module. This exists specifically to
protect WP03's `wait_for_artifacts.py` from coupling to WP02's fleet-verdict-specific needs
(or vice versa) — do not weaken it "to make WP02 easier."

`sleep` is injected (default `time.sleep`) specifically so tests never actually wait —
this is what makes the NFR-003 mocked retry-window tests fast and deterministic. Never call
`time.sleep` directly inside test code; always pass a fake `sleep` callable and assert on
its call history/arguments where relevant.

Charter C-011 (ATDD-First Discipline, `.kittify/charter/charter.md`) binds this WP: it
introduces new functional code, so the WP's git history MUST open with a commit containing
ONLY a failing test (no implementation), committed BEFORE any implementation commit. The
reviewer will verify RED on `planning_base_branch` and GREEN on the WP's final commit.

## Subtask T001: Red-first test — recovery path

**Purpose**: Prove `retry_with_backoff` does not yet exist / does not yet behave correctly,
by writing (and running) a test against it before any implementation lands.

**Steps**:
1. Create `tests/ci/test_reconcile_retry.py` (new file).
2. Write a test that constructs an `attempt` callable (e.g. a closure over a list of
   canned return values, or a `Mock`/`MagicMock` with `side_effect`) that returns `None` on
   its first two calls and a sentinel non-`None` value on its third call.
3. Call `retry_with_backoff(attempt, max_attempts=4, backoff_seconds=lambda i: 0.0,
   sleep=fake_sleep)` where `fake_sleep` is a no-op stub that records its calls (e.g.
   `sleep_calls: list[float] = []; def fake_sleep(s): sleep_calls.append(s)`).
4. Assert the sentinel value is returned, `attempt` was called exactly 3 times (not 4 —
   it should stop as soon as a non-`None` result appears), and `fake_sleep` was called
   exactly 2 times (between attempts 1→2 and 2→3, never after the final successful attempt).
5. Run `.venv/bin/python -m pytest tests/ci/test_reconcile_retry.py -q` and confirm it
   fails with an import error (`reconcile_retry` module does not exist yet). This IS the
   red-first anchor — commit this file now, as its own commit, before writing any
   implementation code. Commit message example:
   `test(ci): red-first test for reconcile_retry.retry_with_backoff recovery path`.

**Files**: `tests/ci/test_reconcile_retry.py` (new, this subtask contributes the recovery-path
test; T002 adds the termination test to the same file before the implementation commit).

**Validation**: `pytest` collection/run fails with `ModuleNotFoundError` or `ImportError` for
`scripts.ci.reconcile_retry` (or however the test imports it — check how sibling test files
in `tests/ci/` import their `scripts/ci/*.py` targets, e.g. `tests/ci/test_fleet_verdict.py`'s
import style, and match it exactly for consistency).

## Subtask T002: Red-first test — termination on exhausted budget

**Purpose**: Prove the bounded-termination behavior (NFR-001's core testable claim) fails
before the primitive exists, completing the red-first anchor for this WP.

**Steps**:
1. In the same `tests/ci/test_reconcile_retry.py`, add a second test: an `attempt` callable
   that always returns `None` (never stabilizes).
2. Call `retry_with_backoff(attempt, max_attempts=5, backoff_seconds=lambda i: 0.0,
   sleep=fake_sleep)`.
3. Assert the return value is `None`, `attempt` was called exactly 5 times (not 4, not 6 —
   the bound is exact), and `fake_sleep` was called exactly 4 times (between attempts,
   never after the last, per the docstring's "never after the last" clause).
4. Add a third test asserting `backoff_seconds(i)` is called with the correct attempt index
   at each sleep point (e.g. `backoff_seconds` is itself a `Mock` and you assert
   `call_args_list == [call(1), call(2), call(3), call(4)]` or whatever indexing convention
   you choose — pick one, document it in the test, and keep the primitive's own
   implementation consistent with it in T003).
5. Confirm all three tests in the file still fail on import (no implementation exists yet).
   This completes the red-first commit for WP01 — commit now as a continuation of, or a
   second commit fully preceding, the implementation commit. Both red-first tests
   (T001 + T002) must land in commit(s) that predate the first implementation commit.

**Files**: `tests/ci/test_reconcile_retry.py` (continues from T001).

**Validation**: Same red import-failure mode as T001; run the full file with
`.venv/bin/python -m pytest tests/ci/test_reconcile_retry.py -q` and confirm every test in
it fails for the same "module does not exist" reason (not a partial pass).

## Subtask T003: Implement `retry_with_backoff`

**Purpose**: Make T001/T002's tests pass with a correct, generic, stdlib-only implementation.

**Steps**:
1. Create `scripts/ci/reconcile_retry.py` (new file). Match the module docstring/header
   conventions of sibling `scripts/ci/*.py` files (e.g. `reconcile_shards.py`'s own
   docstring style — read it for the convention).
2. Implement `retry_with_backoff` with the exact signature quoted in Context above. Use
   only `time`/`typing` from the standard library — no third-party imports (NFR-002/C-004).
3. Loop: call `attempt()`; if the result is not `None`, return it immediately (no sleep
   after a success). If it is `None` and this was not the last attempt, call
   `sleep(backoff_seconds(i))` before the next attempt (pick and document the `i` indexing
   convention consistently with T002's assertions). After `max_attempts` calls all
   returning `None`, return `None` without a further sleep.
4. Add a module-level docstring/comment stating the compatibility contract from Context
   above verbatim or near-verbatim (future-proofing note for reviewers of later changes).
5. Run `.venv/bin/python -m pytest tests/ci/test_reconcile_retry.py -q` and confirm all
   tests now pass (RED → GREEN).

**Files**: `scripts/ci/reconcile_retry.py` (new, ~30–50 lines per plan.md's estimate).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_reconcile_retry.py -q` — all
tests pass. `uv run --frozen ruff check scripts/ci/reconcile_retry.py
tests/ci/test_reconcile_retry.py` and `uv run --frozen ruff format --check
scripts/ci/reconcile_retry.py tests/ci/test_reconcile_retry.py` both clean.

## Subtask T004: Gate verification and handoff readiness

**Purpose**: Confirm this WP's diff is ready for WP02/WP03 to build on, and that it clears
every gate this diff triggers.

**Steps**:
1. Run `.venv/bin/python -m pytest tests/ci/test_reconcile_retry.py -q` one more time
   standalone to confirm a clean, fast, deterministic pass (no real sleeps — total runtime
   should be well under a second given the injected `sleep` stub).
2. Run `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` scoped at
   minimum to the two files this WP owns (a full-repo run is fine too, but do not treat
   unrelated pre-existing lint drift elsewhere in the repo as this WP's problem — see
   CLAUDE.md's baseline-red gotcha).
3. Confirm the import-linter / TID251 check has nothing to flag: this module has no
   external imports beyond `time`/`typing`, so `uv run --frozen ruff check --select TID251 .`
   should be a clean no-op with respect to this file.
4. Double-check `retry_with_backoff`'s signature exactly matches the Context section above
   — WP02 and WP03 will both import it verbatim; a signature drift here breaks both
   downstream WPs silently.
5. State in your completion notes (for the reviewer) the exact git log for this WP's lane,
   showing the red-first test commit(s) preceding the implementation commit, per C-011.

**Files**: none new — verification only.

**Validation**: `pytest`, `ruff check`, `ruff format --check` all green for this WP's two
files; git history shows red-first ordering.

## Definition of Done

- `scripts/ci/reconcile_retry.py` exists, exports `retry_with_backoff` with the exact
  signature specified above, uses only the Python standard library, and states its
  caller-agnostic compatibility contract in its own docstring/comments.
- `tests/ci/test_reconcile_retry.py` exists and covers: (a) recovery within budget (stops
  as soon as a non-`None` result appears, correct call count), (b) exhausted-budget
  termination (exact `max_attempts` call count, no over/under-call), (c) correct
  `backoff_seconds(i)` invocation and no sleep after the final attempt.
- Git history for this WP shows a red-first commit (failing test only) preceding the
  implementation commit — verifiable by checking out the red-first commit on
  `planning_base_branch` and confirming the test fails there, then confirming it passes on
  the WP's final commit (charter C-011).
- Gates this WP triggers, all green: `ruff check .`, `ruff format --check .` (C-005), the
  `ci-modules.yml` `ci` shard over `tests/ci/` (the diff-cover ≥90% floor does NOT apply —
  `scripts/ci/**` is not `--cov`-instrumented, per spec.md C-008 — this does not excuse
  omitting tests, which this WP already provides).
- No new third-party dependency added (NFR-002/C-004) — `pyproject.toml`/`uv.lock`
  untouched by this WP.

## Risks

- **Signature drift risk**: because WP02 and WP03 both import this primitive verbatim, any
  change to its signature after this WP "completes" is a breaking change to both downstream
  WPs. Treat the signature in this prompt as final; if you find a reason to change it,
  flag it explicitly rather than changing it silently.
- **Sleep-indexing convention ambiguity**: the docstring says "sleeps `backoff_seconds(i)`
  between attempts (never after the last)" but does not pin whether `i` is 0-indexed,
  1-indexed, or counts remaining attempts. Pick one, document it in both the implementation
  and the test assertions, and keep it internally consistent — WP02/WP03 do not need to
  know the indexing scheme (they only pass a `backoff_seconds` callable), so this is a
  self-contained decision, but an inconsistent test vs. implementation would be a real bug.

## Reviewer Guidance

Verify red-first history literally (checkout the red-first commit, run the test file,
confirm failure; checkout the final commit, run it again, confirm pass) rather than trusting
a claim in the PR description. Confirm `retry_with_backoff` truly has zero GitHub-specific or
caller-specific parameters — this is the property that makes WP03's independence from WP02
real, not aspirational. Confirm `sleep` is injected everywhere in the test file (no bare
`time.sleep` calls that would make the test suite slow or flaky).

Run: `spec-kitty agent action implement WP01 --agent claude`
