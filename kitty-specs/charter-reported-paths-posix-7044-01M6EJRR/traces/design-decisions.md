# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · The seam kernel.charter_pack_paths.repo_relative_posix() is introduced by #6277 (PR #7045, still open). This mission adds the identical function text at the identical location instead of a CLI-local copy, so an identical-addition hunk merges cleanly whichever PR lands first and one definition survives.

2026-11-02 · python-pedro · _display_path() keeps str(path) for paths outside the repo: an absolute path outside the repository is not a repository-relative path, so the POSIX rule does not reach it and a Windows operator copying it wants the native spelling.
