# Decision Moment `01M7X5WMF7RB40GC84H4XEAWEQ`

- **Mission:** `orientation-content-authority-01M7X5W6`
- **Origin flow:** `specify`
- **Slot key:** `specify.content.slug_fallback`
- **Input key:** `slug_fallback`
- **Status:** `resolved`
- **Created:** `2026-11-20T19:10:47.783693+00:00`
- **Resolved:** `2026-11-20T19:10:50.613787+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which slug when project.slug is missing?

## Options

_(none)_

## Final answer

project.slug, then the git remote repository name, then 'unknown'; never the directory name (operator ruling 2026-11-20 #2).

## Rationale

_(none)_

## Change log

- `2026-11-20T19:10:47.783693+00:00` - opened
- `2026-11-20T19:10:50.613787+00:00` - resolved (final_answer="project.slug, then the git remote repository name, then 'unknown'; never the directory name (operator ruling 2026-11-20 #2).")
