# Discovery findings — remove-decisions-mission-dir-01M6695J

Recorded 2026-10-30 by the maintainer agent (pi/claude on llama-ramen),
grounding issue spec-kitty/spec-kitty#6766 on `main@512567eee7`.

## Decisions (with rationale and evidence)

1. **The issue reproduces on current `main`.** The read-side helper
   `_mission_dir` is defined at `src/specify_cli/decisions/service.py:335`.
   `grep -n "_mission_dir\b" src/specify_cli/decisions/` shows zero call
   sites of the service.py helper inside `src/`: within
   `src/specify_cli/decisions/service.py` every remaining mention is the
   definition itself, its docstring, or historical comments/docstrings
   (`_resolve_mission_id` comment, `_write_mission_dir` and `_ledger_dir`
   docstrings, `open_decision` / terminal-write comments).
   `src/specify_cli/decisions/emit.py` has its own separate, LIVE
   `_mission_dir` (an entry in the COORD writer census of
   `tests/architectural/test_no_write_side_rederivation.py`); it is out of
   scope and must not be touched.

2. **The precondition holds; nothing superseded the issue.** PR #6762
   ("[#4848] One opening per decision; duplicated decision logs read again")
   merged 2026-10-29T07:04:43Z. `git log --oneline -S "_mission_dir" --
   src/specify_cli/decisions/service.py` names `9ca8cc448c` ("refactor
   (decisions): check the opened row on the pre-resolved write-side log") as
   the commit that moved the opened-row check onto the write-side
   `events_path`, leaving `_mission_dir` caller-less. The changelog has no
   entry removing the helper; no open PR claims this work (issue was
   unassigned and unlabelled beyond triage/domain before this mission's
   claim; claim comment, assignment to Ivan-Melck, and labels
   `status:claimed` + `taken-by-human` are verified on the tracker).

3. **The only users of the helper are the two tests named by the issue**:
   `tests/specify_cli/test_read_seam_leniency.py::
   test_decisions_mission_dir_fails_loud_when_coord_deleted` and
   `::test_decisions_mission_dir_preserves_healthy_status_home` (lines
   144-160). They pin the deleted helper's own behaviour (fail-loud
   `CoordinationBranchDeleted` from `read_dir(STATUS_STATE)`, healthy
   primary resolution), not any surviving call path. The fail-loud
   coordination contract for decisions events is still exercised through
   the write-side pre-resolution: `_write_events_path` ->
   `_write_mission_dir` -> `placement_seam(...).write_dir(STATUS_STATE)`
   is covered by `tests/specify_cli/decisions/test_service_coord_single_home.py`,
   `tests/specify_cli/decisions/test_service_open_repair.py` and the
   `tests/decisions/` suites. **Decision: delete the two tests**, and
   correct the module docstring of `test_read_seam_leniency.py`, whose
   "migrate-fail-loud" ledger names "``decisions/service.py`` (1)" — that
   site is the helper being deleted.

4. **Red-first pin (FR-004).** The standing invariant this mission
   establishes: after #4848/#6762, every STATUS_STATE access in
   `decisions/service.py` is a write-side pre-resolution; the module holds
   no `placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)`
   call. On `main`, line 358 inside `_mission_dir` is exactly such a call,
   so a guard asserting its absence is red on the planning base and green
   after the removal. It guards real behaviour (prevents reintroducing a
   second, divergent read path for the decisions event log), per
   DIRECTIVE_041.

5. **Gate impact survey.**
   - `tests/architectural/test_no_dead_symbols.py` scans public names only
     (`__all__` + non-underscore module-level defs); `_mission_dir` is
     private, so it is not in scope — nothing to drain there, gate must
     simply stay green.
   - `tests/architectural/test_no_read_side_bypass.py` allow-lists sites
     by `resolve_feature_dir_for_mission` call shape;
     `decisions/service.py` is not in its allow-list (the comment at its
     line ~659 concerns `decisions/emit.py:71`, a different file). Deleting
     a properly-routed read does not trip it.
   - `tests/architectural/test_no_write_side_rederivation.py` census names
     `("src/specify_cli/decisions/service.py", "_write_mission_dir")`
     (stays) and `_PRE_SPLIT_QUALNAMES` maps that pair to `("_mission_dir",)`
     for the red-at-base proof only (consulted only when
     `SPEC_KITTY_GATE_SCAN_ROOT` points at the base tree; the dict entry is
     asserted to exist by `test_census_names_the_real_base_offenders`, not
     resolved against live source). Both survive the deletion unchanged.

## Evidence

- Direct code inspection of `src/specify_cli/decisions/service.py`
  (lines 280-420, 855-875, 1065-1085) on `main@512567eee7`.
- `gh pr view 6762` → MERGED 2026-10-29T07:04:43Z.
- `gh issue view 6766` → OPEN, unassigned at claim time; claim now verified
  (assignee Ivan-Melck, labels `status:claimed` + `taken-by-human`).
- Test-file inspection: `tests/specify_cli/test_read_seam_leniency.py`
  (module docstring + the two `_mission_dir` pins).

## Open questions

- None blocking. The two leniency tests are deleted rather than re-pointed
  (Decision 3); if the plan-phase squad disagrees, the re-point target would
  be a write-side pre-resolution scenario already covered elsewhere, which
  is why deletion is the honest option.
