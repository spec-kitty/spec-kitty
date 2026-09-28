---
work_package_id: WP01
title: Demote the per-PR charter length assertion
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- C-001
- C-002
- C-005
- NFR-001
planning_base_branch: issue-5189-per-pr-shard-timings-recapture-friction
merge_target_branch: issue-5189-per-pr-shard-timings-recapture-friction
branch_strategy: Planning artifacts for this mission were generated on issue-5189-per-pr-shard-timings-recapture-friction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5189-per-pr-shard-timings-recapture-friction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-per-pr-shard-timings-recapture-friction-01M3H7V8
base_commit: f8dcce82a74f1b6e7a0acf52af022419910081ca
created_at: '2026-09-28T01:32:21.554034+00:00'
subtasks:
- T001
- T002
- T003
- T003b
- T004
- T004b
- T005
- T006
- T007
- T008
phase: Phase 1 - Core demotion (User Stories 1 & 3)
history:
- at: '2026-09-27T22:00:54Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: tests/architectural/test_module_length_agreement.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_module_length_agreement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Demote the per-PR charter length assertion

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any
user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `implementer`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` and `authoritative_surface: tests/architectural/test_module_length_agreement.py`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete.
- **Report progress**: As you address each feedback item, update the Activity Log.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``. Use language identifiers in code
blocks: ` ```python `, ` ```bash `.

---

## Objectives & Success Criteria

**Amended 2026-09-28 (operator ruling, `reviews/amendment.ruling.md`).** After this design's
original `ready` verdict, `main` was found to already carry PR #5240 ("ci(tests): make
shard-timings count drift non-blocking per PR (#5189 interim)", merged 2026-09-27), which demotes
**both** `test_charter_is_not_allowlisted_and_agrees` **and** the cross-module
`test_non_allowlisted_modules_agree_with_live_collection`
(`tests/architectural/test_module_length_agreement.py`) from a hard, blocking `assert` to a visible
`ShardTimingsDriftWarning` (`warnings.warn`), hard-failing again under
`SPEC_KITTY_STRICT_SHARD_TIMINGS=1` via `pytest.fail`. **This is already-merged code on the branch
you are working from — do not reimplement it, and do not build the `_charter_disposition`/
`pytest.xfail` mechanism this WP file originally specified; that design is dead.** Your job is to
(1) verify the merged mechanism actually satisfies FR-001/FR-002/FR-004 for `charter` and record
that verification, and (2) add the red-first tests #5240 itself leaves unmet — it ships 3 new fast
unit tests, but they only exercise the `_report_drift`/`_strict_mode` **helper functions in
isolation**, never the two production gate functions themselves, so a revert of either function's
body back to a bare hard `assert` would not be caught today. This WP owns **FR-001, FR-002, FR-003,
FR-004** (User Stories 1 and 3), plus **C-001** (charter-only *recapture* scope — the demotion
itself, per the ruling, is broader; see spec.md's corrected FR-003) and **C-002** (no
allowlist-mutation feature).

**Success criteria** (this WP is done when all hold):
- SC-001: a synthetic charter length disagreement no longer fails the architectural-battery run —
  it emits a `ShardTimingsDriftWarning` (proven by T003), and hard-fails again under
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` (proven by T005). The complementary AGREEING case — no
  warning emitted, normal return — is proven for `test_charter_is_not_allowlisted_and_agrees` by
  T003b (satisfying User Story 3 Acceptance Scenario 2's charter-specific agreeing case) and, per
  FR-004's general third mandatory fixture, for the cross-module
  `test_non_allowlisted_modules_agree_with_live_collection` by T004b.
- SC-002: `charter` is still absent from `_MISMATCH_ALLOWLIST` (unconditional `assert`, unchanged;
  verified by T002).
- SC-006: the three allowlist-ratchet tests in this file (`test_allowlist_does_not_exceed_baseline`,
  `test_allowlisted_modules_still_genuinely_mismatch`, `test_allowlist_entries_are_real_registry_modules`)
  and the 19-entry `_MISMATCH_ALLOWLIST` are byte-identical before/after (diff review, T008).
  **`test_non_allowlisted_modules_agree_with_live_collection` is NOT in this untouched set** — #5240
  already demoted it too, and T004 exercises it directly.

**This WP does NOT**: touch `_MISMATCH_ALLOWLIST`'s contents, touch `_BASELINE_ALLOWLIST_COUNT`,
touch `capture_shard_timings.py` (it is deliberately unmodified — plan.md item (e)), touch any
module's real registry entry other than `charter`'s (T004's cross-module test uses only synthetic,
in-memory fixture data — it never touches a real non-charter module), or reimplement any part of
#5240's already-merged mechanism.

## Context & Constraints

- **Read in full before editing**: `tests/architectural/test_module_length_agreement.py` as it
  exists on your current HEAD (485 lines, already includes #5240's merged demotion). You are
  **not** editing the two production gate functions' bodies at all — they are already correct,
  merged code. You are adding ~6-8 new test functions plus one verification subtask, and optionally
  a distinct, behaviour-preserving `mypy` fix (T007). The file's existing session-scoped-fixture /
  pure-`_find_mismatches`-helper / self-mutation-test idiom (see the file's own bottom section,
  `test_mismatch_detection_fires_on_synthetic_length_disagreement`, and #5240's own
  `test_report_drift_warns_by_default` / `test_report_drift_fails_in_strict_mode` /
  `test_strict_mode_reads_env_var`) is the shape your additions should match. **No campsite-clean
  commit is needed** for the pre-existing debt — plan.md item (e) read this file in full and found
  no debt in scope beyond the optional, explicitly-admissible T007 item.
- **Supporting docs**: `.kittify/charter/charter.md` (Standing Order #5 — architectural gate
  discipline: relocate, don't drop), `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/spec.md`
  (FR-001..FR-004, User Stories 1 & 3, Charter Tension section — as corrected by this amendment),
  `.../plan.md` (§"Concrete Design Decisions (d)", amended, for the exact fixture list below),
  `.../reviews/spec.ruling.md`, `.../reviews/plan.ruling.md`, and
  `.../reviews/amendment.ruling.md` (the binding amendment ruling this WP implements — do not
  relitigate any of these).
- **Why this matters (Charter Tension, Standing Order #5)**: this demotion is an operator ruling
  (CL-001/CL-002/CL-003 in spec.md, absorbed via #5240 per the amendment ruling), not a green-wash,
  because (1) the exact-count invariant is relocated to a scheduled recapture (WP02) **and** now
  additionally to a scheduled strict-mode CI job (WP03, item (a2)), never dropped; (2) `charter`
  never enters `_MISMATCH_ALLOWLIST`; (3) the three allowlist-ratchet tests are untouched; (4) drift
  stays visible via `ShardTimingsDriftWarning`, never a silent pass, on **both** live-collection
  gates.

## Branch Strategy

- **Strategy**: `SINGLE_BRANCH` — this mission has no lane topology beyond the one planning/target
  branch.
- **Planning base branch**: `issue-5189-per-pr-shard-timings-recapture-friction`
- **Merge target branch**: `issue-5189-per-pr-shard-timings-recapture-friction`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT
> change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Capture the RED-FIRST baseline (before ANY edit)

- **Purpose**: Per plan.md item (f) / `NO_FULL_HEAVY_SUITES_IN_MISSION`, this WP is the first (and
  only) WP to touch `tests/architectural/test_module_length_agreement.py`. The baseline MUST be
  captured on current HEAD, before your own edit, so a pre-existing red is never misattributed to
  this mission's change. **Note (2026-09-28 amendment)**: current HEAD already includes PR #5240's
  merged demotion mechanism — this baseline captures *that* state (all tests green or warning, none
  hard-failing on ordinary drift), before T002-T008 add this WP's own verification and red-first
  tests on top of it. That is expected and correct: this baseline was never meant to capture a
  pre-#5240 state.
- **Steps**:
  1. Confirm you are on current HEAD with no uncommitted changes to this file yet.
  2. Run **exactly** this command (scoped to the one targeted file — never a bare
     `tests/architectural/` directory run, never `make test-full`):
     ```
     .venv/bin/python -m pytest tests/architectural/test_module_length_agreement.py -q
     ```
     (Use `.venv/bin/python -m pytest`, NOT `uv run --frozen pytest` — this checkout's own hard
     rule is never a bare `uv run`, since it re-syncs the environment and can destroy a hand-built
     `.venv`.)
  3. Record the full pass/fail counts and any failure output in this WP's Activity Log.
- **Files**: none changed by this subtask — read-only baseline capture.
- **Parallel?**: Must run before T002-T008 (sequential prerequisite within this WP); safe to run in
  parallel with WP02's subtasks (different files).
- **Notes — MANDATORY escalation path, not a WP decision**: if this baseline surfaces ANY
  pre-existing red (a failure unrelated to a charter change you have not made yet), **do NOT fix
  it and do NOT file a GitHub issue.** Per plan.md item (f), filing an issue for a pre-existing
  failure per the charter's Pre-existing Failure Reporting Rule is an **ORCHESTRATOR action**, not
  something a WP task may do. Record the exact failure in this WP's Activity Log and report it to
  the orchestrator; do not proceed with T002-T008 until the orchestrator has acknowledged (unless
  the orchestrator has pre-authorized proceeding despite the red — record that authorization if
  given).

### Subtask T002 – Verify #5240 satisfies FR-001/FR-002/FR-004 for `charter` (read-and-confirm, not a fixture)

- **Purpose**: Per operator ruling point 2 ("Where #5240 already satisfies a requirement, WP01
  verifies it and records that, rather than re-implementing it"), this subtask is a documented
  verification pass over the already-merged code, not new code.
- **Steps**:
  1. Read `tests/architectural/test_module_length_agreement.py` in full on your current HEAD.
  2. Confirm `class ShardTimingsDriftWarning(UserWarning)`, `_STRICT_ENV_VAR =
     "SPEC_KITTY_STRICT_SHARD_TIMINGS"`, `_strict_mode()`, and `_report_drift(message, *, strict)`
     exist and behave as documented: `_report_drift` calls `pytest.fail(message)` when `strict` is
     `True`, otherwise `warnings.warn(ShardTimingsDriftWarning(message), stacklevel=2)`.
  3. Confirm `test_charter_is_not_allowlisted_and_agrees`'s body still opens with the unconditional
     `assert "charter" not in _MISMATCH_ALLOWLIST, ...` line (FR-002 — this must never become
     conditional or be removed), and that its mismatch branch calls
     `_report_drift(..., strict=_strict_mode())`.
  4. Confirm `test_non_allowlisted_modules_agree_with_live_collection`'s mismatch branch also calls
     `_report_drift(..., strict=_strict_mode())` — this is the second live-collection gate the
     amendment ruling brings into the demotion's scope (spec.md FR-003, corrected).
  5. Record the confirmation (which lines/functions you checked, and that they match this
     description) in this WP's Activity Log. This is a read-only verification — you make **no**
     code edit in this subtask.
- **Files**: none changed — read-only verification.
- **Parallel?**: Depends on T001 (baseline first); T003-T006 depend on this verification having
  actually happened (do not write tests against a mechanism you have not confirmed exists as
  described).
- **Notes**: If ANY of the checks above does not hold against your actual checkout (e.g. the merged
  code differs from this description), **stop and report to the orchestrator** rather than
  proceeding — this WP's remaining subtasks assume the description above is accurate.

### Subtask T003 – Add a red-first test that `test_charter_is_not_allowlisted_and_agrees` warns on disagreement

- **Purpose**: #5240's own 3 new unit tests exercise `_report_drift`/`_strict_mode` in isolation
  only — none of them calls `test_charter_is_not_allowlisted_and_agrees` itself. A revert of that
  function's mismatch branch back to a bare hard `assert` would leave every one of #5240's tests
  green. This test closes that gap.
- **Steps**: Add, in the file's existing idiom (`@pytest.mark.fast`, no subprocess), a test that
  calls `test_charter_is_not_allowlisted_and_agrees` directly with constructed disagreeing
  `_live_timings_state`/`_collected_counts`-shaped arguments and asserts it emits
  `ShardTimingsDriftWarning` via `pytest.warns(...)`, and never raises:
  ```python
  @pytest.mark.fast
  def test_charter_disagreement_emits_shard_timings_drift_warning() -> None:
      """spec-kitty#5189 amendment: catches a revert of test_charter_is_not_allowlisted_and_agrees's
      mismatch branch back to a bare hard assert -- #5240's own 3 unit tests exercise only the
      _report_drift/_strict_mode helpers in isolation, never this production function."""
      fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
      fake_collected = {"charter": 11}
      with pytest.warns(ShardTimingsDriftWarning, match="charter drifted"):
          test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)
  ```
  Ensure `SPEC_KITTY_STRICT_SHARD_TIMINGS` is NOT set in the test environment for this test (or
  explicitly `monkeypatch.delenv(...)` it) — this test proves the default (non-strict) behavior.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Depends on T002. Independent of T004/T005/T006.
- **Notes**: This test should FAIL (with `AssertionError`/`Failed`, never `pytest.warns` catching
  anything) if you mentally revert the production function's mismatch branch to a bare
  `assert committed == collected` — write it and confirm that property before moving on.

### Subtask T003b – Add the complementary AGREEING-case fixture for `test_charter_is_not_allowlisted_and_agrees` (fresh-sweep finding AMENDMENT-FRESH-002)

- **Purpose**: FR-004 requires three mandatory fixtures ("no-op passable: no") — disagreeing,
  agreeing, and infra-break — and User Story 3 Acceptance Scenario 2 is its own falsifiable
  criterion about the agreeing case specifically ("Given charter's lengths agree, ... it reports a
  clean pass with no warning noise"). The pre-amendment design had a dedicated fixture for exactly
  this (`test_charter_disposition_is_none_on_agreement`); it was dropped when that design was
  replaced by the verify-and-red-first-test plan (T002-T006). T008's incidental observation of
  today's live agree/disagree state is not a substitute: it can silently never exercise the
  agreeing branch at all, and never fails specifically because that branch went unexercised. This
  subtask restores a deterministic, constructed proof.
- **Steps**: Add, in the same idiom as T003, a test that calls
  `test_charter_is_not_allowlisted_and_agrees` directly with constructed AGREEING
  `_live_timings_state`/`_collected_counts`-shaped arguments (`committed == collected`) and asserts,
  deterministically via the built-in `recwarn` fixture, that **zero** `ShardTimingsDriftWarning`
  instances were recorded, and that the function itself returns normally (no exception):
  ```python
  @pytest.mark.fast
  def test_charter_agreement_emits_no_shard_timings_drift_warning(recwarn: pytest.WarningsRecorder) -> None:
      """spec-kitty#5189 amendment fix round 2 (AMENDMENT-FRESH-002): FR-004's mandatory
      agreeing-case fixture and User Story 3 Acceptance Scenario 2 -- dropped when the
      pre-amendment _charter_disposition design was replaced. Proves the AGREEING case emits no
      ShardTimingsDriftWarning and the production gate function returns normally."""
      fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
      fake_collected = {"charter": 10}
      result = test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)
      assert result is None
      drift_warnings = [w for w in recwarn.list if issubclass(w.category, ShardTimingsDriftWarning)]
      assert drift_warnings == [], f"expected no ShardTimingsDriftWarning on agreement, got: {drift_warnings}"
  ```
  Adjust the fake-argument shapes to whatever T002 confirmed the production function's actual
  parameter names/types are, matching T003's own adjustment note.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Depends on T002. Independent of T004/T004b/T005/T006.
- **Notes**: Unlike T003, this test is not required to fail against a mentally-reverted bare
  `assert committed == collected` (a bare equality assert also passes silently on agreement) — its
  falsifiable property is instead that it fails if `_report_drift`/`warnings.warn` is ever called
  unconditionally (i.e. even when lengths agree), which `recwarn`'s explicit zero-count assertion
  catches deterministically.

### Subtask T004 – Add the equivalent red-first test for `test_non_allowlisted_modules_agree_with_live_collection`

- **Purpose**: The amendment ruling (point 3) establishes that the demotion covers BOTH
  live-collection gates, not charter alone. This test extends T003's purpose to the second,
  cross-module gate.
- **Steps**: Add a test using constructed fake `_live_registry_state`/`_live_timings_state`/
  `_collected_counts` values with **one synthetic non-allowlisted module** mismatching (never a real
  module from `.github/ci-module-registry.yml` — this stays a pure, synthetic fixture, so this WP
  never touches any real non-charter module's data):
  ```python
  @pytest.mark.fast
  def test_non_allowlisted_disagreement_emits_shard_timings_drift_warning() -> None:
      """spec-kitty#5189 amendment: the second live-collection gate #5240 also demoted. Uses a
      synthetic module name -- never a real SK-247 module -- so this stays in scope (C-001)."""
      fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
      fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
      fake_collected = {"synthetic_test_module": 6}
      with pytest.warns(ShardTimingsDriftWarning, match="synthetic_test_module"):
          test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)
  ```
  Adjust the fake-argument shapes to whatever the production function's actual parameter names/types
  are on your checkout (cross-check against T002's read) — the observable requirement is fixed: one
  synthetic, non-allowlisted module mismatching, run through the actual production function body,
  emits `ShardTimingsDriftWarning`.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Depends on T002. Independent of T003/T003b/T005/T006.
- **Notes**: This test's synthetic module name must not collide with any real registry module name
  or any `_MISMATCH_ALLOWLIST` key — using an obviously-synthetic name like
  `synthetic_test_module` avoids that by construction.

### Subtask T004b – Add the complementary AGREEING-case fixture for `test_non_allowlisted_modules_agree_with_live_collection` (fresh-sweep finding AMENDMENT-FRESH-002)

- **Purpose**: The amendment ruling (point 3) establishes the demotion covers BOTH live-collection
  gates. FR-004's mandatory agreeing-case fixture therefore applies to the cross-module gate too,
  not only to `charter` (T003b) — T004's own disagreeing-case fixture has no agreeing-case
  counterpart in the pre-round-2 subtask set.
- **Steps**: Add a test using the same synthetic, non-allowlisted module shape as T004, but with
  `committed == collected` (agreeing), and assert via `recwarn` that zero
  `ShardTimingsDriftWarning` instances were recorded and the function returns normally:
  ```python
  @pytest.mark.fast
  def test_non_allowlisted_agreement_emits_no_shard_timings_drift_warning(recwarn: pytest.WarningsRecorder) -> None:
      """spec-kitty#5189 amendment fix round 2 (AMENDMENT-FRESH-002): the cross-module gate's own
      agreeing-case proof, mirroring T003b for the charter gate. Uses a synthetic module name --
      never a real SK-247 module -- so this stays in scope (C-001)."""
      fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
      fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
      fake_collected = {"synthetic_test_module": 5}
      result = test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)
      assert result is None
      drift_warnings = [w for w in recwarn.list if issubclass(w.category, ShardTimingsDriftWarning)]
      assert drift_warnings == [], f"expected no ShardTimingsDriftWarning on agreement, got: {drift_warnings}"
  ```
  Adjust the fake-argument shapes to match T002's confirmed production function signature, same as
  T004's own adjustment note.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Depends on T002. Independent of T003/T003b/T005/T006.
- **Notes**: Same non-collision requirement as T004 for the synthetic module name. Like T003b, this
  test is not expected to fail against a mentally-reverted bare equality assert — its falsifiable
  property is that `_report_drift` is never invoked on an agreeing fixture, which `recwarn`'s
  explicit zero-count assertion catches deterministically.

### Subtask T005 – Add strict-mode tests proving `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` restores the hard failure at the integration level

- **Purpose**: #5240's own `test_report_drift_fails_in_strict_mode` already proves the
  `_report_drift` helper fails under strict mode — but only for the helper called directly, not for
  either production gate function. This closes that integration-level gap for both gates the
  amendment ruling brings into scope.
- **Steps**: Add, using `monkeypatch.setenv("SPEC_KITTY_STRICT_SHARD_TIMINGS", "1")`, two tests (or
  one parametrized test covering both functions) asserting that, given the same disagreeing
  fixtures T003/T004 constructed, calling `test_charter_is_not_allowlisted_and_agrees` and
  `test_non_allowlisted_modules_agree_with_live_collection` directly now raises pytest's fail
  outcome (`pytest.fail.Exception`) instead of warning:
  ```python
  @pytest.mark.fast
  def test_charter_disagreement_fails_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
      """spec-kitty#5189 amendment: strict mode restores the hard failure at the integration
      level (T003's disagreeing fixture), not just at the already-tested _report_drift helper."""
      monkeypatch.setenv("SPEC_KITTY_STRICT_SHARD_TIMINGS", "1")
      fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
      fake_collected = {"charter": 11}
      with pytest.raises(pytest.fail.Exception, match="charter drifted"):
          test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)


  @pytest.mark.fast
  def test_non_allowlisted_disagreement_fails_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
      """spec-kitty#5189 amendment: same proof for the cross-module gate."""
      monkeypatch.setenv("SPEC_KITTY_STRICT_SHARD_TIMINGS", "1")
      fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
      fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
      fake_collected = {"synthetic_test_module": 6}
      with pytest.raises(pytest.fail.Exception, match="synthetic_test_module"):
          test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)
  ```
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Depends on T002/T003/T004 (reuses their fixture shapes). Independent of
  T003b/T004b/T006.

### Subtask T006 – Add a test proving a genuine infra break still fails loudly (missing artefact)

- **Purpose**: FR-004's "infra break, not silence" requirement is still unmet after #5240:
  `_load_timings()`/`_load_registry()` already call `pytest.fail(...)` on a missing file (old,
  unchanged behavior), but nothing pins that today.
- **Steps**: Add a test that monkeypatches `_TIMINGS_PATH` (and, separately or in a second test,
  `_REGISTRY_PATH`) to a nonexistent file and asserts `_load_timings()`/`_load_registry()` raises
  the exception class `pytest.fail(...)` raises:
  ```python
  @pytest.mark.fast
  def test_load_timings_fails_loudly_when_artefact_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
      """FR-004: a genuine infra break (missing artefact) still fails, never silently warns."""
      import tests.architectural.test_module_length_agreement as this_module

      monkeypatch.setattr(this_module, "_TIMINGS_PATH", tmp_path / "does-not-exist.json")
      with pytest.raises(pytest.fail.Exception):  # _load_timings() calls pytest.fail(...), raising pytest.fail.Exception
          this_module._load_timings()


  @pytest.mark.fast
  def test_load_registry_fails_loudly_when_artefact_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
      """FR-004: the same infra-break guarantee for the module registry artefact."""
      import tests.architectural.test_module_length_agreement as this_module

      monkeypatch.setattr(this_module, "_REGISTRY_PATH", tmp_path / "does-not-exist.yml")
      with pytest.raises(pytest.fail.Exception):  # _load_registry() calls pytest.fail(...), raising pytest.fail.Exception
          this_module._load_registry()
  ```
  Adjust the self-import idiom to match how this test file already references its own module-level
  names in other tests (or monkeypatch the bare module-level name directly via
  `monkeypatch.setattr(sys.modules[__name__], "_TIMINGS_PATH", ...)` if that proves more idiomatic
  given this file's existing imports) — the observable requirement is what matters, not the exact
  monkeypatch idiom.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Independent of T003/T003b/T004/T004b/T005.

### Subtask T007 – Optional, non-gating: fix the `mypy` `no-any-return` finding in `_resolve_test_dirs` (operator ruling point 6)

- **Purpose**: Admissible, domain-matched campsite debt in the same file — a distinct,
  behaviour-preserving commit, per operator ruling point 6. **This subtask is OPTIONAL and does NOT
  gate this WP's completion.**
- **Steps**: If you choose to do this: read `_resolve_test_dirs` (calls
  `_capture.resolve_test_dirs(registry, module)` and returns its result typed
  `tuple[str, ...]`), identify the `mypy` `no-any-return` finding (the underlying
  `resolve_test_dirs` call presumably returns an untyped/`Any`-typed value that mypy cannot narrow
  to `tuple[str, ...]` without an explicit cast/assertion), and fix it with a narrow, behavior
  preserving type-narrowing (e.g. an explicit `cast(...)` with a comment explaining why it is safe,
  or a runtime `isinstance` assertion) — never a blanket `# type: ignore`. Make this a **separate
  commit** from T002-T006/T003b/T004b's test additions, clearly labeled (e.g. `chore(tests): fix
  mypy no-any-return in _resolve_test_dirs`).
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Independent of T002-T006; skip entirely if time-constrained.

### Subtask T008 – Post-edit targeted test run + diff review

- **Purpose**: Confirm all new tests pass, confirm FR-002/FR-003/SC-006 hold (the three
  allowlist-ratchet tests and the 19-entry allowlist are byte-identical, and the two production gate
  functions' bodies are UNCHANGED — this WP adds tests, it does not edit the already-merged
  mechanism).
- **Steps**:
  1. Run the same targeted command as T001 again, post-edit:
     ```
     .venv/bin/python -m pytest tests/architectural/test_module_length_agreement.py -q
     ```
  2. Confirm `test_charter_is_not_allowlisted_and_agrees` and
     `test_non_allowlisted_modules_agree_with_live_collection` each report either a clean pass (if
     lengths currently agree) or a captured `ShardTimingsDriftWarning` (never a hard failure, unless
     `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` is set).
  3. Confirm all new tests from T003, T003b, T004, T004b, T005, T006 (and, if you did it, T007's
     fix) pass.
  4. Run `git diff tests/architectural/test_module_length_agreement.py` and confirm: (a) the bodies
     of `test_allowlist_does_not_exceed_baseline`, `test_allowlisted_modules_still_genuinely_mismatch`,
     and `test_allowlist_entries_are_real_registry_modules` are unchanged; (b) every entry in
     `_MISMATCH_ALLOWLIST` and the value of `_BASELINE_ALLOWLIST_COUNT` are unchanged; (c) the
     bodies of `test_charter_is_not_allowlisted_and_agrees` and
     `test_non_allowlisted_modules_agree_with_live_collection` (the #5240 mechanism this WP verifies
     but does not edit) are unchanged — your diff should show only additions (new tests, and
     optionally T007's isolated fix), never a modification to either gate function's mismatch
     branch.
  5. Record the final pass/fail counts in the Activity Log, alongside the T001 baseline counts for
     comparison.
- **Files**: `tests/architectural/test_module_length_agreement.py` (read-only verification pass).
- **Parallel?**: Must run last, after T002-T007 (including T003b/T004b).

## Test Strategy

- **Baseline (T001)**: `.venv/bin/python -m pytest tests/architectural/test_module_length_agreement.py -q`
  on current HEAD, before any edit.
- **Post-edit (T008)**: the same command, after all edits.
- **Never** run a bare `tests/architectural/` directory sweep or `make test-full` — this file alone
  is the complete, correctly-scoped blast radius for this WP (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- This file includes the `slow`-marked live-collection tests — running this one named file,
  however slow its own tests are individually, is not the "full/heavy suite" the rule forbids.

## Risks & Mitigations

- **Risk**: constructing fake fixture values (T003, T003b, T004, T004b, T005, T006) in a way that
  doesn't match this file's actual production-function parameter names/shapes (they may differ
  slightly from this WP's illustrative code samples). **Mitigation**: T002's verification pass is
  the explicit safeguard — read the actual function signatures before writing these fixtures;
  adjust argument names/shapes to match, keeping the observable requirement (warns on disagreement,
  emits no warning on agreement, fails under strict mode) fixed.
- **Risk**: accidentally editing one of the three untouched allowlist-ratchet tests', or either
  already-merged gate function's, body while nearby. **Mitigation**: T008's diff review is the
  explicit safeguard — run it before considering this WP done; the diff should show only additions.
- **Risk**: misreading #5240's merged mechanism (e.g. assuming it still uses `pytest.xfail`, or that
  only charter is demoted). **Mitigation**: T002 is a mandatory, recorded verification pass before
  any test is written — do not skip it or assume this WP file's own prose is more current than the
  actual checkout.
- **Risk**: pre-existing red at baseline (T001) gets silently "fixed" instead of escalated.
  **Mitigation**: T001's Notes section states the escalation path explicitly; do not skip it.

## Review Guidance

- Confirm T001's baseline output is recorded in the Activity Log BEFORE the diff shows any edit to
  this file.
- Confirm T002's verification pass is recorded in the Activity Log, with the specific
  functions/lines checked named explicitly.
- Confirm **no edit** exists to either `test_charter_is_not_allowlisted_and_agrees`'s or
  `test_non_allowlisted_modules_agree_with_live_collection`'s body — this WP verifies and tests
  #5240's already-merged mechanism, it does not modify it. The
  `"charter" not in _MISMATCH_ALLOWLIST"` assert stays exactly as merged.
- Confirm `_MISMATCH_ALLOWLIST` (all 19 entries), `_BASELINE_ALLOWLIST_COUNT`, and the three
  allowlist-ratchet test bodies (`test_allowlist_does_not_exceed_baseline`,
  `test_allowlisted_modules_still_genuinely_mismatch`, `test_allowlist_entries_are_real_registry_modules`)
  are byte-identical (`git diff` review, SC-006).
- Confirm all new tests from T003, T004, T005, T006 are present, correctly marked
  `@pytest.mark.fast`, and actually fail (or error) against a mentally-reverted, pre-#5240
  hard-`assert` version of the relevant production function — reviewer should confirm each test is
  not vacuous by this mental (or actual) reversion check.
- Confirm T003b and T004b are present, correctly marked `@pytest.mark.fast`, each construct an
  AGREEING fixture (`committed == collected`) for one of the two production gate functions, and
  each asserts via `recwarn` that **zero** `ShardTimingsDriftWarning` instances were recorded and
  that the function returns normally — this is FR-004's third mandatory fixture (the agreeing
  case) for both gates (User Story 3 Acceptance Scenario 2 states the equivalent charter-specific
  case, satisfied by T003b), restored in fix round 2 after a fresh-sweep review found it missing
  from the amended subtask set. Unlike T003/T004, these two are not expected to fail
  against a reverted bare-`assert` version (a bare equality assert also passes silently on
  agreement) — their vacuousness check is instead: do they fail if `_report_drift` is called
  unconditionally, even on agreement? Confirm the reviewer mentally (or actually) verifies that
  property instead.
- If T007 was done, confirm it is a separate, clearly-labeled commit that changes no observable
  behavior (only a type annotation / narrow cast / assertion).
- No compiler/typecheck step applies here beyond `ruff` (and, if T007 was done, a local `mypy` check
  on the touched function only — this mission does not add a repo-wide mypy gate).
- **C-005 self-check**: run `grep -rn "/home/" tests/architectural/test_module_length_agreement.py`
  and confirm no match, before marking this WP done — no absolute local paths or credentials may
  land in this committed artifact.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-27T22:00:54Z – system – Prompt created.
- 2026-09-28T00:00:00Z – system – Amended per operator ruling (`reviews/amendment.ruling.md`):
  absorbed PR #5240's already-merged `ShardTimingsDriftWarning`/`_report_drift`/`_strict_mode`
  demotion mechanism (covering both `test_charter_is_not_allowlisted_and_agrees` and
  `test_non_allowlisted_modules_agree_with_live_collection`); replaced the dead
  `_charter_disposition`/`pytest.xfail` subtask set (T002-T008) with a verify-then-red-first-test
  subtask set (T002-T008, same IDs, new content); added an optional, non-gating `mypy` fix subtask
  (T007). Frontmatter (`dependencies`, `owned_files`, `authoritative_surface`, `create_intent`,
  `subtasks` IDs, `requirement_refs`) is unchanged.
- 2026-09-28T01:00:00Z – system – Fix round 2 (fresh-sweep finding AMENDMENT-FRESH-002): T003-T006
  covered only the disagreeing, strict-mode, and infra-break dispositions — FR-004's third mandatory
  fixture (the agreeing case) and User Story 3 Acceptance Scenario 2 had no test, dropped when the
  pre-amendment `_charter_disposition` design (which had
  `test_charter_disposition_is_none_on_agreement`) was replaced. Added T003b and T004b, one per
  production gate function, each constructing an agreeing (`committed == collected`) fixture and
  asserting via `recwarn` that zero `ShardTimingsDriftWarning` instances are recorded and the
  function returns normally. WP01's `subtasks` frontmatter list grew from 8 to 10 IDs (T001, T002,
  T003, T003b, T004, T004b, T005, T006, T007, T008) — a frontmatter change; `dependencies`,
  `owned_files`, `create_intent` are unchanged, but the orchestrator should explicitly decide
  whether this warrants a `finalize-tasks` re-run rather than inferring it silently.
