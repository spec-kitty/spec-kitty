---
work_package_id: WP04
title: Preflight auto-refresh swallow fold-in
dependencies: []
requirement_refs:
- FR-001
- NFR-002
planning_base_branch: fix/charter-generation-drops-scoped-references-5257
merge_target_branch: fix/charter-generation-drops-scoped-references-5257
branch_strategy: Planning artifacts for this mission were generated on fix/charter-generation-drops-scoped-references-5257. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-generation-drops-scoped-references-5257 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-generation-drops-scoped-references-01M3M1KF
base_commit: 3759ea9e4f334e5fea85f4c74a9e99fb831bb7fc
created_at: '2026-09-28T18:49:15.257525+00:00'
subtasks:
- T019
- T017
- T018
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/charter_runtime/preflight/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/charter_runtime/preflight/references_refresh.py
- src/specify_cli/charter_runtime/preflight/runner.py
- tests/specify_cli/charter_runtime/test_references_parity_refresh.py
role: implementer
tags: []
tracker_refs: []
---

# WP04 — Preflight auto-refresh swallow fold-in

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Fix a pre-existing silent-success bug in `spec-kitty next`'s preflight auto-refresh path: today,
`refresh_references_if_needed` spawns the targeted `charter generate` subprocess, never inspects
its `CompletedProcess` result (return code or stderr), and unconditionally reports success —
masking a genuine references-parity failure behind an unconditional manifest re-stamp. This WP
is **independent** of WP01/WP02/WP03: it touches a disjoint file set with no ordering dependency
either direction, and can be implemented in parallel with them.

