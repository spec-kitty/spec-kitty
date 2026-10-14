---
work_package_id: WP01
title: Shared bounded-retry install helper
dependencies: []
requirement_refs:
- FR-001
- FR-003
- NFR-001
- NFR-002
- C-003
planning_base_branch: issue-6191-ci-uv-sync-resilience
merge_target_branch: issue-6191-ci-uv-sync-resilience
branch_strategy: Planning artifacts for this mission were generated on issue-6191-ci-uv-sync-resilience. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6191-ci-uv-sync-resilience unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/uv_sync_retry.py
- tests/ci/test_uv_sync_retry.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/uv_sync_retry.py
- tests/ci/test_uv_sync_retry.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared bounded-retry install helper

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Create one shared, stdlib-only Python helper, `scripts/ci/uv_sync_retry.py`, that
runs a given command with a bounded, exponentially-backed-off retry and propagates
the final non-zero exit code. This is the single resilient-install primitive that
WP02 wires into the three CI Router module-test shards.

## Context

The `tests (docs)` module-test shard in `.github/workflows/ci-router.yml`
intermittently fails at `uv sync --frozen --all-extras` because of an isolated
transient network-download failure (grounding note §1, §4). The fix is to retry
that *install* step a bounded number of times — a resilience measure on a
pre-test network step, explicitly **not** a test rerun (grounding note §5;
C-003). This WP delivers the retry primitive; WP02 (which depends on it) invokes
it from each shard and pins the wiring.

Key design decisions (from `plan.md`, IC-01):

- **Stdlib only.** The helper runs on the runner's default `python3`, *before* the
  uv venv exists, so it may import only the Python standard library (NFR-002).
- **Namespace-package convention.** `scripts/ci/` has no `__init__.py`; it is a
  namespace package. Tests import `from scripts.ci import uv_sync_retry`; CI
  invokes it by path: `python3 scripts/ci/uv_sync_retry.py uv sync --frozen
  --all-extras` — mirroring the existing `scripts/ci/green_match.py`.
- **No green-washing.** A deterministic failure (fails on every attempt) must
  exhaust the bounded attempts and return the underlying non-zero exit code so the
  shard still reds (FR-003). No swallowing, no `exit 0`.
- **Bounded + backed off.** ≤ 3 total attempts; exponential backoff between
  attempts; happy path (first-attempt success) sleeps zero; worst-case total
  backoff ≤ 15 s (NFR-001).

### Subtask T001: Failing-first helper unit test (ATDD red)

**Purpose**: Pin the helper's observable behavior with a test that is RED before
the helper exists (ATDD-first, charter C-011), committed as the WP's first commit.

**Steps**:
1. Create `tests/ci/test_uv_sync_retry.py`.
2. Import the helper module: `from scripts.ci import uv_sync_retry`.
3. Write focused tests driving a fake command runner (inject a callable or patch
   `subprocess.run`) so no real process/network is needed:
   - **Retries a transient failure then succeeds**: a runner that returns a
     non-zero code on attempt 1 and 0 on attempt 2 → helper returns 0 and the
     runner was called exactly twice. (FR-001)
   - **Happy path spawns once, sleeps zero**: a runner that returns 0 first try →
     called once, and `time.sleep` was never called. (NFR-001)
   - **Deterministic failure propagates**: a runner that returns the same non-zero
     code on every attempt → helper returns that exact code, and the runner was
     called exactly the attempt cap (3) times. (FR-003)
   - **Bounded attempt cap + backoff growth**: patch `time.sleep` and assert it is
     called `attempts - 1` times with strictly non-decreasing (exponential) delays
     whose sum is ≤ 15 s for the 3-attempt default. (NFR-001)
   - **`main(argv)` wires argv to the command and returns the exit code**: calling
     `uv_sync_retry.main(["uv", "sync", "--frozen", "--all-extras"])` with a
     patched runner returns the runner's final code (so the CI by-path invocation
     exits correctly).
4. Keep the test deterministic (patch `time.sleep`; never sleep for real).

