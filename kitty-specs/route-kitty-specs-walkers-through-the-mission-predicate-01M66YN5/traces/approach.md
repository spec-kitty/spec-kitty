# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi/deepseek-v4.1-flash-1017 · Keep each walker's own enumeration posture (safe_is_dir raise per #3194, dot-dir skip, is_dir) and add one predicate call per child with a per-walk TrackedMissionPaths memo; do not swap them onto iter_kitty_specs_children, whose fail-soft posture would change the #3194 raise into a skip.

2026-10-30 · pi/deepseek-v4.1-flash-1017 · Development-assist test verdict: keep both new files as issue-pinned regression guards (tests/regressions/test_issue_6758_doctor_walkers.py, ..._read_surfaces.py). They pin a standing invariant (each read surface asks the one Mission predicate) that no existing suite owns, and they cannot fold into the fast-tier module test files because the fixture drives real git. The shared Mission+residue fixture lives once in tests/_support/mission_residue_fixture.py so all ten tests share one positive control.
