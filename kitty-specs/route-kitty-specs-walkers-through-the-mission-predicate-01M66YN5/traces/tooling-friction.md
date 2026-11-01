# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi/deepseek-v4.1-flash-1017 · spec-kitty specify defaulted to coord topology and could not commit the scaffold because the current branch was main (protected); re-created on the issue branch with --topology single_branch, matching this mission's single-agent sequential shape.

2026-10-30 · pi/deepseek-v4.1-flash-1017 · scripts/docs/build_cli_reference emitted empty help bodies for every command in this checkout (mode=hybrid, atomic help capture returned nothing), so a full regeneration would have deleted ~1200 lines of the CLI reference. The doctor topology section was instead edited to match the live help body verbatim, and check_cli_reference_freshness confirms no new drift (3 pre-existing HELP-DRIFT warnings remain).
