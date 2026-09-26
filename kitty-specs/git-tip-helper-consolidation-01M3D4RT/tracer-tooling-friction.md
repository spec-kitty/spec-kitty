# Tracer: Tooling Friction

- `gh` on the org repo needs `unset GITHUB_TOKEN` (ambient token lacks scopes).
- REST `issues/<n>.parent` field returned NONE for sub-issues; the reliable
  current-parent source is the GraphQL `issue.parent` field (adjudicated a
  squad/self disagreement against it). Timeline `parent_issue_added/removed`
  events also work.
- Editable install current; do NOT `uv sync` / bare `uv run` (destroys the
  hand-built .venv). Use `.venv/bin/python -m pytest <file> -q`.

## Append during implement

## Coord/lane friction (implement→approve)
- New lane worktrees inherit `core.sparseCheckout=true`; `spec-kitty implement`/`merge`
  abort on ANY sparse worktree. Fix: `git sparse-checkout disable` per worktree (safe,
  non-destructive) — the doctor --fix needs a TTY.
- Running lifecycle commands (mark-status/move-task) from inside the lane worktree writes
  status.json/status.events.jsonl into the lane's kitty-specs; the for_review + approve
  gates then block on "implementation branch modified kitty-specs/". Fix: sync the lane's
  kitty-specs to the primary partition (`git checkout <target> -- kitty-specs/` +
  remove lane-only status.json) and run lifecycle commands from the main checkout.
- Default `spec-kitty merge` strategy is squash; this repo lands commits individually, so
  consolidated manually to preserve the 3 per-issue commits.
