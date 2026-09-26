# Tracer: Tooling Friction

Mission: `startup-assess-cold-concurrency-01M3EQ9S`, which fixes P1 #3998.

Append friction encountered during the mission; it is assessed at close.

## Observations

- **F-1 (specify / decision open).** The first `spec-kitty agent decision open` on a fresh coord-topology mission failed with `CoordinationWorktreeUnmaterialized`, rendered as a full Rich traceback. The message says the worktree "will self-materialize on the mission's first coordination-branch write". The decision write *was* that first write, and it did not self-materialize. Workaround: `CoordinationWorkspace.resolve(repo_root, slug, mid8)`. The first call had already persisted the decision index, and the re-run returned `idempotent: true`. This recurs from the prior mission (ci-coverage-honesty) and is worth an upstream gap.
- **F-2 (spec prose).** Between my Write and a later read, the committed spec's prose had been reworded by some process (a hook or formatter?). This broke an exact-string fold script, so the spec was rewritten whole.
- (append during implement/review)
- F-3 (review loop). `move-task WP01 --to planned --agent reviewer-renata` set the WP *assignee* to the reviewer, so the implementer's re-claim failed with 'Agent mismatch' and needed `--force`. `--agent` on a rejection move reads as 'who acted', but it rebinds ownership.
- F-4 (WP02 / T011). Neither the global `spec-kitty` nor `.venv/bin/spec-kitty` can be pointed at a lane worktree's code — both resolve `src` via the main checkout's editable install regardless of `cwd` or lane. There is no supported CLI flag or env var to run "the lane's version" ad hoc; the only route is a hand-built `PYTHONPATH`-prefixed interpreter wrapper (as this WP's prompt itself prescribed), verified with a manual `hasattr(build_serialized)` probe. This is a real gap for any closeout WP that needs to run reproducer evidence against unmerged lane code rather than the merged repo — worth an upstream gap (a documented `--pythonpath-override` or a `spec-kitty --lane <slug>` dev-mode entry point).

## Closing assessment

- **F-1** (coordination-worktree self-materialize claim is false on first write) recurs across two missions now (ci-coverage-honesty, this one) with the identical workaround. It is no longer a one-off — worth an upstream gap against `CoordinationWorkspace`/`spec-kitty agent decision open`'s docstring and actual behaviour.
- **F-2** (spec prose silently reworded between Write and read) was disruptive enough to force a whole-file rewrite of a fold script; if it recurs a third time it deserves its own investigation into what process is touching committed spec files.
- **F-3** (`--agent` on a rejection move rebinds assignee) is a footgun in the review-loop CLI surface: the flag's meaning silently changes between a claim/implement context (who is doing the work) and a review-rejection context (who acted, but also who now owns it). Worth an upstream gap to either rename the flag in the rejection path or document the rebind explicitly in its `--help` text.
- **F-4** (no supported way to run lane code without a hand-rolled wrapper) is scoped to evidence-gathering WPs and is unlikely to recur often, but the workaround is fragile (silent fallback to main-checkout code if the wrapper is built wrong, as the `hasattr` verification step exists specifically to catch). Worth a small upstream gap: a documented, verifiable way to execute a specific lane's code for ad hoc evidence runs.
- Net: F-1 and F-3 are the two most reusable upstream gaps (both are process/CLI-surface issues that will recur on the next mission with this shape); F-2 and F-4 are lower-priority, situational.
