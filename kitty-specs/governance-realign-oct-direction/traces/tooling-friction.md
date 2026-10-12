# Tooling Friction

- 2026-10-12 (setup): The repository was not present in the execution container and the
  `add_repo` push grant was declined by the permission layer. The repo was cloned read-only
  through the session git proxy (public), so all authoring, guards and local commits run
  normally; only the final push + draft-PR creation needs the push grant. Recorded as the
  one open delivery blocker for the operator.
- 2026-10-12 (setup): `uv sync --frozen --all-extras` + `uv pip install -e .` succeeded;
  `spec-kitty --version` → `4.0.0rc7` (meets the 4.0.0rc7+ floor).
- 2026-10-12: `spec-kitty charter context --action specify` prints a
  `CharterCatalogMissWarning` for `toolguide:typescript-mutation-tools` (scope_filtered to
  the active java/python language set). Pre-existing, unrelated to this mission; noted only.
