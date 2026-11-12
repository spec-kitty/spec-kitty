# Research: Lane worktrees run and verify lane code

Grounding lives in `research/code-grounding.md` and `research/foldable-issues.md`. This file
records the planning decisions in Decision / Rationale / Alternatives form.

## D1 — Invocation mechanism
- **Decision**: hybrid builder + child-process probe (operator ruling `01M7734HC608E8NG5FE016CSP9`).
- **Rationale**: an environment (not an in-process setting) reaches every child the tests
  spawn; `PYTHONPATH=<lane>/src` only when the lane has no venv keeps lane venvs authoritative,
  and the probe turns "should import the lane" into an observed fact.
- **Alternatives**: per-lane venv (slow, Python/uv-only, overlaps #3959); probe-only (lanes
  without a venv stay unfixed).

## D2 — What the probe executes
- **Decision**: `importlib.util.find_spec` for each top-level package under `<lane>/src`, in a
  child process using the invocation's cwd and environment; JSON on stdout; 15 s timeout.
- **Rationale**: `find_spec` resolves the origin without running package code, so a consumer
  package whose `__init__` needs absent dependencies still probes; `importlib.metadata` would
  report the root dist-info under `PYTHONPATH` and cannot tell trees apart.
- **Alternatives**: `import pkg; pkg.__file__` (executes code, fails on missing deps); a
  `sitecustomize` recorder observing the real test run (direct evidence, but shadows a
  project's own `sitecustomize` and is defeated by `-I`; recorded as a possible follow-up).

## D3 — Probe interpreter
- **Decision**: the lane's `.venv` interpreter, else the first `python3`/`python` on the
  invocation's `PATH`, else the CLI's own interpreter.
- **Rationale**: models "a Python started by this invocation"; an activated root venv on
  `PATH` is exactly the case to catch.
- **Alternatives**: always `sys.executable` (the CLI's interpreter is often a uv tool env
  unrelated to the project).

## D4 — Refusal severity and code
- **Decision**: new outcome `foreign_tree`, refusal code `EVIDENCE_TREE_MISMATCH`, exit 1,
  regardless of `review.fail_on_pre_review_regression`; `--force` proceeds and records
  `force_bypassed` (operator ruling `01M7733YYK1615ERKAY41C2M7C`).
- **Rationale**: evidence from another tree is not review evidence; a bypass protects work
  from a probe false positive.
- **ADR**: amend ADR `2026-08-13-6` in place; the "gate faults never refuse" rule keeps
  holding for faults (probe errors are `unverified`), only a proven foreign tree refuses.

## D5 — Where the gate probes
- **Decision**: before the head run; a foreign tree returns at once without running tests.
- **Rationale**: a run against another tree produces no usable evidence; skipping it saves
  the whole test budget.

## D6 — Scope of stripping
- **Decision**: strip `PYTHONPATH` / `UV_PROJECT_ENVIRONMENT` / `VIRTUAL_ENV` on both gate
  paths via the invocation; baseline capture keeps its current environment.
- **Rationale**: closes the declared-path gap; baseline capture runs in its own detached
  base worktree and is out of this Mission's blast radius (C-008).

## Supply chain
No dependency is added, upgraded or removed (DIRECTIVE_051: not applicable).

## Adversarial evidence
A post-plan adversarial squad runs before `/spec-kitty.tasks`; contested findings and their
dispositions are appended below.

### Post-plan squad (architecture lens, test lens) — dispositions, 2026-11-12

| # | Finding | Disposition |
|---|---|---|
| A1/T2 | With `PYTHONPATH` injected the probe is always `verified`; foreign is reachable only through a lane with its own environment | Accepted. Foreign fixtures are a lane `.venv` whose install points elsewhere (US1 AS2 reworded); this is the #1907 detection case. |
| A1 | Probe interpreter differs from the command's | Accepted as a documented limit (D2); interpreter recorded in evidence. |
| A2/T5 | Head and baseline would run in different environments → spurious `new_failures` | Accepted. Baseline uses the same recipe rooted at its worktree. |
| A2/T5 | Stripping `UV_PROJECT_ENVIRONMENT` makes `uv run` sync a lane venv in the gate budget | Accepted as today's behaviour when the variable is unset; stripping only removes the root-venv redirect (which risks #1907). Recorded in plan risks. |
| A3 | Override tier bypasses the handler; lane id dropped | Accepted. Hook builds invocation/probe/evidence; plain `run_env` goes to both runners. |
| A4 | `lanes`→`review.baseline` import loop | Accepted. Caller passes the command; no review import in the leaf. |
| A5/T7/T11 | Unlisted aggregation consumers; `force_bypassed` formula; parity tests | Accepted. Full consumer list in plan; `bypassed_refusal` key; `run_env` read with default. |
| A6/T9 | Persisted probe goes stale; three context writers | Accepted. Never persisted; re-derived per surface; FR-001 reworded. |
| A7/T13 | Windows interpreter, PATH `python3` stub, 15 s per render | Accepted. Lane venv interpreter via `kernel.paths.is_windows`, else `sys.executable`; 5 s; `-P`. |
| A8/T1 | Probe set: untracked/namespace dirs; existing fixtures could flip to refusal | Accepted. Only git-tracked regular packages under `src/`. |
| T3 | Containment against lane root lets a lane-venv copy pass | Accepted. Containment against `<lane>/src`. |
| A9 | Skip path bypasses provenance; force records no test run | Accepted. Spec says so. |
| A10 | Null case keyed on root path catches `single_branch` code work | Accepted. Keyed on planning lane. |
| T4 | FR-004 no-op passable half by half | Accepted. Env-recorder test on the declared path + lane-venv PYTHONPATH test. |
| T6 | SC-005 "unchanged" false: two goldens gain a key | Accepted. SC-005 reworded. |
| T8 | NFR-004 cannot fail on Linux | Accepted. Injected `pathmod`. |
| T10 | Evidence scope wording; key-set test | Accepted. Conditional key; FR-007 reworded. |
| T13 | Absolute machine paths in a tracked log | Accepted. Repository-relative paths where possible. |
| A8 | `spec_kitty_services` workspace member not probed | Rejected for this Mission: only `src/` packages are in scope (assumption recorded). |