This WP produces TWO separate commits, each independently verified, per charter C-011 (binding,
no size-based carve-out — the failing-first test must land as its own commit, strictly before any
implementation commit): commit 1 = T019's red-first test extension, committed ALONE, verified RED
against `af847be71d97c8a126e91c31a7d05629c69c93ba`; commit 2 = T017 (`RefreshOutcome` widening) +
T018 (`_attempt_auto_refresh`'s fail-closed branch), committed together strictly after commit 1,
turning T019's test GREEN.

## Context

Read spec.md's Edge Case "Mid-flight missions" and plan.md's "Auto-refresh fail-closed swallow —
decision: FOLD IN (bounded)" section in full before writing any code — both sections state the
verified, load-bearing facts about the current code (read `references_refresh.py` lines
145-189 and `runner.py` lines 553-773 yourself too, to confirm against live `HEAD` — line numbers
may have drifted since planning).

**The confirmed defect** (verified against actual code at plan time, restated here as fact, not
a hypothesis):
- `references_refresh.refresh_references_if_needed` spawns `subprocess.run(cmd, cwd=repo_root,
  capture_output=True, text=True, timeout=..., check=False)` and does NOT bind the
  `CompletedProcess` result to any variable — the return value is discarded entirely.
- It catches only `(OSError, subprocess.TimeoutExpired)` at debug-log level.
- It unconditionally `return`s `True` regardless of whether the subprocess exited 0 or non-zero.
- Its caller, `runner.py::_attempt_auto_refresh`, receives that `True` as `references_refreshed`
  and — with no outcome information available — unconditionally re-runs `spec-kitty charter
  synthesize` (the manifest re-stamp), which re-stamps `synthesized_drg`'s stored content-hash
  against whatever is CURRENTLY in `charter.yaml` — so the recompute afterward sees
  `synthesized_drg="fresh"` even though `generate` FAILED to actually reconcile anything.
- This is reachable for ANY reason `generate` exits non-zero at this call site (a crash, a lock
  conflict, a schema error, disk-full, etc.) — not only for the #5257 scoped-reference defect
  class specifically (which, once WP02 lands, should rarely need a fail-closed exit for THIS
  defect class — but the swallow bug is broader than that one cause).

**Why this is "bounded" enough to fold in rather than defer** (operator doctrine — do not
re-litigate this decision, it was already made): one call site
(`_attempt_auto_refresh`'s post-`refresh_references_if_needed` branch), one function's
return-type widening confined to a module and its single caller, testable red-first in
isolation, **no contract change** to `CharterPreflightResult`/`contracts/charter-preflight-json.md`
beyond reusing a field that already exists (`blocked_reason: str | None`) in exactly the pattern
the function already uses elsewhere in the same branch sequence.

**Cross-WP coupling note (acknowledged, not a defect):** this same test module's pre-existing
test `test_references_parity_drift_recompiles_the_catalog` already drives the real `generate` CLI
path in-process through `compiler.py` — the file WP02 exclusively rewrites. It intentionally
compares `healed_references`/`baseline_references` by activated-id SET only, not full record
equality, specifically because a pre-existing, WP04-unrelated quirk in `compile_charter`'s
language-scoped doctrine lookup can vary placeholder `title`/`summary` text across repeat
`generate` calls — WP02's `SCOPE_FILTERED` placeholder-text change (`"Definition unavailable in
bundled doctrine. Reason: scope_filtered — ..."`) lands inside exactly that already-tolerated
variance. This pre-existing test does not need updating when WP02 lands; the tolerance is
deliberate and already verified in its own docstring/comment, not accidental.

## Subtask T019: Red-first regression test (commit 1 — authored and committed FIRST, alone)

**Purpose**: Pin the bug (RED) in isolation from WP01-WP03's red-first tests — this is a distinct
defect class and must not be conflated with them (a reviewer must be able to verify each fix
independently caused its own test to flip). Per charter C-011, this commit lands STRICTLY BEFORE
T017/T018's implementation commit.

**Steps**:
1. Extend `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` — the REAL,
   already-existing test module for `preflight.references_refresh`, which already ships
   `_git_init`, `_make_generate_subprocess_fake`, and `_seed_baseline_repo` fixture machinery.
   Do NOT create a new `tests/specify_cli/charter_runtime/preflight/` subdirectory — it does not
   exist in the current test tree and is not the right home.
2. Adapt `_make_generate_subprocess_fake` (or add a sibling fake) so the faked `generate`
   subprocess invocation inside the auto-refresh path returns a non-zero returncode/stderr
   instead of success.
3. Assert (a) BEFORE the fix (i.e. write this assertion first and confirm it fails against the
   pre-fix code — RED verification): the swallow means the failure never reaches an actionable
   `blocked_reason` — `passed` can report `True` despite the underlying `generate` failure,
   demonstrating the bug is real; (b) AFTER T017/T018 land: `passed=False` and `blocked_reason`
   names the failure detail (GREEN — asserted once you resume work after commit 2).
4. Commit this test change ALONE, in its own commit — per charter C-011 (binding, no
   size-based carve-out): the failing-first test lands as its own commit, strictly before any
   implementation commit. This mirrors WP01/WP02's two-commit red-first pattern. (An earlier draft
   of this WP instructed bundling this test with T017/T018's implementation into one commit,
   citing plan.md's "PR Shape" section — that citation was a conflation: plan.md's "PR Shape"
   answers the PR/lane-split question, i.e. that WP04 counts as one self-contained WP within the
   mission's single PR, not a licence to combine a red-first test with its own implementation
   commit. Corrected.)

**Files**: `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` (extended).

**Validation**: Run the extended test against the pre-fix code (before T017/T018 are applied) and
confirm it FAILS (RED) — record the exact RED pytest output. Commit this file ALONE (`git add
tests/specify_cli/charter_runtime/test_references_parity_refresh.py && git commit`), with a
message naming the RED verification, before starting T017.

## Subtask T017: Widen `refresh_references_if_needed`'s return contract (commit 2, with T018)

**Purpose**: Make the function actually inspect the subprocess outcome instead of discarding
it.

**Steps**:
1. In `src/specify_cli/charter_runtime/preflight/references_refresh.py`, define a new small
   frozen outcome type: `RefreshOutcome(attempted: bool, succeeded: bool, detail: str | None)`
   — a `NamedTuple` or `@dataclass(frozen=True)` (implementer's choice).
2. Bind the `subprocess.run(...)` call's result to a name (it is currently discarded — this is
   the core of the fix).
3. Set `succeeded = completed.returncode == 0`.
4. Set `detail` to a short excerpt on failure — e.g. the last non-empty stderr line, or stdout if
   stderr is empty; `None` on success.
5. Change `refresh_references_if_needed`'s return type from `bool` to `RefreshOutcome`.
6. This is an INTERNAL signature change, confined to this one module and its one in-repo caller
   (`runner.py`) — NOT a change to `CharterPreflightResult` or any documented/public contract.
   `references_refresh.py`'s own `__all__` (currently `["refresh_references_if_needed"]`) does
   NOT need the new `RefreshOutcome` type added — it is an implementation detail of this one
   function's signature, consumed only by its one in-module caller and by `runner.py`'s wrapper.
   Only add it to `__all__` if a second, external caller genuinely needs to construct/inspect one
   directly (not the case here).

**Files**: `src/specify_cli/charter_runtime/preflight/references_refresh.py`.

**Validation**: existing callers of `refresh_references_if_needed` (just `runner.py`, per T018)
must be updated in the same commit — do not leave a type mismatch. This subtask's changes land
together with T018 in ONE commit (commit 2), strictly after T019's red-first commit.

## Subtask T018: `runner.py::_attempt_auto_refresh` — fail closed on refresh failure, skip the restamp (commit 2, with T017)

**Purpose**: Stop restamping the manifest over content that was not actually regenerated.

**Steps**:
1. In `runner.py::_attempt_auto_refresh`, update the wrapper around
   `refresh_references_if_needed` (~line 553-582) and the post-refresh branch (~line 733) to
   consume the new `RefreshOutcome` instead of a bare `bool`.
2. When the outcome is `attempted and not succeeded`: return
   `CharterPreflightResult(passed=False, checks=initial_checks, auto_refresh_applied=True,
   auto_refresh_actions=actions, blocked_reason=f"references-parity refresh failed:
   {detail}")` IMMEDIATELY — skip the manifest-restamp step (`spec-kitty charter synthesize`)
   entirely. This reuses the EXACT existing pattern the function already applies at other steps
   in the same sequence (lines ~686-692, ~704-709 already return `blocked_reason=reason` with
   `auto_refresh_applied=True` for a failed step — this fold-in makes the references-parity step
   behave consistently with every OTHER step, rather than being the one step whose failure is
   invisible).
3. When `not attempted` or `attempted and succeeded`: the existing restamp+recompute flow
   (~lines 749-773) is UNCHANGED, byte-for-byte — do not touch this branch's logic.
4. Do NOT alter `_attempt_auto_refresh`'s behavior for any OTHER step in the sequence
   (source-remediation, synthesize, bundle-validate) — the change is scoped exclusively to the
   branch immediately following `refresh_references_if_needed`'s call.

**Files**: `src/specify_cli/charter_runtime/preflight/runner.py` — `_attempt_auto_refresh`
ONLY, no other function in this module changes.

**Validation**: T019's red-first test (committed in commit 1) must now pass GREEN. Commit T017 and
T018's changes together as ONE commit — commit 2 of this WP, strictly after T019's red-first
commit — and confirm T019's test is GREEN on this commit before considering the WP done.

## Definition of Done

- `tests/specify_cli/charter_runtime/test_references_parity_refresh.py`'s T019 extension is
  committed ALONE, in its own commit (commit 1), and was verified RED against
  `af847be71d97c8a126e91c31a7d05629c69c93ba` before that commit (record the exact RED pytest
  output/count in your WP completion note).
- T017+T018's implementation is committed together in ONE commit (commit 2), strictly after
  T019's commit, turning T019's test GREEN on this WP's final commit — two separate commits,
  verified RED then GREEN, matching WP01's and WP03's two-commit red-first pattern. (WP02 has a
  different, four-commit shape with no internal red-first commit of its own, since it turns
  WP01's already-landed red tests green rather than authoring its own — it is not a comparable
  match.)
- `RefreshOutcome(attempted, succeeded, detail)` type exists in `references_refresh.py`, and
  `refresh_references_if_needed` returns it (not `bool`).
- `runner.py::_attempt_auto_refresh` returns `passed=False` with a `blocked_reason` naming the
  failure detail when the refresh subprocess failed, WITHOUT running the manifest restamp in
  that case.
- The existing restamp+recompute flow for the `not attempted` / `attempted and succeeded` cases
  is byte-for-byte unchanged.
- No other function in `runner.py` changed.
- `CharterPreflightResult`/`contracts/charter-preflight-json.md` were NOT modified (no new
  field, no field-shape change).
- Per-subtask completion evidence recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T017-T019.

## Risks

- **Risk**: Accidentally widening this into a general refactor of `_attempt_auto_refresh`'s
  other steps. **Mitigation**: the change is scoped EXCLUSIVELY to the branch immediately
  following `refresh_references_if_needed`'s call — do not touch source-remediation, synthesize,
  or bundle-validate logic.
- **Risk**: Reintroducing this as a new/changed field on `CharterPreflightResult` (a documented,
  public contract) instead of reusing the existing `blocked_reason: str | None`. **Mitigation**:
  this is explicitly forbidden by the fold-in's "bounded" justification — reuse the existing
  field only.
- **Risk**: `RefreshOutcome`'s `detail` extraction logic (last non-empty stderr line vs. stdout
  fallback) producing an empty or unhelpful message. **Mitigation**: T019's test should assert
  `blocked_reason` is non-empty and names something concrete from the faked failure, not just
  that it changed.
