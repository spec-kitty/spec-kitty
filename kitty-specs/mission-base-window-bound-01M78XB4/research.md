# Research — mission-base-window-bound-01M78XB4

Detailed findings: [research/code-grounding.md](research/code-grounding.md), [research/foldable-issues.md](research/foldable-issues.md).

## Decisions

- **Decision**: the Mission base is `meta.json` `mission_base_sha` when recorded and an ancestor of the Mission branch; otherwise the first parent of the earliest first-parent commit on the Mission branch adding `kitty-specs/<slug>/`; otherwise unavailable (today's bound).
  **Rationale**: operator rulings; the scaffold commit is the first Mission-authored commit by construction.
  **Alternatives considered**: `merge-base(target, mission)` (never excludes anything `^target` does not), lane creation base (above pre-implement Mission commits: unsound), record-only (leaves reporters blocked).
- **Decision**: pre-Mission history = `rev-list <window_base>..<mission_base>`, exempted with the #6771 machinery (`_final_authored_walk`).
  **Rationale**: one walk, empty in the non-fork case (NFR-001 by construction).
  **Alternatives considered**: tree comparison against the base blob (would hide a landing that reverts post-base target changes in the non-fork case).
- **Decision**: declared-ref window unchanged (`target..ref`).
  **Rationale**: challenger repro: `^base` empties report 2's declared window.

## Adversarial challenge dispositions

| Finding | Disposition |
|---|---|
| Lane-base derivation unsound | Accepted; ruling corrected (DM 01M78XBWYTWJ6TZJVF4GWQMCQF) |
| `^base` on the declared window empties it | Accepted; window unchanged |
| Lane spines are bounded by `coord_base_ref`, not `window_base` | Accepted; lane spine walk left as is (lanes descend from the base) |
| Fixing only the guard leaves report 2 failing the closed world | Accepted; all-axes ruling |
| `_mission_work_reaches` passes trivially for a below-base ref | Accepted; harmless — a below-base ref exempts only pre-Mission history, already exempt |

No dependency is added, upgraded or removed (supply-chain section not applicable).
