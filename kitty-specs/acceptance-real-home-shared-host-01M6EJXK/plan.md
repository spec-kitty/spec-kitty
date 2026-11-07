# Implementation Plan: Acceptance Harness — the "real home stayed clean" guard on a shared host

**Branch**: `issue-7026-acceptance-real-home-shared-host` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/acceptance-real-home-shared-host-01M6EJXK/spec.md`

## Summary

Narrow the acceptance harness's real-home fingerprint to two named, per-mission, content-addressed
runtime-state subtrees (`spec-kitty-prompts/`, `gate-locks/`) **only** when the host is declared
shared (`SPEC_KITTY_ACCEPTANCE_SHARED_HOST`), so a concurrent Mission's writes stop failing a green
scenario (SC-001); keep today's whole-tree comparison as the default and force it on a GitHub Actions
runner regardless of the switch (FR-002, FR-003, SC-003, SC-004); and carry a runtime negative control
that proves on every scenario that a planted leak outside those subtrees still changes the fingerprint
(FR-004, SC-002). Java-only change inside `acceptance-jvm/src/test/java`, plus one docs page and one
changelog fragment.

## Technical Context

**Language/Version**: Java 25 (acceptance-jvm toolchain; `acceptance-jvm/build.gradle`)
**Primary Dependencies**: JUnit Platform + Cucumber-JVM 7 (engine auto-discovery), AssertJ, Allure.
No new dependency is added — deliberately, so `gradle/verification-metadata.xml` stays untouched.
**Storage**: filesystem only — the fingerprint walks `~/.spec-kitty` and a synthetic tree under the
scenario's temp root.
**Testing**: the acceptance suite itself is the entry point (`gradle -p acceptance-jvm test
--no-daemon -Pacceptance.pass=gating`, nightly on Linux/macOS/Windows by
`.github/workflows/ci-nightly.yml`); the non-vacuity control lives in the harness and runs inside
every scenario. No per-PR JVM lane exists (recorded in [research.md](research.md), decision 4).
**Target Platform**: Linux, macOS, Windows (the three nightly legs).
**Project Type**: single repository; the change is confined to one Gradle subproject's test sources.
**Performance Goals**: no additional `Files.walk` of the real home (NFR-001); the control touches at
most three files it creates itself.
**Constraints**: strict-scope fingerprint string byte-identical to `main` (NFR-002); four scenarios run
in parallel (NFR-003); a failing control raises, never skips (NFR-004).
**Scale/Scope**: 1 new package-private class (~120 lines), 1 guard rewired in `ScenarioLifecycle`,
1 docs page paragraph, 1 changelog fragment. No CLI, no Python runtime, no feature-file change.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / one owner.** The excused-subtree list is declared once, in the new
  `RealHomeFingerprint` class, and the docs page cites it instead of restating the rule (C-003). The
  subtree names come from their production owners (`runtime/next/_tmp_namespace.py`'s
  `SPEC_KITTY_PROMPT_NAMESPACE`, the `gate-locks` directory of `review/pre_review_gate.py`); the
  harness cannot import Python, so it carries the two literals with a comment naming those owners.
- **Locality of change / smallest viable diff** (`DIRECTIVE_024`, `change-apply-smallest-viable-diff`).
  One class added, one call site changed, one message extended. No restructuring of `ScenarioWorld` or
  the step classes.
- **No weakening a gate** (charter Quality Gates; operating brief). Default stays strict; CI refuses
  the switch; the control proves the guard still reddens; nothing becomes `@wip`, skipped or `xfail`.
- **ATDD-first / red-first** (`DIRECTIVE_034`). The pre-existing entry point (the acceptance run)
  reproduced 13/14 red on this host before the change; the same run is green after it. The control is
  the same-fixture positive control the non-vacuity tactic asks for: one synthetic tree proves both
  the "skip" and the "still detects" halves.
- **NO_FULL_HEAVY_SUITES_IN_MISSION.** Only the affected feature set / ad-hoc selection is run locally;
  the full three-OS gating pass belongs to the nightly.

## Project Structure

### Documentation (this mission)

```
kitty-specs/acceptance-real-home-shared-host-01M6EJXK/
├── plan.md              # This file
├── research.md          # Phase 0 (discovery step authored it; planning extends it)
├── spec.md              # Requirements
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── tasks.md             # Phase 2 (/spec-kitty.tasks)
└── traces/              # Mission tracer files
```

No `data-model.md`, `contracts/` or `quickstart.md`: the change adds no entity, no external contract
and no new runbook — the run instructions already live on the docs page this plan updates.

### Source Code (repository root)

```
acceptance-jvm/src/test/java/kitty/acceptance/environment/
├── RealHomeFingerprint.java   # NEW: fingerprint + scope policy + runtime non-vacuity control
├── ScenarioLifecycle.java     # CHANGED: use the fingerprint, name the scope in the failure message
└── ScenarioWorld.java         # unchanged (delegates to ScenarioLifecycle)

