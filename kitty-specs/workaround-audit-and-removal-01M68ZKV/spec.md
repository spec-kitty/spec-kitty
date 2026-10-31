# Mission Specification: Audit and remove special-case workarounds

**Mission Branch**: `issue-6745-workaround-audit-and-removal`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6745 — "Audit and remove special-case workarounds where a clean fix exists (just-make-it-work bias)" (P0, `tech-debt`).

## Purpose

The repository carries branches that tolerate a wrong input, a private seam or a test
double instead of fixing or refusing its cause. Each one adds a second authority: the
tolerated case behaves differently from the canonical path and the two drift. Issue #6745
asks for the audit method and a disposition per suspect, and the operator extended the
scope for this Mission: **remove a bounded, well-evidenced set in the same PR** rather
than filing a child issue for every one.

This Mission does not claim to complete the audit. 327 `except Exception  # noqa: BLE001`
sites in `src/` are sampled, not reviewed one by one. The PR body names every suspect it
audited and deliberately left, with the reason, and every confirmed workaround it did not
remove carries a child issue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer can run the audit and see a disposition per suspect (Priority: P1)

A maintainer picking up issue #6745 (or repeating it in six months) opens one page in the
developer docs that states the heuristics, the time-box, the four classifications, and a
table naming every suspect from the issue with its disposition and evidence. The page is
the durable output of the audit: it says which suspects are genuine constraints (and why),
which are confirmed workarounds (with the child issue that removes each one), and which
were fixed here.

**Why this priority**: without this, the audit leaves no trace and the next agent redoes it
from a keyword grep.

**Independent Test**: read the page; every suspect named in issue #6745 has a row with a
classification, a one-line evidence pointer (file:line or commit/issue) and either "removed
here" or a child issue number.

**Acceptance Scenarios**:

1. **Given** the merged mission, **When** a maintainer opens the audit page, **Then** it
   states the audit method (heuristics, time-box per subsystem, the four classifications)
   and classifies all six suspects from the issue plus the ones the audit added.
2. **Given** the page's "removed here" rows, **When** the maintainer greps for the named
   code, **Then** the workaround is gone and the canonical path is the only one left.

---

### User Story 2 - One seam builds the runtime `DiscoveryContext` (Priority: P1)

`spec-kitty next`, query mode and `mission run <key>` all resolve missions through a
`DiscoveryContext`. Today two byte-identical constructors exist because the runtime's
builder is module-private, and the comment at the copy says so: `mission run` does not
depend on a private surface, so it duplicates the construction. The org tier was then
wired into both copies by hand in the same mission — the drift the issue warns about was
already one edit away. After this story, one public builder is the only repo-rooted
constructor, and a patch on that seam is observed by both entry points.

**Why this priority**: it is the highest-evidence instance of "workaround for a missing
seam" in the issue's candidate list, and the fix is a seam, not a branch.

**Independent Test**: patch `runtime.next.runtime_bridge_io.build_discovery_context` and
run `run_custom_mission` — the patch is observed (proving `mission run` no longer builds its
own context); the two constructor call sites are one.

**Acceptance Scenarios**:

1. **Given** the module `specify_cli.mission_loader.command`, **When** it runs
   `run_custom_mission` without an injected context, **Then** it obtains the context from
   the one public builder in `runtime.next.runtime_bridge_io` and defines no constructor of
   its own.
2. **Given** the seam's owned-symbol list, **When** the non-vacuity test runs, **Then** it
   names the public builder (so the seam really defines it) and the deleted private copy is
   absent from both modules.

---

### User Story 3 - Production code stops being shaped by test doubles (Priority: P2)

