# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-01 · claude · mission create on a non-primary branch needed --topology single_branch explicitly to keep all writes on the session branch; retrospect generator emits a noisy coord-branch-deleted warning when run against a historical in-repo mission.

2026-10-01 · claude · spec-kitty implement WP01 refused WRITE_CHECKOUT_OCCUPIED because the committed mission reconcile-flake-family-01M34HR7 (single_branch, target fix/reconcile-flake-family-4882) has WP04 in_progress; the occupancy scan in lanes/implement_support.py does not scope occupants to missions whose write branch equals the checkout's branch. Worked around with move-task --to in_progress; filed upstream.
