---
title: Vertical-Slice Test Organisation
description: Reorganises the suite by system capability instead of by unit-versus-integration, demoting test type to pytest markers and filename suffixes where it belongs.
status: Accepted
date: '2026-03-15'
doc_status: active
kind: ADR
updated: '2026-03-15T00:00:00Z'
---

## Context and Problem Statement

The test suite grew organically alongside the codebase and ended up with two competing
top-level organising axes that are never reconciled:

- `unit/` and `integration/` are organised by **test type** — but their internals are a
  large flat bag of files with no relation to what the system actually does. A reader
  cannot look at either directory and understand system capabilities.
- `specify_cli/` mirrors the **source package tree** — but mixes unit and integration
  tests indiscriminately inside each module folder, so the type axis is invisible.

Neither axis is consistently applied. The result is that navigating tests to understand
system behaviour requires reading filenames and imports rather than following directory
structure. It also makes it hard to answer "what tests cover the merge workflow?" or
"where do I add a test for a new mission capability?" without a mental map built from
experience.

A secondary issue: several test-type directories (`unit/`, `integration/`) have
accumulated flat test files at their root that cover unrelated concerns, functioning as
catch-all dumping grounds. This compounds over time.

## Decision Drivers

- **Readability**: the test tree should be a readable description of system capabilities,
  not a reflection of internal module boundaries or test-runner mechanics.
- **Navigability**: a new contributor should be able to locate tests for a feature by
  finding the feature's slice directory, without knowing the source package layout.
- **Clear placement**: when adding a test, there should be one obvious place for it.
- **Testing pyramid**: the pyramid (many unit, fewer integration, few e2e) should be
  visible from markers and filename conventions, not directory depth.
- **Consistency**: the organising principle must be applied uniformly — no directories
  that mix axes.

## Considered Options

- **Option A — Vertical slices as top level, test type via markers + filename suffix**
- **Option B — Source package mirror as top level, each module gets `unit/` + `integration/` subdirs**
- **Option C — Keep `unit/` and `integration/` top level, reorganise their internals to mirror the source package tree**

## Decision Outcome

**Chosen option: Option A**, because it expresses the system as a set of capabilities
rather than implementation artefacts. Test type (unit vs integration) is a
runner-mechanics concern that is better expressed through pytest markers and filename
suffixes than through directory structure. Option B optimises for source code proximity
at the cost of capability visibility. Option C only partially fixes the problem — the
type/slice inversion remains at the top level.

### Consequences

#### Positive

- The test tree reads as a capability map of the system.
- `pytest tests/<slice>/` runs all tests for one vertical of the product.
- `pytest -m fast` or `pytest -m git_repo` give fast-feedback and mid-tier runs
  orthogonally — test-type selection is via markers, not path.
- New tests have one unambiguous home.
- The migration is incremental: each slice can be reorganised independently without
  breaking others.

#### Negative

- A one-time migration effort is required to move files from the current layout.
- Some tests genuinely span multiple slices (e.g. a migration that touches both
  `upgrade` and `missions`); these go into the most responsible slice with a comment
  noting the cross-cutting concern.

#### Neutral

- `legacy/` is unchanged for now; it will be addressed as a follow-up (audit valuable
  knowledge, extract 2.x-relevant tests, then delete).
- Cross-cutting concerns without a natural slice home (encoding validation, packaging,
  doctrine schema compliance) keep their existing `cross_cutting/` and `doctrine/`
  directories — those are already organised by concern, not by test type.

### Confirmation

The restructure is complete when:
1. `unit/` and `integration/` directories no longer exist (or are empty stubs awaiting
   migration).
2. Every slice directory contains both `*_unit.py` and `*_integration.py` files (or
   `*_unit.py` only, for slices with no integration surface).
3. `pytest tests/<slice>/` produces a meaningful subset of the suite for each slice.
4. The full suite still passes with no regressions.

## Pros and Cons of the Options

### Option A — Vertical slices as top level

Top-level directories map to system capabilities:
`missions/`, `merge/`, `agent/`, `tasks/`, `git_ops/`, `status/`, `upgrade/`,
`init/`, `sync/`, `runtime/`, `research/`, `next/`.

Test type is expressed by:
- pytest marker: `fast` (unit/mock-boundary) or `git_repo`/`slow` (integration)
- filename suffix: `*_unit.py` vs `*_integration.py` (or plain `test_*.py` where the
  distinction is not meaningful)

**Pros:**
- Capability-first — matches how developers and product owners think about the system.
- Markers + suffixes give orthogonal test-type filtering without directory nesting.
- Scales well: adding a new capability means adding a new slice, not editing a shared bucket.

**Cons:**
- Requires migrating existing `unit/` and `integration/` directories.
- Some tests are harder to classify (cross-cutting or multi-concern).

### Option B — Source package mirror

Top-level directories mirror `src/specify_cli/`: `charter/`, `glossary/`,
`status/`, `sync/`, etc. Each module directory gets `unit/` and `integration/`
subdirs.

**Pros:**
- Strong coupling between source module and its tests — easy to find tests for a
  given module.
- `specify_cli/` already partially follows this pattern.

**Cons:**
- Internal module boundaries leak into the test tree. Refactoring the source
  package (e.g. splitting or merging modules) forces test directory renames.
- Module boundaries do not align with user-facing capabilities — `glossary/` and
  `charter/` are implementation details, not product features.
- The `unit/` + `integration/` nesting restores the type-first problem one level deeper.

### Option C — Type-first top level, internals mirror source

Keep `unit/` and `integration/` as top-level directories but organise their
internals to mirror the source package tree (e.g. `unit/agent/`, `unit/merge/`,
`integration/merge/`).

**Pros:**
- No change to the top-level shape that CI scripts and contributor docs reference.
- Internal structure becomes navigable.

**Cons:**
- The fundamental inversion remains: test type is the primary axis, capability is
  secondary. This is the opposite of what communicates system behaviour.
- Related tests for one feature are split across two top-level directories, requiring
  navigation between them.

## More Information

- Initiative tracker: `architecture/2.x/initiatives/test_improvement/README.md`
- Current test suite profile: section 2 of the initiative README
- Filename convention: `*_unit.py` files carry `pytestmark = pytest.mark.fast`;
  integration tests carry `pytestmark = pytest.mark.git_repo` (or `slow`).
- Marker registry: `pytest.ini`
