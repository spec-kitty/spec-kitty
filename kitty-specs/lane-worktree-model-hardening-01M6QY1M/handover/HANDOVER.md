# Handover: Mission lane-worktree-model-hardening-01M6QY1M (epic #7276)

You are taking over a Spec Kitty Mission partway through implement/review. Read this whole file before acting.

## Where things are

- **Repository:** spec-kitty/spec-kitty. **Topic branch:** `issue-7276-lane-worktree-hardening` (all planning, status, traces, decisions). Never push `main`; the operator merges.
- **Mission:** `lane-worktree-model-hardening-01M6QY1M`, topology `lanes`, 20 WPs, 17 lanes. Mission dir: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/`.
- **Lane branches:** all pushed to origin as `kitty/mission-lane-worktree-model-hardening-01M6QY1M-lane-<x>` (a–l). Lane worktrees are clone-local and do not exist in a new container.
- **Binding operator decisions:** 20 resolved Decision Moments. Run `spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M --json`. Rationale is in `traces/design-decisions.md`.
- **Analysis report is current.** Do not edit spec.md, plan.md, tasks.md or WP files until every WP is claimed; that makes the report stale and blocks claims. Spec edits are batched at closeout, then analyze is re-run.
- **The issue matrix is filled:** #7277–#7285 are `in-mission`; context issues are `not-applicable`.

## WP status

| State | WPs |
|---|---|
| Approved | WP01, WP02, WP03, WP04, WP05, WP06, WP08, WP09, WP11, WP12, WP13, WP15 |
| Canceled | WP19 (S11 shipped via open-packs PR #128) |
| In review, no verdict | **WP10** cycle 2. The reviewer was cut off after writing "Confirmed a real regression"; nothing is recorded. Re-run the review fully. |
| In progress, nothing committed | **WP07**, re-scoped by the operator: consolidation readers only, NO gate (decision `01M6S40GBWB6JD0FFTMQ2F6NW7`). Lane-d sits at fd763cc807. |
| In progress, nothing committed | **WP14**, S7 settlement. Lane-k already merges lanes c/i/j/l with `_baselines.yaml` resolved (013cf94cff). |
| Planned | WP16 (blocked on #7275), WP17, WP18, WP20 |

Dependencies still pending:
- WP20 needs WP07, WP14, WP15.
- WP17 needs WP07, WP08, WP10, WP12, WP14, WP15, WP20.
- WP18 needs WP17.
- WP16 needs #7275 merged into main; if it hasn't merged when everything else is approved, cancel WP16 and record FR-036/037/039 and SC-006 as deferred-with-followup.

## Restore the environment

```bash
cd /home/user/spec-kitty
git fetch origin issue-7276-lane-worktree-hardening
git checkout issue-7276-lane-worktree-hardening
git fetch origin 'refs/heads/kitty/mission-lane-worktree-model-hardening-01M6QY1M*:refs/heads/kitty/mission-lane-worktree-model-hardening-01M6QY1M*'
bash scripts/dev/cloud-session-setup.sh && make sync-packs && make sync-services
uv tool install --force --editable .
git config user.email noreply@anthropic.com && git config user.name Claude
```

Lane worktrees are recreated by the claim command: `spec-kitty agent action implement WPxx ...` re-enters or recreates the lane worktree. This is unverified after a fresh clone, so check that the worktree HEAD equals the pushed lane branch tip.

## Rules learned the hard way

1. **Claim with the full identity:** `--agent claude::python-pedro --profile python-pedro` (implementers) and `--agent claude::reviewer-renata --profile reviewer-renata` (reviewers). A bare `--agent claude` on a code-lane claim records no profile. That is a core defect to file: `implement_claim` drops `--profile`. Every approval then fails with REVIEW_NOT_INDEPENDENT.
2. **Auto-commit is off.** `move-task` and `mark-status` write `status.events.jsonl` / `status.json` but do not commit them. The orchestrator commits them, with the attribution trailers, and pushes.
3. **Sparse override:** the installed CLI predates the managed status sparse exclusion now applied to all lane worktrees, so claims refuse as "legacy sparse-checkout". Pass `--allow-sparse-checkout`; the override is logged. `consolidate` will hit the same preflight: decide there between the override and `git sparse-checkout disable` per lane. Never run a mutating `doctor ... --fix`, `upgrade` or `migrate` against the shared repository.
4. **Every code-WP review runs** `tests/architectural/test_no_dead_symbols.py -p no:xdist` serially (~4–5 min). It caught a defect in four WPs.
5. **Lane worktree tests:** `PYTHONPATH=$PWD/src /home/user/spec-kitty/.venv/bin/python -m pytest ...` (the shared venv otherwise imports the root checkout's src). "Source mismatch" failures are stale-install false reds.
6. **Briefs:** `handover/implementer-brief.md` and `handover/reviewer-brief.md` are the exact dispatch briefs used. Copy them to your scratchpad and replace `<SCRATCHPAD>`. Feedback files lived in the old scratchpad; the cycle records survive in `tasks/WPxx-*/review-cycle-*.md`.
7. **Commits:** no model id. Trailer:
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
   plus a `Claude-Session:` line for the new session. If the stop hook flags commits as Unverified, run `git rebase --exec "git commit --amend --no-edit --reset-author" origin/<branch>`.
8. **Spend limit:** the previous session hit the monthly spend limit (resets Nov 10, 16:00 UTC). Prefer the sonnet model for small mechanical fixes.

## Next steps, in order

1. Re-dispatch **WP10 review cycle 2**. The cycle-1 blockers were B1 (NFR-002 / structured husk error), B2 (migration settles refused lanes), B3 (probe false positive) and B4 (test-order dependence); the rework is in lane-g commits 7768dad42c, dd69dadef6, 962ba8662e. Scrutinize the new "legacy Missions are exempt from the lane write refusal" decision against ruling 8.
2. Re-dispatch **WP07** (re-scoped) and **WP14**, using the prompts in `tasks/WP07-*.md` / `tasks/WP14-*.md` plus the overrides in `traces/design-decisions.md`:
   - **WP07:**
     - consolidation readers onto the door;
     - an explicit committed-ref read entry for `done_bookkeeping._durable_coordination_lanes`;
     - `phase_advance`'s landed-reader copy delegated to `mission_runtime.mission_has_landed`;
     - one pin test per topology state;
     - no gate, no allowlist.
   - **WP14:**
     - the size rule at the first finalize;
     - lanes_with_coord on every target, with the topic branch as the coordination branch;
     - the root checkout moves to `create_return_branch` first;
     - compensation;
     - remove WP13's two allowlist entries (baselines 232→231, widened 84→83);
     - obligation N1: write/read alignment plus a read-after-write test;
     - context-resolve / check-prerequisites PRIMARY tests.
3. Then **WP20**, **WP17**, **WP18**, and WP16 only if #7275 has merged.
4. **Closeout items** (see `traces/approach.md`):
   - delete `write_branch_bound._commits_outside_windows`;
   - ADR wording on the landed_worktrees hint (WP09);
   - record MISSION_BRANCH_REF in ADR 2026-11-06-2 and data-model;
   - retarget the C-1/C-3 links to spec-kitty-events main (PR #215 merged);
   - fix spec FR-084/C-003 and record the deferred S1-gate FRs, then re-run analyze;
   - add the new error codes to `contracts/error-codes.yaml`;
   - correct the S8 missing-O_k residual text;
   - changelog notes: the `events tail` / `materialize` exit-1 behaviour change;
   - PR-body notes: release coupling C-010 (WP13 + WP14 ship together), the WP12 orchestrator-api out-of-map call, and the two #6884 tests that WP04 flips on purpose;
   - run `tests/specify_cli/cli/commands` and `tests/specify_cli/upgrade` (out of the CI matrix) on the consolidated branch and on origin/main, and classify every red;
   - check `test_module_length_agreement` after WP09's deletions.
5. **Accept, consolidate, finish:**
   - `spec-kitty accept`, then `spec-kitty consolidate` into `issue-7276-lane-worktree-hardening`, never main;
   - clean up worktrees and lane branches, tidy history, rebase onto origin/main (#7274, #7275, #7255, #7248, #6884 may have landed);
   - changelog fragments and docs (execution-lanes.md, git-worktrees.md, docs/context/topology.md, CLAUDE.md sections);
   - pre-PR adversarial squad;
   - DRAFT PR with `Closes` for the delivered slices and `Refs #7276`;
   - subscribe to PR activity, drive CI to green, mark ready, post the hand-off comment.
