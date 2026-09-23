# WP01 — 3.11 `fast or unit` baseline evidence

Owned by WP01 (`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tasks/WP01-baseline-capture-and-fr005-issue.md`).
Recorded before any implementation change lands in mission `interpreter-matrix-3-13-env-and-divergence-01M34HVD` (#4866).

## T001 — Baseline run

**Branch / commit at measurement time**: `issue-4866-interpreter-matrix-3-13` @
`14d47ca0d6d361655cd689a24d0a856fb6089c28` (tree clean, zero source/test changes
landed by this or any earlier WP at measurement time — this WP is the mission's
root node).

**Environment**:
- Interpreter: Python 3.11.15 (`.venv/bin/python --version`)
- `.venv` build: this checkout's `.venv` was found already built against Python
  3.13 at session start (`.venv/bin/python -> /usr/bin/python3.13`). Re-synced
  to the repo floor with:
  ```
  uv sync --frozen --all-extras --python 3.11
  ```
  Post-sync: `.venv/bin/python -> ~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11`,
  `python --version` → `Python 3.11.15`. `--all-extras` per SK-94
  (`tracer-tooling-friction.md`) — a bare `uv sync` installs neither the
  `test` nor `lint` extra, which would produce phantom collection/failure
  noise unrelated to any real defect.

**Command run** (exactly the command in WP01 subtask T001, step 2 — no `-n auto`):

```
.venv/bin/python -m pytest -m "fast or unit" -q
```

**Methodology note — why this run is serial, not `-n auto`**: this is the
literal command specified in WP01's own prompt (T001, step 2), so it is
followed as written. Independently of that, it is also the methodologically
correct choice for a control baseline: this mission's WP04/IC-04 is
separately investigating a shared-`.venv` mid-run interpreter-identity
corruption hazard that only manifests under `-n auto` parallel execution
(spec.md User Story 3 / plan.md "The venv-corruption spike"). Running this
baseline serially avoids any risk of that *separate*, not-yet-fixed hazard
contaminating the one measurement every later re-measurement in this mission
(WP05/FR-004) is diffed against. Both reasons hold; neither is retroactively
invented — the WP prompt's literal command already avoids `-n auto` for
exactly this class of reason.

**Runtime note**: this run took **5036.54s (1:23:56)** wall-clock — far
longer than the readiness report's ~485s estimate for this same command on
3.11. Root cause, confirmed live via `ps aux` during the run: this is a
shared machine running multiple other missions' pytest processes
concurrently for the entire duration (observed concurrently: a
`tests/architectural/` run under a different shell session, and a pytest run
inside a different mission's worktree at
`SK-missions/4882/.worktrees/reconcile-flake-family-01M34HR7-lane-a`) — CPU
contention, not a defect in this command, this environment's `.venv`, or
this mission's code. The run was executed in the foreground per NFR-001/
SK-99; the harness's own hard ~600s-per-call foreground ceiling repeatedly
auto-backgrounded the long-running process, so it was tracked via a
held background-task handle and confirmed complete (PID exit) rather than
abandoned or silently assumed finished.

**Exact summary line**:

```
20 failed, 34661 passed, 146 skipped, 10222 deselected, 909 warnings in 5036.54s (1:23:56)
```

**Discrepancy vs. the plan's 21/34659 expectation — flagged explicitly, not
silently reconciled**: plan.md's "The baseline" section (citing the
readiness report) expected approximately **21 failed / 34659 passed**. This
run measured **20 failed / 34661 passed** — one fewer failure, two more
passed, 0 errors either way (no `ERROR`-prefixed collection/setup failures
appear in this run's short summary; grepped for `^ERROR` in the raw log:
zero hits). The failure-ID set below does not contain any test that isn't
also plausibly explained by ordinary test flakiness (none of the 20 are
new/unexpected subsystems relative to what a stale/flaky-test class would
produce) — but this WP does not further investigate which specific test
flipped, per its own scope (a pure baseline-capture WP, not a flake
investigation). The 20-failure set recorded here, not the plan's 21-figure,
is the authoritative control for this mission's later re-measurements
(WP05/FR-004), per T001's own instruction to record the real observed
numbers rather than substitute the plan's expected figure.

**Full list of failing test node IDs (20)**:

