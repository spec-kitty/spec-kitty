# Decision Moment `01M78SWKHY78WQJCEW89WKBHJ9`

- **Mission:** `settled-placement-surface-01M78GR4`
- **Origin flow:** `plan`
- **Slot key:** `plan.wp04.target-helper-reader`
- **Input key:** `target_helper_reader`
- **Status:** `resolved`
- **Created:** `2026-11-12T21:16:15.294441+00:00`
- **Resolved:** `2026-11-12T21:16:17.939335+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which reader do the #7595 target helpers (get_feature_target_branch, resolve_target_branch) collapse onto, given PlacementSeam.read_dir -> resolve_lifecycle_phase -> get_feature_target_branch recurses for every consolidated Mission?

## Options

- (a) read_dir_for(root, slug, kind=PRIMARY_METADATA)
- (b) split #7595 out
- (c) break the cycle in resolve_lifecycle_phase

## Final answer

(a), operator ruling 2026-11-12 relayed via the dispatching session; AMENDS the #7595 fold reader choice (decisions 01M78GRTFPCKDXTY7T3V20EJKY, 01M78GRZDX410TZ1V8H1ZVC1EM). Fold #7595 through mission_runtime.resolution.read_dir_for(root, slug, kind=PRIMARY_METADATA), not PlacementSeam.read_dir (which recurses via resolve_lifecycle_phase -> get_feature_target_branch for every consolidated Mission). Unchanged: remove the bypass-sanction rows for the two helpers; leave resolve_merge_target_branch's row untouched; test the blast radius on a settled fixture with target != main. Add a regression test pinning 0 re-entries on a consolidated Mission; fix the stale 'read_dir never reaches this' comments; record the cycle hazard in the tracer and PR residuals.

## Rationale

_(none)_

## Change log

- `2026-11-12T21:16:15.294441+00:00` - opened
- `2026-11-12T21:16:17.939335+00:00` - resolved (final_answer="(a), operator ruling 2026-11-12 relayed via the dispatching session; AMENDS the #7595 fold reader choice (decisions 01M78GRTFPCKDXTY7T3V20EJKY, 01M78GRZDX410TZ1V8H1ZVC1EM). Fold #7595 through mission_runtime.resolution.read_dir_for(root, slug, kind=PRIMARY_METADATA), not PlacementSeam.read_dir (which recurses via resolve_lifecycle_phase -> get_feature_target_branch for every consolidated Mission). Unchanged: remove the bypass-sanction rows for the two helpers; leave resolve_merge_target_branch's row untouched; test the blast radius on a settled fixture with target != main. Add a regression test pinning 0 re-entries on a consolidated Mission; fix the stale 'read_dir never reaches this' comments; record the cycle hazard in the tracer and PR residuals.")
