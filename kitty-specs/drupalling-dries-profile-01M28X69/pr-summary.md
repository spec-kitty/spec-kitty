<!--
Rendered copy of this file goes in the GitHub PR body.
Everything below the marker is the PR body verbatim.
-->

## Summary

- Adds **Drupalling Dries**, a Drupal-specialist implementer agent profile, so Drupal work packages route to an implementer that already knows the framework's conventions instead of a generic one that has to be coached on every task.
- Ships the full specialist package the other stack profiles use: profile + DRG lineage, two styleguides carrying all fourteen community "never do this" anti-patterns, and a review-checks toolguide.
- Ships **inactive**. Nothing changes for an existing project until an operator runs `spec-kitty charter activate agent-profile drupalling-dries`.

## Why Now

- The built-in roster has stack specialists for Java, Python, Node and browser frontend, but none for Drupal. A Drupal work package could only be routed to a generic implementer or a wrong-stack specialist, so module structure, dependency injection, the Entity API, configuration management and Drupal's three PHPUnit tiers had to be re-explained per task, and mistakes surfaced in review rather than being avoided.
- A usable community source became available — amazee.io's `drupal-agents-md` — making it possible to build the profile from distilled domain material rather than from scratch.

## What This PR Does

**New profile**

- `packs/built-in/agent_profiles/drupalling-dries.agent.yaml` — implementer-role specialist for Drupal 10.x/11.x on PHP 8.3+. Declares backend competence (modules, services/DI, Entity API, plugins, hooks, Forms API, routing, configuration management, Batch/Queue/Migration) and Drupal-native theming (Twig, `*.libraries.yml`, `Drupal.behaviors`, render arrays, preprocess). Carries a ten-step self-review protocol and six directive / four tactic references.
- Registered in both shipped-profile README tables, which `tests/doctrine/test_shipped_profiles.py` asserts against a filesystem-derived inventory.

**New guidance artifacts**

- `drupal-conventions.styleguide.yaml` — "how do I write this?" Positive patterns plus nine of the source's anti-patterns, each a paired wrong/right example.
- `drupal-security-performance.styleguide.yaml` — "how do I keep it safe and fast?" Output escaping, entity-query access checks, cacheability metadata, credential hygiene, query efficiency, plus the remaining five anti-patterns.
- `DRUPAL_REVIEW_CHECKS.md` + `drupal-review-checks.toolguide.yaml` — the phpcs / phpstan / drupal-check / composer audit / PHPUnit commands a reviewer should expect, with guidance on choosing a test tier. No analysis level, coverage percentage or mutation score is asserted; the source specifies none and inventing one would present a fabrication as guidance.

**Change to an existing profile**

- `frontend-freddy.agent.yaml` — **two fields**. `avoidance-boundary` gains a clause deferring Drupal-native theming to Drupalling Dries. `initialization-declaration` previously asserted "if it runs in a user's browser, it is my concern" and named only the Node Norris and Designer Dagmar deferrals, which the new boundary contradicted (`Drupal.behaviors` runs in a browser); it now names the Dries deferral too.

**Lineage**

- `src/charter/offering/drg/migration/extractor.py` — one `_CURATED_ARTIFACT_EDGES` entry (5 lines) minting `drupalling-dries --specializes_from--> implementer-ivan`. Built-in profile lineage lives in that table; the per-profile `specializes-from` field was retired and is rejected by the model.

**Tests**

- Three new files covering profile load (including a fixture-based negative case proving a malformed profile is reported, not swallowed), lineage/edge resolution and DAG acyclicity, and artifact presence with the required `suggests` edges.
- Two consequential updates: the curated-lineage count moves 4 → 5 specialists, and the context-sources golden-diff test gains a ledger entry for the eleven new edges. That test asserts strict equality, so an unledgered edge still fails.

**Mechanically regenerated — not hand-edited**

- `packs/built-in/agent_profile.graph.yaml`, `styleguide.graph.yaml`, `toolguide.graph.yaml` and `pack-manifest.yaml` are output of `spec-kitty doctrine regenerate-graph`. The delta is 4 nodes and 14 edges with no removals. Reviewers can regenerate and diff rather than reading these by hand.