- **Risk**: Committing T019's test together with T017/T018's implementation (the pre-fix-round
  instruction), which violates charter C-011's binding separate-commit requirement.
  **Mitigation**: T019's commit MUST land alone, verified RED, strictly before T017/T018's
  commit — see Definition of Done and Reviewer Guidance.

## Gates (run these; do not invent others)

- `.venv/bin/python -m ruff check .` (whole-repo, always-on)
- `.venv/bin/python -m ruff format --check .` (whole-repo, always-on)
- Targeted shard (own module tests):
  `.venv/bin/python -m pytest -q tests/specify_cli/charter_runtime/`
- Baseline (must stay 56 passed, 0 failed — this WP does not touch any file this baseline
  covers; it is independent of WP01/WP02/WP03):
  `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py tests/charter/test_catalog_completeness_4785.py`
- `spec-kitty regen --check` — **NOT APPLICABLE**: no schema-generated file changes.
- `tests/architectural/test_no_dead_symbols.py` — **NOT APPLICABLE**: `src/specify_cli/charter_runtime/preflight/`
  is not under `src/charter/` or `src/kernel/`, so C-007's `__all__` convention does not bind
  this path at all; additionally, `RefreshOutcome` is deliberately NOT added to
  `references_refresh.py`'s `__all__` per T017 step 6.
