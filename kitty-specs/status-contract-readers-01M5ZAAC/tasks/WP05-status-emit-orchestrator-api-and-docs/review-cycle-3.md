---
affected_files: []
cycle_number: 3
mission_slug: status-contract-readers-01M5ZAAC
reproduction_command:
reviewed_at: '2026-10-27T22:00:21Z'
reviewer_agent: claude-reviewer
wp_id: WP05
---

# WP05 — changes requested (integration finding at consolidation)

`spec-kitty consolidate` refused and rolled back (nothing landed):
"Reconciliation FAILED: file 'src/specify_cli/status/__init__.py' (blob 9fc623edad) IS reachable on the target but belongs to NO approved WP — un-attributable".

## Blocking

1. `src/specify_cli/status/__init__.py` on lane-e duplicates WP03's facade re-exports:
   - two imports of the same names: the `from .actor import (ActorRole, build_status_actor, compose_status_actor, role_for_hop)` block (from WP03) AND `from .actor import ActorRole, role_for_hop` (WP05, after the `.review_roles` block);
   - `"ActorRole"` and `"role_for_hop"` listed twice in `__all__`.
   Fix in an AUTHORED commit on lane-e (not a merge commit): keep exactly one `.actor` import block (WP03's) and one `__all__` entry per name; keep WP05's `actor_from_option` import and `__all__` entry. The resulting file must equal "WP03's facade exports + `actor_from_option`", nothing duplicated.
2. Add a check that would have caught it: a unit assertion that `specify_cli.status.__all__` has no duplicates (e.g. in `tests/status/test_status_actor.py` or a new small test in a file WP05 owns).

## Also fold (from earlier reviews, small)
- `src/specify_cli/status/work_package_lifecycle.py:~72` `actor_from_option` raises a new mypy `no-any-return` (follow_imports=skip); return through a typed local like WP04's helpers so mypy reports no new issue.
