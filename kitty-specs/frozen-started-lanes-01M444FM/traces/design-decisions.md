# Design decisions — frozen-started-lanes-01M444FM

- 2026-10-04 — D1: preserve by construction, refuse only when unsatisfiable (decision 01M444ZKK397G09XJ1GM3WC29Z).
  A refuse-only post-hoc diff would refuse #5573's own reproduction instead of keeping WP02 on lane-b.
- 2026-10-04 — D2: "started" is history-based (ever entered a lane other than planned/blocked/canceled), with
  lane-work-tip fallback evidence. Rationale: the FSM allows resets to planned; committed work survives a reset.
- 2026-10-04 — D7: the #3432 residual is deferred to #5701 (decision 01M444ZPVGXPXZY365PGJ7K68P). A canonical
  cancellation projection would blind consolidation's canceled-content axes and activate
  STALE_CANCELED_DEPENDENCIES.
- 2026-10-04 — The refusal happens in a read-only preflight before finalize's first status write. Finalize's
  existing write-scope restore then guarantees byte-identical mission files on refusal (SC-003).
- 2026-10-04 — Plan: `started_wp_ids` lives in `lanes/frozen_membership.py` (consuming the status facade), not in `status/`. Adding it there would edit `status/__init__.py`, and CLAUDE.md ties any `__init__.py` change to a version bump.
- 2026-10-04 — WP03: an existing step already refuses a corrupt status line before the preflight (`read_wp_frontmatter`, "Invalid JSON on line N"), so FR-007 still holds by failing closed earlier. `status_unreadable` only surfaces end to end for coordination or unresolvable surfaces. The earlier message stays unchanged (C-003); the ADR and docs must say so.
