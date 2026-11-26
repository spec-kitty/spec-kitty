# Contract: refusal codes and envelopes

## `RESOLUTION_MERGE_UNREVIEWED` (CLI `consolidate`, `--dry-run`, `orchestrator-api consolidate-mission`)

**When it fires**: a merge commit on an approved code lane, beyond the claim base, meets all of the following:

- none of that lane's own approval stamps reaches it. This is the predicate shared with the gate's unreviewed-merge rule;
- no `refs/spec-kitty/auto-rebase/<lane-branch>/<sha>` record names it;
- `merge_own_changed_paths`, run behind the FR-010 guard, lists at least one non-bookkeeping path.

**When it is raised**: at claim time, before the first mutation. No branch moves. `--dry-run` reports it as `CLAIM_REFUSED_FORECAST` naming the code.

**Rendering**: it goes through `approved_bound.render_refusals`.

- Per merge, one line: `RESOLUTION_MERGE_UNREVIEWED: lane <id> (<WP ids>): merge <sha12> carries its own content on <n> path(s) and no review approval of the lane reaches it.`
- Then the shared recovery block:
  - the send-back command per WP (`move_back_command`);
  - "resolve, submit for review, an independent reviewer approves: the new approval must reach merge <sha12>";
  - `spec-kitty consolidate --mission <slug>`.

**Compounding**: the code joins `_compound_refusal` after the existing approved-bound codes.

**orchestrator-api**: `PREFLIGHT_FAILED`. `data.preflight_error_code` holds the first code and `data.preflight_error_codes` holds every distinct code. `CONTRACT_VERSION` becomes `1.30.0`.

## Rollback outcome `LANE_MOVED_SINCE_AUTO_REBASE`

**Report line**: `lane <branch>: moved since this run's auto-rebase merge <sha12> (now <tip12>; recorded before <before12>, after <after12>); not restored. The lane keeps the auto-rebase merge; review the lane's new commits, then re-run spec-kitty consolidate --mission <slug>.` No raw git recipe is printed (consistent with the stale-remedy rule of #7285). WP03 asserts the line names the lane, before, after and the live tip.

**Effects**:

- The record is kept, so `rebaselineable` is False.
- `--abort` reports the lane, as it does today for kept branches.

## FR-010 probe refusal

**Error**: `GitProbeError("merge attribute '<value>' from <source> applies to <path>; refusing to classify a merge whose resolution git would compute with an unregistered driver")`.

**Callers**: the clean-fold recognizer, the closed world and FR-004 already turn a probe error into REFUSE. The text names the path and the attribute.
