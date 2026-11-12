# Decision Moment `01M78GRZDX410TZ1V8H1ZVC1EM`

- **Mission:** `settled-placement-surface-01M78GR4`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.checkout-authority`
- **Input key:** `checkout_authority`
- **Status:** `resolved`
- **Created:** `2026-11-12T18:36:59.197947+00:00`
- **Resolved:** `2026-11-12T18:37:01.935788+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where is the single authority for which checkout a Mission write lands in after settlement?

## Options

- (A) route commit_router use_coord by topology+kind
- (B) PlacementSeam.write_dir(kind).surface_root as the one checkout authority
- Other

## Final answer

(B) approved by the operator: PlacementSeam.write_dir(kind).surface_root is the one checkout authority; its PRIMARY arm is fixed via kernel.git_topology with no new outbound edge; commit_router._primary_commit_root delegates to it; a root-anchored Mission path is re-expressed through write_dir(kind).path; a root-only copy refuses (never copies) with a remedy naming the holding worktree; protected checks, baseline commit, #7595 target helpers and #7602 renderer read through the seam; settled topology stays read from meta.json via the existing locator. (A) rejected: does not fix #7551 and regresses PUBLISHED/landed Missions.

## Rationale

_(none)_

## Change log

- `2026-11-12T18:36:59.197947+00:00` - opened
- `2026-11-12T18:37:01.935788+00:00` - resolved (final_answer="(B) approved by the operator: PlacementSeam.write_dir(kind).surface_root is the one checkout authority; its PRIMARY arm is fixed via kernel.git_topology with no new outbound edge; commit_router._primary_commit_root delegates to it; a root-anchored Mission path is re-expressed through write_dir(kind).path; a root-only copy refuses (never copies) with a remedy naming the holding worktree; protected checks, baseline commit, #7595 target helpers and #7602 renderer read through the seam; settled topology stays read from meta.json via the existing locator. (A) rejected: does not fix #7551 and regresses PUBLISHED/landed Missions.")