6. **Ask the operator:** whether to bump the open-packs pin to main 9013b34 in this PR.

## Follow-up issues to file at closeout

- The claim-identity defect (`implement_claim` drops `--profile`).
- The deferred S1 single-door gate plus about 53 legacy read sites. The census summary is in `traces/design-decisions.md`.
- `claim_base.on_wp_terminal` clears a canceled lane's tip ref.
- `move-task` takes 2–10 minutes.
- Claiming leaves bookkeeping staged.
- The `git rebase None` remedy text.
- `context cleanup` scope.

## Sibling sessions (claude-code-remote `send_message`)

- Dispatcher: `session_01DGGMy56JAhF4peqEYi5AVc`.
- S4 / #7275 (destructive guard): `session_019C2Tk5Q848gmy5vB9Cmggg`. WP16 binds to `guarded_landed_removal(repo_root, LandedRemoval(...))`.
- S10 / #7274 (late window): `session_019C2Tk6ZJUcAJgoM5SWNcoQ`.
- S11 open-packs (PR #128 merged): `session_019C2Tk4YnRJL9LbgwmdbDBL`. Tell it if WP16 lands, so the `--prune` "backstop" wording can be restored.
- S9 events (PR #215 merged): `session_019C2Tk3wuwRrWAuhT7cgfgt`. It wants the core PR number.
