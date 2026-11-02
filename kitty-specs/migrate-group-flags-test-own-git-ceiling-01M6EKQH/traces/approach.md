# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · Two guards because one is host-shape dependent: Guard A (invariant: tmp_path in git_ceiling_dirs()) fails on every host without the fixture wiring; Guard B clears the ambient value, asserts the leak is real (unpinned walk returns the enclosing repo), asserts the pin makes it raise WorkspaceRootNotFound, then runs the real non-dry-run control. Half-by-half proof: reverting the fixture wiring reds only Guard A; neutering the _append_ceiling helper reds both.

2026-11-02 · python-pedro · Host contention is visible in the numbers: the same 79-test module run took 6.6 s, 414 s and 109 s on three consecutive runs with no code change in between (20 agents share this VM). Report durations as ranges, not absolutes.