`_compose_action` reads the executor's result through `getattr(result, "invocation_ids",
())`, a `try: len(...) except TypeError`, and `getattr(result, "steps", ())`, and the
comment says why: "so test mocks (MagicMock) and real instances both flow through
cleanly". `StepContractExecutionResult` always carries both attributes. The clean fix is to
read the contract; the test that exists only to pin the tolerance (it sets
`invocation_ids = object()`) is rewritten to assert the contract instead of the tolerance.

**Why this priority**: it is the smallest, most literal instance of the bias this issue
names — production bent to fit a double — and its evidence is the comment itself.

**Independent Test**: the composed action reads `result.invocation_ids` and `result.steps`
directly; no `getattr` default and no `except TypeError` remain on that path; the rewritten
test proves a result carrying real attributes logs its invocation ids.

**Acceptance Scenarios**:

1. **Given** a fake executor result carrying `invocation_ids=("inv-001", "inv-002")`,
   **When** the action composes, **Then** the bridge log reports 2 invocations.
2. **Given** the same module, **When** the source is scanned, **Then** no `getattr(result,
   ...)` default and no `except TypeError` remain around the result read.

### Edge Cases

- A caller injects its own `discovery_context=` into `run_custom_mission`: the injected
  context still wins; the seam is only the default (`or` short-circuit preserved).
- `build_discovery_context` propagates `OrgPackSubdirEscapeError` /
  `OrgPackEnvVarUnsetError` unchanged: the move must not add a `try/except` around
  `resolve_pack_chain` (DEC-005/NFR-001 of `up-org-template-fsm-01M06F9K`).
- A mission with no org packs configured: `org_roots` stays `[]` (NFR-005/SC-007 of that
  mission) — unchanged by the move.
- The two bare `DiscoveryContext()` drift-detection fallbacks (`engine.py`,
  `discovery.py:_build_tiers`) have no `repo_root` and stay out of scope (DEC-006).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Audit method is written down | As a maintainer, I want the heuristics, time-box and the four classifications on one docs page so the audit is repeatable. | High | Open | [build] | no — the page does not exist today |
| FR-002 | Every suspect carries a disposition | As a maintainer, I want a disposition row with evidence for every suspect in issue #6745 plus those the audit added, so nothing is silently dropped. | High | Open | [build] | no — six suspects currently have none |
| FR-003 | Confirmed-but-unremoved workarounds get a child issue | As a maintainer, I want a child issue naming the cause and the clean fix for each confirmed workaround not removed here, so the debt is owned. | High | Open | [build] | yes — paired with the page row that must cite a real issue number |
| FR-004 | One public `DiscoveryContext` builder | As an operator of `mission run <key>`, I want the same context construction as `spec-kitty next`, so the org tier cannot be wired in one copy and missed in the other. | High | Open | [build] | no — two constructors exist today |
| FR-005 | `mission_loader.command` defines no constructor | As an architecture reviewer, I want `specify_cli.mission_loader.command` to keep no `_build_discovery_context` of its own. | High | Open | [ratchet] | no — the copy exists today |
| FR-006 | Composition reads the executor contract directly | As an operator reading bridge logs, I want the invocation chain read from the real result type, so a renamed contract fails loudly instead of logging "0 invocation(s)". | Medium | Open | [build] | no — the `getattr` defaults mask it today |
| FR-007 | The tolerance-pinning test asserts the contract | As a reviewer, I want `test_dispatch_handles_non_sized_invocation_ids…` rewritten to assert the contract, so no test keeps the tolerance alive. | Medium | Open | [build] | no — the test pins `object()` today |
| FR-008 | Changelog entry | As a consumer, I want the `[Unreleased]` entry to say what changed for me. | Medium | Open | [build] | no — no entry exists today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new tolerance | The mission adds no `except Exception` and no `getattr(..., default)` fallback; the diff removes at least one of each kind it touches. | Maintainability | High | Open |
| NFR-002 | Behaviour preserved on the canonical path | `mission run <key>`, `spec-kitty next` and query-mode discovery keep today's byte-identical outputs for a repo with no org packs (existing tests stay green unchanged). | Reliability | High | Open |
| NFR-003 | Coverage on changed lines | Diff-cover on the changed lines stays at or above the CI threshold (90%); no test is deleted to reach it. | Quality | High | Open |
| NFR-004 | Bounded diff | Fewer than 200 changed lines outside `kitty-specs/` and docs, so the PR is reviewable in one pass. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | No behaviour change by refusal | This mission does not convert a logged tolerance into a refusal where the tolerant path is reachable from user pack content; those are child issues needing an operator decision. | Technical | High | Open |
| C-002 | One PR, honest scope | The PR states which suspects were audited and left, with reasons; it does not claim the audit complete. | Business | High | Open |
| C-003 | Never weaken a gate | No gate, test or allowlist is skipped, xfailed or relaxed to get green; a test whose premise is the removed workaround may be rewritten but not deleted without a replacement assertion. | Technical | High | Open |
| C-004 | Doctrine stays in its tier | The audit page is a developer doc; no doctrine artifact is added to `packs/built-in/` (it would ship to consumers). The proposed "workaround lens" is a tracker issue for the operator. | Technical | Medium | Open |

### Key Entities

- **Audit ledger**: the disposition table on the docs page — one row per suspect, with
  classification, evidence pointer and outcome.
- **`DiscoveryContext` builder**: the one public function in
  `runtime.next.runtime_bridge_io` that a repo-rooted discovery context is constructed by.
- **`StepContractExecutionResult`**: the dataclass whose `invocation_ids` and `steps` the
  composition reads directly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The audit page classifies all six suspects from issue #6745 and every suspect the audit added, each with a file:line or issue evidence pointer, and every "confirmed workaround" row that is not removed cites an open child issue number — [build] · no-op passable: no
- **SC-002**: A maintainer can point to exactly one construction of a repo-rooted discovery context: both entry points that resolve custom missions obtain the context from the same public seam, and a patch on that seam is observed by `mission run` — [ratchet] · no-op passable: no
- **SC-003**: For a composed action the bridge log reports the executor's real invocation count, and no defaulted attribute read or length tolerance remains on that path — [build] · no-op passable: no
- **SC-004**: The focused suites (`tests/runtime/test_bridge_io.py`, `tests/specify_cli/next/test_runtime_bridge_composition.py`, `tests/integration/test_mission_run_command.py`) pass, and no test is deleted — [ratchet] · no-op passable: no
