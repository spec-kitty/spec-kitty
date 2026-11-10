# Decision Moment `01M7286WQY7NYXCPNDH0S72M7N`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.wp-files.locator`
- **Input key:** `wp_locator`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:51.422418+00:00`
- **Resolved:** `2026-11-10T08:11:52.738563+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7443: how should the work package task-file locators match a WP id?

## Options

- One shared locator in core: case-insensitive id, separator tail, README excluded, non-regular-file matches fail closed; dependency, roster and WP view all use it
- Make the dependency locator case-insensitive only
- Other

## Final answer

One shared locator in the core layer used by the dependency guard, the subtask roster and the WP view: WP id matched case-insensitively with the existing separator tail, README excluded case-insensitively (the spec-kitty-events R26 rule). A match that is not a regular file (directory, dangling link) makes the gate readers fail closed (roster: SubtaskRosterResolutionError; dependency read: unresolvable TransitionError) and the read-only view/mirror treat it as no file. Other locators (dependency_graph, task_utils/support, workspace/context) are a follow-up.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:51.422418+00:00` - opened
- `2026-11-10T08:11:52.738563+00:00` - resolved (final_answer="One shared locator in the core layer used by the dependency guard, the subtask roster and the WP view: WP id matched case-insensitively with the existing separator tail, README excluded case-insensitively (the spec-kitty-events R26 rule). A match that is not a regular file (directory, dangling link) makes the gate readers fail closed (roster: SubtaskRosterResolutionError; dependency read: unresolvable TransitionError) and the read-only view/mirror treat it as no file. Other locators (dependency_graph, task_utils/support, workspace/context) are a follow-up.")
