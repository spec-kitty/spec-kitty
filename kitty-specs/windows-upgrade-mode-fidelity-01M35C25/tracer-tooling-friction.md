# Tracer: Tooling Friction — windows-upgrade-mode-fidelity

Append friction encountered with tools/CLI/tests during this mission.

- 2026-09-22 (specify): `upstream` remote is named `skupstream` here, not `upstream` — the workflow's `git fetch upstream` fails; use `skupstream`.
- 2026-09-22 (specify): the defects are Windows-only but Linux CI is the test host. The `kernel.paths.is_windows` mock seam (per `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py`) is the established way to simulate Windows; for #4923 additionally simulate `os.utime`/`os.chmod` rejecting `follow_symlinks` (real Linux accepts the flag). Faithful mocking is the main friction risk — mock too coarsely and the test passes for the wrong reason.

- 2026-09-22 (analyze): record-analysis fails with DIRTY_WORKTREE on pre-existing untracked files (.kittify/evidence/<ULID>/ + 9 kitty-ops/*.jsonl from a prior session). Most kitty-ops/*.jsonl are TRACKED — never `mv kitty-ops/*.jsonl` (mass-deletes tracked files). Move ONLY the specific untracked paths aside, record, restore.
- 2026-09-22 (brownfield): installer.py imports no-follow helpers via the RE-EXPORT SHIM specify_cli/core/no_follow.py, not kernel.no_follow directly — new helpers need adding to the shim's import list AND __all__ (or import direct from kernel). os.supports_follow_symlinks is new to src/ (only in tests/_support/run_basetemp.py today). windows_dir_mode_only_divergence has exactly 2 callers; managed_skills.py:181 already routes through it, so generalizing the helper likely needs ZERO edits there (don't add a 2nd authority — C-002).
