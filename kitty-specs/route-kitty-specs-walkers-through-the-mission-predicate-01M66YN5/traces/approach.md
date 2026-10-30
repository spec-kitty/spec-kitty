# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi/deepseek-v4.1-flash-1017 · Keep each walker's own enumeration posture (safe_is_dir raise per #3194, dot-dir skip, is_dir) and add one predicate call per child with a per-walk TrackedMissionPaths memo; do not swap them onto iter_kitty_specs_children, whose fail-soft posture would change the #3194 raise into a skip.
