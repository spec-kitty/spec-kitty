# Tracer: tooling-friction

Mission git-paths-are-data-01M3SSXR. Append-only during implementation.

- 2026-09-30 specify: `pip install -e .` into system python fails (debian PyJWT); used `uv sync --frozen --all-extras` + .venv.

## 2026-09-30 — implement

- `spec-kitty implement WPxx` stamps `base_branch`/`base_commit` into the WP file and `vcs`/`vcs_locked_at` into `meta.json` on the planning checkout, then refuses the NEXT `implement` with "Planning artifacts not committed" (auto-commit disabled). Each lane start needs a manual `spec-kitty safe-commit … --to-branch <planning branch>` first.
- `implement` prints a bulk-edit inference warning for any mission whose spec says "migrate"/"rename"; `--acknowledge-not-bulk-edit` is needed on every call.
- The pytest `tests/` conftest takes ~30 s to set up even for a 70-test fast file; three focused test files took 3 minutes wall-clock.
