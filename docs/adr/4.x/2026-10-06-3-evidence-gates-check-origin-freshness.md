---
title: 'ADR: evidence gates check origin freshness before they trust local evidence'
description: 'Remote contact has one owner; review, accept and consolidate refresh and classify the branches they trust against origin before any mutation, with an explicit opt-out.'
status: Accepted
date: '2026-10-06'
updated: '2026-10-07'
---

**Status:** Accepted

**Date:** 2026-10-06

**Deciders:** Stijn Dejongh (owner). The operator rulings on the two escalated forks (origin ahead, origin unreachable) are recorded under Decision.

**Technical Story:** [#5780](https://github.com/spec-kitty/spec-kitty/issues/5780), [#5758](https://github.com/spec-kitty/spec-kitty/issues/5758) and [#5759](https://github.com/spec-kitty/spec-kitty/issues/5759), Mission `second-clone-origin-reconciliation-01M48V8W`. Builds on the probe-only fixes [#4969](https://github.com/spec-kitty/spec-kitty/issues/4969) and [#4979](https://github.com/spec-kitty/spec-kitty/issues/4979). Amends Decisions 1 and 2 of ADR [2026-06-05-1](../3.x/2026-06-05-1-merge-publish-layer-boundary.md).

**Reader:** a maintainer who needs to know why `spec-kitty consolidate`, `accept`, `agent action review` and the two `orchestrator-api` gates contact origin, which codes they refuse with, and which module may run `git fetch`. An operator looking at `ORIGIN_STATUS_STALE`, `ORIGIN_LANE_STALE`, `ORIGIN_LANE_DIVERGED` or `ORIGIN_UNREACHABLE` should start from the remedy in the refusal text.

---

## Context and Problem Statement

Two people work on one Mission from two clones of one remote. The reviewer in clone B rejects a work package and pushes the status change. The integrator in clone A has not pulled and runs `spec-kitty consolidate`. Clone A's local view says the work package is approved, so the rejected work lands as done with exit 0 and the "Reconciliation verified" banner, and `--push` publishes it (#5780).

The same shape breaks the review loop. A reviewer rejects, the author pushes a fix, the reviewer runs `git pull` (which updates only the remote-tracking ref of the lane) and reviews again: the workspace still holds the rejected version, the reviewer approves it, and consolidate lands it (#5758). And a teammate's fresh clone never receives the per-clone merge-driver settings, so its first pull text-merges `status.events.jsonl` and `meta.json` and leaves conflict markers that wedge every command (#5759).

Every gate decided on local state alone. Nothing in the code base asked origin before trusting a branch. The only remote contacts that existed were narrow: a target-branch refresh in `push_preflight` for `--push`, and an existence probe in `remote_probes` ([#4979](https://github.com/spec-kitty/spec-kitty/issues/4979)). The earlier fixes ([#4969](https://github.com/spec-kitty/spec-kitty/issues/4969), [#4979](https://github.com/spec-kitty/spec-kitty/issues/4979)) fixed one probe each and left the class open.

ADR 2026-06-05-1 had set the rule that blocked a general fix: remote-state inspection lives only in `push_preflight.py` and the domain preflight stays network-free. That rule was written to stop `merge` from refusing when the local target is legitimately ahead of origin (#1706). It is the right rule for **push safety** and the wrong rule for **evidence**: a gate that reads status events as the truth about a Mission cannot be network-free when the truth lives on a branch another person writes.

## Considered Options

Recorded in the Mission's `research.md` (R-1, R-2, R-4, R-7); the first four were rejected, the last is the chosen shape.

1. **Read the existing `refs/remotes/*` only.** Keeps ADR 2026-06-05-1 network-free, and is the shape of the probe-only fixes #4969 and #4979. Rejected: #5780's clone never fetched, so the tracking refs were as stale as the local branches and the P0 stayed open. The operator rejected it.
2. **A full `git fetch <remote>`.** Rejected: it transfers an unbounded set of refs (every lane of every Mission), is slower, and with pruning can remove unrelated refs. The chosen check lists the wanted branches with one `ls-remote` and fetches only those, which also makes `remote_missing` a positive answer from the remote instead of an inference from an absent local ref (and a `git fetch` of an absent ref fails the whole call).
3. **A hard-coded `origin`.** The state of #4969. Rejected: wrong for a clone whose only remote is `upstream` or a fork, and it cannot honor `branch.<b>.remote`.
4. **Ask every remote.** Rejected: one dead secondary remote (a fork named `upstream`) would then refuse every gate. The rule is the branch's configured remote, else the sole remote, else `origin`; the all-remotes existence probe of #4979 keeps its own semantics inside the same owner (see #5859).
5. **A boolean skip flag (`--skip-origin-check`).** Rejected for the opt-out: it has no environment-default symmetry and no way to say "warn but continue". A valued `--origin-check` with a `SPEC_KITTY_ORIGIN_CHECK` default mirrors `SPEC_KITTY_MODE` and is the shape chosen.

**Chosen:** a named freshness preflight that contacts the one resolved remote with `ls-remote`, fetches only the listed branches into their tracking refs, and applies a per-gate policy.

## Decision

**Remote contact has one owner. Evidence freshness is a named preflight in the evidence gates. Push safety stays where it was.**

### Amendment to ADR 2026-06-05-1

- **Decision 1 (remote inspection only in `push_preflight`) is amended.** `kernel.git.remote` (`src/kernel/git/remote.py`) is the only module that builds a remote-contacting argv: `fetch`, `ls-remote`, `remote show` without `-n`, `pull` and `clone`. It owns the no-prompt environment, the timeouts (`LS_REMOTE_TIMEOUT` 5 s, `FETCH_TIMEOUT` 15 s) and the meaning of "unreachable". `push_preflight` keeps the push-safety predicate (`is_safe_to_push`) and asks the owner by intent. `push` itself is outside the rule.
- **Decision 2 (domain preflight is network-free) is amended** from "the domain layer never touches a remote" to "the domain layer never contacts a remote **except through a named evidence-freshness preflight**". The local merge path still performs no remote contact that decides push safety, and a local consolidate still never refuses because the target is behind for commits that do not touch this Mission's status log (#1706, FR-015). Decisions 3 to 5 are unchanged.

### The remote rule

One rule says which remote a branch is checked against: the branch's configured remote, else the sole configured remote, else the remote named `origin`, else no remote. Reachability is judged against that remote only. The all-remotes existence probe of #4979 keeps its own documented semantics inside the same owner. With no remote resolving, no remote is contacted and every gate behaves as before.

### The check

`specify_cli.git.origin_freshness` is the intent layer. In one invocation it refreshes the remote's view of the branches a gate is about to trust (one contact per remote), then classifies each against the remote tip: `up_to_date`, `behind`, `ahead`, `diverged`, `local_missing`, `remote_missing`, `unreachable` or `no_remote`. `up_to_date` and `remote_missing` are concluded only from a remote that answered in this invocation; a failed refresh is `unreachable` whether or not a stale remote-tracking ref exists. `specify_cli.git.origin_gate.run_origin_gate` is the one shared adapter the gates call: it contacts the remote once, sets a coordination-only `local_missing` verdict aside for the existing `COORDINATION_WORKTREE_UNMATERIALIZED` refusal (ADR [2026-09-24-2](../3.x/2026-09-24-2-coord-read-fail-closed.md), reused, not duplicated), applies the policy and returns the warnings to print. The common case costs one round trip: when every tip `ls-remote` lists already equals the local remote-tracking ref, the fetch is skipped; any doubt fetches.

Status evidence is judged on the commits that change this Mission's `status.events.jsonl`, under every directory alias of the Mission (ADR [2026-10-05-1](2026-10-05-1-bare-slug-coordination-directory-alias.md)). A lanes Mission whose target branch is behind only because a teammate landed an unrelated Mission is not stale, which keeps FR-001 and FR-015 consistent.

### The policy

| Gate | Branch class | `behind` | `diverged` | `local_missing` (remote has it) | `unreachable` |
|---|---|---|---|---|---|
| `consolidate`, `accept`, `orchestrator-api accept-mission` / `consolidate-mission` | status evidence branch | refuse `ORIGIN_STATUS_STALE` | refuse `ORIGIN_STATUS_STALE` | `COORDINATION_WORKTREE_UNMATERIALIZED` on a coordination branch, else `ORIGIN_STATUS_STALE` | refuse `ORIGIN_UNREACHABLE` |
| `consolidate`, `orchestrator-api consolidate-mission` | approved code lanes | refuse `ORIGIN_LANE_STALE` | refuse `ORIGIN_LANE_STALE` | refuse `ORIGIN_LANE_STALE` | refuse `ORIGIN_UNREACHABLE` |
| `agent action review` | the work package's lane | fast-forward, else refuse | refuse `ORIGIN_LANE_DIVERGED` | create the workspace from the remote's lane | warn and continue |

`up_to_date`, `ahead`, `remote_missing` and `no_remote` pass everywhere.

### Operator rulings

1. **Origin ahead splits by branch class.** The gates never mutate the status evidence branch (a refusal names the commits and the pull command; with a merge record present the remedy is `consolidate --abort`, then the pull, then `consolidate`). A reviewer's local lane is the one branch a gate may move, forward only: it is cut from origin when absent, and fast-forwarded when it is a strict ancestor of the remote tip, every checkout of it is clean (review-lock residue excepted) and no foreign review lock is live. The fast-forward goes through `advance_branch_ref`, which is compare-and-swap, updates every checkout and records the lane work tip. The consolidate lane check runs before the approval-stamp check of ADR [2026-10-04-5](2026-10-04-5-approval-stamp-bounds-the-approved-claim.md) and only refuses: it never adds content to the approved claim, and its remedy is to update the lane, after which the stamp check decides.
2. **Unreachable fails closed, with an opt-out.** No remote, or a branch that was never pushed, passes silently. A remote that resolves but cannot be reached refuses at the merge-path gates (`consolidate`, `accept` and their orchestrator-api forms) and only warns at review. `--origin-check warn` per invocation (on `consolidate`, `accept` and the two `orchestrator-api` forms), with `SPEC_KITTY_ORIGIN_CHECK=warn` as its environment default (default `enforce`), turns every freshness refusal into a printed warning that names the verdict and where the opt-out came from (`flag` or `environment`). `agent action review` has no flag and honors only the environment variable: in `warn` mode a diverged lane is kept as it is and the warning is printed. An unrecognized value enforces and warns. The variable name avoids the retired "sync" vocabulary on purpose: that transport was deleted and nothing here re-enables it.

3. **`off` is a no-contact mode (2026-10-07).** `--origin-check off` (and `SPEC_KITTY_ORIGIN_CHECK=off`) contacts no remote, refuses nothing and prints one warning that origin was not checked and stale evidence is accepted. It exists for an offline machine or a remote that cannot be reached, where `warn` would still pay the contact and its timeout. The accepted risk is the one this ADR removes: a teammate's pushed rejection or lane fix is not seen and can land as done. Before this ruling `off` was an unrecognized value and enforced. Review honors it through the environment variable only and keeps the last-known lane with the warning.

### Surfaces

- `consolidate` runs one combined check (status evidence and approved lanes, one contact per remote) right after the placement seam is resolved and before `_resolve_run_status_dir` can seed or commit a coordination surface, so before any branch moves and before the lock; lanes are selected read-only. `consolidation/origin_gate.py` keeps only lane selection (skipping planning lanes, fully canceled lanes and, on `--resume`, lanes whose work packages are all completed), the merge-record flag, rendering and `typer.Exit`.
- `accept` runs it once, between the merge-commit verification and the summary. `accept --no-commit` and `--diagnose` are read-only and only warn.
- `orchestrator-api accept-mission` refuses with `MISSION_NOT_READY` and `consolidate-mission` with `PREFLIGHT_FAILED`, each with `data.preflight_error_code(s)` set to the freshness code and the verdicts in `data.origin_freshness`. The contract version is 1.11.0.
- `consolidate --dry-run` is **not** a gate: it returns the conflict forecast before the executor is entered, moves nothing and acts on no evidence. It is recorded as a reasoned non-gate in the registry gate below, not as an allowlist entry.
- `spec-kitty init` on an already-initialized clone, and `spec-kitty upgrade` even when every migration is recorded as applied, install the per-clone merge-driver settings idempotently. Upgrade reports the install in its one outcome (ADR [2026-10-04-3](2026-10-04-3-upgrade-reports-one-outcome.md)).

### Two architectural gates, both with empty allowlists

Standing order: an allowlist is priced debt (ADR [2026-09-30-1](2026-09-30-1-allowlist-ratchets-are-priced-debt.md)). Both gates close with none.

- `tests/architectural/test_remote_contact_owner.py`: zero remote-contacting argv outside `src/kernel/git/`, a scanned-file floor, a planted violation per argv form and an owner-bypass positive control.
- `tests/architectural/test_evidence_gates_check_origin.py`: the entry set is **derived** (the `review` command, and every function in `cli/commands/` and `orchestrator_api/` that transitively calls `_run_lane_based_consolidation`, `_execute_lane_merge` or `collect_feature_summary` and is not called by another such function), asserted to contain a floor of five known entry points, and each must reach an `ast.Call` to a freshness-check function (`run_origin_gate`, `check_origin_before_status_dir`, `check_mission_branches`, `check_branches`, `enforce_merge_gate`, `plan_review_lane`). A name reference or an import proves nothing, and neither does calling a lane selector such as `approved_lane_branches`. A planted entry that omits the call fails the gate; removing the call from each real entry point was shown to fail it.

## Pre-existing drift this records

ADR 2026-06-05-1 said remote inspection lives in `push_preflight`. It did not. `remote_probes` (the existence probe) and `protection_policy` (a `git remote show`) already contacted remotes outside `push_preflight`, and `git_source` in the doctrine layer cloned and fetched on its own. Each decided its own timeout and prompt behaviour. Those sites now call `kernel.git.remote`, which is what makes the first gate enforceable at zero.

## Consequences

- A second clone that has not heard from origin can no longer land a teammate's rejection, review a superseded lane, or accept on a stale log; the integrator gets a refusal with the exact remedy before anything moves.
- Every merge-path gate can now contact the network. A user with a remote and no connectivity is refused until they opt out; a solo user with no remote, or whose Mission branches were never pushed, is unaffected.
- A committed project-tier environment file that sets `SPEC_KITTY_ORIGIN_CHECK=warn` turns the check off for every clone. The warning names its source so the choice is visible; refusing a repository-tier value is a policy change left for later.
- NFR-003 (under 200 ms overhead when no remote resolves) is **review-checked, not timed in CI**. A wall-clock assertion would be the flaky kind the flakiness policy forbids; the no-remote arm is covered functionally (no remote contact, behaviour unchanged) and the reviewer reads the code path.

## Residuals

Each is recorded, not fixed here.

- **The check and the mutation are not atomic.** A teammate can push after the fetch and before the gate moves a branch. The window is the gate's own run time. It is bounded by what runs after: consolidate's lane check and the approval-stamp check (`LANE_MOVED_AFTER_APPROVAL`, ADR 2026-10-04-5) and the reconciliation gate catch a moved lane at the end, and nothing is pushed unless `--push` is given.
- **Review only warns when the remote is unreachable.** That is safe because review is not the terminus: what review approves is judged again at consolidate, where an unreachable remote refuses, and a lane that moved after approval is refused there. Refusing at review would block a reviewer on a train for no safety gain.
- **An ambiguous remote refuses (operator ruling 2026-10-07).** When remotes exist but none owns the branch (no `branch.<b>.remote`, not exactly one remote, no `origin`) the verdict is `remote_ambiguous` and the merge-path gates refuse `ORIGIN_REMOTE_AMBIGUOUS` (review warns). Before the ruling this read `no_remote` and passed silently. A repository with no remote at all still passes with nothing contacted (NFR-003).
- **`off` is a no-contact mode (operator ruling 2026-10-07)** and accepts the risk the ADR exists to remove. It prints one warning and nothing is asked of origin. See operator ruling 3.
- **A customized merge driver is preserved (operator ruling 2026-10-07).** `init` and `upgrade` write a `merge.<key>.name` / `.driver` value only when it is unset or one a release shipped (the current one, plus the 3.2.6rc1 issue-matrix name); a value the operator set is kept and named in a warning. The merge path's own self-heal (`_ensure_merge_driver_git_config`) still restores the shipped values when a consolidation or auto-rebase runs.
- **The freshness fetch never moves a local branch.** It passes `--refmap=` so a mirror-style `remote.<name>.fetch` cannot reset a lane, and it compares fully qualified `refs/heads/<b>` so a tag of the same name cannot shadow the branch.
- **Follow-ups filed:** #5857 (review's lane fast-forward re-probes ancestry in the CLI; the diverged-lane policy lives in two places), #5858 (`consolidate --push` runs `git push` with no timeout, no prompt guard, to the literal `origin`), #5859 (two rules for which remote: the existence probe and the freshness check disagree), #5860 (a credential dialog through `GIT_ASKPASS` or a GUI helper can still appear, and a hang can outlive the timeout on Windows), #5861 (`consolidate --dry-run` does not predict `ORIGIN_*` refusals).

- **The literal `origin` survives in push safety and push.** `push_preflight`'s default remote, the `phase_finalize` push, `consolidation/preflight.py:307`, `orchestrator_api/consolidation.py:170`, `mission_branch_context.py:228`, `coordination/policy.py:112` and `core/git_ops.py:331` still name `origin`. FR-015 keeps push safety unchanged, so they stay; a non-`origin` freshness test pins the new rule where it applies.
- **`--push` refreshes the target branch twice in the `lanes` topology**: once for the evidence check (the evidence branch is the target there) and once in `push_preflight`. Correct, one extra bounded contact.
- **`write_target`'s #4979 probe** still answers its own existence question with the all-remotes semantics; the owner hosts it but it does not use the FR-017 rule.
- **`run_git`'s timeout does not reap a grandchild on Windows.** On POSIX the timeout kills the child and returns. On Windows `subprocess.run` keeps reading pipes a grandchild (an `ssh` hung on a prompt) still holds, so a hang can outlive the timeout. Pre-existing, shared with `remote_probes`; a follow-up, not changed here.
- **`protection_policy`'s default-branch probe still uses `remote show`.** Swapping it for `ls-remote --symref` would drop that argv form from the census, but changes its argv and needs a characterization test; deferred.
- **Not covered, linked follow-ups:** an origin check at the approval transition itself (`move-task`, `agent status emit`), which the consolidate lane check covers at the terminus; `implement` on an existing lane (reuse, crash recovery, dependency tips); `doctor coordination` staleness against the remote; a `doctor` finding for missing merge-driver settings; renaming the `*Sync*` identifiers in `push_preflight`. Linked only (same family, separate seams): #5460, #5465, #4955, #5644, #5778, #2273.
