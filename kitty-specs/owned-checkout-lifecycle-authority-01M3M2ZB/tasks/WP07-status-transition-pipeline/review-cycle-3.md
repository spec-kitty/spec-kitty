---
affected_files: []
cycle_number: 3
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T03:51:10Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 3: CHANGES REQUESTED (one narrow item)

Reviewer: reviewer-renata. Commits reviewed: 5a214d03c..5ede8d06b. Base: 55610f516.

## Verified OK in this cycle

- **mypy:** 0 new errors.
  - Run with `--no-incremental --strict --explicit-package-bases`, PYTHONPATH set to each worktree's own `src`.
  - The 54-file caller set gives 22 errors on the base and 22 on the head, the identical set.
  - Adding `mission_runtime/owned_checkout.py` and `__init__.py` (56 files) gives 22 on both sides.
- **Red-first:** the cycle-3 tests fail at 5a214d03c.
  - The predicate module fails to import (ImportError).
  - The 3 non-canonical-path agreement tests fail: identity, write_seam and bootstrap.
  - The mismatch and agree-by-value tests pass there, as expected: they pin cycle-2 behaviour that previously had no test.
- **One collapse:** `collapse_owned_facts` is the only owned/owned_mission collapse; `owned_fact()` and bootstrap both call it. There is no inline `owned or owned_mission` left in src.
- **Layering:**
  - The predicate is in `mission_runtime.owned_checkout`, with no new outbound import.
  - It is exported from the package root and pinned in the surface test.
  - test_layer_rules, test_ledger_floor, test_mission_runtime_surface and test_no_legacy_terminology all pass.
  - Cold import is unchanged: `mission_runtime` was already loaded by `import specify_cli.status` on the base.
- **Markers:** 18 TRANSITIONAL(WP18), per file exactly as the amended DoD lists. There are 3 `bridging: WP17 converts` markers.
- **LOW items 3 to 7:** all folded.

## Blocking

**1. [MEDIUM] src/specify_cli/agent_tasks_ports.py:88: `MissionHandle.__post_init__` still has its own checkout-agreement rule.**
- The current check is `self.effective_root.resolve() != self.owned.owned_root`, a raw comparison that resolves only one side.
- It does not call the canonical `checkout_root_agrees_with_effective_root`.
- It is not just a matter of style. The canonical predicate's own docstring, its `__all__` comment, the surface-test comment, and the comments in status_transition.py and write_seam.py all say MissionHandle calls it. As written, those statements are false.
- Required fix: `if self.owned is not None and not checkout_root_agrees_with_effective_root(self.effective_root, self.owned.owned_root): raise TypeError(...)`. Keep the existing message, which the T036 test matches.
- Behaviour is equivalent today, because `owned_root` is always minted resolved. A behavioural red test is therefore not possible; pin the delegation instead, as a red-first commit:
  - monkeypatch `specify_cli.agent_tasks_ports.checkout_root_agrees_with_effective_root` to return `False`;
  - assert that constructing a `MissionHandle` with agreeing roots raises `TypeError`.
  - This is red now, because the name is not imported, and green after the fix.
- Then run test_tasks_ports and the T036 tests.

## Non-blocking

2. [LOW] mission_runtime/owned_checkout.py, `checkout_root_agrees_with_effective_root`: it uses plain `Path.resolve()`, but the same module's canonical resolver is `kernel.resolution.resolve_rejecting_loops`, which `_mint` uses. On a symlink loop, plain `resolve()` raises `RuntimeError` or `OSError` instead of the module's fail-closed refusal. Consider using `resolve_rejecting_loops` for the `effective_root` side.