```
tests/docs/test_plantuml_no_egress_corpus.py::test_full_corpus_renders_offline_error_free
tests/docs/test_plantuml_render.py::test_unusual_code_class_still_renders
tests/docs/test_plantuml_render.py::test_round_trip_renders_svg_with_exact_literal_alt
tests/docs/test_plantuml_render.py::test_two_diagrams_get_distinct_alt
tests/docs/test_plantuml_sandbox_negative.py::test_benign_diagram_renders_under_sandbox_isolation
tests/integration/test_review_durability_matrix.py::test_arbiter_override_cell_suppresses_fabricated_approval[auto_commit]
tests/integration/test_review_durability_matrix.py::test_arbiter_override_cell_suppresses_fabricated_approval[no_auto_commit]
tests/integration/test_review_durability_matrix.py::test_arbiter_override_is_sensitive_to_its_own_commit_removal
tests/specify_cli/charter_lint/checks/test_orphan.py::TestOrphanCheckerBuiltInGraphExactSet::test_orphaned_directive_findings_exact_set
tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py::test_registered_command_names_match_frozen_subcommands
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestFallbackSignalPresent::test_unresolvable_mission_type_prints_loud_cli_warning
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestFallbackSignalPresent::test_signal_survives_default_warning_filters
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestNonFallbackWarningsReemitted::test_unrelated_warning_is_reemitted_while_fallback_still_prints
tests/specify_cli/cli/test_decision_command_shape_consistency.py::test_agent_decision_subgroup_has_canonical_visible_subcommands
tests/specify_cli/invocation/cli/test_dispatch.py::test_dispatch_non_git_project_json_envelope_is_parseable
tests/specify_cli/session_presence/test_manager.py::TestBuildContent::test_health_uses_fresh_prerelease_cache
tests/specify_cli/skills/test_installer.py::test_coordinated_skill_installation_exact_delta_and_project_precheck[False]
tests/specify_cli/skills/test_installer.py::test_coordinated_skill_installation_exact_delta_and_project_precheck[True]
tests/specify_cli/skills/test_installer_global_reassess_convergence.py::TestApplySkillInstallationConcurrentPeerConvergence::test_without_rebuild_a_concurrent_peer_still_crashes_the_loser
tests/specify_cli/test_audit_tail_readers.py::test_decision_open_corrupt_events_log_json_envelope_names_the_typed_kind
```

(0 errors; the summary line above has no `error` term because there were
none — confirmed by grepping the raw pytest output for `^ERROR` lines:
zero matches.)

## T002 — Pre-existing classification

**`#3284` state, verified live** (not assumed from any prompt paraphrase):

```
$ unset GITHUB_TOKEN && gh issue view 3284 --repo spec-kitty/spec-kitty --json state,title
{"state":"CLOSED","title":"main full suite has 23 untracked failures and 2 errors after bootstrap prewarm"}
```

`#3284` is **CLOSED**. Per the charter's Pre-existing Failure Reporting Rule
("before treating those failures as accepted baseline context"), a closed
issue cannot discharge the obligation for currently-observed failures — this
is exactly why T003 opens a fresh issue rather than pointing at `#3284`.

**Merge-base equivalence**: this mission (interpreter-matrix-3-13-env-and-
divergence-01M34HVD, #4866) had made **zero source or test-file changes** at
the moment this measurement was taken — WP01 is the mission's root node,
dispatched and run before WP02/WP03/WP04/WP05/WP06/WP07. The current branch
tip (`14d47ca0d`) is therefore equivalent to the mission's fork point /
`main`'s state for the purpose of the charter's baseline-red gotcha
classification (AGENTS.md, "Test-run baseline-red gotcha") — no second
comparison run against `upstream/main` was performed, per T001's own
instruction, since it would cost another ~80+ minutes for no additional
grounding value: the branch *is* the merge-base right now.

**Named honestly-red P0 cross-check** (informational only — not an action
item; none of these are "fixed" by this mission regardless): the charter
names `#2736`, `#2772`, `#1834` as honestly-red P0s that should not be
"fixed". Checked live:

```
#2736: CLOSED — "One invalid event poisons its whole sync batch; innocent events don't deliver and get a misleading error"
#2772: CLOSED — "charter refresh must not clobber curated charter.md; charter.md is a curated reference, never a charter-resolving input"
#1834: CLOSED — "spec-kitty accept auto-runs negative-invariant verification against the PRE-MERGE primary tree and overwrites recorded results"
```

All three are now **CLOSED** — none of the 20 failures observed here map to
those specific historical P0s (they were already resolved before this
measurement). This is purely informational cross-referencing per T002's
instruction; no action taken.

**Duplicate-issue check** (per T003 step 3, performed before opening a fresh
issue): searched GitHub issues for an already-open report covering these
specific 20/21 pre-existing 3.11 `fast or unit` failures. No matching open
issue found — the closest hits were `#3284` (closed, different failure set:
"23 untracked failures and 2 errors after bootstrap prewarm") and several
other closed issues about earlier, since-resolved pre-existing-failure
batches (`#3188`, `#3140`, `#2034`, all closed). `#4506` (open) is an
unrelated ruff-format-line-length ratchet. Per spec.md FR-005's own
resolution, option (a) — a fresh issue — is confirmed as the correct path.

## T003 — FR-005 GitHub issue

**Issue opened**: spec-kitty/spec-kitty#4916 — see
<https://github.com/spec-kitty/spec-kitty/issues/4916>

Reports the 20 pre-existing 3.11 `fast or unit` failures recorded above:
exact command, exact summary line, full 20-ID failure list, the pre-existing
rationale (T002's reasoning above), and cross-links `#4866` (noting #4866
itself covers the *environment*-pinning defect, not these 20 failures).
Verified live post-creation: `state=OPEN`.

---

*Recorded by WP01 (`python-pedro`/implementer). PR-prep (WP07 or a later
step, not this WP) links issue #4916 from the mission's PR body.*
