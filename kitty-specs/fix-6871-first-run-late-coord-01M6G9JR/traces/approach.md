# Approach tracer — #6871 first-run late coordination window

- Grounded on current `main` (d18c4f1d58) before specifying: `_land_late_coordination_commits`
  still returns early for `is_resume=False` (`consolidation/phase_teardown.py`, the `if not
  run.is_resume: return` guard), so the projection and the #6791/#6857 assertion run on resumes
  only.
- The resume path's protection is two-part (project then assert) and the assertion is what #6857
  added. The fix therefore reuses both parts for the first run rather than adding a new guard.
- Window base for a first run: `coord_tip_after_projection`, the merge's own last write to the
  coordination ref, captured in `phase_bookkeeping._phase_record_done_and_project`. Anything at or
  before it was projected by the merge itself; anything after it is late. Using the resume base
  (`pre_mutation_coord_sha`) on a first run would re-walk the whole merge and re-project stale
  primary artifacts.
- The projection teardown gate + CAS branch delete already protect the window *after* the gate.
  The uncovered window is between the merge's verification capture and teardown, plus every run
  whose gate cannot be built.
