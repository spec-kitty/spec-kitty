---
work_package_id: WP02
title: Recapture decision-logic script
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- C-001
- C-003
- C-004
- C-005
- C-006
planning_base_branch: issue-5189-per-pr-shard-timings-recapture-friction
merge_target_branch: issue-5189-per-pr-shard-timings-recapture-friction
branch_strategy: Planning artifacts for this mission were generated on issue-5189-per-pr-shard-timings-recapture-friction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5189-per-pr-shard-timings-recapture-friction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-per-pr-shard-timings-recapture-friction-01M3H7V8
base_commit: f8dcce82a74f1b6e7a0acf52af022419910081ca
created_at: '2026-09-28T01:32:40.035498+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Core demotion (User Story 2)
history:
- at: '2026-09-27T22:00:54Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: scripts/ci/recapture_charter_shard_timings.py
create_intent:
- scripts/ci/recapture_charter_shard_timings.py
- tests/ci/test_recapture_charter_shard_timings.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/recapture_charter_shard_timings.py
- tests/ci/test_recapture_charter_shard_timings.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Recapture decision-logic script

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any
user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `implementer`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` and `authoritative_surface: scripts/ci/recapture_charter_shard_timings.py`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!** Check `review_ref` in the event log (via
`spec-kitty agent tasks status`) or the Activity Log below before starting.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks: ` ```python `,
` ```bash `.

---

## Objectives & Success Criteria

Build `scripts/ci/recapture_charter_shard_timings.py`: every piece of decision logic (open-PR
match, drift compare, mechanism-vs-ordinary-failure classification, missing-secret fail-loud) as
pure, unit-tested functions, with a thin `gh`/`git`-calling `main()` edge — mirroring
`scripts/ci/stale_running_sweep.py`'s shape (pure decision + thin I/O edge) per
DIRECTIVE_044 (canonical sources, no improvise). This WP owns **FR-005, FR-006, FR-007, FR-008,
FR-009, FR-010**, plus **C-001** (charter-only), **C-003** (`main` is PR-only, no direct push),
**C-004** (no silent `GITHUB_TOKEN` fallback), **C-006** (concurrency — the script itself has no
concurrency logic; that's WP03's workflow-level `concurrency:` block, but this WP's TOCTOU re-check
is the code-level half of the same safety property), and **NFR-003** (no credential leakage).

**This WP does NOT**: modify `scripts/ci/capture_shard_timings.py` (deliberately left unmodified —
plan.md item (e); this WP's design depends on its existing write-before-return-decision control
flow), invoke it as a subprocess (call `capture_shard_timings.main(argv)` **in-process**, per the
design-problem resolution below), or write the workflow YAML file (that is WP03, which depends on
this WP).

## Context & Constraints

- **Read before starting**: `scripts/ci/capture_shard_timings.py` in full (286 lines) — you depend
  on its exact control flow (its `main()` writes `.github/ci-shard-timings.json` to disk via
  `destination.write_text(...)` strictly before it can return cleanly; any exception from
  `_capture_all`/`capture_module`/`merge_capture` propagates uncaught, before the write). Also read
  `scripts/ci/stale_running_sweep.py` (the closest in-repo precedent for a pure-decision-functions
  + thin-`gh`-edge script shape) and `scripts/ci/release_nightly_gate.py` (for the
  `resolve_token`/`_redact` truthy-check and redaction precedent — **but do NOT copy its
  `GITHUB_TOKEN` fallback loop**; CL-002/C-004 explicitly forbid that fallback here).
- **No in-repo precedent for `gh pr create`/`gh pr list`-based PR-opening exists** in this repo
  today (verified: `grep -rln "gh pr create\|gh pr list" scripts/ci/ .github/workflows/` returns no
  hits) — you are writing this wiring fresh, following plan.md's verbatim invocation spec below,
  not copying an existing script.
- **Supporting docs**: `kitty-specs/.../spec.md` (FR-005..FR-010, User Story 2, Key Entities),
  `kitty-specs/.../plan.md` §"Concrete Design Decisions (b) and (c)" and the
  "mechanism-vs-ordinary-failure design problem" section (the exact code sketch you should
  implement, reproduced below), `.../reviews/spec.ruling.md` (ruling 2: **skip if open**, never
  force-update — do not implement force-push-over-an-open-PR under any circumstance), `.../reviews/plan.ruling.md`.

## Branch Strategy

- **Strategy**: `SINGLE_BRANCH`.
- **Planning base branch**: `issue-5189-per-pr-shard-timings-recapture-friction`
- **Merge target branch**: `issue-5189-per-pr-shard-timings-recapture-friction`

## Subtasks & Detailed Guidance

### Subtask T009 – `CaptureOutcome` dataclass + `run_capture_or_die()`

- **Purpose**: Never trust a raw subprocess exit code (ambiguous — an uncaught exception exits the
  interpreter with code 1, same as a clean `return 1`). Call `capture_shard_timings.main(argv)`
  **in-process**, catching any mechanism failure at the call site.
- **Steps**: Implement verbatim, per plan.md's design-problem resolution:
  ```python
  from __future__ import annotations

  from collections.abc import Callable
  from dataclasses import dataclass

  MODULE = "charter"  # FR-009: hardcoded, no --module flag exposed by this script at all


  @dataclass(frozen=True)
  class CaptureOutcome:
      mechanism_ok: bool
      pytest_exit_code: int | None
      error: str | None


  def run_capture_or_die(capture_main: Callable[[list[str]], int], argv: list[str]) -> CaptureOutcome:
      try:
          exit_code = capture_main(argv)
      except KeyboardInterrupt:
          raise
      except (Exception, SystemExit) as exc:
          # Deliberately broad: ANY uncaught exception from the mechanism is a crash -- AND so is a
          # SystemExit, which Exception alone would miss (argparse's parser.error() raises SystemExit,
          # a BaseException subclass, not an Exception subclass). KeyboardInterrupt is re-raised,
          # never swallowed as a mechanism crash.
          return CaptureOutcome(mechanism_ok=False, pytest_exit_code=None, error=str(exc))
      return CaptureOutcome(mechanism_ok=True, pytest_exit_code=exit_code, error=None)
  ```
- **Files**: `scripts/ci/recapture_charter_shard_timings.py` (new).
- **Parallel?**: Foundational — T010-T013 build on this and `MODULE`.
- **Notes**: `MODULE = "charter"` is the FR-009 scope lock. This script exposes **no** `--module`
  CLI flag — there must be no code path by which this workflow could silently expand to another
  module. `capture_main` is passed in (dependency injection) so unit tests never need the real
  `capture_shard_timings` module.

### Subtask T010 – `has_drift(before_length, after_length) -> bool`

- **Purpose**: A pure, length-only drift comparator (FR-006) — mirrors
  `test_charter_is_not_allowlisted_and_agrees`'s own comparison. Never a raw file-diff/`git diff`
  check (`--write` rewrites `run_id`/`captured_at`/duration-value noise on every invocation even
  with no test-count change — that noise must NOT be treated as drift).
- **Steps**:
  ```python
  def has_drift(before_length: int, after_length: int) -> bool:
      """FR-006: length-only drift. Equal lengths => no drift, even if --write rewrote
      run_id/captured_at/duration-value noise (never compare raw file diffs)."""
      return before_length != after_length
  ```
- **Files**: `scripts/ci/recapture_charter_shard_timings.py`.
- **Parallel?**: Independent of T009, T011, T012 — can be written in any order.

### Subtask T011 – Open-PR matching function

- **Purpose**: FR-007's fixed-branch detection: "an open PR exists with head = the fixed recapture
  branch and base = `main`." An unrelated PR touching the same file on a different head branch (the
  #5175/#5177 shape) must never match.
- **Steps**: Implement a function that takes the **already-parsed** JSON array `gh pr list` returns
  (dependency injection — the function itself does no subprocess call) and returns the matching
  PR's number or `None`:
  ```python
  RECAPTURE_BRANCH = "ci/recapture-charter-shard-timings"


  def find_open_recapture_pr(open_prs: list[dict]) -> int | None:
      """FR-007: match ONLY on head branch == RECAPTURE_BRANCH. An unrelated PR that also
      touches .github/ci-shard-timings.json on a different head (e.g. #5175/#5177) is never
      matched, because its head branch differs."""
      for pr in open_prs:
          if pr.get("headRefName") == RECAPTURE_BRANCH:
              return pr.get("number")
      return None
  ```
  Separately, implement (or fold into `main()`, T013) the actual `subprocess` call that produces
  `open_prs`:
  ```
  gh pr list --repo <owner/repo> --head ci/recapture-charter-shard-timings --base main --state open --json number,headRefName
  ```
  authenticated with `GH_TOKEN` set to `CHARTER_SHARD_RECAPTURE_TOKEN` (never `GITHUB_TOKEN`). An
  empty JSON array means no open PR. Both JSON fields are required, not just `number`:
  `find_open_recapture_pr` reads `headRefName` to do its own match, and the caller needs `number`
  to report/return the matched PR's number — requesting `--json number` alone would leave every
  `pr.get("headRefName")` call returning `None`, silently disabling the head-branch match (and
  therefore FR-007's skip-if-open behavior) in every real invocation.
  - **Supersession note (TASKS-FRESH2-001):** `plan.md`'s "Open-PR check (verbatim)" bullet
    (item (b)) and its TOCTOU re-verification paragraph's restatement of this same `gh pr list`
    command still show the pre-fix `--json number` field list (no `headRefName`). Both passages
    predate this correction and are **superseded** by the `--json number,headRefName` command
    above — this T011 section, not plan.md's now-stale sample, is authoritative for
    implementation. `plan.md` itself is a PASSED artifact from a prior phase and is intentionally
    left unedited; this note is the reconciliation instead.
- **Files**: `scripts/ci/recapture_charter_shard_timings.py`.
- **Parallel?**: Independent of T009/T010/T012.
- **Notes**: Keep `find_open_recapture_pr` pure (list-of-dicts in, `int | None` out) so fixtures 1
  and 2 (T014) need no real `gh` call.

### Subtask T012 – Secret truthy-check (fail-loud, no fallback)

- **Purpose**: FR-005/CL-002/C-004: `CHARTER_SHARD_RECAPTURE_TOKEN` counts as missing when unset OR
  an empty string (GitHub Actions injects `""` into an `env:` mapping for a referenced secret that
  does not exist as a repository secret). This is `main()`'s **very first action**, before ANY
  subprocess call — including the open-PR check (T011) — and it must **never** fall back to
  `GH_TOKEN`/`GITHUB_TOKEN`.
- **Steps**: Implement, mirroring `release_nightly_gate.py::resolve_token`'s truthy test but
  **without** its `GITHUB_TOKEN` fallback loop:
  ```python
  import os
  import sys

  SECRET_NAME = "CHARTER_SHARD_RECAPTURE_TOKEN"


  def require_recapture_token() -> str:
      """FR-005/CL-002/C-004: truthy check ONLY. Never falls back to GH_TOKEN/GITHUB_TOKEN --
      that fallback would silently reintroduce the anti-recursion / CI-gate-bypass risk CL-002
      forbids. Fails loud (::error:: + non-zero exit) BEFORE any recapture, commit, push, or
      open-PR check."""
      value = os.environ.get(SECRET_NAME)
      if not value:  # catches both "unset" and "" (GitHub's injected-empty-string case)
          print(f"::error::{SECRET_NAME} is not set (or is empty) -- refusing to run", file=sys.stderr)
          raise SystemExit(1)
      return value
  ```
- **Files**: `scripts/ci/recapture_charter_shard_timings.py`.
- **Parallel?**: Independent of T009-T011; must be wired as the FIRST call inside `main()` (T013).
- **Notes (NFR-003)**: this function returns the token so `main()` can pass it to the `gh`/`git`
  subprocess environment — never print, log, or interpolate the **value** anywhere. Error paths
  print only the secret's **name** (`SECRET_NAME`), mirroring `release_nightly_gate.py`'s
  `_redact()` convention.

### Subtask T013 – `main()` orchestration sequence

- **Purpose**: Wire T009-T012 into the exact ordering plan.md specifies — this is the single most
  important subtask: an ordering bug here would silently violate C-003/C-004/FR-005/FR-007.
- **Steps**: Implement `main(argv: list[str] | None = None) -> int` in this exact sequence:
  1. **First action, no exceptions**: call `require_recapture_token()` (T012). If it raises
     `SystemExit`, let it propagate — the process exits before anything else runs. **Do not call
     the open-PR check or the capture wrapper before this.**
  2. Read `.github/ci-shard-timings.json` from the working tree (post-`actions/checkout`, so this
     should be a clean, current file) and extract
     `len(payload["module_test_durations"]["charter"])` as `before_length`. **This read MUST
     happen before step 3's capture call** — `capture_shard_timings.main()` overwrites this file
     in place as a side effect of the very call that produces `after_length`; reading both lengths
     after that call would compute `before_length == after_length` unconditionally on every run
     (see fixture 11, T015).
  3. Run the open-PR check (T011's `find_open_recapture_pr`, backed by a real `gh pr list ...`
     subprocess call authenticated with the token from step 1). If it returns a PR number: write
     one line to the job summary (`$GITHUB_STEP_SUMMARY`, e.g. `f"Recapture PR #{pr_number} is
     already open; skipping."`) and return `0` — **no push, no force-push, no comment, no PR-open,
     no capture invocation at all** (ruling 2: skip if open).
  4. If no PR is open: call `run_capture_or_die(capture_shard_timings.main, ["--module", MODULE,
     "--write"])` (T009). If `mechanism_ok` is `False`: print the caught error, and abort with a
     non-zero exit — **no commit, no push, no PR-open** (FR-008).
  5. If `mechanism_ok` is `True`: re-read `.github/ci-shard-timings.json` (now freshly written) and
     extract `after_length` the same way as step 2. Call `has_drift(before_length, after_length)`
     (T010).
  6. If `has_drift` is `False`: no commit, no push, no PR-open (FR-006) — return `0`.
  7. If `has_drift` is `True`: **re-run the open-PR check one more time** (the TOCTOU re-check,
     immediately before the push — the ~18-30 minute capture step in step 4 is a window during
     which something else could have opened a PR against the fixed branch). If the re-check now
     finds an open PR: abort the push exactly like step 3's skip-if-open path (job-summary line
     naming the newly-found PR, no push/force-push/commit/PR-open/comment, return `0`). Otherwise,
     proceed to push.
  8. Commit the freshly-written `.github/ci-shard-timings.json` with author identity
     `spec-kitty-ci-bot <ci-bot@users.noreply.github.com>` and commit message
     `chore(ci): automated charter shard-timings recapture` (verbatim, FR-010), push to the fixed
     branch `ci/recapture-charter-shard-timings` (a plain `git push --force` is acceptable **only**
     in this no-open-PR path — never against an open PR under review, per ruling 2), then
     `gh pr create` with title = the same commit-message string, and body (verbatim template, fill
     only `<before>`, `<after>`, `<run_url>`):
     > "Automated recapture opened by the scheduled `ci-charter-shard-recapture.yml` workflow
     > (`scripts/ci/recapture_charter_shard_timings.py`). Updates `.github/ci-shard-timings.json`'s
     > `charter` entry: committed length `<before>` -> `<after>`. Workflow run: `<run_url>`. See
     > spec-kitty#5189."
     `<run_url>` is filled from the environment (the workflow, WP03, passes
     `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` as an
     env var this script reads) — never free-form prose.
