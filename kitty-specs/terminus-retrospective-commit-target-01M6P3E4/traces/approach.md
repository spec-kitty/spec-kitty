# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · pi-claude · Two call sites thread the target: the coordination teardown persist leg (where the commit normally happens, before the coord worktree is destroyed) and the post-merge terminus call in _run_real_merge. mission close gains an optional --target because the resolved target is not durable after clear_state() removes state.json and the --target override is never written back to meta.json/lanes.json.