- `tests/architectural/test_no_legacy_terminology.py` — not required by path (`src/specify_cli/`
  is neither `src/charter/offering/` nor prose-heavy documentation). This WP's new
  `blocked_reason` message text is short and mechanical ("references-parity refresh failed:
  ..."), not the kind of prose this guard's two retired terms would ever appear in. Skip.
- diff-cover ≥90% of changed lines — informational locally; the real gate is
  `ci-aggregate.yml`'s `diff-cover` job. Re-run `make ci-parity` once this WP's `src/` diff
  lands, per plan.md's "Gate set" section.

## Reviewer Guidance

- Confirm the `subprocess.run(...)` result is genuinely bound and inspected now — grep the diff
  for the discarded-expression pattern this bug depended on (a bare `subprocess.run(...)` call
  with no assignment) and confirm it is gone.
- Confirm the manifest restamp (`spec-kitty charter synthesize` re-run) is SKIPPED on the new
  failure branch — this is the actual bug fix; merely adding a `blocked_reason` without also
  skipping the restamp would leave the masking behavior partially in place.
- Confirm no OTHER step in `_attempt_auto_refresh`'s sequence changed behavior.
- Confirm `CharterPreflightResult`/the preflight JSON contract doc were not touched.
- Confirm the red-first test genuinely fails against pre-fix code (ask for the RED verification
  evidence, don't just trust a passing final-state test).
- Confirm the two commits are genuinely separate (`git log --oneline` on this WP's branch shows
  two distinct commits, T019's red-first test first, T017+T018's implementation second) — NOT
  squashed into one.

## Implementation Command

```bash
spec-kitty agent action implement WP04 --agent claude
```
