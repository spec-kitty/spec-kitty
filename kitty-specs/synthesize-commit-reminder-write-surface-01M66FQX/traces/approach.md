# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · Derive the reminder from the write surface: append_synthesized_activations returns warnings + the repo-relative paths it wrote (record when _record() fires, activation target when _promote fires); _print_synthesis_commit_reminder renders base paths plus exactly those, deduped, stable order. Rejected: longer fixed list (names paths that may not exist; drifts), exists-on-disk heuristic (not write-surface truth, names unchanged paths).
