# Tooling friction — implement-degod-01M44488

Running log (1-3 sentences per dated entry). Seeded at planning.

Tooling this mission touches: the `spec-kitty` CLI (installed editable from this checkout), the
mission loop (`agent mission create/setup-plan/finalize-tasks`, `implement`, `move-task`,
`consolidate`), pytest with xdist, ruff, mypy, and the architectural gate files.

- 2026-10-04 — `spec-kitty` was not on PATH in the cloud container. Fixed with an editable install
  into `.venv` plus a symlink into `~/.local/bin`, so `spec-kitty --version` reports `4.0.0rc6` from
  this checkout.
- 2026-10-04 — The shallow clone hid the 90-day churn history. The archaeologist lens had to deepen
  it with `git fetch --shallow-since=2026-06-20` before `git log --since=90.days` was meaningful.
- 2026-10-04 — The specify workflow leaves `spec.md` untracked until it is substantive (#846). The
  session's stop hook flags every untracked file, so the empty scaffold had to be parked outside the
  repo until the spec was written.
- 2026-10-04 — `finalize-tasks` literal-path validation forces later WPs in a dependency chain to
  list files that an *earlier* WP creates under `create_intent`. That is semantically odd, since
  the later WP does not create them. The analyze pass flagged it (I11).
- 2026-10-04 — The approval gate requires an `issue-matrix.json` verdict for every bare `#NNNN` in
  spec/plan/research/tasks. This mission cites 18 historical and context issues, so the matrix had
  to be seeded before WP01 could ever be approved. The tasks prompt mentions this only as a
  non-gating heads-up.
- 2026-10-04 — Editing spec.md/plan.md after `record-analysis` marks the analysis stale, and
  `implement` refuses (`stale_analysis_report`). Folding analyze findings therefore needs a second
  record-analysis pass; the analyze prompt does not describe this remediate-then-re-record loop.
- 2026-10-04 — A new lane worktree reuses the root `.venv` editable install, so its tests would
  import the root checkout's `src`. It needed its own `uv sync --frozen --all-extras` before any
  test run could be trusted.
- 2026-10-05 — Any test that runs `implement` in-process must re-arm the once-per-process
  charter-advisory latch. If it does not, `test_implement_preflight` fails whenever the two files
  share an xdist worker (#5714). Three suites in this mission needed the same reset fixture.
- 2026-10-05 — Building a mission in-process through the `mission` sub-app takes about 2.5 s per
  fixture, against about 12 s through a subprocess. That gap is what kept the FR-015 reachability
  suite under its 60 s budget.
- 2026-10-05 — WP09: moving the phases exposed the once-per-process charter-warning latch in
  `test_implement_preflight` again (#5714). That file now re-arms the warning around each test.
