# Acceptance Harness: the "real home stayed clean" guard on a shared host

**Mission**: `acceptance-real-home-shared-host-01M6EJXK`
**Type**: software-dev
**Target branch**: `main` (via `issue-7026-acceptance-real-home-shared-host`)
**Issue**: [#7026](https://github.com/spec-kitty/spec-kitty/issues/7026) — `acceptance-jvm: the "real home stayed clean" guard fails when several Missions run on one host`

---

## Purpose

Every CLI acceptance scenario runs the real `spec-kitty` CLI with `HOME` and `SPEC_KITTY_HOME`
redirected into a temp directory, and its After hook asserts that the process owner's **real**
`~/.spec-kitty` was not touched (`ScenarioLifecycle.assertObservedWriteInsideTempDir`, NFR-002's
positive control). That guard is right on a CI runner, where the harness is the only `spec-kitty`
writer. On a host that runs several Missions in parallel it also fires on **another Mission's**
legitimate writes and turns a green scenario red: the reported run had all 15 steps of three
scenarios pass and only the After hook fail, because one other agent's `spec-kitty next` wrote
`~/.spec-kitty/spec-kitty-prompts/<repo-hash>/spec-kitty-implement-<other-mission>-WP02.md` inside
the two-minute window.

The mission narrows the fingerprint so a concurrent Mission's writes to the per-mission,
content-addressed runtime-state subtrees no longer read as *this* scenario's pollution — and keeps
the guard from becoming vacuous by proving, at runtime in every scenario and on every nightly leg,
that a genuine leak outside those subtrees still reddens it.

### Reproduction on current `main` (grounding)

Reproduced on `main` at `9aed3a8012` on a host with concurrent Missions, with the pre-existing
entry point (`gradle -p acceptance-jvm test --no-daemon`, ad-hoc pass, 4 scenarios in parallel):
13 of the 14 executed scenarios failed, every failure `AssertionError at ScenarioLifecycle.java:62`,
for example

```
The scenario changed the real /home/<host>/.spec-kitty
(before: files=1332,newestMtime=1793638337018,bytes=59194202,
 after:  files=1333,newestMtime=1793638358346,bytes=59251247)
```

and the files that appeared in the window were all under
`~/.spec-kitty/spec-kitty-prompts/<16-hex-repo-identity>/`, never anywhere else. That is the same
shape the issue reports.

## Background — which surfaces a concurrent Mission writes

`~/.spec-kitty` (the *runtime state root*, `kernel.paths.get_runtime_state_root`; `SPEC_KITTY_HOME`
when set) is written by every `spec-kitty` process the user runs, whatever project it works on:

| Subtree | Written by | Per-mission? | Safe to race? |
|---|---|---|---|
| `spec-kitty-prompts/<repo-hash>/` | every `next` / `implement` / `review` prompt writer (`src/runtime/next/_tmp_namespace.py`) | yes — leaf name is the SHA-256 of the *other* repo's resolved path | yes — per-repo, content-addressed, swept per session |
| `gate-locks/` | the cross-process pre-review gate (`src/spec_cli/review/pre_review_gate.py`) | yes | yes — a cross-process lock's whole job is to be raced |
| `credentials` | tracker credential storage | per-user | **no** — holds secrets; a write there is a leak worth failing on |
| everything else (`activation*`, tool-surface ledger, cache/state entries) | the scenario's own CLI | — | not ours to excuse |

The two racy subtrees are exactly the ones the shared-machine table in the operating brief names as
safe to race; `credentials` deliberately stays inside the comparison.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Concurrent-mission writes are not pollution | As a maintainer running the acceptance suite beside other Missions, I want another Mission's prompt/gate-lock writes under `~/.spec-kitty` to stop failing my scenarios, so a green run reports green. | High | Open | [build] | no |
| FR-002 | Strict comparison is still the default | As a maintainer on a single-writer machine, I want the whole-tree comparison unchanged unless the shared-host switch is set, so I keep the strongest guard by default. | High | Open | [ratchet] | no |
| FR-003 | CI keeps its force | As a maintainer, I want the shared-host switch to be ignored on a GitHub Actions runner, so the flag cannot silently weaken the nightly gate. | High | Open | [build] | no |
| FR-004 | The narrowed guard proves itself non-vacuous | As a maintainer, I want the guard to prove on every scenario run that a genuine leak outside the racy subtrees still changes the fingerprint, so the narrowing cannot rot into a check that can never fail. | High | Open | [build] | no |
| FR-005 | A red names the comparison it ran | As a maintainer reading a failure, I want the failure message to state which scope (strict or shared-host) was compared, so I can tell a leak from a scope mistake. | Medium | Open | [build] | no |
| FR-006 | The switch is documented where the suite is documented | As a maintainer, I want the shared-host switch and its CI refusal documented next to the run instructions, so nobody has to read the Java to find it. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra tree walk | The guard keeps exactly one `Files.walk` of the real home per scenario; the non-vacuity control inspects at most 3 files in a synthetic tree it creates under the scenario's own temp root. | Performance | High | Open |
| NFR-002 | Byte-identical fingerprint when strict | With the switch unset, the fingerprint string of any given tree is byte-identical to `main`'s (same fields, same `*.lock` exclusion), so nothing else that reads the message changes. | Compatibility | High | Open |
| NFR-003 | Deterministic under Cucumber's 4-way parallelism | The control and the fingerprint share no mutable state across scenarios; each scenario's synthetic tree lives under its own temp root. | Reliability | High | Open |
| NFR-004 | Fail loud, never silent | A control that cannot prove non-vacuity raises an error naming the exact expectation that failed; it never degrades to a skip. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Harness-only blast radius | The change touches `acceptance-jvm/` test harness sources, one docs page and one changelog fragment. No CLI behaviour, no runtime-state layout, no `tests/scenarios` feature file changes. | Technical | High | Open |
| C-002 | Never weaken the gate silently | The narrowing must not be reachable on a CI runner, must not cover `credentials`, and must not turn any assertion into a skip or an `xfail`. | Regulatory | High | Open |
| C-003 | One owner for the exclusion list | The set of excused subtrees is declared once in the harness, next to the guard, and cited by the docs page; no second copy. | Technical | Medium | Open |

### Key Entities

- **Runtime state root**: `~/.spec-kitty` (or `SPEC_KITTY_HOME`), the per-user directory the guard fingerprints.
- **Real-home fingerprint**: the string `files=<n>,newestMtime=<ms>,bytes=<n>` (or `absent`) that stands in for the tree; the guard compares the before/after values.
- **Comparison scope**: `strict` (whole tree, the default) or `shared-host` (whole tree minus the two racy per-mission subtrees).
- **Non-vacuity control**: a synthetic tree under the scenario temp root on which both scopes are exercised against a planted leak and a planted concurrent-mission write.

## Success Criteria

- **SC-001**: On the shared host that reproduced the defect, the same ad-hoc acceptance run that was 13-of-14 red on `main` completes with zero "changed the real `~/.spec-kitty`" failures. — [build] · no-op passable: no
- **SC-002**: In `shared-host` scope a planted file at the root of the fingerprint tree, and a planted file under `credentials`, each change the fingerprint; only files under `spec-kitty-prompts/` and `gate-locks/` do not. — [ratchet] · no-op passable: no
- **SC-003**: With `GITHUB_ACTIONS` set, a planted write under `spec-kitty-prompts/` still changes the fingerprint, so a CI run cannot be relaxed by the switch. — [build] · no-op passable: no
- **SC-004**: With the switch unset, a planted write under `spec-kitty-prompts/` still changes the fingerprint (strict scope is unchanged from `main`). — [ratchet] · no-op passable: no
