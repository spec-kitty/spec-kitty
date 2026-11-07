# Approach

- **[2026-11-07][plan] Four sequential WPs on one branch.** WP01 test re-pins, WP02 the only production change (`checkout_file_recipe`), WP03 charter tests, WP04 the six nodes of #7183. Each WP records RED then GREEN for its exact node ids because the nodes are nightly-only in CI.
