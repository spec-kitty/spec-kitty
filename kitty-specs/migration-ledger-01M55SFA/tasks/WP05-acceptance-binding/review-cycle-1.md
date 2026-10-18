---
affected_files: []
cycle_number: 1
mission_slug: migration-ledger-01M55SFA
reproduction_command: spec-kitty agent tasks move-task WP05 --to approved --mission migration-ledger-01M55SFA --agent reviewer-renata
reviewed_at: '2026-10-18T08:02:34Z'
reviewer_agent: reviewer-renata
wp_id: WP05
---

Approved by reviewer-renata: approval:WP05

# WP05 — Acceptance Binding (Cucumber-JVM) — Review Cycle 1

**Reviewer:** reviewer-renata
**Verdict:** APPROVE
**Owned surface reviewed:** `tests/scenarios/upgrade/migration-ledger.feature`,
`acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java`,
`acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java`
**WP05 commits:** `fbb759432c` (initial binding), `d5d699f67c` (finding-2 re-author)

## Checks

1. **T027 rebind + @wip lift — PASS.** Exactly 3 `When` lines rebound to
   `spec-kitty migrate ledger` (was 1× `upgrade --list-applied` + 2× `doctor
   migrations`); `grep -c '"spec-kitty migrate ledger"'` = 3. All `@wip` tags
   lifted (0 remain). 9 scenarios, all gating. The 2 pre-existing gating
   scenarios ("Upgrading a project that is already current changes nothing", "A
   tracked refresh … is not redone") are untouched by the diff. Footer read-
   surface note names `migrate ledger`. Scenario prose stays consumer-language
   ("setup steps", "local git setup") — no "ledger"/"migration internals" leak.

2. **T028/T029 bindings — PASS.** 4 new `@Given` in ArrangeSteps + 6 new `@Then`
   in AssertSteps, convention-correct (Given=Arrange, Then=Assert). No duplicate
   or ambiguous step text across the step files (`uniq -d` over all
   `@Given/@Then/@When` = empty). Clean Java recompile:
   `gradle compileTestJava --offline --rerun-tasks` → BUILD SUCCESSFUL. All
   required imports present. Arrange steps fail-fast on a broken fixture
   (assert their own seeded precondition), so a fixture error never reads as a
   product pass.

3. **FINDING-2 RE-AUTHOR IS ADR-FAITHFUL — PASS (key integrity check).**
   - (a) The clone `Given` (`aFreshlyPulledCloneMissingItsLocalGitSetup`) seeds a
     GENUINE fresh-clone state: it runs `upgrade --yes`, commits the shared
     records, then `deleteRelative(".kittify/migrations/clone-local.jsonl")`
     (the git-ignored per-clone ledger that never travels with a pull) AND
     `removeCloneLocalSetup()` (strips the `.spec-kitty/` `info/exclude` effect).
     The tracked ledger `.kittify/migration-ledger.jsonl` is left intact, so the
     shared records still show the project's setup ran. NO fabricated
     `skipped`/success per-clone record — the forbidden green-wash is absent.
   - (b) The new `@Then` asserts the REAL design signal:
     `.contains("(clone-local): not yet applied")`. Verified against the product
     renderer (`migrate_cmd.py::_print_ledger_summary`, line
     `{step['id']} [dim]({step['partition']})[/dim]: {label}`): partition literal
     is `clone-local` (`ledger.py` `_PARTITION_CLONE_LOCAL = "clone-local"`), and
     `_ledger_step_state` returns `_STATE_PENDING` → `"not yet applied"` when
     `not row.applied`. A genuine fresh clone has no per-clone record, so
     `assemble_report` sets `applied=False` → pending, partition clone-local.
     The non-TTY subprocess capture drops rich markup and `flowed()` normalizes
     whitespace, so the literal `(clone-local): not yet applied` is produced.
     This is the no-dual-write design's real output, not a faked state.
   - (c) The old `@Then` binding (`theReportShowsALocalOnlySetupRecordedElsewhere`,
     "recorded elsewhere but not here") was REMOVED (renamed), leaving no dead
     glue; no source feature/step references the retired text (the one grep hit
     is a stale `build/` allure artifact from a prior run). The product token
     `_STATE_RECORDED_ELSEWHERE` in `migrate_cmd.py` was NOT touched — it remains
     valid for the distinct real state `applied=True AND in_place_here=False`.
     WP05 touched no product code at all.

4. **Scenario-contract gate — PASS (SC-007).**
   `PWHEADLESS=1 PYTHONPATH=$PWD/src .venv/bin/python -m pytest
   tests/architectural/test_scenario_contract.py -q` → **41 passed** in 0.67s.
   All 9 scenarios bound/gating. Java compiles clean.

5. **Finding-1 reds correctly ISOLATED — PASS.** The 5 remaining feature reds
   are the upgrade non-idempotency scenarios, each terminating on a PRE-EXISTING
   step (`the repository has no new commits` / `the file "…" is unchanged` / `the
   working tree has no uncommitted changes`) — none of them a WP05-authored step.
   Scenario A ("A teammate's clone gets its own local git setup") and scenario C
   ("The report tells me a local-only step is not yet in place") terminate on
   genuine WP05 assertions and PASS. No WP05-authored step is a tautology or
   swallows an exception, so none masks a failure or falsely passes. The
   characterization is sound; the idempotency defect is a WP01/WP02 ledger
   concern deferred to closeout remediation, not a WP05 blocker.

## Anti-pattern checklist

1. Dead code — PASS (all 10 step methods bound to feature steps; all private
   helpers have live callers).
2. Synthetic-fixture test — PASS (steps drive the real CLI and observe real git
   state; delete the product and the scenarios fail).
3. Silent empty return — PASS (IO helpers fail closed via `UncheckedIOException`;
   `cloneLocalSetupInPlace()` returning false encodes a meaningful state).
4. FR coverage — PASS (FR-015 acceptance binding realized; SC-007 gate green).
5. Frozen surface — PASS (only the 3 owned test files touched; no product code).
6. Locked decision — PASS (no-dual-write / genuine-fresh-clone design honored; no
   fabricated record).

## Tests run
- `pytest tests/architectural/test_scenario_contract.py -q` → 41 passed.
- `gradle compileTestJava --offline --rerun-tasks` → BUILD SUCCESSFUL.
- Live acceptance gating pass NOT run: the gating task sweeps the whole
  `../tests/scenarios` tree with real subprocess upgrades (a heavy suite, not
  targetable to this one feature), which the mission test discipline forbids.
  Finding-1 isolation confirmed by static feature/binding analysis instead.
