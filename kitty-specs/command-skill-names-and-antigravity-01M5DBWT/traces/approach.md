# Approach

- **[2026-10-20][plan] One leaf authority per concern.** Naming (`skills/command_skill_names.py`) and frontmatter projection (`skills/skill_frontmatter.py`) are dependency-free leaves every producer imports, mirroring `_agent_roster.py` (#1941).
- **[2026-10-20][plan] Red-first through init.** Both P0 repros drive `spec-kitty init` via CliRunner and assert the on-disk command surface, marked `p0_repro(issue=6475|6470)`; the fix removes the marker.
- **[2026-10-20][plan] Sequential single_branch WPs.** Topology single_branch on the issue branch; WPs implemented sequentially in the repository root checkout, reviewed per WP, branch rebuilt fresh from origin/main at closeout.
