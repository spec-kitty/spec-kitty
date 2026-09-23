# WP05 — 3.13 `fast or unit` re-measurement evidence (FR-004)

Owned by WP05 (`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tasks/WP05-remeasure-3.13.md`).
Recorded after WP01 (baseline), WP02 (kernel `dir_fd` fix) and WP04 (venv-corruption
fix) all landed on `issue-4866-interpreter-matrix-3-13`. Supersedes the mission's
original, distrusted "429 failing/erroring only on 3.13" figure per FR-004.

## ⚠ Discrepancy vs. this WP's own prompt — followed the dispatch's override, flagging rather than silently choosing

Both WP05's own task file (`tasks/WP05-remeasure-3.13.md`, T001/T002) and
`plan.md`'s "Re-measurement (FR-004, Edge Case (b))" section instruct running
the re-measurement against the checkout's own `.venv`, freshly re-synced to
3.13 (`uv sync --frozen --all-extras --python 3.13`, then
`.venv/bin/python -m pytest ...`). **This run did not do that.** My dispatch
for this WP explicitly overrode that instruction: `.venv` in this checkout is
Python 3.11.15 and is WP01's baseline-measurement environment (WP01's own
evidence file, `evidence-baseline-3.11.md`, records re-syncing `.venv` to
3.11 as part of capturing that baseline); re-syncing it to 3.13 for this WP
would silently destroy the interpreter WP01's baseline was measured under,
for any other agent or reviewer who later runs `.venv/bin/python -V`
expecting 3.11.15. My dispatch instead directed use of `.venv313` (a
dedicated, already-3.13.15, gitignored project environment under this
checkout, not `/tmp`), confirmed via `UV_PROJECT_ENVIRONMENT`-scoped
`uv sync`. This run therefore did **not** consume the exact `.venv/bin/python`
path both planning documents specify — it consumed an interpreter-equivalent
substitute at `.venv313/bin/python`. The command, selector, flags (`-m
"fast or unit" -q -n auto --junitxml=...`) and 900s-class bounded-timeout
discipline are otherwise followed exactly as specified. `.venv/bin/python -V`
is confirmed still `Python 3.11.15` at the end of this WP (see "Environment
integrity" below) — proof the override achieved its purpose.

Separately: WP05's own task file states the 3.11 baseline as "21 failed" in
T003's prose. The actual recorded baseline artifact it cites as its input,
`evidence-baseline-3.11.md`, records **20 failed** (with the reasoning for
why 20, not the plan's originally-expected 21, spelled out in that file).
This evidence file uses the real 20-ID baseline from `evidence-baseline-3.11.md`,
not the WP05 prompt's "21" figure, per T003's own instruction to diff against
"WP01's recorded 3.11 baseline" (the artifact, not the prompt's paraphrase of it).

## T001 — Environment: fresh 3.13 sync

**Environment used**: `.venv313` (project environment via
`UV_PROJECT_ENVIRONMENT=/home/jeroennouws/dev/SK-missions/4866/.venv313`),
**not** the checkout's `.venv` — see discrepancy note above.

```
$ export UV_PROJECT_ENVIRONMENT=/home/jeroennouws/dev/SK-missions/4866/.venv313
$ uv sync --frozen --all-extras --python 3.13
Checked 133 packages in 8ms
```

Fresh-sync confirmed: `uv sync --frozen --all-extras --python 3.13` against
`.venv313` reported all 133 packages already checked/consistent (this venv
was already correctly synced going into this WP; the frozen sync is the
"fresh, not reused-without-verification" confirmation, not evidence of
drift). Interpreter confirmed:

```
$ .venv313/bin/python -V
Python 3.13.15
$ cat .venv313/pyvenv.cfg
home = /usr/bin
implementation = CPython
uv = 0.11.28
version_info = 3.13.15
include-system-site-packages = false
prompt = spec-kitty-cli
```

## T002 — The re-measurement run

**Exact command** (run in the foreground, backgrounded by the harness per
SK-99 and tracked to completion by PID/log-tail polling rather than
abandoned — never a fire-and-forget dispatch):

```
.venv313/bin/python -m pytest -m "fast or unit" -q -n auto \
  --junitxml=out/reports/xunit-remeasure-3.13.xml
```

Launched 2026-09-22T21:31:09+02:00 (PID 3743986), completed
2026-09-22T21:39:08+02:00 (approx, derived from the summary line's own
`475.87s` wall time). `out/reports/xunit-remeasure-3.13.xml` is a build
artifact, not committed.

**`-n auto` vs. serial — decided deliberately, not defaulted into**: this
run used `-n auto` (parallel via pytest-xdist), matching both WP05's own
prompt and `plan.md`'s IC-05 command, and matching the real
`ci-nightly.yml` job's own invocation shape. This is also the
methodologically correct choice independent of "the prompt said so": this
WP is explicitly **Deliverable 2** — the first full-scale exercise of
WP04's venv-corruption fix — and that fix's entire purpose is to keep the
shared `.venv`'s interpreter identity stable specifically under `-n auto`
parallel execution (the condition under which the corruption originally
manifested; a serial run would never stress the hazard WP04 fixed at all).
Running serial here would answer a different, less useful question.
**Comparability caveat, stated plainly, not hidden**: WP01's 3.11 control
was run serial (no `-n auto`), by its own prompt's instruction and for its
own good methodological reasons (isolating the baseline from the
then-unfixed corruption hazard). This WP05 run and that WP01 baseline
therefore differ in parallelism as well as interpreter version — a
node-ID-level failure diff (this document's whole purpose) is comparatively
robust to that difference (a test either failed or it didn't, regardless of
worker scheduling), but raw wall-clock-time comparisons between the two
runs carry no meaning, and any flaky-under-parallelism test could in
principle appear in one run's failure set and not the other's for reasons
unrelated to the interpreter. No such case was observed here (see
classification below — the diff is clean), but the caveat holds regardless.

> **Mission-closing correction — this clause is now contradicted by a
> later finding and is corrected here, not deleted.** The "no such case
> was observed here" statement above was true of what this WP itself
> checked (a node-ID diff, not a repeated-runs stability check) at the
> time it was written. WP06's own follow-up investigation
> (`evidence-residual-disposition.md`) found exactly the
> parallelism-sensitive case this clause said hadn't occurred:
> `tests/specify_cli/cli/commands/test_glossary_validate.py::TestValidateSingleFileValid::test_human_output_shows_valid`
> — one of this run's 23 failures — **passed 3/3 times when re-run
> standalone**, but failed under this WP's full `-n auto` run. WP06
> recorded this as "context-sensitive... only observed under the full
> parallel `fast or unit` run, not reproduced in isolation," without
> asserting a cause. This does not change T003's classification below
> (the ID is still correctly counted as a 3.13-only residual, since the
> real `ci-nightly.yml` job also runs the full `-n auto` selector, not an
> isolated node), but the caveat's claim that no such case existed does
> not hold — a reader relying on this paragraph alone would wrongly
> conclude the diff needs no isolation-sensitivity caveat. It does. The
> original sentence above is left unmodified, per this mission's
> append-only correction convention.

**Machine contention observed**: live `ps aux` snapshots taken during the
run showed this box's 24 pytest-xdist worker processes each consuming
roughly 75–90% CPU concurrently on a 24-core machine, alongside multiple
unrelated concurrent processes: three separate `claude` sessions, two
`codex --yolo` sessions, two Nx daemon processes (unrelated
spec-kitty-design-missions / _cutover checkouts), a Hermes agent process,
Firefox, and — separately from this run — a `spec-kitty init` invocation
under this same checkout's `.venv` and a `spec-kitty agent tasks status`
call under a different mission's checkout (`SK-missions/4865`). This is
real, observed cross-mission contention on a shared box, not a defect in
this command or environment. It plausibly explains some of the gap between
this run's 475.87s and the ~411s "quiet" reference figure my dispatch cited
(closer to, though still faster than, the ~680s "contended" reference
figure) — but it did not affect correctness: no environment failure,
timeout, or collection error occurred.

**Exact summary line**:

```
23 failed, 34666 passed, 146 skipped, 987 warnings in 475.87s (0:07:55)
```

Cross-checked against the recorded `out/reports/xunit-remeasure-3.13.xml`:
`<testsuite ... errors="0" failures="23" skipped="146" tests="34835" .../>`
— `34835 - 23 - 146 = 34666` passed, consistent with the console summary.
0 errors (no `ERROR`-classified collection/setup failures — all 23 reds are
genuine `failures`).

## Deliverable 2 — environment integrity: did the corruption fix hold?

**`.venv313/pyvenv.cfg` recorded immediately before and immediately after
the run**:

```
BEFORE (captured pre-run):
home = /usr/bin
implementation = CPython
uv = 0.11.28
version_info = 3.13.15
include-system-site-packages = false
prompt = spec-kitty-cli

AFTER (captured post-run):
home = /usr/bin
implementation = CPython
uv = 0.11.28
version_info = 3.13.15
include-system-site-packages = false
prompt = spec-kitty-cli
```

**Byte-identical** (`diff` of the two captures: no output). Additionally,
`.venv313/bin/python3.13`'s binary md5sum was checked before and after the
run and was identical (`0015cf6b2cea7c11c8993463ce159cab` both times) — the
interpreter binary itself was never replaced or relinked mid-run.

**Conclusion: the WP04 venv-corruption fix holds under a real, full-scale,
`-n auto` `fast or unit` run.** This is the first full-scale exercise of
that fix (WP04's own investigation used smaller, targeted repros), and it
shows no interpreter-identity drift — end-to-end confirmation the fix is
not merely theoretically correct but actually effective under the real
workload it was written to protect. Nothing further to report here beyond
this positive result; there was no corruption to escalate.

## T003 — Failure-ID classification (the point of this WP)

**Full list of this run's 23 failing node IDs** (from
`out/reports/xunit-remeasure-3.13.xml`, `<failure>`-tagged testcases,
reconstructed to pytest node-ID form and spot-verified against the real
files/line numbers in this checkout):

```
tests/dashboard/test_artifact_containment.py::TestArtifactPathIsContained::test_unresolvable_path_is_not_contained
tests/docs/test_plantuml_no_egress_corpus.py::test_full_corpus_renders_offline_error_free
tests/docs/test_plantuml_render.py::test_round_trip_renders_svg_with_exact_literal_alt
tests/docs/test_plantuml_render.py::test_two_diagrams_get_distinct_alt
tests/docs/test_plantuml_render.py::test_unusual_code_class_still_renders
tests/docs/test_plantuml_sandbox_negative.py::test_benign_diagram_renders_under_sandbox_isolation
tests/integration/test_review_durability_matrix.py::test_arbiter_override_cell_suppresses_fabricated_approval[auto_commit]
tests/integration/test_review_durability_matrix.py::test_arbiter_override_cell_suppresses_fabricated_approval[no_auto_commit]
tests/integration/test_review_durability_matrix.py::test_arbiter_override_is_sensitive_to_its_own_commit_removal
tests/specify_cli/charter_lint/checks/test_orphan.py::TestOrphanCheckerBuiltInGraphExactSet::test_orphaned_directive_findings_exact_set
tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py::test_registered_command_names_match_frozen_subcommands
tests/specify_cli/cli/commands/test_glossary_validate.py::TestValidateSingleFileValid::test_human_output_shows_valid
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestFallbackSignalPresent::test_signal_survives_default_warning_filters
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestFallbackSignalPresent::test_unresolvable_mission_type_prints_loud_cli_warning
tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py::TestNonFallbackWarningsReemitted::test_unrelated_warning_is_reemitted_while_fallback_still_prints
tests/specify_cli/cli/test_decision_command_shape_consistency.py::test_agent_decision_subgroup_has_canonical_visible_subcommands
tests/specify_cli/invocation/cli/test_dispatch.py::test_dispatch_non_git_project_json_envelope_is_parseable
tests/specify_cli/session_presence/test_manager.py::TestBuildContent::test_health_uses_fresh_prerelease_cache
tests/specify_cli/skills/test_installer.py::test_coordinated_skill_installation_exact_delta_and_project_precheck[False]
tests/specify_cli/skills/test_installer.py::test_coordinated_skill_installation_exact_delta_and_project_precheck[True]
tests/specify_cli/skills/test_installer_global_reassess_convergence.py::TestApplySkillInstallationConcurrentPeerConvergence::test_without_rebuild_a_concurrent_peer_still_crashes_the_loser
tests/specify_cli/test_audit_tail_readers.py::test_decision_open_corrupt_events_log_json_envelope_names_the_typed_kind
tests/specify_cli/tool_surface/providers/test_command_skills.py::test_wp04_dispatch_config_observation_boundary[loop]
```

### Group 1 — Failing on BOTH 3.11 and 3.13 (pre-existing, reported in #4916, NOT interpreter divergence): 20 IDs

Every one of WP01's 20 recorded 3.11-baseline failing node IDs
(`evidence-baseline-3.11.md`) reappears verbatim in this 3.13 run's failure
set — a clean 1:1 match, no drift in this group:

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

These are already reported at spec-kitty/spec-kitty#4916 (WP01's fresh
issue). No further action needed here per FR-005 (already discharged).

### Group 2 — Failing ONLY on 3.13 (genuine interpreter divergence — THE NUMBER WP06 FILES AGAINST #3189): **3 IDs**

```
tests/dashboard/test_artifact_containment.py::TestArtifactPathIsContained::test_unresolvable_path_is_not_contained
tests/specify_cli/cli/commands/test_glossary_validate.py::TestValidateSingleFileValid::test_human_output_shows_valid
tests/specify_cli/tool_surface/providers/test_command_skills.py::test_wp04_dispatch_config_observation_boundary[loop]
```

Not diagnosed further or fixed here — out of this WP's scope (measurement
only) and out of WP02/WP03/WP04's scope (C-002: "does not attempt to fix
3.13 divergence beyond the 4 confirmed `dir_fd` failures"). For WP06's
benefit, the raw assertion failures observed (from
`out/reports/xunit-remeasure-3.13.xml`, not further investigated):

- `test_unresolvable_path_is_not_contained`: `_artifact_path_is_contained(...)`
  returned `True` where the test expects `False` for an unresolvable path —
  plausibly a `pathlib`/`os.path.realpath` symlink-resolution behavior
  difference on 3.13, but not confirmed.
- `test_human_output_shows_valid`: expected substring `"2 terms"` not found
  verbatim in CLI output; the actual output contains `"2 \nterms"` (a line
  wrap inserted between "2" and "terms") — plausibly a Rich/terminal-width
  rendering difference on 3.13, but not confirmed.
- `test_wp04_dispatch_config_observation_boundary[loop]`: an
  `OwnerAssessment.complete` boundary assertion (`assert ... is not
  broken`) fails when both sides evaluate `True` — a rich comparison /
  dataclass-equality edge case, not confirmed further.

This is a **count of 3**, not "4-5" — smaller than SK-99's own dispatch
reference range for the (separate, already-fixed) WP02 kernel group.
Reported plainly, not inflated and not minimized.

### Group 3 — Failing ONLY on 3.11 (surprising, would need flagging): **0 IDs**

None. Every one of WP01's 20 baseline 3.11 failures reappears identically
in this 3.13 run (Group 1); nothing dropped out. Nothing to flag here.

### WP02 validation — the 5 `dir_fd` teardown failures are confirmed ABSENT from this 3.13 run

Per WP02's own completion evidence
(`tracer-tooling-friction.md`, "WP02 — FR-002 was not actually 3.13-only"
entry) and this WP's own isolated confirmation run
(`.venv313/bin/python -m pytest tests/kernel/test_lock_parity.py
tests/kernel/test_no_follow.py tests/specify_cli/core/test_no_follow.py -v`
→ `30 passed` in 2.53s, 0 errors, run immediately before the full
measurement above), the 5 previously-ERRORing node IDs are:

```
tests/kernel/test_lock_parity.py::test_naive_second_open_of_a_held_lock_raises_under_simulation
tests/kernel/test_lock_parity.py::test_sync_primitive_never_reopens_the_resource_while_held
tests/kernel/test_lock_parity.py::test_async_primitive_never_reopens_the_resource_while_held
tests/kernel/test_no_follow.py::test_read_rejects_symlink_planted_before_open
tests/specify_cli/core/test_no_follow.py::test_read_rejects_symlink_planted_before_open
```

(Spec.md/plan.md describe this group as "the 4 confirmed `dir_fd`
failures"; WP02's own tracer entry independently recorded the real
observed count as 5 — 3 in `test_lock_parity.py` plus 1 in each
`test_no_follow.py` copy. Both counts are cited in mission docs; this
evidence file checks the fuller, 5-ID set to be conservative.)

**Explicitly confirmed: none of these 5 IDs appear anywhere in this run's
23-item failure set** (grep-checked against the full node-ID list above —
zero matches). This independently validates WP02's fix held on this branch
state under the real `-n auto` full-suite run, not just WP02's own isolated
3-file confirmation.

## Summary for WP06 / PR-prep

- **Baseline (3.11, WP01, serial)**: 20 failed / 34661 passed / 146 skipped
  / 10222 deselected in 5036.54s.
- **Re-measurement (3.13, this WP, `-n auto`)**: 23 failed / 34666 passed /
  146 skipped / 987 warnings in 475.87s. (Different deselection count is a
  `-n auto` vs. `-q` reporting artifact — `-n auto` does not print a
  `deselected` count in the summary line the way the serial `-q` run did;
  not itself evidence of a different test selection — same `-m "fast or
  unit"` marker expression was used both times.)
- **20/20** of WP01's baseline failures reproduce identically on 3.13 —
  pre-existing, already reported (#4916), not this mission's concern.
- **3** node IDs are 3.13-only genuine interpreter divergence — this is the
  number to file against #3189 per Edge Case (c)'s disposition. Full IDs
  enumerated in Group 2 above.
- **0** node IDs are 3.11-only.
- WP02's fix independently re-confirmed clean under this full-scale run
  (5/5 previously-ERRORing IDs absent).
- WP04's venv-corruption fix independently re-confirmed clean under this
  full-scale, `-n auto` run (`.venv313`'s `pyvenv.cfg` and interpreter
  binary md5sum byte-identical before/after).
- `.venv` (the checkout's own baseline environment) was never touched by
  this WP: confirmed `Python 3.11.15` both before this WP started and after
  it finished.

---

*Recorded by WP05 (`python-pedro`/implementer). PR-prep (WP07) and WP06's
residual-disposition step read this file directly rather than re-deriving
anything from raw pytest output.*
