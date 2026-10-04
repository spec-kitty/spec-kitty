# tooling-friction

- 2026-10-04: dogfooding this mission as single_branch hits #5459 itself; implement via top-level `spec-kitty implement`.
- `gh issue view` fails (GraphQL blocked in this cloud env); used `gh api` REST.
- `spec-kitty implement WP01` refused WRITE_CHECKOUT_OCCUPIED: merged mission reconcile-flake-family-01M34HR7 WP04 is still recorded in_progress on main, so the occupancy scan blocks every single_branch claim in this repository. Not ours to move; WPs implemented directly on the branch. Worth an upstream ticket (stale foreign in_progress blocks the checkout).