No formatting-only churn is included: the one unrelated file that had ridden the branch (`.kittify/command-skills-manifest.json`, CLI upgrade version stamps) was reverted before submission.

## Effect on Existing Projects

- **Runtime / compatibility:** No behavioural change for any existing project. The profile ships inactive; a project that has not activated it renders byte-identical governance context (verified: same md5 before and after, zero Drupal references in the rendered context). No new runtime dependency — `pyproject.toml` and `uv.lock` are unchanged.
- **Upgrade / migration:** None required. Adoption is opt-in via `spec-kitty charter activate agent-profile drupalling-dries`.
- **Operator / reviewer impact:** A project already using Frontend Freddy sees Freddy's declared scope narrow: Drupal-native theming now defers to Drupalling Dries. For a non-Drupal project this changes nothing in practice. Built-in profile count goes 25 → 26.

## Validation

- [x] Relevant tests pass locally or in CI
- [x] Backward compatibility impact considered
- [x] Follow-up work called out if intentionally deferred

Run locally on this branch:

- `pytest tests/doctrine/` — 3182 passed, 13 skipped
- `pytest tests/charter/` — 2830 passed, 22 skipped
- `pytest tests/doctrine/agent_profiles/ tests/doctrine/styleguides/ tests/doctrine/toolguides/ tests/doctrine/drg/` — 819 passed
- `pytest tests/architectural/test_no_legacy_terminology.py` — 90 passed
- `spec-kitty doctrine regenerate-graph --check` — fresh
- `spec-kitty doctor doctrine --json` — 26/26 valid, 0 skipped
- `git diff --stat main -- pyproject.toml uv.lock` — empty (no new dependencies)

Known pre-existing, reproduces on `main`, unrelated to this diff: `tests/doctrine/test_packaging_parity.py` errors because `python -m build` is absent from the local venv.

Not re-run on the final branch: `ruff check` / `ruff format --check` — `ruff` was not resolvable in the venv at submission time. The six Python files in the diff passed `ruff check` earlier on byte-identical content and no Python has changed since; CI is the authoritative check.

## Tickets / Contracts

- No tracker issue — contributed directly. Maintainers may wish to open one retroactively, per the "discuss large changes first" note in `contributing.md`.

## Mission Artifacts

- **Spec:** `kitty-specs/drupalling-dries-profile-01M28X69/spec.md`
- **Plan:** `kitty-specs/drupalling-dries-profile-01M28X69/plan.md`
- **Research:** `kitty-specs/drupalling-dries-profile-01M28X69/research.md`
- **Review:** `kitty-specs/drupalling-dries-profile-01M28X69/verification-report.md` (and per-WP `tasks/WP*/review-cycle-*.md`)
- **PR summary:** `kitty-specs/drupalling-dries-profile-01M28X69/pr-summary.md`

## Follow-ups

- **Report the upstream error to amazee.io.** `drupal-agents-md` states at line 701 that `accessCheck(TRUE)` is "required from Drupal 10.2" and "will be required in Drupal 12". Per change record https://www.drupal.org/node/3201242, implicit access checking was deprecated in **9.2.0** and throws from **10.0.0** — on Drupal 10/11 an unchecked entity query already fatals. This PR ships the corrected facts plus an inline annotation naming the divergence so a later fidelity audit does not restore the error.
- **Contract text worth tidying in a later pass:** mission contract clause C-S2 names a single styleguide as carrying all fourteen anti-patterns while C-S3 mandates the two-file split, so the clause as literally written was unsatisfiable alongside its neighbour. The delivered 9/5 split satisfies the intent; the wording was not corrected here.
- **Acceptance matrix scope:** `acceptance-matrix.json` carries rows for the thirteen functional requirements only, not for the non-functional requirements or constraints. Not an overstatement — the evidence for those lives in `verification-report.md` — but the matrix is narrower than the requirement set.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01UbXVMhaxRzqbuzJB8n5fjL
