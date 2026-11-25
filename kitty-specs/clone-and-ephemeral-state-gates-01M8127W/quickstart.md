# Quickstart: verifying the Mission

1. **Hex colours:** put a colour declaration such as `color:` followed by a hash and `000000` in `research.md`. `spec-kitty agent tasks status` shows no issue row for it.
2. **Docs WP gets a lane:**
   - Create a Mission without `--topology`, with WP01 code (`src/a/**`), WP02 code (`src/b/**`) and WP03 docs (`docs/x.md`, `execution_mode: planning_artifact`).
   - `finalize-tasks` settles `lanes_with_coord`, prints a notice for WP03, and `lanes.json` gives WP03 its own lane.
3. **Remote-only lane:** in a second clone (`git clone`), run `spec-kitty agent action review WP01 --mission <m>`. The local lane branch is created, tracking origin.
4. **Pre-sync stamp:**
   - In the second clone, approve WP01 and push only the coordination branch.
   - In the first clone, `git pull`, then `spec-kitty consolidate --dry-run`. No `APPROVAL_STAMP_NOT_ON_LANE`.