docs/development/testing/acceptance-scenarios.md   # CHANGED: the switch, its CI refusal, the subtrees
docs/changelog/unreleased/<pr>.internal.md         # NEW: internal fragment
```

## Phase 0 — research (extended)

[research.md](research.md) already records the reproduction, the writer census, the six decisions and
the rejected alternatives. Nothing remains `[NEEDS CLARIFICATION]`: the two open questions in the spec
were settled by the reproduction (the racy surfaces are exactly the two named subtrees) and by the
brief's shared-machine table.

No dependency decision is made, so `supply_chain_security_check` and the adversarial-evidence pass have
nothing to adjudicate: the plan adds no dependency and reads no new external input. The grep for
`spec-kitty` state writers above is the evidence that the exclusion list is complete for the reported
failure mode.

## Phase 1 — design

### Design decisions (binding for tasks)

**D-1 — One owner for the policy.** `RealHomeFingerprint` owns: the scope resolution, the excused
subtree set, the fingerprint computation, and the non-vacuity control. `ScenarioLifecycle` keeps its
role (construct before the scenario, compare after) and holds one `RealHomeFingerprint`.

**D-2 — Scope resolution is a pure function of the environment map.**
`sharedHost(Map<String,String> env)` is truthy(`SPEC_KITTY_ACCEPTANCE_SHARED_HOST`) && !truthy(`GITHUB_ACTIONS`).
Truthy = `1`, `true`, `yes`, `on` (case-insensitive, trimmed). Passing the map in (rather than reading
`System.getenv()` inside) keeps the resolution readable and lets the control exercise both scopes
without mutating the process environment.

**D-3 — Excused paths are matched on the path *below the root*, not on a filename.**
`root.relativize(file).getName(0)` equals `spec-kitty-prompts` or `gate-locks`. This survives new
prompt filenames, new lock names, and nested directories; it cannot excuse a file at the root, nor a
sibling such as `credentials`. The `.lock` suffix exclusion stays, in every scope, unchanged.

**D-4 — The fingerprint stays a single walk and a single string.**
Same fields and order as `main` (`files=`, `newestMtime=`, `bytes=`, or `absent`), so NFR-002 holds and
the message keeps its shape. The scope is appended by the *caller's* message, not embedded in the
fingerprint (so a strict-mode fingerprint is byte-identical to `main`'s).

**D-5 — Non-vacuity control: a four-expectation self-check on a synthetic tree.**
For each scope (`strict`, `shared-host`) the control fingerprints a small tree it builds under the
scenario temp root, then:
1. plant `credentials` (a file at the root) → **both** scopes must see a change (genuine leak);
2. plant `spec-kitty-prompts/<hex>/prompt.md` → **strict** must see a change, **shared-host** must not
   (the exclusion is scoped, not global — in one assertion pair, so the halves cannot drift);
3. remove both, extend the already-excluded prompt file with one more byte → shared-host must still
   ignore it (an *edit*, not only a creation, is excused);
4. any expectation that fails raises `IllegalStateException` naming exactly which expectation broke
   (NFR-004).
The control runs once per scenario (in the `ScenarioLifecycle` constructor, before the "before"
fingerprint is taken) and cleans up its tree immediately, so it cannot be mistaken for scenario output
and cannot leak into the redirected-home positive control.

**D-6 — Failure message carries the scope.** `The scenario changed the real <root> (scope=<strict|shared-host>,
before: ..., after: ...)`. Strict output gains only the `scope=` token; nothing else changes.

### Implementation Concern Map

| IC | Concern | Owns |
|----|---------|------|
| IC-01 | Scope policy + excused subtrees + fingerprint | `RealHomeFingerprint` (D-2, D-3, D-4) |
| IC-02 | Wiring the guard and the message | `ScenarioLifecycle` (D-1, D-6) |
| IC-03 | Non-vacuity control | `RealHomeFingerprint` (D-5) |
| IC-04 | Operator-facing documentation | `docs/development/testing/acceptance-scenarios.md`, changelog fragment |

IC-01, IC-02 and IC-04 are separable; IC-03 depends on IC-01 (it calls the fingerprint).

### Required verification (per task)

| Check | Command | Expectation |
|-------|---------|-------------|
| Red, before the change | `gradle -p acceptance-jvm test --no-daemon` on a host with concurrent Missions | real-home failures (the issue's shape) |
| Green, after the change | the same run, with `SPEC_KITTY_ACCEPTANCE_SHARED_HOST=1` | zero "changed the real" failures |
| Control reddens on a leak | run the compiled `RealHomeFingerprint` over a synthetic tree (a `main`-style harness in `/tmp`, not committed) | root-level write changes the fingerprint in both scopes; prompt write changes it only in strict scope |
| Docs still fresh | `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` | errors=0 |
| Changelog style | `uv run --frozen python -m scripts.docs.check_changelog_style` | pass |
| Scenario contract untouched | `uv run --frozen pytest -q tests/architectural/test_scenario_contract.py` | pass |

## Risks

- **Risk:** a reviewer reads the switch as "the gate can be turned off". **Mitigation:** the switch
  cannot reach a CI runner (D-2), the default is strict, and the control proves the narrowed comparison
  still fails on a leak. The docs page states all three in one paragraph.
- **Risk:** the control itself is wrong and passes vacuously. **Mitigation:** expectation 1 is a genuine
  leak in both scopes; expectation 2 is an assertion *pair* on one fixture, so a control that always
  passes fails expectation 2's strict half and a control that always changes fails its shared half.
- **Risk:** Windows path separators in `relativize`. **Mitigation:** compare the `Path` component
  (`getName(0)`), never a joined string; `FileSnapshots` already normalises separators when it needs a
  string, and this policy needs none.
