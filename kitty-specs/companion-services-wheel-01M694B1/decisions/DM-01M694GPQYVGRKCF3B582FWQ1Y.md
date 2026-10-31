# Decision Moment `01M694GPQYVGRKCF3B582FWQ1Y`

- **Mission:** `companion-services-wheel-01M694B1`
- **Origin flow:** `plan`
- **Slot key:** `plan.packaging.extra-lock-resolution`
- **Input key:** `extra_lock_resolution`
- **Status:** `resolved`
- **Created:** `2026-10-31T14:06:17.854920+00:00`
- **Resolved:** `2026-10-31T14:08:10.406185+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The exact services extra (spec-kitty-services==<cli version>) makes uv lock unsatisfiable because the companion of that version is never on PyPI at release-commit time. Keep the extra via a uv workspace member (packages/spec-kitty-services, [tool.uv.workspace] + [tool.uv.sources] workspace=true), or drop the extra and document a separate pip install?

## Options

- Workspace member (keep the extra)
- Drop the extra (separate install only)
- Other

## Final answer

A: uv workspace member with a stdlib in-tree PEP 517 backend; clarify the CLAUDE.md bullet and the ADR amendment; guard the version lock (companion == CLI == extra pin) in a test, RELEASE_CHECKLIST.md and validate_release.py (operator ruling 2026-10-31, relayed)

## Rationale

_(none)_

## Change log

- `2026-10-31T14:06:17.854920+00:00` — opened
- `2026-10-31T14:08:10.406185+00:00` — resolved (final_answer="A: uv workspace member with a stdlib in-tree PEP 517 backend; clarify the CLAUDE.md bullet and the ADR amendment; guard the version lock (companion == CLI == extra pin) in a test, RELEASE_CHECKLIST.md and validate_release.py (operator ruling 2026-10-31, relayed)")
