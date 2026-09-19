---
title: 'Onboarding Run: Priming a Co-Maintainer Mission Session'
description: 'A reusable priming prompt and 12-step cadence for running a full Spec-Driven Development mission the way this team runs them — for onboarding prospective co-maintainers.'
doc_status: active
updated: '2026-08-15'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/reference/known-friction-points.md
- docs/development/how-to/pr-landing.md
- docs/development/contributing.md
- docs/development/testing/testing-parallel.md
- docs/development/testing/testing-flakiness.md
- docs/development/reference/quality-and-tech-debt-standing-orders.md
---
# Onboarding Run: Priming a Co-Maintainer Mission Session

This page is a **reusable priming prompt** for a prospective co-maintainer's AI
session (Claude Code + Spec Kitty). It encodes the team's standard Spec-Driven
Development (SDD) cadence — spec → plan → tasks → draft PR — with the adversarial
squad checkpoints and operator-led architecture gates baked in, so an onboarding
run teaches the *why*, not just the sequence.

## How to use it

1. Copy the prompt block below into the co-maintainer's session.
2. Fill in the **`## The mission`** block with the specific work (problem,
   starting design intent, where the evidence lives, hard constraints). Leave the
   architecture *unlocked* — it is decided with the operator at step 2.
3. Point them at [Known current friction points](../reference/known-friction-points.md) as
   required pre-reading — that page is the fast-drifting companion to this durable
   cadence, and the prompt below references it by path rather than inlining it (so
   the gotchas stay current without re-issuing the prompt).

The cadence itself is stable; the friction list is not. Keeping them in separate
pages is deliberate.

## The priming prompt

````text
# Onboarding mission — Spec Kitty co-maintainer run

You are running a full Spec-Driven Development (SDD) mission end-to-end, the way
this team runs them. This is an ONBOARDING run: work deliberately, explain your
reasoning at each gate, and PAUSE for operator review at the checkpoints marked 🛑.
The operator leads architecture decisions and is the ONLY one who merges to
origin/main — you never do.

## 0. Orient before you touch anything (non-negotiable)
- Read the project charter FIRST: `.kittify/charter/charter.md`, then load
  action-scoped doctrine as you go via `spec-kitty charter context --action <name>`.
- Read `CLAUDE.md`, `docs/development/pr-landing.md` (maintainer runbook),
  `docs/development/known-friction-points.md` (REQUIRED — the current gotchas),
  `CONTRIBUTING.md`, `docs/development/testing/testing-parallel.md`, and
  `docs/development/testing/testing-flakiness.md`.
- Terminology canon: it's a **Mission**, never a "feature". Run the terminology
  guard before pushing any prose/doctrine:
  `pytest tests/architectural/test_no_legacy_terminology.py`.
- Git law: `origin` = your fork, `upstream` = Priivacy-ai. NEVER `git push origin
  main`. All shared changes go through a draft PR. `spec-kitty merge` is LOCAL only;
  the operator merges to origin/main.

## Known current friction points
Read `docs/development/known-friction-points.md` BEFORE you start — it is the
fast-drifting list of current repo/tooling gotchas you WILL hit: red-main
attribution, CI-environment false reds, stale-install reds, real-port/daemon
leakage (`-n0`), `uv run` in lanes, the CI-only gates that fail ~40 min late, the
status-daemon auto-commit, no `git stash` in lane worktrees, and more. Treat it as
required pre-reading and re-verify anything version- or issue-specific against the
tracker.

## The mission
<REPLACE THIS BLOCK for the specific run. One or two paragraphs: state the problem,
the STARTING design intent if any, WHERE the evidence/context lives (issue #, PR #,
prior squad review, design doc), and any hard constraints. Leave the architecture
UNLOCKED — it is decided WITH the operator in step 2, not asserted here.>

## The cadence — follow in order, pause at 🛑

1. **Branch off main.** Reuse one mission clone; create a fresh branch off
   `upstream/main`: `git fetch upstream main && git checkout -b kitty/<mission-slug>
   upstream/main`. One mission per checkout — never race two missions on one tree.

2. **Pre-spec research squad → operator-led architecture run.** Deploy a bounded,
   PROFILE-LOADED adversarial squad (load the actual profile YAML for each lens, not
   a persona name; give any agent that touches a branch/PR `isolation: worktree`).
   Cover four lenses: (a) alignment to planned architecture, (b) risks, (c)
   integration points, (d) related/foldable issues. Synthesize their findings into a
   short options memo. 🛑 Then convene the ARCHITECTURE run WITH the operator —
   present the options, do NOT unilaterally lock the design. Wait for the operator's
   architectural call before speccing.

