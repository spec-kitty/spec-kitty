---
affected_files: []
cycle_number: 2
mission_slug: readme-rename-and-docs-audit-01M78WZM
reproduction_command:
reviewed_at: '2026-11-13T01:55:27Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP02
---

# WP02 review, cycle 2: changes requested (one narrow item)

Reviewer: `claude-reviewer::reviewer-renata`.

Every cycle-1 item is fixed and verified: each red commit was red on its own commit; the shallow
refusal works (exit 2 on a `--depth 1` clone, nothing written); the snapshot has no graft date;
the derived slash set is right; title and description are scanned; all 89 pairs map to their
section issue. One gap remains, and it was named as a done-when in cycle 1 ("so entries can only
leave").

## Issue 1 (medium): a drained pair can be added back

`_LANDING_PAIRS` (`tests/docs/test_retired_surface_gate.py`) is a fixed set, and `refilled()`
fails only for pairs outside it. Walk through this:

1. A section pass fixes a page and drops its pair. The burn-down is now 88. The ratchet only
   warns, so `_baselines.yaml` stays at 89.
2. A later PR adds the mention back, together with its burn-down entry.

`refilled(BURN_DOWN, _LANDING_PAIRS) == []`, the count is 89 ≤ 89, and the gate is green. I
checked this against the committed state:
`refilled(frozenset(BURN_DOWN), landing) == []` when a pair is removed and then put back.
`test_a_swapped_or_re_added_pair_is_a_refill` tests only a pair from outside the landing set.

Fix: make leaving one-way. For example, assert `gate.BURN_DOWN == _LANDING_PAIRS` exactly, so
a drained pair must leave the test literal in the same PR. Putting it back then means re-adding
it to a test-owned frozen set, a deliberate and visible act. Or assert that the burn-down count
equals the `_baselines.yaml` value, so every drain locks itself in. Add a test with a removed
pair that is re-added.

## Low (fix while you are here, not blocking on their own)

- `scripts/docs/retired_surface_gate.py` module docstring: the new "The body, the `title` and
  the `description` are scanned…" paragraph sits between "The gate fails on:" and its two
  bullets. Move it below the bullets.
- `_published_text` keeps only lines that start with `title:` / `description:`. A folded or
  continued YAML value (`description: >-`) would lose its continuation lines. No living page
  uses one today; say so in the docstring.
- The inventory's `retired_surfaces` field still reads the body only, while the gate reads the
  title and description too. They agree today (89 = 89). Read the same text in both, or note
  the difference.
