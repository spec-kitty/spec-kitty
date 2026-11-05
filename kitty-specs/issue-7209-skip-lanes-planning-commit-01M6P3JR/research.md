# Discovery: `consolidate --skip-lanes` and the #6715 evidence window (issue #7209)

## Evidence gathered

- **Reproduced on this tree.** `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`
  fails at claim time on `origin/main@b4d1e918e2` with
  `EVIDENCE_WINDOW_UNCOMPUTABLE: WP01 has no evidence window (lane-planning: lanes.json records
  no planning commit)`. Exit code 1, target ref untouched.
- **Cause confirmed in code.** `src/specify_cli/consolidation/entry_preflight.py:_synthesize_no_lane_manifest`
  builds the `--skip-lanes` `LanesManifest` without `planning_commit_sha`;
  `src/specify_cli/consolidation/wp_evidence.py:lane_evidence_window` returns `None` when that
  field is unset, and `_scan_lane` turns that into `EVIDENCE_WINDOW_UNCOMPUTABLE` for every
  approved work package. `evaluate_evidence` is reached from
  `reconciliation.build_approved_wp_set` (claim time) and from `accept` / `orchestrator-api`
  through `mission_evidence_report`.
- **No attestation path exists.** `_RECOVERY` in `wp_evidence.py` is the only recovery text, and
  its `EVIDENCE_WINDOW_UNCOMPUTABLE` line names `spec-kitty agent mission finalize-tasks`, which
  records a planning commit in a `lanes.json` the direct-on-target topology does not have.
- **Not superseded.** No open PR touches this seam: PR #7221 (#7175 fixture re-seed) deliberately
  leaves the three nodes red and cites #7209 (`## Deferred`). Sibling issues #7198/#7199 are the
  coordination teardown seam (`phase_teardown.py`, `bookkeeping_projection.py`) — disjoint.
  #7210 (pre-pin `lanes.json` recovery advice) and #7222/#7223/#7224 (accept diagnostics,
  forecast no-op) are disjoint too.
- **The topology is sanctioned.** `--skip-lanes` was added by #2745 for a Mission whose work
  packages were committed directly on the target with no lane branch; `_synthesize_no_lane_manifest`
  documents the fallback and reuses `is_planning_artifact_only` to skip the branch merge.
- **What history offers.** The Mission's planning artifacts live on the target branch
  (`kitty-specs/<slug>/`), and implementation commits follow them. The target branch's own
  history therefore contains a defensible boundary: the target tip immediately before the first
  commit that introduced `kitty-specs/<slug>/`.

## Decisions

1. **Populate the synthesized manifest, do not special-case the axis.** The issue's first option
   ("the synthesized manifest carries a planning commit the evidence window can use") keeps one
   authority for what a window is: `lane_evidence_window`. The axis keeps refusing exactly as it
   does for a recorded manifest.
2. **Base = the first parent of the earliest target-branch commit that touches
   `kitty-specs/<slug>/`.** Using the *parent* (not the introducing commit) keeps the window
   non-empty when a Mission's planning artifacts and a work-package change landed in one commit
   (the shape of the existing #2745 fixture, and of a squashed history). A root introducing
   commit has no parent and is used as its own base.
3. **Resolution never raises and never fabricates.** A git error, or a Mission directory absent
   from target history, yields "no base" — the existing `EVIDENCE_WINDOW_UNCOMPUTABLE` refusal.
   No timestamp, no invented SHA, no fallback window that would pass vacuously.
4. **The refusal text names a remedy that works in this topology.** The
   `EVIDENCE_WINDOW_UNCOMPUTABLE` recovery line keeps the `finalize-tasks` advice for a recorded
   but unpinned `lanes.json` (the #7210 case) and adds the no-`lanes.json` remedy: commit the
   Mission's planning artifacts on the target branch. Both halves are remedies an operator can
   actually perform; neither weakens the refusal.
5. **No new field, no schema change.** `LanesManifest.planning_commit_sha` already means "the
   planning-artifact base of the evidence window"; the synthesized manifest records the value its
   own `computed_from` line documents as synthesized.
6. **The fixture becomes faithful rather than the gate becoming lenient.** The #2745 fixture's
   `WP01-work.md` omits `owned_files`, which a real Mission's task file always declares (and which
   `read_authored_wp_frontmatter` reads as an authored empty list). It gains `owned_files`; no
   assertion is relaxed and no gate is touched.

## Open questions

- None blocking. Whether a future Mission type should record its start boundary in `meta.json`
  instead of deriving it from history is a larger question, out of scope here and not needed for
  the direct-on-target fallback.