3. **Ensure latest-HEAD Spec Kitty is installed and active.** From the repo,
   editable-install your working tree so the `spec-kitty` CLI reflects HEAD:
   `uv pip install -e .` (or `pip install -e .`), then `spec-kitty upgrade` to
   regenerate agent commands/skills, and verify: `spec-kitty --version` +
   `spec-kitty doctor`. Re-run this after ANY rebase — a stale install produces false
   reds on commands that shell out to `spec-kitty`.

4. **Spec the mission.** Run `/spec-kitty.specify` inside your coding agent session
   (it is a slash command, not a shell command). Answer the discovery interview
   honestly (it refuses to proceed until the question set is answered). The spec lands
   in `kitty-specs/<mission>/`. Encode the operator's architecture decision as
   constraints/FRs. Seed the 3 mission tracer files.

5. **Post-spec squad.** Bounded profile-loaded adversarial pass: anti-laziness,
   scope-vs-intent, ambiguity/underspecification, testability of acceptance criteria.
   Fold MAJORs into the spec. 🛑 Operator review of the spec.

6. **Plan.** Run `/spec-kitty.plan`. Architecture, data flow, risks, integration
   points — consistent with the locked design.

7. **Post-plan squad (brownfield checks).** Foldable-issue check, split-brain / LOC /
   duplication check, deprecation & canonical-source check, undersizing check. The
   pre-flight squad cadence catches undersizing 4–5×. Fold findings into the plan.

8. **Commit and push to fork.** Commit the planning artifacts; push the branch to
   `origin` (your fork). The draft PR comes at step 12, but pushing early keeps a
   backup and a visible trail. Never to origin/main.

9. **Rebase onto latest upstream/main + drift check.** `git fetch upstream main &&
   git rebase upstream/main`. Re-install editable (step 3). Then CHECK whether recent
   upstream changes impact the planned approach — new seams, moved canonical sources,
   changed contracts. If they do, revise the plan (and flag the operator) before
   tasking. Don't rebase/switch a tree while a background test run is using it.

10. **Tasks.** Run `/spec-kitty.tasks` (outline → packages), then `spec-kitty agent
    mission finalize-tasks` (validates deps, writes lane metadata). Post-tasks
    adversarial squad: verify WP-decomposition claims against the code, census Sonar
    attack-vectors in touched files, per-WP campsite scope. Verify the issue-matrix
    after finalize (see the friction-points page).

11. **Full e2e run.** Full suite green on the rebased tip — this is where CI-only
    arch gates surface locally. Run `PWHEADLESS=1 pytest tests/ -n auto --dist
    loadfile` (daemon/real-port tests separately with `-n0`), plus
    `tests/architectural/`, `ruff check .`, `mypy`, the terminology guard, and
    docs-freshness. Any UI claim needs Playwright proof, never API-response
    inference. Classify every red into PR-defect / contract-crossed /
    pre-existing-main / flake — never retry-to-green.

12. **Draft PR + self-review.** Open a DRAFT PR from the mission branch
    (`gh pr create --draft`). Write a readable PR per DIRECTIVE_046 (what / why /
    verification; call out any remaining Sonar or UI work). Run the
    mission-wrap-up-sequence procedure. Then SELF-REVIEW with a fresh squad lens
    (architect + reviewer) over the aggregate diff and synthesize a LAND/HOLD verdict
    for the operator. 🛑 Hand off — the operator merges. You never run `gh pr merge`.

## Discipline that applies at every step
- Squads are BOUNDED and PROFILE-LOADED (load the YAML; delegations LOAD the profile,
  never a persona name). implement=sonnet, review=opus; match the Agent model to the
  profile identity.
- Any agent touching the PR/branch runs in `isolation: worktree`.
- In a lane/clone, always `uv run <cmd>` — bare `python`/`pytest` imports the PRIMARY
  src, not your lane.
- Red-first for any bugfix element: prove the test reds through the real entry point
  BEFORE the fix. Live evidence over "looks fixed".
- Realistic, production-shaped test data. Every new branch/helper gets a focused test
  in the same PR. Campsite-clean surfaces you touch before you change them.
- When a canonical command/template/surface looks missing or broken, trace the source
  and file an upstream gap — never improvise a workaround.

Start with step 0, then step 1. At each 🛑 checkpoint, stop and summarize for the
operator before proceeding.
````

## See also

- [Known current friction points](../reference/known-friction-points.md) — the fast-drifting
  companion this prompt references.
- [Landing contributor PRs](../how-to/pr-landing.md) — the maintainer landing runbook the
  cadence hands off into.
- [Quality & tech-debt standing orders](../reference/quality-and-tech-debt-standing-orders.md).
- [`mission-wrap-up-sequence` procedure](../../../packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml)
  and [DIRECTIVE_046](../../../packs/built-in/directives/046-readable-consistent-prs.directive.yaml) — the
  canonical close-out sequence and readable/consistent-PR standard step 12 of the cadence follows.
