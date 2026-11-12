# Decision Moment `01M78JFMRQS6GE04BENPXGQX8J`

- **Mission:** `settled-placement-surface-01M78GR4`
- **Origin flow:** `plan`
- **Slot key:** `plan.guards.protected-check-input-amended`
- **Input key:** `protected_check_input_amended`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:06:50.519737+00:00`
- **Resolved:** `2026-11-12T19:06:53.381895+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Amend: what do the implement and move-task protected-branch checks judge, given the post-tasks review evidence (new refusals for flat-Mission resumes and the lanes coordination-branch test; move-task skip flag gates more than --note)?

## Options

- (A) write_target(WPT).ref everywhere
- (B) branch of the checkout the commit runs in
- (C) A for implement, B for move-task

## Final answer

(B), operator ruling 2026-11-12 relayed via the dispatching session; SUPERSEDES decision 01M78GS4H8AAJW5Y4ATZ3TES6B. implement: the protected preflight judges the HEAD of _claim_commit_checkout(...), the same checkout the #5738 check judges. move-task: the WP file's holder via placement_seam.write_dir(WORK_PACKAGE_TASK).surface_root, fed to both _skip_target_branch_commit and _mt_refuse_protected_status_commit. Non-settled Missions byte-identical; a settled Mission passes and its WP frontmatter is committed (regression test for the former silent skip); protected targets never written. #2453 not drained: its single allow-list entry is re-pointed to the one shared holder-HEAD helper (count unchanged); #2453 stays open. #7595 blast radius acknowledged: get_feature_target_branch callers read the declared target; tested on a settled fixture with target != main.

## Rationale

_(none)_

## Change log

- `2026-11-12T19:06:50.519737+00:00` - opened
- `2026-11-12T19:06:53.381895+00:00` - resolved (final_answer="(B), operator ruling 2026-11-12 relayed via the dispatching session; SUPERSEDES decision 01M78GS4H8AAJW5Y4ATZ3TES6B. implement: the protected preflight judges the HEAD of _claim_commit_checkout(...), the same checkout the #5738 check judges. move-task: the WP file's holder via placement_seam.write_dir(WORK_PACKAGE_TASK).surface_root, fed to both _skip_target_branch_commit and _mt_refuse_protected_status_commit. Non-settled Missions byte-identical; a settled Mission passes and its WP frontmatter is committed (regression test for the former silent skip); protected targets never written. #2453 not drained: its single allow-list entry is re-pointed to the one shared holder-HEAD helper (count unchanged); #2453 stays open. #7595 blast radius acknowledged: get_feature_target_branch callers read the declared target; tested on a settled fixture with target != main.")
