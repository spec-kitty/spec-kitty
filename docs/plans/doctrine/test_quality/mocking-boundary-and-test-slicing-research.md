---
title: "Test Slicing & Mocking-Boundary Discipline — Research Findings"
description: "Research for refining Spec Kitty's test-boundary doctrine after #2934, covering functional slicing, internal mocks, and outcome assertions."
doc_status: draft
updated: '2026-07-26'
related:
- docs/plans/doctrine/README.md
---
# Test Slicing & Mocking-Boundary Discipline — Research Findings

**Author:** Research squad (5 parallel researchers) + synthesis
**Date:** 2026-07-26
**Feeds:** [#2935](https://github.com/Priivacy-ai/spec-kitty/issues/2935) (doctrine artefact authoring) and the test-friction epic
**Motivating incident:** [#2934](https://github.com/Priivacy-ai/spec-kitty/issues/2934) — a P0 "data-loss" that was a test-quality false alarm
**Landed alongside:** PR #2936 (de-mocked the friction test; made the merge review-readiness check side-effect-free)

---

## 1. Purpose and scope

This note collects the research basis for a **binding doctrine artefact** on test
slicing/scoping and mocking antipatterns. It is not the artefact itself — it is the
evidence and synthesis a curator will compile into a doctrine `tactic`/`directive`
under `src/doctrine/` (see §8, Recommendations).

The operator direction being formalised (verbatim):

> We should never mock out internal code. Mocks/Stubs are only sensible on the
> boundaries of the system under test (its responsibility border). Everything that
> is owned within the system under test is to be executed.
>
> Acceptable mocks:
> - entry to a different domain (domain contract tests)
> - filesystem interaction
> - database interaction
> - system logic (when testing simple DTO validation / hook sends) → rare

### 1.1 Why this is worth doctrine, not just a review comment

**Incident #2934.** A regression test mocked `_mark_wp_merged_done` /
`_assert_merged_wps_reached_done` — **internal merge-subsystem logic** — to "pin the
call-contract". That stub manufactured a mission with **zero status events**, a state
the successful approved-to-done closeout path represented by the test cannot produce.
With done-marking stubbed, `status.events.jsonl`
was never written; a downstream existence-filter (correctly) dropped the absent event
log; and the committed-path assertion failed against a scenario **only the mock could
create**. Hours of "data-loss" investigation for a test asserting its own stub. The fix
was to run the real pipeline and mock only genuine boundaries — zero production change
was required to make the test pass.

The lesson is general and recurrent enough to bind as doctrine: **mocking internal
system-under-test logic couples the test to an implementation shape and can manufacture
impossible states, producing false alarms (and, symmetrically, false confidence).**

---

## 2. The rule (synthesised)

**Never mock code the system under test owns. Stubs/mocks are legitimate _only at the
responsibility border_ — the point where control genuinely leaves the system. Everything
inside that border executes for real, and assertions target observable outcomes, not
stub call-args.**

**Acceptable mock seams (exhaustive):**

| Seam | Source anchor |
| ---- | ------------- |
| Entry to a **different domain** (domain-contract tests) | "external services" — _Clear Test Boundaries_, step 3 |
| **Filesystem** interaction | "externals, such as … the file system" — _Clear Test Boundaries_, step 4 |
| **Database** interaction | "data access layers" — _Clear Test Boundaries_, step 3; `UserDatabaseProxy` in the case study |
| **System logic** (rare — simple DTO validation / hook sends) | "components that are not directly related to the functionality being tested" — _Clear Test Boundaries_, step 3 |

**The antipattern:** mocking an internal helper/collaborator that belongs to the same
responsibility as the unit under test — typically to assert on _how_ it was called
(`assert_called_once()`, call-arg pinning) rather than on _what the system produced_.

---

## 3. Source-by-source synthesis

Each source is the operator's canon (`patterns.sddevelopment.be`) except Test Desiderata
(Kent Beck). Faithfulness notes and honest counterpoints are carried through from the
researchers in §7.

### 3.1 Clear Test Boundaries — the primary operative rule

_Stijn Dejongh, patterns.sddevelopment.be/practices/define_test_boundaries/ (2024)._ This
is the **most load-bearing** source: it states the mock/stub-scope rule directly and
carries a worked before/after example structurally identical to #2934.

Core prescription:

> Based on the functionality you are looking to validate, adjust your test boundary to
> contain only the components that are responsible for supplying said functionality.

The binary rule:

> Do not stub or mock components that are part of the system module being tested.

> Stub or mock external services, data access layers, or other components that are not
> directly related to the functionality being tested.

The boundary is **functional, not structural** — drawn by responsibility, not by layer,
module, or class:

> Define the scope of a 'unit under test' based on the responsibility and functionality
> it provides rather than strictly adhering to structural boundaries such as layers or
> modules.

Structural conventions are explicitly listed as **deterrents**: "Each layer should be
tested in isolation." and "Each function should have its own test." are named as
conventions to avoid.

**The case study (the #2934 twin).** A `UserRegistrationAPITest` mocked
`UserBusinessService` — an _internal_ collaborator in the same functional slice — and
asserted `verify(userService, times(1)).createUser(...)` (a call was made, not that
registration produced correct state). Adding a Captcha step "broke most of the tests …
written at the API level," requiring re-stubbing and eroding "the team's confidence in
the system's validity." The fix re-scoped around the full functional slice
(`UserRegistrationTest`), mocking **only** `UserDatabaseProxy` (the genuine persistence
boundary), letting `UserBusinessService` and `EmailValidationService` run for real, and
moving assertions to real outcomes (`assertThat(response)…isEqualTo(RegistrationStatus.CREATED)`).

Its own over-mocking guardrail:

> Teams without strong test doubles can over-mock collaborators and recreate brittleness;
> invest in tooling and coaching so substitutes represent behaviour, not implementation
> detail.

### 3.2 The Testing Pyramid — why level choice avoids mocking internals

_Stijn Dejongh, patterns.sddevelopment.be/concepts/testing_pyramid/ (2023)._ Provides the
taxonomy that explains _why_ a well-chosen test level removes the need to mock internals.

- A well-scoped **unit test** is defined by "**minimizing the need for external
  functionality stubbing/mocking**" — i.e., if you need a mock to make a unit test pass,
  the boundary is misdrawn, not a green light to add a mock.
- **Acceptance tests**: "external interactions are stubbed out, **but internal code is
  used**" — "internal" is never a legitimate stub target, even one level up.
- **Integration tests** exist for the external boundary and should be limited: "It's
  advisable to limit the use of integration tests to specific cases."

**Footnote 2 — the single most quotable justification for "don't mock internals":**

> Being too strict in your definition of 'Unit Tests' can lead to difficult-to-maintain
> code, as it commonly pushes people towards structural testing (i.e. verifying a certain
> method calls another method). This will make future refactoring and restructuring a lot
> more difficult. In general, **write your tests as if you are unaware of the internal
> structure of your code.** If you decide to extract part of the functionality in a class
> to a composite object (helper class), there should be no effect on your test suite.

### 3.3 Connascence — the theoretical backbone

_Nicholas Ocket & Stijn Dejongh, patterns.sddevelopment.be/concepts/connascence/ (2025)._
Gives the precise vocabulary for _why_ internal mocking is harmful coupling.

Definition (Page-Jones, quoted on-page):

> Two elements are connascent if a change to one element would also force a change to the
> other in order for the program to be correct.

Coupling is assessed by **strength**, **degree**, and **locality** (the same strength is
more tolerable at high locality, more dangerous when it crosses a boundary).

**The core move:** a mock of an internal collaborator does not remove coupling — it
_relocates and manufactures_ it. A stub encoding "when called with X, return Y" is a
second, hand-authored copy of the collaborator's contract (Connascence of **Algorithm**),
kept in agreement by discipline alone, with no compiler or runtime check forcing the
match.

The #2934-shape assertion (`assert marked_wps == [...]`, `assert_called_once()`) stacks
several forms **at low locality** (test tree ↔ private implementation several frames deep):

- **Connascence of Name** — hard-codes the internal method name; a pure rename breaks the
  test though the system is unchanged.
- **Connascence of Position / Meaning** — asserts on literal call-argument shape/meaning,
  binding the test to an internal signature that was never a contract.
- **Connascence of Algorithm** — asserts _how_ the result was computed (which collaborator,
  how many times), not _what_ was produced.
- **Connascence of Execution** (dynamic) — pins invocation count/order of internal
  orchestration.

**"Run the real code, assert on outcomes" is literal connascence minimisation:** it
eliminates Name/Position/Algorithm/Execution coupling across the test↔internals boundary
entirely, leaving at most **Connascence of Meaning at the system's actual public
boundary** — the only coupling a test should legitimately carry, at the shortest possible
locality.

One-line framing for the artefact (the site's own "instead of X, say Y" style):

> This test has connascence of name, position, and algorithm with the internal
> implementation of `mark_wps`, at very low locality — the test lives outside the module
> and pins a private call shape that isn't the system's contract. Assert on the persisted
> outcome instead, which reduces the remaining coupling to connascence of meaning at the
> system's actual public boundary.

### 3.4 Test Desiderata (Kent Beck) — the property-level backing

_Kent Beck, testdesiderata.com._ The 12 properties of a good test. **Important
faithfulness note:** the source never mentions mocking/test-doubles — the mapping below is
the _correct application_ of Beck's properties, not a Beck quote.

- **Predictive** — "if the tests all pass, then the code under test should be suitable for
  production." Mocking internal logic tests a fictional pipeline; it can pass while
  production is broken, or alarm while production is fine (exactly #2934). This is the
  property most damaged.
- **Specific** — "if a test fails, the cause of the failure should be obvious." With an
  internal mock, a failure signals "the stub's contract diverged," not "production broke" —
  false specificity.
- **Structure-insensitive** — "tests should not change their result if the structure of the
  code changes." Anything the SUT owns is internal _structure_; reaching in to stub it
  couples the test to structure — a near-direct violation.
- **Behavioral** — "tests should be sensitive to changes in the behavior of the code under
  test." A mocked-out internal is a mechanism the test no longer exercises; a real
  regression there can ship silently.
- **Composable** — Beck's own resolution to "Fast vs. Predictive" is _not_ "mock the
  internals to go faster" — it is "test different dimensions of variability separately and
  combine." That maps directly onto boundary-only mocking: keep the internal pipeline real
  (predictive/behavioral) on one axis; vary genuine external boundaries on a separate axis.
- **Terminology trap to name explicitly:** Beck's **Isolated** means test-run order/state
  independence — it does **not** mean "isolate the unit from its collaborators via mocks."
  Conflating the two is the most common justification for over-mocking and should be called
  out in the artefact.

### 3.5 Clean Code — supporting framing (by extension only)

_Stijn Dejongh, patterns.sddevelopment.be/concepts/clean-code/._ **Faithfulness note:** this
page is silent on testing (no FIRST principles, no test-double guidance; the words
"coupling", "single responsibility", and "test" do not appear). Cite it only by extension.

- "a program should be written for people to read—and only incidentally for machines to
  execute" (Schildt, cited on-page) → a test's job is to communicate what the system does;
  a test asserting a mock artifact communicates about the mock, not the system.
- "If your code requires you to hold a lot of this knowledge just to be able to understand
  what is going on, it is probably not very well written" → a test requiring the reader to
  track which internals were stubbed and what fabricated values they return forces exactly
  that extraneous context.
- "Avoid Gold Plating: write readable code that is as well-designed as it needs to be at
  this point in time" → supports the _rare_ system-logic exception (full-fidelity execution
  of trivial DTO/hook logic would be gold-plating), but the artefact must pre-empt the
  misread that this justifies broad internal mocking on cost grounds.

---

## 4. The remediation recipe

Drawn from _Clear Test Boundaries_ and the #2934 fix:

1. **Identify the functionality under test, not the class under test.** Scope is derived
   from the feature; the boundary encloses however many collaborators jointly deliver it.
2. **Draw the responsibility boundary around everything that co-owns that functionality**,
   explicitly including collaborators that traditionally sit "in another layer."
3. **Re-classify each existing mock.** Keep it only if the collaborator is genuinely
   external (other domain / filesystem / DB / rare side-channel). If it is part of the
   slice, un-mock it and let it run for real — seeding real state as a finished mission
   would have (the #2934 fix seeds WPs to `approved` via the real status-emit pipeline).
4. **Move assertions from interaction-verification to outcome-verification.** Replace
   `verify(...times(1))` / `assert_called_once()` / call-arg pinning with assertions on
   persisted or returned state (a DB row, a return value, a written file). Once internals
   run for real, no manufactured state remains to assert against — only production-reachable
   outcomes exist.
5. **Budget for the adoption cost.** _Clear Test Boundaries_ names it honestly: decreased
   initial speed, knowledge requirements, possible rework, and resistance to change. The
   payoff is durability under refactor.
6. **Guard against relocating the antipattern to the boundary.** Even boundary mocks must
   represent the real dependency's _behaviour_, not a hand-shaped stand-in that only supports
   the one scenario the author imagined — that is precisely the "manufactures an impossible
   state" failure, one step out.

---

## 5. Worked example — #2934, in the vocabulary above

- **Before (antipattern):** mocks `_mark_wp_merged_done` (internal), asserts
  `marked_wps == ["WP01","WP02"]` and `assert_called_once()`. Connascence of Name +
  Position + Algorithm + Execution at low locality. Manufactures a zero-event mission ⇒
  violates Predictive/Specific/Behavioral. Structural test per Pyramid Footnote 2.
- **After (fix, PR #2936):** runs the real done-marking pipeline; seeds WPs to `approved`
  via the real status-emit pipeline; mocks only boundaries (network side-effects, git
  preflight, the `commit_merge_bookkeeping` git write — spied for its path set); asserts on
  the **persisted** event log (`reduce(read_events(...)).work_packages["WP01"]["lane"] ==
  "done"`) and the requested bookkeeping path set. Passes against unchanged production
  code. The spy does not independently prove target-branch history.
- **Residual production defect found and fixed in the same PR:** the merge review-readiness
  check reduced status via the _writing_ `materialize()` — a gate with a disk-write side
  effect that orphaned a `status.json` with no backing event log. Switched to the read-only
  `materialize_snapshot()`. A gate reads; it does not persist.

---

## 6. Existing project alignment

> **Correction (post-review).** An earlier draft called the mocking-boundary rule
> "currently unwritten." That overclaimed uniqueness. A doctrine overlap audit found the
> rule is **already carried by wired, activatable authority** —
> `styleguide:test-desiderata-and-boundaries`, `tactic:test-boundaries-by-responsibility`,
> `tactic:function-over-form-testing`, `tactic:connascence-analysis`, and the
> `enforcement: required` `directive:DIRECTIVE_041` ("Tests as Scaffold, Not Friction").
> The correct move is **reconcile and extend** that authority, not create parallel doctrine.
> The genuine deltas and the full augment-heavy series live in the companion
> [artefact-series proposal](doctrine-artefact-series-proposal.md), which supersedes §8 below.

- `CLAUDE.md` carries test-quality guidance (Sonar "prefer testable extractions",
  "every new branch/helper needs tests in the same PR"); the doctrine pack carries the
  boundary/desiderata authority above. This work adds only the genuine deltas: the positive
  mock allow-list as a citable rule, the "internal-SUT-logic mock manufactures a
  production-unreachable state" failure mode, an "unfake a test" procedure, and the mindset
  paradigm the rule currently mis-homes inside a directive.
- The charter's Quality & Tech-Debt Standing Orders (adversarial squad cadence, red-first
  discipline) are the natural enforcement surface: the new/augmented artefacts should be a
  **binding lens** the post-tasks / pre-merge squad and reviewers can cite, not advisory prose.

---

## 7. Tensions and counterpoints (stated honestly)

These were flagged by the researchers and must survive into the artefact — an honest rule
is more durable than an overstated one.

1. **Test Desiderata does not literally say "mock only at boundaries."** It never mentions
   mocking. Frame the rule as "the correct application of Beck's Predictive / Specific /
   Structure-insensitive / Behavioral properties," never as a Beck quote. Beck also treats
   unit tests as _deliberately_ trading predictive confidence for speed/writability — a
   conscious, bounded tradeoff, not a blanket ban. The operator's "never mock internal code"
   is a **stronger, narrower policy** than the source mandates — a defensible extension for
   this incident class, and it should be presented as a project _policy choice_, not a
   universal law.
2. **Clean Code is silent on testing.** Use it only for readability/intent framing by
   extension; do not cite it as a testing claim. "Avoid Gold Plating" cuts both ways —
   pre-empt its misuse as a cost-grounds excuse for internal mocking.
3. **Connascence is a diagnostic lens, not a proof.** The page itself: "not a silver
   bullet … does not replace the need for good design principles, testing practices, and
   team communication." The Algorithm-form application to _test_ mocks is a natural but
   slightly extended reading (the "two entities" become production code and its test-authored
   stand-in) — state the extension explicitly.
4. **Removing internal mocks relocates residual risk to runtime.** "Run the real code"
   trades static, refactor-loud coupling for dynamic, runtime-only coupling; it does **not**
   remove the need for genuine integration/contract tests at real boundaries. Connascence of
   **Convention** (implicit shared assumptions) survives internal-mock removal and still needs
   explicit contract definition.
5. **Boundaries are not free and not permanent.** Adoption has real cost (speed, knowledge,
   rework, resistance), and boundary definitions "can fossilise as architecture evolves" —
   the artefact should include a review/re-audit clause and note that functional slicing
   _complements_ (does not replace) contract/component tests.
6. **The `UserRegistration` and Microservices/Database examples are analogical**, not a
   literal case study of test-double misuse — they support the argument; they are not proof
   the sources make this exact claim.

---

## 8. Recommendations for the doctrine artefact (#2935)

> **Superseded.** The single-artefact recommendation below reflected the false-uniqueness
> premise corrected in §6. The authoritative, augment-heavy artefact series (a
> Tests-as-Scaffold paradigm, the `DIRECTIVE_041` disambiguation, checklist→asset moves,
> exemplar assets, and the full DRG edge map) lives in the companion
> [artefact-series proposal](doctrine-artefact-series-proposal.md). The notes below are
> retained only as the source-authority mapping the proposal draws on.

1. **Kind & placement:** a `tactic` (or `directive` — curator's call) in a doctrine
   test-discipline family under `src/doctrine/`, placed per the DRG. **Primary authority:**
   _Clear Test Boundaries_. **Taxonomic backdrop:** _Testing Pyramid_ (esp. Footnote 2).
   **Theoretical backbone:** _Connascence_. **Property backing:** _Test Desiderata_
   (applied, not quoted). **Framing only:** _Clean Code_.
2. **State the rule + the exhaustive allow-list** (§2), plus the **named antipattern**
   ("mocking internal system-under-test logic to pin a call-contract") with #2934 as the
   worked example.
3. **Ship the remediation recipe** (§4) and the interaction-→outcome assertion shift.
4. **Carry the terminology traps explicitly:** Beck's "Isolated" ≠ "isolate via mocks"; the
   Gold-Plating misread; connascence-as-diagnostic-not-proof.
5. **Wire it as a binding lens** for the post-tasks / pre-merge adversarial squad and
   reviewers, not advisory prose.
6. **Verify the live link** for _Clear Test Boundaries_ before publishing (researchers hit
   404s on guessed paths; the working URL is
   `https://patterns.sddevelopment.be/practices/define_test_boundaries/`).

---

## 9. References

- Kent Beck — _Test Desiderata_ — https://testdesiderata.com/ (and the companion Medium
  essays under `@kentbeck_7670`).
- Stijn Dejongh — _Clear Test Boundaries_ —
  https://patterns.sddevelopment.be/practices/define_test_boundaries/
- Stijn Dejongh — _The Testing Pyramid_ —
  https://patterns.sddevelopment.be/concepts/testing_pyramid/
- Nicholas Ocket & Stijn Dejongh — _Connascence_ —
  https://patterns.sddevelopment.be/concepts/connascence/
- Stijn Dejongh — _Clean Code_ —
  https://patterns.sddevelopment.be/concepts/clean-code/
- Meilir Page-Jones — connascence definition (as quoted on the Connascence page).
- Incident & remediation: [#2934](https://github.com/Priivacy-ai/spec-kitty/issues/2934),
  [#2935](https://github.com/Priivacy-ai/spec-kitty/issues/2935), PR #2936.
