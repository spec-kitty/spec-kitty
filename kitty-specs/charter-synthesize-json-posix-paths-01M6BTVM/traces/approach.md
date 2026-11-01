# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Fixed the spelling at production, not at each JSON field: one helper (kernel.charter_pack_paths.repo_relative_posix) feeds all five emit sites, and it delegates the separator swap to kernel.paths.to_posix rather than re-implementing as_posix/replace, so the repo keeps one normalisation seam.