**Files**: `tests/ci/test_uv_sync_retry.py` (new, ~90 lines).
**Validation**: Before T002 the module import fails → the test file is RED
(collection/ImportError). Capture that RED as the first commit.

### Subtask T002: Implement the helper (green)

**Purpose**: Make T001 green with the smallest correct implementation.

**Steps**:
1. Create `scripts/ci/uv_sync_retry.py`, stdlib-only (`from __future__ import
   annotations`; `subprocess`, `sys`, `time`, `collections.abc.Sequence`,
   typing).
2. Expose a pure-ish core, e.g.
   `run_with_retry(cmd: Sequence[str], *, attempts: int = 3, base_delay: float =
   1.0, runner=subprocess.run, sleep=time.sleep) -> int` that:
   - runs `cmd`; on exit code 0 returns 0 immediately;
   - on a non-zero code, if attempts remain, sleeps `base_delay * 2**(i-1)` then
     retries; else returns the last non-zero code.
   - Injectable `runner`/`sleep` keep it unit-testable (NFR-002, "testable
     extractions").
3. Add `main(argv: Sequence[str] | None = None) -> int` that treats `argv` as the
   command to run (everything after the program name) and returns
   `run_with_retry(...)`.
4. `if __name__ == "__main__": raise SystemExit(main(sys.argv[1:]))`.
5. Print a short stderr note on each retry (e.g. "uv_sync_retry: attempt N/3
   failed (exit C); retrying in Ds") so CI logs show why a retry happened — never
   a credential or environment dump (DIRECTIVE_050).
6. Keep cyclomatic complexity ≤ 15 and pass `mypy` strict (annotate fully).

**Files**: `scripts/ci/uv_sync_retry.py` (new, ~45 lines).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_uv_sync_retry.py -q` is
GREEN.

### Subtask T003: Lint / type / complexity gate

**Purpose**: Prove the helper meets the repo's code-quality bars (NFR-002).

**Steps**:
1. `uv run --frozen ruff check scripts/ci/uv_sync_retry.py tests/ci/test_uv_sync_retry.py`
2. `make format-check-files FILES="scripts/ci/uv_sync_retry.py tests/ci/test_uv_sync_retry.py"`
   (per-file formatter needs `--force-exclude`; the make target passes it).
3. `uv run --frozen mypy scripts/ci/uv_sync_retry.py` — zero issues.
4. Confirm complexity ≤ 15 (ruff `C901` is configured repo-wide at 15).

**Files**: none beyond T001/T002.
**Validation**: all three commands exit 0 with no findings.

## Definition of Done

- `tests/ci/test_uv_sync_retry.py` was RED before the helper existed and is GREEN
  after (ATDD red→green; the first commit is the failing test).
- `run_with_retry` retries a transient failure, spawns once on the happy path with
  zero sleep, propagates a deterministic failure's exit code after the bounded cap,
  and backs off ≤ 15 s total for the 3-attempt default.
- `ruff check`, `ruff format --check --force-exclude`, and `mypy` are clean on both
  files; complexity ≤ 15.
- Each subtask recorded via `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- **Importability**: running `python3 scripts/ci/uv_sync_retry.py …` by path must
  still allow `from scripts.ci import uv_sync_retry` in tests — keep all executable
  logic behind `main()`/`if __name__ == "__main__"`, no import-time side effects.
- **Real sleeps in tests** would slow CI — always inject/patch `sleep`.
- **Over-engineering**: keep it a tiny retry loop; do not add config files, env
  knobs, or a CLI framework (smallest-viable-diff).

## Reviewer Guidance

- Confirm the helper is stdlib-only and has no import-time side effects.
- Confirm FR-003: a stub failing every time returns the real non-zero exit code and
  is NOT green-washed — this is the charter-critical anti-"retry-to-green" property.
- Confirm the retry count, backoff growth, and ≤15 s bound are asserted by the test,
  not just the implementation.

Implement with:
`spec-kitty agent action implement WP01 --agent claude --mission ci-uv-sync-resilience-01M4VDBW`
