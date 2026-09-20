---
title: 'Landing Contributor PRs: The Maintainer Runbook'
description: 'The maintainer workflow for landing contributor PRs: claim, worktree isolation, rebase, red classification, folds, red-first verification, push discipline, and hand-off.'
doc_status: active
updated: '2026-09-08'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/guides/index.md
- docs/development/how-to/review-gates.md
- docs/development/testing/testing-flakiness.md
- docs/development/how-to/manage-issue-tracker.md
- docs/development/reference/red-main-and-release-readiness.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
- docs/changelog/index.md
---
# Landing Contributor PRs: The Maintainer Runbook

**Audience**: Maintainers taking contributor PRs from "open with red CI" to
"merge-ready, evidence posted, operator merges".
**Issue**: [Priivacy-ai/spec-kitty#2341](https://github.com/Priivacy-ai/spec-kitty/issues/2341)
**Origin**: The 2026-07-04 landing pass (#2332, #2336, #2338, #2239, #2238),
where this workflow was run end-to-end and its friction points were logged.

The deliverable of a landing pass is never a merge. It is a PR that is green,
un-drafted, carries a full evidence trail in its comment thread, and states
any landing-order constraints — so the operator can merge it without
re-deriving the adjudication. The maintainer never merges
(see [step 11](#11-hand-off--the-operator-merges)).

## The workflow at a glance

1. [Claim before touching](#1-claim-before-touching)
2. [One isolated worktree per PR](#2-one-isolated-worktree-per-pr)
3. [Rebase onto current upstream/main first](#3-rebase-onto-current-upstreammain-first)
4. [Classify every red check](#4-classify-every-red-check)
5. [Folds: remediation commits on the contributor branch](#5-folds-remediation-commits-on-the-contributor-branch)
6. [Red-first verification for bugfix PRs](#6-red-first-verification-for-bugfix-prs)
7. [Review focus areas beyond CI](#7-review-focus-areas-beyond-ci)
8. [Adversarial squad for architectural or API-surface PRs](#8-adversarial-squad-for-architectural-or-api-surface-prs)
9. [Push discipline](#9-push-discipline)
10. [Post the remediation summary](#10-post-the-remediation-summary)
11. [Hand-off — the operator merges](#11-hand-off--the-operator-merges)
12. [Follow-up hygiene](#12-follow-up-hygiene)

## 1. Claim before touching

Post a claim comment on the PR **before** any rebase or review work: what you
are picking up, in which landing queue, and what you plan to do. One claim per
PR in the pass, posted first.

```bash
unset GITHUB_TOKEN   # keyring auth has full repo scope; a limited env token may not
gh pr comment <N> --repo spec-kitty/spec-kitty \
  --body "Claiming this PR for today's landing pass: rebase onto upstream/main, adjudicate red checks, fold fixes as needed. Evidence to follow."
```

Why: it prevents duplicated maintainer effort when several PRs are being
landed in parallel, and it means the contributor is never surprised by
maintainer commits appearing on their branch.

## 2. One isolated worktree per PR

Never touch the primary checkout — a mission session may own it. Give every
PR its own worktree:

```bash
git fetch upstream pull/<N>/head:pr-<N>-local
git worktree add .worktrees/pr-<N>-landing pr-<N>-local
cd .worktrees/pr-<N>-landing
```

Each worktree builds its own `uv` virtualenv on the first `uv run` — expect
roughly 40 seconds and some disk on that first command. That is normal, not a
hang.

## 3. Rebase onto current upstream/main first

Contributor branches are routinely 100+ commits behind. Every adjudication —
tests, gates, review — happens on the rebased tip, not the stale base:

```bash
git fetch upstream main
git rebase upstream/main
```

Changelog conflicts resolve in `docs/changelog/CHANGELOG.md`, which is the
canonical changelog. The root `CHANGELOG.md` is a symlink to it (since the
symlink cutover that rode #2338), so both paths reach the same file — resolve
the conflict once, in the canonical location.

## 4. Classify every red check

This is the core reviewer decision point. Diagnose each red check on the
rebased tip and classify it into exactly one of four bins:

| Classification | What it looks like | Action |
|---|---|---|
| **PR defect** | The PR's own change breaks a test or gate | Fix it on the branch (a "fold", [step 5](#5-folds-remediation-commits-on-the-contributor-branch)) |
| **Contract the PR legitimately crosses** | A seam move-set completeness gate, a census tolerance band | Re-pin the contract **in the same PR**, with a dated rationale in the pin |
| **Pre-existing main breakage** | The same red reproduces on an unrelated main-based branch | **Fold the fix in by default** ([step 5](#5-folds-remediation-commits-on-the-contributor-branch)) — keep main green even for a red the PR did not cause — *unless* one of the two carve-outs below applies |
| **Perf-budget flake** | A budget gate trips without a correctness signal | Note it, watch for recurrence, tune the budget at the root if it repeats — never retry-to-green |

**Start with main's own CI run at the merge-base — it is cheaper and more
decisive than any local rerun.** CI already ran the same shards against the
commit your branch is based on, so the comparison is a fetch, not a test run:

```bash
unset GITHUB_TOKEN
gh run list --repo spec-kitty/spec-kitty --branch main --limit 5 \
  --json databaseId,name,conclusion,headSha
# then, per failing job, pull the logs and diff the failing-test sets:
gh api --allow-escape-sequences "/repos/spec-kitty/spec-kitty/actions/jobs/<job-id>/logs" \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E "^FAILED|short test summary| failed,"
```

Two things make this decisive rather than merely suggestive:

- **Match on test id *and* assertion text**, not just job status. A job can be
  red on both sides for different reasons.
- **Compare the pass counts too.** `1 failed, 572 passed` on main against
  `1 failed, 583 passed` on the PR proves the PR added 11 tests and no
  failures. That single line refutes "the PR broke something" faster than any
  argument.

**Decompose composite jobs.** `lint` is not one check — it runs schema
generation, `ruff`, `mypy`, `commitlint`, `markdownlint`, `pip-audit` and
`bandit` as separate steps. Never classify `lint` as a unit: extract the
failing **steps** on both sides and compare those. On the 2026-08-04 pass,
`pip-audit` and `bandit` were red on main (pre-existing) while `commitlint`
and `markdownlint` were introduced by the folds — a distinction invisible at
job level:

```bash
grep -nE "##\[group\]Run |##\[error\]Process completed" <log> \
  | awk '/error/{print prev} {prev=$0}'
```

Then reproduce locally only for the reds you still need to settle:

```bash
git worktree add /tmp/repro-main upstream/main
cd /tmp/repro-main && PWHEADLESS=1 uv run pytest <failing test> -q
```

A red there too confirms the failure is pre-existing, not the PR's. **The
default is then to fold the fix in anyway** (boy-scout / campsite-clean,
`DIRECTIVE_025`) — a stale generated artifact, a forgotten regen, or a small
unwired reference are all fixable inline, and a landing pass that leaves an
easy pre-existing red on the board just defers the cost and keeps main red for
longer. Two carve-outs override that default:

- **A `regression`-marked red-first test.** An intentionally-failing,
  issue-pinned reproduction (per
  [ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md))
  is a *deliberate* red-mainline signal for an open P0 bug — **leave it red.**
  Do not fold it to green; the product fix that closes its tracking issue is
  separate, dedicated work, never a landing-pass fold. Greening it here would
  erase the honest release-blocker signal the ADR exists to preserve.

  Tell these apart by the `@pytest.mark.regression` marker and the in-test
  NOTE naming the tracking issue — but **check for the marker per test, not
  per file.** It is routinely applied as a decorator on the individual test
  while the module's `pytestmark` lists only category markers, so a file-level
  grep reports "unmarked" for a properly-pinned P0 reproduction. This misread
  happened on the 2026-08-04 pass and nearly produced a needless "add the
  marker" fold for three tests that already had it:

  ```bash
  grep -rn "pytest.mark.regression" tests/ | sort   # catches both forms
  ```

  Since the 2026-08-04 pass, these tests live in `tests/regression/` and are
  excluded from every other suite's selection — so **a red outside
  `tests/regression/` is a real signal**, and the classification above only
  has to be applied to reds inside it. Entry and exit rules:
  [`tests/regression/README.md`](../../../tests/regression/README.md).
- **A fix that is mission scope and cannot reasonably be folded.** If the real
  fix belongs to a distinct mission — wide blast radius, its own spec/design, an
  in-flight mission's own reconciliation — do not cram it into the contributor
  PR. Instead **accept the failure as an honest P0 red**: mark the failing test
  `@pytest.mark.regression`, pin it (an in-test note) to the owning issue/mission,
  and leave it red per
  [Red Main and Release Readiness](../reference/red-main-and-release-readiness.md). Never
  retry-to-green.

See [manage-issue-tracker.md](manage-issue-tracker.md#triaging-issues-type-severity-and-release-blocking-bugs)
for the type/severity triage this leans on, and
[testing-flakiness.md](../testing/testing-flakiness.md) for the never-retry-to-green rule
behind the fourth bin.

### Multi-WP lanes: classify against the true base, not the lane tip

A mission with dependency-merged lanes (`lanes.json`, [execution-lanes.md](../../architecture/execution-lanes.md))
gives a downstream WP's lane tip a branch that already **contains every
upstream WP it depends on** — the tip is not close to the mission's own base,
it is ahead of it by however many WPs merged in first. Diffing or classifying
reds against that lane tip mixes in work this PR did not write.

Always classify against the **true base**, computed fresh, not against the
lane tip and not against a remembered branch point:

```bash
git merge-base <mission-branch> upstream/main
```

Reds that reproduce between that merge-base and the lane tip are **pre-existing
or upstream-WP fallout**, not this WP's defect — apply the same four-bin
classification above, but with the merge-base as the comparison point.

One concrete trap this produces: a `mock.patch.object(...)` raising
`AttributeError` inside a red you have classified as "pre-existing" is very
often **migration fallout** — an earlier WP in the same dependency chain
renamed or removed the attribute the mock patches — not a defect in the WP
under review. Confirm by checking whether the patched attribute still exists
on the target at the merge-base; if it does not, the fix belongs to whichever
WP renamed it, not to a fold on this PR.

### Stale-stack diagnostic: two-dot vs three-dot diff

A "small fix" PR whose diff shows charter, doctrine, or other governance
files it has no business touching is a symptom of a **stale stack**: the
branch was cut before a since-merged doctrine change, and rebasing (or a
naive two-dot diff) is smuggling that governance change back in as if it
were part of this PR.

Tell the two apart with git's own diff-base semantics:

```bash
git diff upstream/main..HEAD    # two-dot: literal tip-to-tip diff
git diff upstream/main...HEAD   # three-dot: diff since the merge-base
```

- **Two-dot** (`..`) diffs the two commits directly — if `upstream/main` has
  moved on, this includes both "what the PR changed" *and* "what upstream/main
  changed since," conflated into one diff.
- **Three-dot** (`...`) diffs from `git merge-base upstream/main HEAD` to
  `HEAD` — only the PR branch's own commits, regardless of how far
  `upstream/main` has since moved.

If the three-dot diff is clean (only the PR's intended files) but the two-dot
diff shows charter/governance files, the branch is stale, not defective: fetch
and rebase onto current `upstream/main` ([step 3](#3-rebase-onto-current-upstreammain-first))
before re-classifying. If charter/governance files still show up in the
**three-dot** diff, that is a real defect — the PR is genuinely carrying
governance changes it should not — and belongs in the "PR defect" bin, not the
"stale stack" bin.

## 5. Folds: remediation commits on the contributor branch

Folds are maintainer commits pushed directly to the contributor branch. This
relies on `maintainerCanModify`, which is true by default on PRs from forks.

- **One commit per fold.** Each landing-pass remediation is its own
  single-purpose commit — never bundle two unrelated fixes into one commit,
  and never split one logical fix across several. This is a hard rule, not a
  preference: a mixed-purpose fold commit is what makes a later `git revert`
  or bisect ambiguous.
- **Label the commit subject `<type>(landing): ...`** — a Conventional Commits
  type, with `landing` as the scope. Pick the type from what the commit
  actually touches: `fix` (product behaviour), `test` (tests/gates/baselines),
  `docs` (prose, changelog, mission artifacts), `chore` (config, CI, tooling).
  The scope keeps every fold greppable (`git log --grep '(landing)'`).

  > **Do not write `landing fold: ...`.** This runbook prescribed that label
  > until 2026-08-04 and it is **rejected by the repo's own commitlint gate**:
  > "landing fold" contains a space, so the Conventional Commits parser
  > extracts no type at all and every such commit fails both `type-empty` and
  > `subject-empty`. It went unnoticed for several landing passes because
  > commitlint only lints commits **in the PR range** — main's own
  > `landing fold:` commits were never checked, so the violation only ever
  > surfaces on the PR that carries the folds. commitlint is not a
  > `devDependency`, so mirror CI's own invocation (`ci-quality.yml`, the
  > `commitlint` step) and verify the whole batch before pushing:
  > ```bash
  > for c in $(git rev-list upstream/main..HEAD); do
  >   npx --yes @commitlint/cli@19.8.1 --config commitlint.config.cjs \
  >     --from "$c~1" --to "$c" --verbose \
  >     || echo "FAILED: $(git log --format=%s -n1 "$c")"
  > done
  > ```
  > Allowed types come from `type-enum` in `commitlint.config.cjs`
  > (`build chore ci docs feat fix lint perf plan refactor revert spec style
  > test`). There is no `scope-enum`, so `(landing)` needs no registration.
- Explain every fold in the remediation summary comment ([step 10](#10-post-the-remediation-summary)).

Typical folds: canonical-source fixes (the changelog lives in
`docs/changelog/`), seam re-pins with dated rationale, retired-shim API
migrations, doc/contract artifact sync, and — by default — fixes for
**pre-existing main breakage** the PR happens to surface ([step 4](#4-classify-every-red-check)).
The one red you do **not** fold to green is a `regression`-marked red-first
test: it is a deliberate open-P0 signal and stays red until its own product
fix lands (ADR 2026-07-17-1).

### Clean history: compress bookkeeping, keep code separate

Recent practice over-corrected on this point: several contributor PRs were
landed **fully squashed**, erasing the reviewable seam between distinct code
changes. That is not the target. When landing a contributor PR:

- **Compress bookkeeping/admin commits** — planning notes, fixups, "wip",
  formatting-only, mission-scaffolding, revert-of-own-typo — into the related
  work commit they belong to.
- **Keep genuinely separate code/feature work as separate, reviewable
  commits.** If the contributor made two distinct logical changes, land two
  commits, not one.
- The goal is a readable history where each commit is one coherent change —
  neither a single opaque squash nor 200 noise commits.

This governs the *contributor's* commits. Landing folds (above) are always
their own single-purpose `landing fold: ...` commits regardless.

## 6. Red-first verification for bugfix PRs

A fix whose test is green before and after the fix captures nothing. Prove
the PR's test actually witnesses the bug by swapping the pre-fix product file
back in:

```bash
git checkout upstream/main -- <product-file>
PWHEADLESS=1 uv run pytest <the PR's test> -q     # MUST FAIL
git checkout HEAD -- <product-file>
PWHEADLESS=1 uv run pytest <the PR's test> -q     # must pass again
```

Post the result on the PR. If the test never goes red, the fold is a better
test — not a green checkmark.

## 7. Review focus areas beyond CI

What the maintainer reads the diff for, beyond the checks:

- **Canonical sources** — does the change edit the source of truth, or a
  generated mirror/agent copy? (Agent directories under `.claude/`,
  `.amazonq/`, etc. are generated; sources live under `packs/built-in/` and
  `src/charter/offering/`.)
- **SSOT / duplication** — does new code near-copy an existing canonical seam
  or resolver? Justified divergence must be adjudicated explicitly (name the
  contract difference), never assumed.
- **Contract artifacts** — a new command or field on a versioned surface must
  land in the machine contract (`upstream_contract.json`), the version
  ledger, and the human docs together, in the same PR.
- **Scope-vs-spec** — an apparent scope surprise may be required by the
  mission spec; check the FRs and constraints before flagging creep.
- **Error-handling nets** — best-effort helpers must catch the *actual*
  exception types their callees raise, not a guessed superset.
- **Terminology canon** — on any prose or doctrine touch, run the guard
  locally: `PWHEADLESS=1 uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.
- **PR body style** — does the PR body lead with impact (what changes for a
  user or operator), before architecture or test-strategy detail? See
  [Review gates: PR body style](review-gates.md#pr-body-style-consumer-focused-bluf).
- **Changelog update** — does a user-facing change carry a consumer-focused
  entry in `docs/changelog/CHANGELOG.md`? See
  [Review gates: Changelog update and style](review-gates.md#changelog-update-and-style).

## 8. Adversarial squad for architectural or API-surface PRs

For changes to versioned contracts or shared seams, dispatch profile-loaded
review lenses in parallel — for example `architect-alphonso` for design and
contract adherence, `paula-patterns` for SSOT and duplication — with
read-only access to the landing worktree.

- **Fold their findings — MAJOR, MINOR, and NOTE alike** ([step 5](#5-folds-remediation-commits-on-the-contributor-branch)).
  The default is to fix everything the squad surfaces, in this PR, while the
  branch is open and the context is loaded. A MINOR or NOTE is cheap to fold now
  and expensive to rediscover later; deferring it to a "someday" issue is how
  easy fixes rot on a backlog and how the same finding gets re-raised on the next
  pass. Do not triage-by-severity into fold-vs-defer — fold by default.
- **File a follow-up issue only as the exception**, when folding is genuinely the
  wrong call for one of two reasons: (a) the finding's **scope is too large** to
  fold cleanly into this PR (wide blast radius, many files, a refactor that would
  swamp the review), or (b) its **impact is severe enough that the remediation
  needs its own mission or design pass** — a spec, an ADR, or an operator
  decision before any code moves. In those cases file the issue, parent it under
  the relevant functional epic, and say in the remediation summary why it was not
  folded. Severity alone never justifies deferral; only unfoldable scope or a
  required design pass does.

### Delegate remediation to subagents

When a landing pass needs remediation beyond a one-line fold, delegate the
implementation to a profile-loaded subagent rather than hand-authoring it
inline — load the agent profile through the charter
(`spec-kitty charter context --action implement --include agent-profile:<id>`,
or `spec-kitty agent profile show <id>`), and apply model discipline:
implementation work routes to `sonnet`, review work routes to `opus`. The
maintainer's job is to classify each red ([step 4](#4-classify-every-red-check))
and adjudicate the result, not to write every fold by hand. This complements
the adversarial squad above — the squad finds and classifies, subagents
implement the fold, the maintainer adjudicates and lands it as one commit
([step 5](#5-folds-remediation-commits-on-the-contributor-branch)).

Mechanics that make a parallel pass work, learned on 2026-08-04 (24+ folds,
14 delegated agents):

- **Give every agent its own worktree and an explicit no-touch list.** Name
  the files other in-flight agents hold. Without it, two agents edit
  `resolver.py` and both cherry-picks conflict. Sequence anything that shares
  a file; parallelise everything that does not.
- **Agents commit in their own worktree and never push.** The maintainer
  cherry-picks onto the landing branch. Because the worktrees share one object
  store, `git cherry-pick <sha>` works with no remote round-trip.
- **`cd` into the landing worktree on every cherry-pick, and check the branch
  before applying.** A shell whose working directory resets between commands
  lands you in the **primary checkout — which is on `main`** — and a
  cherry-pick there silently commits landing folds onto local `main`. This
  happened on the 2026-08-04 pass: three commits went onto `main` before the
  branch name in git's output gave it away. It is fully recoverable (nothing
  was pushed; `git reset --hard upstream/main` restored it, and the commits
  re-applied cleanly to the landing branch from the agent worktree), but only
  because it was noticed immediately. Make it structural rather than vigilant:
  ```bash
  cd <landing-worktree> && test "$(git branch --show-current)" = "<landing-branch>" \
    && git cherry-pick <sha>...
  ```
  Re-check the fold count after each cherry-pick (`git log --oneline <base>..HEAD | wc -l`)
  — a count that resets to a small number means you are on the wrong branch.
- **A revert pair cancels out — skip both and prove tree parity.** An agent
  that self-corrects may leave `X` and `Revert "X"` plus a re-landed `X'`.
  Cherry-pick the net set, then prove nothing was lost:
  ```bash
  git diff <agent-branch> HEAD -- <the files that agent owned>   # expect empty
  ```
- **Convergence is the signal worth acting on.** When independent lenses
  reproduce the same defect with live before/after output, treat it as
  confirmed and fix it — do not re-derive. Conversely, a single lens's
  *proposed fix* still needs checking: on 2026-08-04 two lenses proposed the
  same one-line change and the implementer correctly rejected it, because that
  line would have destroyed a legitimately-empty configured value. Brief
  agents to **verify the diagnosis before applying the prescription**, and to
  stop and report if the code disagrees with the brief.
- **Instruct agents never to fabricate evidence.** A measurement they could
  not take must be reported as not taken. A matrix row marked `pending` with a
  reason is worth more than one marked `pass` without proof.

## 9. Push discipline

Before any force-push to a fork branch, check for commits you have not seen —
Copilot-review commits and parallel-session commits get cherry-picked, never
clobbered:

```bash
# Fetch into an explicit remote-tracking ref — never rely on FETCH_HEAD.
git fetch <fork-remote> <branch>:refs/remotes/<fork-remote>/<branch> --force
git log <old-head>..refs/remotes/<fork-remote>/<branch> --oneline  # anything here? cherry-pick it first
LEASE_SHA=$(git rev-parse refs/remotes/<fork-remote>/<branch>)
git push <fork-remote> HEAD:refs/heads/<branch> --force-with-lease=<branch>:"$LEASE_SHA"
```

Two lease lessons from the 2026-07-04 pass, both worth internalizing:

1. **A bare `--force-with-lease` fails with `(stale info)` on fork branches
   you have never fetched** — the lease has no remote-tracking ref to compare
   against locally. The explicit `<branch>:<sha>` form above is the standard
   flow, not a workaround.
2. **The lease sha must come from `git rev-parse`, never retyped from a
   display.** Two pushes in the pass were rejected because a lease sha was
   retyped from a 9-character abbreviated prefix.
3. **`rev-parse FETCH_HEAD` is only valid immediately after fetching the ref
   you mean.** `FETCH_HEAD` is a single global file that *every* fetch
   overwrites, so a `git fetch upstream main` between the fork fetch and the
   push silently substitutes main's sha into the lease — producing a
   `(stale info)` rejection that looks like "someone else pushed" when nothing
   moved. This cost a rejected push on the 2026-08-04 pass. Fetch into an
   explicit `refs/remotes/<fork-remote>/<branch>` and rev-parse that, as
   above; it survives any number of intervening fetches.

## 10. Post the remediation summary

After pushing folds, post one structured comment on the PR:

- the review verdict;
- each fold, with its why;
- squad verdicts, if a squad ran;
- local test evidence — counts, plus `ruff` / `mypy` results;
- pre-existing failures called out **with the filed issue number**;
- the state: e.g. "watching CI; merge-ready on green".

Contributor-education notes (for example, which file is the canonical
changelog) go in this comment too, addressed to the author.

## 11. Hand-off — the operator merges

The operator merges; the maintainer never runs `gh pr merge`. The hand-off
deliverable is:

- green CI;
- the PR un-drafted;
- the evidence trail on the PR;
- landing-order constraints stated explicitly — for example, a structural
  cutover riding one PR forces an order on the rest of the pass.

## 12. Follow-up hygiene

Most of what a landing pass discovers should be **folded, not filed** — see the
fold-first default in [step 8](#8-adversarial-squad-for-architectural-or-api-surface-prs).
What genuinely cannot be folded — a finding whose scope is too large for this PR,
or whose impact needs its own mission or design pass — gets a tracked home **the
same day**: filed, labeled, and parented under a functional epic (never a meta
rollup). New issues get processed by a triage pass immediately, so the next
landing pass starts from a clean queue.

## Gotchas

Field notes from the 2026-07-04 landing pass. Where the friction has since
been fixed, the end-state is stated instead of the trap.

- **The changelog has one canonical home.** `docs/changelog/CHANGELOG.md` is
  the canonical changelog; the root `CHANGELOG.md` is a symlink to it. Edits
  and conflict resolutions land in the canonical file either way — there is
  no longer a generated root mirror to trip docs-freshness.
- **`--force-with-lease` on never-fetched fork branches.** See
  [step 9](#9-push-discipline): use the explicit `<branch>:<sha>` lease form,
  and take the sha from `git rev-parse` — never retype it from an
  abbreviated display.
- **Pre-existing main breakage surfaces mid-pass.** One broken contract on
  main (#2339: dotted `migration_id` vs the dry-run JSON contract) turned
  local runs red on *every* rebased branch in the pass. The default is to
  **fold the fix** ([step 4](#4-classify-every-red-check)) — that clears main
  and every rebased branch inherits the green. When you *can't* fold (a
  `regression`-marked red-first test, or a mission-scope fix), file early; the
  filed issue is what lets subsequent PRs skip re-reproducing it.
- **Saturated tolerance bands trip on the next legitimate change.** The CLI
  visible-count census sat at the top of its band, so the next legitimate
  command (#2338) tripped it. A saturated band needs a re-pin with a dated
  rationale — e.g. the 2026-07-04 re-pin at 236 visible (tolerance 212–259)
  in `tests/docs/test_check_cli_reference_freshness.py`; the current values
  live in that test, not here. That re-pin-in-the-same-PR pattern is the
  model for the second bin of [step 4](#4-classify-every-red-check).
- **Seam completeness gates are invisible to contributors.** Adding a `def`
  to `src/specify_cli/cli/commands/agent/tasks_move_task.py` also requires
  joining the `_MOVE_SET` pin in
  `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py` and the
  re-export block in `agent/tasks.py`. Expect this as a fold on PRs that
  touch decomposed command modules.
- **CI-only architectural gates land late.** Repo-wide gates (terminology,
  shim retirement, seam boundaries) run in the
  `integration-tests-core-misc (architectural)` shard — a PR can pass every
  fast shard and fail ~40 minutes later. Run `tests/architectural/` locally
  on the rebased tip before declaring a branch green.
- **Shard path-filters mask pre-existing failures.** The `changes` filter
  skips shards like `fast-tests-cli` on PRs that do not touch those paths, so
  a pre-existing red only surfaces on the first PR that does — the innocent
  PR wears the failure. Classify it as pre-existing (bin three of
  [step 4](#4-classify-every-red-check)), not as the PR's defect.
  **Your own folds trigger this too:** a fold that touches a new path un-skips
  that path's shard, so the pass surfaces reds the PR never caused. On
  2026-08-04 a fold under `cli/commands/agent/` un-skipped `fast-tests-agent`
  and exposed a golden-contract drift that reproduced cleanly on
  `abca7ec96`. Re-classify after each batch of folds, not only at the start.
- **File-scoped linters lint the whole file, not your diff.** `markdownlint`
  runs over *changed files*, so editing one line of a long-lived document
  subjects its entire pre-existing violation set to the gate. Touching
  `docs/changelog/CHANGELOG.md` surfaced ~21 pre-existing `MD049` findings
  spread across the file. Expect this on any changelog or large-doc fold, and
  budget for fixing the file rather than only your lines. Run the repo's own
  markdownlint invocation (see the step in `.github/workflows/ci-quality.yml`)
  rather than a default config.
- **Moving or adding a test file trips completeness baselines.** New or
  relocated test files must join their registries in the *same commit* as the
  move, each with a dated rationale. Search the repo for the new filename
  before committing. Never key an allowlist by line number or whole file
  (banned by #2077 / `DIRECTIVE_041`) — use content descriptors.
- **Verify architectural gates from a non-dot path.** Gates that walk the tree
  can silently skip dot-prefixed path segments, so a run from
  `.worktrees/…` or `.claude/worktrees/…` can report a false green. Confirm
  from a plain checkout before declaring a gate satisfied:
  ```bash
  git worktree add /tmp/verify-<N> <sha>
  cd /tmp/verify-<N> && PWHEADLESS=1 uv run pytest tests/architectural/<gate>.py -q
  ```
- **A frozen-contract drift with `missing: []` means flags were *added*, not
  removed.** Read the direction before acting: extras with nothing missing is
  a pin that was never joined when a feature shipped, so the fix is to re-pin
  with a dated rationale. Never remove a shipped flag to satisfy a stale pin —
  that smuggles a breaking change into a landing pass. Trace each addition
  (`git log -S'--flag-name' -- src/`) and confirm it predates the merge-base
  before re-pinning.
- **Never green-wash a red by "updating the test".** Twice on the 2026-08-04
  pass the obvious read — new gating narrowed a payload, so the assertion is
  stale — was wrong: the rendered output was byte-identical on both sides and
  the real defect was a product bug (a `str.replace` deleting a section header
  along with its body). Prove the assertion is wrong *before* changing it, by
  showing the expected behaviour genuinely changed. If the test is right, fix
  the product even when that is the larger job.
- **`scripts/` invocations need `PYTHONPATH=.`.** The docs scripts import
  `scripts.docs.*` as a package; without it they crash with
  `ModuleNotFoundError: scripts`:

  ```bash
  PYTHONPATH=. uv run python scripts/docs/check_docs_freshness.py --ci
  ```

- **`build_cli_reference.py` defaults to the wrong output path.** Its
  defaults write `docs/reference/`, while the live canonical reference is
  `docs/api/cli-commands.md`. Always pass the outputs explicitly:

  ```bash
  PYTHONPATH=. uv run python scripts/docs/build_cli_reference.py \
    --output docs/api/cli-commands.md \
    --agent-output docs/api/agent-subcommands.md
  ```

- **Per-worktree venv rebuild.** The first `uv run` in a fresh landing
  worktree rebuilds the virtualenv (~40 s + disk). Budget for it; do not
  debug it.

## PR-body contract (PROGRAM.md §5)

Spec Kitty PRs use a fixed body shape; an ad-hoc body (Summary/Changes/Why/…) draws a
squad **MAJOR** and blocks merge even when the diff is perfect. The fleet squad validates
the body with `bin/validate-pr-body.py`. Exactly five sections, in order:

- `## Issue` — must carry a `closes #<n>` link. If no tracking issue exists, **file/claim
  one first** (a docs-gap issue counts), name the branch `issue-<n>-<slug>` (not a bare
  `docs/<slug>`), and align the PR title to the `[#<n>] …` form.
- `## Change` — what changed and why.
- `## Tests run` — must contain a nested `Self-review:` block, and every recorded command
  must be **runnable verbatim** (full `tests/…` / `docs/…` paths; invoke doc scripts as
  `uv run python -m scripts.docs.<x>`, never the bare `scripts/docs/<x>.py` path, which
  fails `ModuleNotFoundError: scripts`).
- `## Blast radius` — a `Discovery:` line (the git-grep command) plus `Files:` (paths
  re-derived from a fresh run of it).
- `## Deferred` — anything intentionally left for follow-up.

Validate locally before opening: `bin/validate-pr-body.py` must exit 0 (also with
`--verify-discovery --expected-head <sha>`). Note the description-length SEO gate
(50–180 chars) is **CI-only** — run `scripts/docs/description_length_check.py` (or the
docs SEO tests) as part of any docs blast radius.

## See also

- [Review gates: pre-PR / pre-review checklist](review-gates.md) — the
  contributor-side hygiene this runbook assumes.
- [Test-flakiness handling policy](../testing/testing-flakiness.md) — the
  never-retry-to-green rule and budget-gate tuning.
- [Guides index](../../guides/index.md)