- **Files**: `scripts/ci/recapture_charter_shard_timings.py`.
- **Parallel?**: Depends on T009-T012 all existing first.
- **Notes**: Structure `main()` so every decision point above (steps 3, 4, 6, 7) is a call to a
  pure, injectable function (`find_open_recapture_pr`, `run_capture_or_die`, `has_drift`) — the
  `subprocess`/`gh`/`git` calls themselves should be the thinnest possible glue around those calls,
  so T014/T015's fixtures can inject fakes for every one of them without any real network/git/gh
  call.

### Subtask T014 – Unit tests for fixtures 1-6

- **Purpose**: Prove the core decision logic red-first, with injected fakes — no real `gh`, `git`,
  or `pytest.main()` call needed for any of these.
- **Steps**: In `tests/ci/test_recapture_charter_shard_timings.py` (new; import the module by
  direct `from scripts.ci.recapture_charter_shard_timings import ...`, mirroring
  `tests/ci/test_stale_running_sweep.py`'s import style — `scripts.ci` resolves as a namespace
  package with the repo root on `sys.path`), write:
  1. **skip-if-open**: a fake `gh pr list` JSON response with one open PR whose `headRefName` is
     `ci/recapture-charter-shard-timings` -> `find_open_recapture_pr` returns that PR's number; the
     orchestration path that consumes it performs no push/commit/PR-open call (inject a fake
     "would-push" callable, assert it is never invoked).
  2. **unrelated-PR-not-matched**: an open-PR JSON payload whose `headRefName` is a *different*
     branch (the #5175/#5177 shape) -> `find_open_recapture_pr` returns `None`, even though the
     same JSON shape carries a PR number.
  3. **no-drift-no-PR**: `has_drift(before_length=N, after_length=N)` returns `False`; the
     orchestration path performs no commit/push/PR-open call.
  4. **capture-failure-no-commit**: a fake `capture_main` callable that raises a plain `Exception`
     -> `run_capture_or_die` returns `mechanism_ok=False`; orchestration aborts before any
     commit/push/PR-open call, surfacing the caught exception's message.
  5. **missing-secret-loud-failure** (two required sub-cases, both must produce the SAME loud
     failure):
     - (a) `CHARTER_SHARD_RECAPTURE_TOKEN` set to the empty string `""`.
     - (b) `CHARTER_SHARD_RECAPTURE_TOKEN` fully absent/unset (deleted from `os.environ`, e.g. via
       `monkeypatch.delenv("CHARTER_SHARD_RECAPTURE_TOKEN", raising=False)`).
     Both must: raise `SystemExit` with a non-zero code, print a message naming the secret, and —
     via a spy/fake in place of BOTH the capture-wrapper callable AND the open-PR-check callable —
     prove **neither** is ever invoked in either sub-case (not merely "no branch/commit exists
     afterward", which cannot distinguish "recapture ran, then the check failed before commit" from
     "the check failed before recapture ran").
  6. **drift-triggers-push**: `has_drift(before_length=N, after_length=M)` with `N != M` returns
     `True`; the orchestration path that consumes a `True` result DOES invoke the commit/push/PR-open
     callable exactly once (fake callable asserted called, with expected arguments).
- **Files**: `tests/ci/test_recapture_charter_shard_timings.py` (new).
- **Parallel?**: Independent of T015 (different fixtures), but both live in the same file — write
  sequentially or split into two commits within this WP, implementer's choice.
- **Notes**: Mark this test file (or these tests) `pytest.mark.fast` — none of fixtures 1-6 needs a
  subprocess, `slow` marker, or live collection.

### Subtask T015 – Unit tests for fixtures 7-11

- **Purpose**: Cover the TOCTOU re-check, the `SystemExit`-raising crash variant, the
  post-write-logging-failure edge case, the ordinary-failure-continues flip side of FR-008, and the
  snapshot-before-overwrite ordering — the five remaining fixtures plan.md's item (c) requires.
- **Steps**: Add to `tests/ci/test_recapture_charter_shard_timings.py`:
  7. **toctou-recheck-aborts-push**: a fake open-PR-check callable that returns "no PR open" on its
     first invocation and "PR open, number N" on its second (the re-check immediately before the
     push) -> the orchestration path runs the capture, finds drift, but aborts before the
     push/commit/PR-open call (fake "would-push" callable asserted never invoked), falling back to
     the job-summary line naming PR `N` — exactly mirroring fixture 1's outcome.
  8. **mechanism-crash-via-systemexit**: a fake `capture_main` that raises `SystemExit(2)`
     (mirroring `capture_shard_timings.py`'s own `_parse_args` -> `parser.error(...)` path) ->
     `run_capture_or_die` still returns `mechanism_ok=False` (SystemExit never propagates uncaught
     out of the wrapper); orchestration aborts identically to fixture 4.
  9. **post-write-logging-failure-fails-closed**: a fake `capture_main` that raises only *after*
     performing its own simulated write side effect -> `run_capture_or_die` still returns
     `mechanism_ok=False`; orchestration aborts before any commit/push/PR-open call (the
     already-written local file is never re-read or trusted — a safe false-negative, not a
     data-corruption risk).
  10. **ordinary-failure-continues**: a fake `capture_main` that returns a plain non-zero exit code
      (e.g. `1`) **without raising** -> `run_capture_or_die` returns `mechanism_ok=True,
      pytest_exit_code=1`; the orchestration proceeds to the drift check exactly as for
      `pytest_exit_code=0` — and, when drift is also found, on to commit/push (fake "would-push"
      callable asserted invoked, mirroring fixture 6's assertion style) — never aborting on a
      nonzero-but-clean pytest exit code. This is FR-008's "ordinary failing test does not abort"
      half.
  11. **snapshot-before-overwrite**: a fake `capture_main` that, when invoked, mutates a fake
      in-memory dict standing in for `.github/ci-shard-timings.json`'s parsed payload (appending or
      removing an entry from its `module_test_durations["charter"]` list in place, simulating the
      real `destination.write_text(...)` side effect). The orchestration under test reads the fake
      dict's `charter` length as `before_length` **before** calling
      `run_capture_or_die(capture_main, argv)`, then — only after that call returns
      `mechanism_ok=True` — re-reads the (now-mutated) fake dict's `charter` length as
      `after_length` and calls `has_drift(before_length, after_length)`. Assert `before_length`
      equals the pre-mutation length (never the post-mutation one) and that the resulting
      `has_drift` call correctly reports drift when the fake `capture_main` changed the list's
      length. This is the fixture that would fail if `before_length`/`after_length` were both read
      from the same post-write state.
- **Files**: `tests/ci/test_recapture_charter_shard_timings.py`.
- **Parallel?**: Independent of T014 (different fixtures within the same file).
- **Notes**: Mark `pytest.mark.fast` — none of these needs a subprocess or `slow` marker.

## Test Strategy

- Every fixture (1-11) is a `pytest.mark.fast` unit test in
  `tests/ci/test_recapture_charter_shard_timings.py`, using injected fakes for `gh`, `git`, and
  `capture_shard_timings.main` — no real network/git/gh call is needed for any of them.
- Run targeted: `.venv/bin/python -m pytest tests/ci/test_recapture_charter_shard_timings.py -q`.
  This file does not exist on current HEAD, so its baseline is vacuous ("does not exist / not run"
  per plan.md item (f)) — no RED-FIRST baseline capture is needed for a brand-new file, only for
  the pre-existing `test_module_length_agreement.py` (WP01's T001).
- Never run a bare `tests/ci/` directory sweep or `make test-full`.

## Risks & Mitigations

- **Risk**: the pre-merge manual-`workflow_dispatch` end-to-end rehearsal (plan.md item (c)) needs
  the operator-created `CHARTER_SHARD_RECAPTURE_TOKEN` secret to exist on the dispatching branch.
  **Mitigation**: flag this dependency explicitly in the PR body rather than silently skipping that
  rehearsal — this WP's own unit tests (T014/T015) do not depend on it.
- **Risk**: accidentally invoking `capture_shard_timings.py` as a subprocess instead of in-process,
  reintroducing the exit-code ambiguity the design explicitly avoids. **Mitigation**: T009's
  `run_capture_or_die` signature takes a `Callable`, not a subprocess command — review should
  confirm no `subprocess.run([..."capture_shard_timings.py"...])` call exists anywhere in this
  script.
- **Risk**: silently falling back to `GITHUB_TOKEN` anywhere (e.g. copy-pasting
  `release_nightly_gate.py::resolve_token` verbatim, fallback loop included). **Mitigation**:
  T012's Notes explicitly forbid this; review should grep the new file for `GITHUB_TOKEN` and
  confirm any hit is only in a comment explaining why it is NOT used.

## Review Guidance

- Confirm `main()`'s first action is `require_recapture_token()`, with no other subprocess call
  (including the open-PR check) reachable before it.
- Confirm the open-PR check runs TWICE in the drift-found path (initial check + TOCTOU re-check
  immediately before push) and only ONCE in the no-drift / mechanism-crash paths.
- Confirm `has_drift`'s two integer arguments are sourced pre- and post-capture respectively (never
  both post-capture) — fixture 11 is the direct proof; also review `main()`'s read ordering by eye.
- Confirm no `--module` CLI flag exists on this script (FR-009).
- Confirm the commit message, PR title, and PR body match plan.md's verbatim text exactly
  (FR-010) — this is falsifiable by inspection, so check character-for-character.
- Confirm `CHARTER_SHARD_RECAPTURE_TOKEN`'s value never appears in any print/log/commit-message/PR-body
  string — only its name does (NFR-003).
- **C-005 self-check**: run `grep -rn "/home/" scripts/ci/recapture_charter_shard_timings.py
  tests/ci/test_recapture_charter_shard_timings.py` and confirm no match, before marking this WP
  done — no absolute local paths or credentials may land in these committed artifacts.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-27T22:00:54Z – system – Prompt created.
