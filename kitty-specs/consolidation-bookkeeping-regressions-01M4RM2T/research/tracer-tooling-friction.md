# Tracer: Tooling Friction (#6071, #6073)

- Fresh cloud container: repo not pre-cloned; `GH_TOKEN` reported "invalid" via `gh auth
  status` (GraphQL probe) but REST (`gh api repos/...`) works — only GraphQL is blocked in CCR
  sessions. Used REST throughout. (Not a mission defect; environment note.)
- `charter context --action specify` emits a CharterCatalogMissWarning for
  `toolguide:typescript-mutation-tools` (scope_filtered; active languages java/python). Pre-
  existing charter-catalog noise, unrelated to this mission.
- Shallow clone (`--depth 1`) hid churn history; deepened with a bounded `fetch --depth=1000`
  to run `git log --since=90.days` for the regression-window analysis.
- The integration resume tests must run `-p no:xdist` to avoid the `__global_merge__` lock
  artifact masking the real resume regression (orchestrator note; confirmed).
