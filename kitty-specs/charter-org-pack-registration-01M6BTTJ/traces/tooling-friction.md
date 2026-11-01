# Tracer: tooling friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi/deepseek-v4.1-flash-1017 · `spec-kitty consolidate` (squash, the default) refused twice with `SQUASH reconciliation refused: projected coordination bookkeeping content did not land on the target` — once on a clean run, once on `--resume` after committing the coordination branch's dirty review-cycle render. `--strategy merge` then conflicted on `status.json` and the review-cycle files, because the target branch carries the mission's planning artifacts while the coordination branch carries the execution bookkeeping. Disposition: landed manually (cherry-pick from the lanes, tree verified equal), recorded in the PR's Deferred section as a candidate tooling gap. Nothing was torn down and no branch history was lost.

2026-11-01 · pi/deepseek-v4.1-flash-1017 · `scripts/docs/build_cli_reference` takes ~9.5 minutes for a full build (270 command paths × a `uv run spec-kitty --help` subprocess each), which is why the reference update here is a targeted splice of the two new sections from a temp build rather than an in-place rebuild. A `--only <path>` filter would make the generated-reference workflow affordable for every PR that adds a command.
