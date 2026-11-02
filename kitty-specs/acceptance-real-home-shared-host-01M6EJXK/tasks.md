# Tasks: Acceptance Harness — the "real home stayed clean" guard on a shared host

**Mission**: `acceptance-real-home-shared-host-01M6EJXK` · **Branch**: `issue-7026-acceptance-real-home-shared-host` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Scope resolution: `SPEC_KITTY_ACCEPTANCE_SHARED_HOST` truthy selects shared-host, `GITHUB_ACTIONS` truthy forces strict | WP01 | |
| T002 | Excused-surface predicate on the path component below the root (`spec-kitty-prompts`, `gate-locks`), scoped to shared-host only; `.lock` suffix exclusion unchanged in every scope | WP01 | [P] |
| T003 | Single-walk fingerprint string, byte-identical to `main` in strict scope | WP01 | [P] |
| T004 | Non-vacuity control: four expectations on one synthetic tree (root-level leak seen in both scopes; prompt write seen in strict, ignored in shared-host; an in-place edit stays ignored) | WP01 | |
| T005 | `ScenarioLifecycle` holds one fingerprint built from the process environment and uses it before/after | WP02 | |
| T006 | Failure message names the scope it compared (`scope=strict` / `scope=shared-host`) | WP02 | [P] |
| T007 | Run the control once per scenario from the constructor, under the scenario's own temp root, and clean it up | WP02 | |
| T008 | Docs: the shared-host switch, its CI refusal, the two excused subtrees and the runtime control on the acceptance how-to | WP03 | |
| T009 | Changelog fragment `docs/changelog/unreleased/<pr>.internal.md` | WP03 | [P] |

## Phase 1 — The narrowed fingerprint and its control

### WP01 — `RealHomeFingerprint`: scope policy, excused surfaces, non-vacuity control

**Goal**: one package-private class owns the comparison policy — which trees the fingerprint covers, how the scope is resolved, and the runtime control that proves the narrowed comparison still detects a leak. **Priority**: P1. **Prompt**: [tasks/WP01-real-home-fingerprint.md](tasks/WP01-real-home-fingerprint.md)
**Independent test**: compile the class on its own (`javac` from the JDK 25 toolchain) and run it over a synthetic tree — a root-level file changes the fingerprint in both scopes, a `spec-kitty-prompts/<hex>/x.md` write changes it only in strict scope.

T001 Scope resolution (WP01)
T002 Excused-surface predicate (WP01)
T003 Single-walk fingerprint (WP01)
T004 Non-vacuity control (WP01)

Dependencies: none. Risk: the control must not become an "always passes" stub — T004's expectation 2 is an assertion *pair* on one fixture, so a control that always ignores fails the strict half and one that always notices fails the shared-host half.

## Phase 2 — Wire the guard

### WP02 — `ScenarioLifecycle` compares with the narrowed fingerprint and reports the scope

**Goal**: the After hook uses the new class, states which comparison ran, and runs the control exactly once per scenario. **Priority**: P1. **Prompt**: [tasks/WP02-wire-the-guard.md](tasks/WP02-wire-the-guard.md)
**Independent test**: the ad-hoc acceptance run that was 13-of-14 red on `main` completes with zero "changed the real" failures when `SPEC_KITTY_ACCEPTANCE_SHARED_HOST=1`, and still reddens on a planted file at the root of the real runtime root.

T005 Fingerprint wiring (WP02)
T006 Scope in the failure message (WP02)
T007 Control invocation and teardown (WP02)

Dependencies: WP01 (the class it consumes). Risk: the control's synthetic tree must live under the scenario temp root, never under the redirected home (it would otherwise satisfy the "redirection took effect" positive control by itself) and never under the real home.

## Phase 3 — Documentation and changelog

### WP03 — Document the switch and record the change

**Goal**: the how-to page that already explains the isolation guard gains the switch, its CI refusal and the two excused subtrees; the changelog fragment lands. **Priority**: P2. **Prompt**: [tasks/WP03-docs-and-changelog.md](tasks/WP03-docs-and-changelog.md)
**Independent test**: `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and `uv run --frozen python -m scripts.docs.check_changelog_style` accepts the fragment.

T008 Docs page (WP03)
T009 Changelog fragment (WP03)

Dependencies: WP02 (the wording must match the shipped behaviour). Risk: the docs page carries an `updated:` frontmatter date — refresh it, or the freshness check flags a stale page.
