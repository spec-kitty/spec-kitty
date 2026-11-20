# Tooling friction

Context: canonical spec-kitty CLI (4.0.0rc9, source install), uv, pytest in a cloud container.

- 2026-11-20 — A single fixture-backed pytest (`make_prefix_coord_mission`) takes ~100 s here (19 s setup, mostly `create_mission_core` + git). Budget targeted runs accordingly.
- 2026-11-20 — `mission create` mints and checks out `kitty/mission-<slug>-<mid8>` even when started from a non-primary topic branch; the branch contract names the topic branch as target.
